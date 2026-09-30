"""The ONLY module that talks to OpenRouteService (docs/ARCHITECTURE.md sections 4, 6, 7, 11).

Rules enforced here, in one place:
- one module-level, thread-safe `httpx.Client`; the key travels in the Authorization header only
  and user text reaches ORS only as a `params=` value against the constant base URL;
- every call checks the deadline, spends the global budget, and gets a `min(cap, remaining)` timeout;
- retries (tenacity) never outlast the deadline; errors are never cached;
- nothing sensitive is logged: never the key, a URL with query, location text, coordinates, a body,
  or `str(exc)` of an httpx error (its message can embed the full URL). Only class + status + kind.
"""

from __future__ import annotations

import functools
import json
import logging
import math
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import polyline
from django.conf import settings
from django.core.cache import caches
from tenacity import Retrying, retry_if_exception, stop_after_attempt, stop_any, wait_random

from routing import budgets, stats
from routing.cache_keys import (
    AUTOCOMPLETE_TTL,
    DIRECTIONS_TTL,
    GEOCODE_TTL,
    REVERSE_TTL,
    InvalidTextError,
    autocomplete_key,
    clean_text,
    directions_key,
    geocode_key,
    reverse_key,
)
from routing.deadline import Deadline
from routing.errors import (
    DeadlineExceeded,
    LocationNotFound,
    RouteNotFound,
    TripTooLong,
    UnsupportedLocation,
    UpstreamAuthError,
    UpstreamBadRequest,
    UpstreamBadResponse,
    UpstreamQuotaExhausted,
    UpstreamRateLimited,
    UpstreamUnavailable,
)
from routing.labels import street_label_from_properties
from routing.models import MAX_TRIP_M, LegRoute, Place, Profile

logger = logging.getLogger("eld.routing")

HGV: Profile = "driving-hgv"
CAR: Profile = "driving-car"

AUTOCOMPLETE_DEADLINE_S = 5.0
MAX_ATTEMPTS = 2
DEFAULT_RATE_LIMIT_WAIT_S = 2.0
DEFAULT_RATE_LIMIT_RETRY_AFTER_S = 60.0
MAX_BODY_BYTES = 10_000_000
MAX_ERROR_BODY_BYTES = 64 * 1024
MAX_POLYLINE_CHARS = 2_000_000
LOW_QUOTA_FRACTION = 0.10

_UNROUTABLE_CODES = frozenset({2009, 2010})
_TOO_LONG_CODE = 2004
_TRANSIENT_CODE = 2099

_client = httpx.Client(
    base_url=settings.ORS_BASE_URL,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    follow_redirects=False,
    trust_env=False,
)
_sleep = time.sleep  # indirection so tests do not really wait
_MISS = object()


class _Unroutable(Exception):  # noqa: N818 - internal control flow for the driving-car fallback
    """ORS 2009/2010 on this profile. Never leaves this module."""


# ---------------------------------------------------------------------------------------------
# Transport: one request, classified into typed errors
# ---------------------------------------------------------------------------------------------


def _log_failure(kind: str, error_class: str, status: int | None) -> None:
    logger.warning(
        "ors_call_failed",
        extra={"endpoint_kind": kind, "error_class": error_class, "upstream_status": status},
    )


