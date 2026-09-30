"""Maps adapter and engine exceptions to ApiError (docs/ARCHITECTURE.md section 6, API_CONTRACT 6).

Messages are written here from validated input only, never from an exception or an upstream body.
"""

import logging
from typing import Any

from hos import HosEngineError, HosInputError
from routing.errors import (
    LocationNotFound,
    RouteNotFound,
    RoutingError,
    TripTooLong,
    UnsupportedLocation,
    UpstreamAuthError,
    UpstreamBadResponse,
    UpstreamQuotaExhausted,
    UpstreamRateLimited,
    UpstreamUnavailable,
)
from trips.errors import ApiError, ErrorCode, clamp_retry_after, internal_error

logger = logging.getLogger("eld.errors")

SERVICE_ERRORS = (RoutingError, HosInputError, HosEngineError)
_UNAVAILABLE = "The routing service is not responding. Try again in a minute."
_GEOCODE_DAILY = (
    "Place lookup has reached its daily limit. Pick each place from the suggestions list, or try again later."
)
_DAILY = "The routing service has reached its daily limit. Try again later."


def _label_of(validated: dict[str, Any], field: str) -> str:
    value = validated.get(field, "")
    return value["label"] if isinstance(value, dict) else str(value)


def _per_minute(retry_after_s: float | None) -> ApiError:
    wait = clamp_retry_after(retry_after_s)
    return ApiError(
        ErrorCode.UPSTREAM_QUOTA_EXCEEDED,
        f"The routing service is at its per-minute limit. Wait {wait} seconds, then try again.",
        retry_after_s=wait,
    )


def map_service_error(exc: Exception, validated: dict[str, Any] | None = None) -> ApiError:
    """Translate one service exception. `validated` supplies the user's own (normalized) place text."""
    validated = validated or {}
    if isinstance(exc, LocationNotFound):
        text = _label_of(validated, exc.field)
        return ApiError(
            ErrorCode.LOCATION_NOT_FOUND,
            f'We couldn\'t find "{text}". Check the spelling or pick a suggestion from the list.',
            field=exc.field,
        )
    if isinstance(exc, UnsupportedLocation):
        return ApiError(
            ErrorCode.UNSUPPORTED_LOCATION,
            "Trips must start, pick up and drop off in the lower 48 states. "
            f'"{exc.label}" is outside that area.',
            field=exc.field,
        )
    if isinstance(exc, RouteNotFound):
        return ApiError(
            ErrorCode.ROUTE_NOT_FOUND,
            "We couldn't find a drivable route between these places. Try a nearby city or a street address.",
        )
    if isinstance(exc, TripTooLong):
        return ApiError(
            ErrorCode.TRIP_TOO_LONG, "This trip is too long to plan (over 6,000 miles). Try a shorter route."
        )
    if isinstance(exc, UpstreamRateLimited):
        return _per_minute(exc.retry_after_s)
    if isinstance(exc, UpstreamQuotaExhausted):
        if exc.scope == "minute":
            return _per_minute(exc.retry_after_s)
        message = _GEOCODE_DAILY if exc.kind == "geocode" else _DAILY
        return ApiError(ErrorCode.UPSTREAM_QUOTA_EXCEEDED, message)
    if isinstance(exc, UpstreamUnavailable | UpstreamAuthError | UpstreamBadResponse):
        # DeadlineExceeded is an UpstreamUnavailable. The adapter already logged auth/malformed causes.
        return ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, _UNAVAILABLE)
    # UpstreamBadRequest, other RoutingError, HosInputError (our bug or bad ORS data), HosEngineError.
    logger.error("service_error", exc_info=(type(exc), exc, exc.__traceback__))
    return internal_error()
