"""plan_trip: geocode, route two legs, run the HOS engine, label remark places, build the DTO.

Flow and budgets: docs/ARCHITECTURE.md section 4. Response shape: docs/API_CONTRACT.md 5.2.
All I/O goes through `routing.ors_client`; all HOS logic is `hos.plan`; the DTO is built by the pure
`trips.services.response`. Routing exceptions propagate unchanged (the API layer maps them); the only
errors raised here are `ApiError` for user-caused input problems and `INTERNAL` for engine failures.
"""

from __future__ import annotations

import contextvars
import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any

import hos
from hos.models import HosEngineError, HosInputError
from routing import ors_client
from routing.geometry import LegGeometry, build_leg_geometry, build_leg_geometry_from_points, interpolate
from routing.labels import KnownLabel, coordinate_label, fallback_label, reuse_known_label, round_point
from routing.models import LegRoute, Place
from routing.timezone import FrozenTimezone, home_terminal_timezone, quantize_time
from trips.errors import ApiError, ErrorCode, internal_error
from trips.services.deadline import Deadline
from trips.services.response import (
    LABEL_COORDINATES,
    LABEL_GEOCODED,
    LABEL_INPUT,
    LABEL_NEARBY,
    Bounds,
    Dto,
    LegView,
    PlaceView,
    PointInfo,
    ResponseBuildError,
    ResponseInput,
    Timing,
    build_plan_response,
    required_point_keys,
)
from trips.types import LocationInput, PlanRequest

logger = logging.getLogger("eld.trips")

FIELDS = ("current_location", "pickup_location", "dropoff_location")
GEOCODE_WORKERS = 3
REVERSE_WORKERS = 5
MAX_REVERSE_CALLS = 25
REVERSE_BUDGET_S = 6.0
REVERSE_RESERVE_S = 1.0
SAME_PLACE_DP = 5
SAME_PLACE_MESSAGE = "Pickup and dropoff are the same place. Choose a different dropoff."


def _parallel[T](tasks: Sequence[Callable[[], T]], workers: int) -> list[T]:
    """Run `tasks` in a small pool (each with a copy of the request context), results in task order.

    Every task finishes before anything is raised; the first failure in task order is re-raised so the
    error a client sees does not depend on thread timing.
    """
    if len(tasks) == 1:
        return [tasks[0]()]
    with ThreadPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
        futures = [pool.submit(contextvars.copy_context().run, task) for task in tasks]
    return [future.result() for future in futures]


def _resolve_places(request: PlanRequest, deadline: Deadline) -> tuple[list[Place], list[str]]:
    """Step 2: PlaceInputs are used as-is, free text is geocoded in parallel."""
    values: list[LocationInput] = [request[field] for field in FIELDS]  # type: ignore[literal-required]
    places: list[Place | None] = [None] * 3
    sources = [LABEL_INPUT] * 3
    todo: list[int] = []
    for index, value in enumerate(values):
        if isinstance(value, str):
            todo.append(index)
            sources[index] = LABEL_GEOCODED
        else:
            places[index] = Place(value["label"], float(value["lat"]), float(value["lng"]))
    found = (
        _parallel(
            [lambda i=i: ors_client.geocode_search(values[i], FIELDS[i], deadline) for i in todo],  # type: ignore[arg-type]
            GEOCODE_WORKERS,
        )
        if todo
        else []
    )
    for index, place in zip(todo, found, strict=True):
        places[index] = place
    return [p for p in places if p is not None], sources


def _same_point(a: Place, b: Place) -> bool:
    return (round(a.lat, SAME_PLACE_DP), round(a.lng, SAME_PLACE_DP)) == (
        round(b.lat, SAME_PLACE_DP),
        round(b.lng, SAME_PLACE_DP),
    )


def _route_legs(places: Sequence[Place], deadline: Deadline) -> list[LegRoute]:
    """Step 3: both legs in parallel; a leg between identical points is zero-length without a call."""
    legs = _parallel(
        [
            lambda: ors_client.directions_leg(places[0], places[1], deadline),
            lambda: ors_client.directions_leg(places[1], places[2], deadline),
        ],
        2,
    )
    ors_client.ensure_total_within_limit(legs)
    return legs


