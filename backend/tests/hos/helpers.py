"""Small builders shared by the engine tests. Synthetic legs run at 60 mph unless stated (1 mi = 1 min)."""

from hos import Kind, Leg, PlanResult, Status, TripInput, plan
from tests.hos.audit import assert_clean

START_08 = 480


def trip(
    l0: tuple[float, float], l1: tuple[float, float], cycle_h: float = 0, start: int = START_08
) -> TripInput:
    """l0 and l1 are (miles, minutes). cycle_h in hours (multiples of 0.25)."""
    return TripInput(
        (Leg(l0[0], l0[1], "Origin, ST", "Pickup, ST"), Leg(l1[0], l1[1], "Pickup, ST", "Dropoff, ST")),
        round(cycle_h * 60),
        start,
    )


def run(l0, l1, cycle_h: float = 0, start: int = START_08) -> tuple[TripInput, PlanResult]:
    """Plan a synthetic trip and assert the independent audit is clean."""
    inp = trip(l0, l1, cycle_h, start)
    result = plan(inp)
    assert_clean(result, inp)
    return inp, result


def tuples(result: PlanResult) -> list[tuple[int, int, str, str]]:
    return [(e.start_min_abs, e.end_min_abs, str(e.status), str(e.kind)) for e in result.events]


def kinds(result: PlanResult) -> list[str]:
    return [str(e.kind) for e in result.events]


def of_kind(result: PlanResult, kind: Kind):
    return [e for e in result.events if e.kind == kind]


def drive_minutes(result: PlanResult) -> int:
    return sum(e.end_min_abs - e.start_min_abs for e in result.events if e.status == Status.D)


def after(result: PlanResult, kind: Kind):
    """The event that follows the first event of `kind`."""
    events = result.events
    i = next(i for i, e in enumerate(events) if e.kind == kind)
    return events[i + 1]
