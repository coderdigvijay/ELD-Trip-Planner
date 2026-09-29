"""Trip summary (HOS_ENGINE_SPEC section 2, `Summary`)."""

from .exact import MileSpan, as_float
from .models import DutyEvent, Kind, Status, Summary
from .recap import cycle_at


def _minutes(events: tuple[DutyEvent, ...], *statuses: Status) -> int:
    return sum(e.end_min_abs - e.start_min_abs for e in events if e.status in statuses)


def _count(events: tuple[DutyEvent, ...], kind: Kind) -> int:
    return sum(1 for e in events if e.kind == kind)


def _dropoff(events: tuple[DutyEvent, ...]) -> DutyEvent:
    dropoffs = [e for e in events if e.kind == Kind.DROPOFF]
    return dropoffs[-1] if dropoffs else events[-1]


def _trip_start(events: tuple[DutyEvent, ...]) -> int:
    return next((e.start_min_abs for e in events if e.kind == Kind.PRE_TRIP), events[0].start_min_abs)


def build_summary(
    events: tuple[DutyEvent, ...], spans: tuple[MileSpan, ...], cycle_used_min: int, sheet_count: int
) -> Summary:
    dropoff = _dropoff(events)
    return Summary(
        total_miles=as_float(spans[-1].end, 1),
        total_drive_min=_minutes(events, Status.D),
        total_on_duty_min=_minutes(events, Status.D, Status.ON),
        start_min_abs=_trip_start(events),
        arrive_dropoff_min_abs=dropoff.start_min_abs,
        complete_min_abs=dropoff.end_min_abs,
        sheet_count=sheet_count,
        fuel_stops=_count(events, Kind.FUEL),
        breaks=_count(events, Kind.BREAK),
        rests=_count(events, Kind.REST),
        restarts=_count(events, Kind.RESTART),
        cycle_end_min=cycle_at(events, cycle_used_min, dropoff.end_min_abs),
    )