@dataclass(frozen=True, slots=True)
class _Leg:
    """A leg after normalization: ORS zero distance or zero duration becomes exactly (0, 0)."""

    route: LegRoute
    miles: float
    duration_min: float
    geometry: LegGeometry
    polyline: str


def _normalize_leg(route: LegRoute, start: Place) -> _Leg:
    if route.distance_m == 0 or route.duration_s == 0:
        return _Leg(route, 0.0, 0.0, build_leg_geometry_from_points([(start.lat, start.lng)], 0.0), "")
    geometry = build_leg_geometry(route.polyline, route.distance_m)
    return _Leg(route, route.miles, route.duration_s / 60, geometry, route.polyline)


def _leg_bounds(leg: _Leg, start: Place, end: Place) -> Bounds:
    return Bounds.around([*leg.geometry.points, (start.lat, start.lng), (end.lat, end.lng)])


def _point_at(mile: float, legs: Sequence[_Leg]) -> tuple[float, float]:
    """(lat, lng) of a cumulative trip mile: bisect on the leg's rescaled cumulative distances."""
    first = legs[0].miles
    if 0 < mile <= first:
        return interpolate(legs[0].geometry, mile)
    return interpolate(legs[1].geometry, max(0.0, mile - first))


def _reverse_geocode(
    points: Sequence[tuple[float, float]], deadline: Deadline
) -> dict[tuple[float, float], str]:
    """Step 7 network part: at most 5 in flight, sub-budget min(6 s, remaining - 1 s), never raises."""
    budget = min(REVERSE_BUDGET_S, deadline.remaining() - REVERSE_RESERVE_S)
    if not points or budget <= 0:
        return {}
    sub = Deadline(budget)

    def one(point: tuple[float, float]) -> str | None:
        try:
            return ors_client.reverse_label(point[0], point[1], sub)
        except Exception:  # noqa: BLE001 - a label problem never fails a plan
            return None

    labels = _parallel([lambda p=p: one(p) for p in points], REVERSE_WORKERS)
    return {point: label for point, label in zip(points, labels, strict=True) if label}


@dataclass(frozen=True, slots=True)
class _Labeled:
    points: dict[int, PointInfo]
    approximated: bool
    reverse_calls: int
    sources: dict[str, int]


def _label_points(
    keys: Sequence[int], legs: Sequence[_Leg], places: Sequence[Place], deadline: Deadline
) -> _Labeled:
    """Steps 6 and 7: place every needed mile on the route and give it a label (never fatal)."""
    known = [KnownLabel((p.lat, p.lng), p.label) for p in places]
    positions = {k: _point_at(k / 1000, legs) for k in keys}
    infos: dict[int, PointInfo] = {}
    pending: dict[int, tuple[float, float]] = {}
    for key, (lat, lng) in positions.items():
        near = reuse_known_label((lat, lng), known)
        if near:
            infos[key] = PointInfo(lat, lng, near, LABEL_NEARBY)
        else:
            pending[key] = round_point((lat, lng))
    unique = list(dict.fromkeys(pending.values()))
    resolved = _reverse_geocode(unique[:MAX_REVERSE_CALLS], deadline)
    known_all = [*known, *(KnownLabel(pt, label) for pt, label in resolved.items())]
    approximated = False
    for key, rounded in pending.items():
        lat, lng = positions[key]
        if rounded in resolved:
            infos[key] = PointInfo(lat, lng, resolved[rounded], LABEL_GEOCODED)
            continue
        approximated = True
        label = fallback_label((lat, lng), known_all)
        source = LABEL_NEARBY if label != coordinate_label((lat, lng)) else LABEL_COORDINATES
        infos[key] = PointInfo(lat, lng, label, source)
    sources: dict[str, int] = {}
    for info in infos.values():
        sources[info.source] = sources.get(info.source, 0) + 1
    return _Labeled(infos, approximated, min(len(unique), MAX_REVERSE_CALLS), sources)


def _timing(frozen: FrozenTimezone) -> Timing:
    return Timing(
        name=frozen.name,
        abbreviation=frozen.abbreviation,
        offset_minutes=frozen.offset_minutes,
        utc_offset=frozen.utc_offset,
        day0=frozen.start.replace(hour=0, minute=0, second=0, microsecond=0),
    )