def _logs_bad_response[**P, R](kind: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log a malformed ORS body at ERROR once, where the endpoint kind is known.

    Class, kind and status only: never the body, the URL or any user text. A 200 that fails to parse
    is the only way to get here without a status already set.
    """

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except UpstreamBadResponse as exc:
                if exc.upstream_status is None:
                    exc.upstream_status = 200
                logger.error(
                    "ors_bad_response",
                    extra={
                        "endpoint_kind": kind,
                        "error_class": type(exc).__name__,
                        "upstream_status": exc.upstream_status,
                    },
                )
                raise

        return wrapper

    return decorate


def _header_seconds(headers: httpx.Headers, *names: str) -> float | None:
    for name in names:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        if value > 1e9:  # an epoch timestamp rather than a number of seconds
            value -= time.time()
        return max(0.0, value)
    return None


def _note_quota(kind: str, response: httpx.Response) -> None:
    try:
        remaining = float(response.headers["x-ratelimit-remaining"])
        limit = float(response.headers["x-ratelimit-limit"])
    except (KeyError, ValueError):
        return
    if limit > 0 and remaining / limit < LOW_QUOTA_FRACTION:
        logger.warning("ors_quota_low", extra={"endpoint_kind": kind, "ratelimit_remaining": remaining})


def _read_body(response: httpx.Response, deadline: Deadline, cap: int) -> bytes:
    """Stream the body, enforcing the byte cap and the request deadline on every chunk.

    httpx timeouts are per chunk, so a slow trickle would otherwise outlive the deadline.
    """
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > cap:
            raise UpstreamBadResponse
        deadline.ensure_time_left()
        chunks.append(chunk)
    return b"".join(chunks)


def _error_code(response: httpx.Response, deadline: Deadline) -> int | None:
    try:
        error = json.loads(_read_body(response, deadline, MAX_ERROR_BODY_BYTES)).get("error")
    except (ValueError, RecursionError, AttributeError, UpstreamBadResponse):
        return None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, int) and not isinstance(code, bool) else None


def _reject_constant(name: str) -> Any:
    raise ValueError(name)


def _json_body(response: httpx.Response, deadline: Deadline) -> dict[str, Any]:
    raw = _read_body(response, deadline, MAX_BODY_BYTES)
    try:
        body = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise UpstreamBadResponse from None
    if not isinstance(body, dict):
        raise UpstreamBadResponse
    return body


def _classify(kind: str, response: httpx.Response, deadline: Deadline) -> dict[str, Any]:
    """Return the parsed body for a 200, else raise the typed error from the taxonomy table."""
    status = response.status_code
    if status == 401:
        logger.critical("ors_auth_failed", extra={"endpoint_kind": kind, "upstream_status": 401})
        raise UpstreamAuthError
    if status == 403:
        _log_failure(kind, "HTTPStatus", status)
        raise UpstreamQuotaExhausted(kind, scope="day")
    if status == 429:
        # retry_after_s stays raw; the API mapper clamps to 1..300 (API_CONTRACT section 6).
        # TEST_PLAN O-07's 1..3600 is superseded by that contract.
        _log_failure(kind, "HTTPStatus", status)
        reset = _header_seconds(response.headers, "x-ratelimit-reset", "retry-after")
        if reset is None:
            raise UpstreamRateLimited(DEFAULT_RATE_LIMIT_RETRY_AFTER_S, DEFAULT_RATE_LIMIT_WAIT_S)
        raise UpstreamRateLimited(reset, reset)
    if status >= 500:
        _log_failure(kind, "HTTPStatus", status)
        raise UpstreamUnavailable(_header_seconds(response.headers, "retry-after"))
    if 400 <= status < 500:
        _log_failure(kind, "HTTPStatus", status)
        code = _error_code(response, deadline)
        if kind == "directions" and code in _UNROUTABLE_CODES:
            raise _Unroutable
        if code == _TOO_LONG_CODE:
            raise TripTooLong
        if code == _TRANSIENT_CODE:
            raise UpstreamUnavailable
        logger.error("ors_bad_request", extra={"endpoint_kind": kind, "upstream_status": status})
        raise UpstreamBadRequest
    if status != 200:
        raise UpstreamBadResponse
    return _json_body(response, deadline)


def _attempt(
    kind: str,
    deadline: Deadline,
    method: str,
    path: str,
    params: dict[str, Any] | None,
    body: dict[str, Any] | None,
    read_cap_s: float,
) -> dict[str, Any]:
    deadline.ensure_time_left()
    budgets.spend(kind)
    stats.record_call(kind)
    key = settings.ORS_API_KEY
    if not key:
        logger.critical("ors_key_missing", extra={"endpoint_kind": kind})
        raise UpstreamAuthError
    try:
        with _client.stream(
            method,
            path,
            params=params,
            json=body,
            headers={"Authorization": key},
            timeout=deadline.http_timeout(read_cap_s),
        ) as response:
            _note_quota(kind, response)
            try:
                return _classify(kind, response, deadline)
            except UpstreamBadResponse as exc:
                exc.upstream_status = response.status_code
                raise
    except httpx.HTTPError as exc:
        _log_failure(kind, type(exc).__name__, None)
        raise UpstreamUnavailable from None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, DeadlineExceeded):
        return False
    return isinstance(exc, UpstreamUnavailable | UpstreamRateLimited)


def _retry_wait(retry_state: Any) -> float:
    exc = retry_state.outcome.exception()
    hinted = getattr(exc, "retry_delay_s", None)
    if hinted is not None:
        return float(hinted)
    return wait_random(0.2, 0.8)(retry_state)


def _call(
    kind: str,
    deadline: Deadline,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    attempts: int = MAX_ATTEMPTS,
    read_cap_s: float = 10.0,
) -> dict[str, Any]:
    """One logical ORS call: up to `attempts` tries, never sleeping past the deadline."""

    def out_of_time(retry_state: Any) -> bool:
        return retry_state.upcoming_sleep >= deadline.remaining()

    retrying = Retrying(
        stop=stop_any(stop_after_attempt(attempts), out_of_time),
        wait=_retry_wait,
        retry=retry_if_exception(_is_retryable),
        sleep=lambda seconds: _sleep(seconds),
        reraise=True,
    )
    return retrying(_attempt, kind, deadline, method, path, params, body, read_cap_s)


# ---------------------------------------------------------------------------------------------
# Parsing helpers (upstream output is untrusted input)
# ---------------------------------------------------------------------------------------------


def _finite_coord(value: Any, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) and low <= number <= high else None


def _is_us(props: dict[str, Any]) -> bool:
    """False only when Pelias names a different country (absent fields do not reject)."""
    country_a, code = props.get("country_a"), props.get("country_code")
    if country_a is not None and country_a != "USA":
        return False
    return code is None or code == "US"


def _place_from_feature(feature: Any) -> Place | None:
    if not isinstance(feature, dict):
        return None
    coords = (feature.get("geometry") or {}).get("coordinates")
    props = feature.get("properties")
    if not isinstance(coords, list) or len(coords) < 2 or not isinstance(props, dict):
        return None
    lng = _finite_coord(coords[0], -180, 180)  # ORS order is [lng, lat]
    lat = _finite_coord(coords[1], -90, 90)
    label = street_label_from_properties(props)
    if lat is None or lng is None or label is None:
        return None
    return Place(label=label, lat=lat, lng=lng, us=_is_us(props))


def _features(body: dict[str, Any]) -> list[Any]:
    features = body.get("features")
    if not isinstance(features, list):
        raise UpstreamBadResponse
    return features


def _measure(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UpstreamBadResponse
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise UpstreamBadResponse
    return number


def _validate_geometry(encoded: str) -> None:
    """Decode before caching: a bad polyline must be a 503, never an IndexError later."""
    try:
        points = polyline.decode(encoded, 5)
    except Exception:  # noqa: BLE001 - the decoder raises assorted errors on garbage
        raise UpstreamBadResponse from None
    if not points or not all(
        math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180
        for lat, lng in points
    ):
        raise UpstreamBadResponse


def _parse_leg(body: dict[str, Any], profile: Profile) -> LegRoute:
    try:
        route = body["routes"][0]
        summary = route["summary"]
        geometry = route["geometry"]
        segments = route.get("segments")
        if not isinstance(geometry, str) or not geometry or len(geometry) > MAX_POLYLINE_CHARS:
            raise UpstreamBadResponse
        _validate_geometry(geometry)
        if segments is not None and (not isinstance(segments, list) or len(segments) != 1):
            raise UpstreamBadResponse
        return LegRoute(
            polyline=geometry,
            distance_m=_measure(summary["distance"]),
            duration_s=_measure(summary["duration"]),
            profile=profile,
        )
    except (KeyError, IndexError, TypeError):
        raise UpstreamBadResponse from None


# ---------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------


@_logs_bad_response("geocode")
def geocode_search(text: str, field: str, deadline: Deadline) -> Place:
    """Resolve free text to one lower-48 place. Raises LocationNotFound / UnsupportedLocation."""
    try:
        text = clean_text(text)  # ORS receives exactly the text the cache key was built from
        key = geocode_key(text)
    except InvalidTextError:
        raise LocationNotFound(field) from None
    cache = caches["geo"]
    place = cache.get(key, _MISS)
    if place is not _MISS:
        stats.record_cache_hit("geocode")
    else:
        body = _call(
            "geocode",
            deadline,
            "GET",
            "/geocode/search",
            params={"text": text, "boundary.country": "US", "size": 1},
        )
        features = _features(body)
        if not features:
            cache.set(key, None, GEOCODE_TTL.not_found_s)
            raise LocationNotFound(field)
        place = _place_from_feature(features[0])
        if place is None:
            raise UpstreamBadResponse
        cache.set(key, place, GEOCODE_TTL.hit_s)
    if place is None:
        raise LocationNotFound(field)
    if not place.plannable:
        raise UnsupportedLocation(field, place.label)
    return place


@_logs_bad_response("autocomplete")
def autocomplete(text: str) -> tuple[Place, ...]:
    """Up to 5 lower-48 suggestions. One attempt, 5 s deadline: the next keystroke is the retry."""
    try:
        text = clean_text(text)
        key = autocomplete_key(text)
    except InvalidTextError:
        return ()
    cache = caches["geo"]
    cached = cache.get(key, _MISS)
    if cached is not _MISS:
        stats.record_cache_hit("autocomplete")
        return cached
    body = _call(
        "autocomplete",
        Deadline(AUTOCOMPLETE_DEADLINE_S),
        "GET",
        "/geocode/autocomplete",
        params={
            "text": text,
            "boundary.country": "US",
            "size": 5,
            "layers": "locality,address,venue,postalcode",
        },
        attempts=1,
        read_cap_s=AUTOCOMPLETE_DEADLINE_S,
    )
    places = tuple(p for p in (_place_from_feature(f) for f in _features(body)) if p and p.plannable)[:5]
    cache.set(key, places, AUTOCOMPLETE_TTL.hit_s if places else AUTOCOMPLETE_TTL.not_found_s)
    return places


@_logs_bad_response("reverse")
def _reverse_lookup(lat: float, lng: float, deadline: Deadline) -> str | None:
    key = reverse_key(lat, lng)
    cache = caches["geo"]
    cached = cache.get(key, _MISS)
    if cached is not _MISS:
        stats.record_cache_hit("reverse")
        return cached
    body = _call(
        "reverse",
        deadline,
        "GET",
        "/geocode/reverse",
        params={
            "point.lat": round(lat, 2),
            "point.lon": round(lng, 2),
            "boundary.country": "US",
            "layers": "locality,localadmin,county",
            "size": 1,
        },
    )
    place = next((p for p in (_place_from_feature(f) for f in _features(body)) if p and p.us), None)
    label = place.label if place else None
    cache.set(key, label, REVERSE_TTL.hit_s if label else REVERSE_TTL.not_found_s)
    return label


def reverse_label(lat: float, lng: float, deadline: Deadline) -> str | None:
    """'City, ST' for a point, or None. Never raises: a failed label is a fallback, not an error."""
    try:
        return _reverse_lookup(lat, lng, deadline)
    except Exception as exc:  # noqa: BLE001 - reverse geocoding must never fail a plan
        logger.info("reverse_label_skipped", extra={"error_class": type(exc).__name__})
        return None


def _rounded_point(place: Place) -> tuple[float, float]:
    return (round(place.lat, 5) + 0.0, round(place.lng, 5) + 0.0)


def _directions_call(profile: Profile, start: Place, end: Place, deadline: Deadline) -> LegRoute:
    body: dict[str, Any] = {
        "coordinates": [[start.lng, start.lat], [end.lng, end.lat]],
        "units": "m",
        "instructions": False,
        "radiuses": [-1, -1],
    }
    if profile == HGV:
        body["options"] = {"vehicle_type": "hgv"}
    response = _call("directions", deadline, "POST", f"/v2/directions/{profile}/json", body=body)
    return _parse_leg(response, profile)


@_logs_bad_response("directions")
def directions_leg(start: Place, end: Place, deadline: Deadline) -> LegRoute:
    """One leg, HGV first. On ORS 2009/2010 only, one driving-car retry (profile says which won)."""
    start_pt, end_pt = _rounded_point(start), _rounded_point(end)
    if start_pt == end_pt:
        return LegRoute(polyline.encode([start_pt, end_pt]), 0.0, 0.0, HGV)
    key = directions_key(HGV, start_pt, end_pt)
    cache = caches["routes"]
    cached = cache.get(key, _MISS)
    if cached is not _MISS:
        stats.record_cache_hit("directions")
    if cached is None:
        raise RouteNotFound(start.label, end.label)
    if cached is not _MISS:
        return cached
    try:
        leg = _directions_call(HGV, start, end, deadline)
    except _Unroutable:
        try:
            leg = _directions_call(CAR, start, end, deadline)
        except _Unroutable:
            cache.set(key, None, DIRECTIONS_TTL.not_found_s)
            raise RouteNotFound(start.label, end.label) from None
    cache.set(key, leg, DIRECTIONS_TTL.hit_s)
    return leg


def ensure_total_within_limit(legs: Sequence[LegRoute]) -> None:
    """Total route over 6,000 mi is TripTooLong (each leg alone can pass ORS's 6,000 km limit)."""
    if sum(leg.distance_m for leg in legs) > MAX_TRIP_M:
        raise TripTooLong