def _run_engine(
    legs: Sequence[_Leg], places: Sequence[Place], cycle_h: float, start_min: int
) -> hos.PlanResult:
    trip = hos.TripInput(
        legs=(
            hos.Leg(legs[0].miles, legs[0].duration_min, places[0].label, places[1].label),
            hos.Leg(legs[1].miles, legs[1].duration_min, places[1].label, places[2].label),
        ),
        cycle_used_min=round(cycle_h * 60),
        start_min=start_min,
    )
    try:
        return hos.plan(trip)
    except (HosInputError, HosEngineError) as exc:
        logger.error("hos_engine_rejected", extra={"error_class": type(exc).__name__})
        raise internal_error() from None


class _Steps:
    """Per-step wall time in ms for the plan_completed line."""

    def __init__(self) -> None:
        self.ms: dict[str, int] = {}
        self._t = time.monotonic()

    def mark(self, name: str) -> None:
        now = time.monotonic()
        self.ms[name] = round((now - self._t) * 1000)
        self._t = now


def plan_trip(validated: PlanRequest) -> Dto:
    """Plan a trip end to end. Raises routing errors, `ApiError`, or `ApiError(INTERNAL)`."""
    started = time.monotonic()
    log: dict[str, Any] = {}
    try:
        body = _plan(validated, Deadline(), _Steps(), log)
    except Exception as exc:
        code = exc.code.value if isinstance(exc, ApiError) else None
        logger.warning(
            "plan_completed",
            extra={
                "status": "error",
                "code": code,
                "error_class": type(exc).__name__,
                "duration_ms": round((time.monotonic() - started) * 1000),
                **log,
            },
        )
        raise
    logger.info(
        "plan_completed",
        extra={
            "status": "ok",
            "code": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            **log,
        },
    )
    return body


def _plan(validated: PlanRequest, deadline: Deadline, steps: _Steps, log: dict[str, Any]) -> Dto:
    places, sources = _resolve_places(validated, deadline)
    steps.mark("resolve")
    log["steps_ms"] = steps.ms
    if _same_point(places[1], places[2]):
        raise ApiError(ErrorCode.VALIDATION_ERROR, SAME_PLACE_MESSAGE, field="dropoff_location")

    routes = _route_legs(places, deadline)
    steps.mark("directions")
    profile = "driving-car" if any(r.profile == "driving-car" for r in routes) else "driving-hgv"
    legs = [_normalize_leg(routes[0], places[0]), _normalize_leg(routes[1], places[1])]
    if legs[1].miles == 0:
        raise ApiError(ErrorCode.VALIDATION_ERROR, SAME_PLACE_MESSAGE, field="dropoff_location")
    log["profile_used"] = profile

    frozen = home_terminal_timezone(
        places[0].lat, places[0].lng, validated.get("start_date"), validated["start_time"]
    )
    start = quantize_time(validated["start_time"])
    cycle_h = float(validated["current_cycle_used_hours"])
    result = _run_engine(legs, places, cycle_h, start.hour * 60 + start.minute)
    steps.mark("engine")

    views = tuple(
        LegView(leg.polyline, leg.miles, leg.duration_min, _leg_bounds(leg, places[i], places[i + 1]))
        for i, leg in enumerate(legs)
    )
    place_views = tuple(PlaceView(p.label, p.lat, p.lng, s) for p, s in zip(places, sources, strict=True))
    base = ResponseInput(
        places=place_views,  # type: ignore[arg-type]
        legs=views,  # type: ignore[arg-type]
        profile=profile,
        plan=result,
        points={},
        timing=_timing(frozen),
        cycle_used_h=cycle_h,
        log_header=validated["log_header"],
    )
    labeled = _label_points(required_point_keys(base), legs, places, deadline)
    steps.mark("labels")

    try:
        body = build_plan_response(
            replace(base, points=labeled.points, labels_approximated=labeled.approximated)
        )
    except ResponseBuildError:
        logger.exception("response_invariant_violated")
        raise internal_error() from None
    steps.mark("response")
    summary = result.summary
    log.update(
        {
            "total_miles": summary.total_miles,
            "days": summary.sheet_count,
            "events": len(result.events),
            "reverse_calls": labeled.reverse_calls,
            "label_sources": labeled.sources,
        }
    )
    return body
