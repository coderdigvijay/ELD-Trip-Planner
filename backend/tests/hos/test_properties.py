"""Property tests for the HOS_ENGINE_SPEC section 7 invariants (hypothesis, profiles in conftest).

`audit()` re-derives invariants 1 to 16, 19 and 20 from raw events (audit.py never imports the
simulator), so one clean audit per generated trip covers each numbered invariant, and a failure
message names the invariant. Invariants 17 and 18 and the input-independence properties (P3) are
asserted here directly. Invariant map (audit id -> where):

  1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 19 20 : audit.audit(), run for each of the five strategies
  17 : test_inv_17_cycle_zero_short_trips_never_restart
  18 : test_inv_18_determinism
  P3 : test_p3_driving_and_miles_do_not_depend_on_cycle_or_start
"""

import dataclasses
import json

from hypothesis import assume, given
from hypothesis import strategies as st

from hos import Kind, Status, TripInput, plan
from tests.hos.audit import audit, audit_recap_bound, audit_summary, fmt
from tests.hos.strategies import (
    boundary_trip,
    cycle_min,
    fuel_trip,
    midnight_trip,
    raw_ors_trip,
    start_min,
    trip,
)


def check(inp: TripInput) -> None:
    result = plan(inp)
    violations = audit(result, inp) + audit_summary(result, inp)
    assert not violations, f"{len(violations)} violation(s)\n{fmt(violations, result.events)}\ninput={inp}"


@given(trip)
def test_audit_clean_for_any_input_in_range(inp):
    check(inp)


@given(boundary_trip())
def test_audit_clean_on_8_11_14_hour_and_cycle_boundaries(inp):
    check(inp)


@given(fuel_trip())
def test_audit_clean_around_1000_mile_fuel_boundaries(inp):
    check(inp)


@given(midnight_trip())
def test_audit_clean_when_events_land_on_midnight(inp):
    check(inp)


@given(raw_ors_trip())
def test_audit_clean_for_raw_ors_shaped_floats(inp):
    check(inp)


def _dump(result) -> str:
    return json.dumps(dataclasses.asdict(result), sort_keys=True, default=str)


@given(trip)
def test_inv_18_determinism(inp):
    a, b = plan(inp), plan(inp)
    assert a == b
    assert _dump(a) == _dump(b)


@given(
    trip,
    st.tuples(cycle_min, start_min),
)
def test_p3_driving_and_miles_do_not_depend_on_cycle_or_start(inp, other):
    a = plan(inp)
    b = plan(dataclasses.replace(inp, cycle_used_min=other[0], start_min=other[1]))
    drive = lambda r: sum(e.end_min_abs - e.start_min_abs for e in r.events if e.status == Status.D)  # noqa: E731
    assert drive(a) == drive(b)
    assert a.summary.total_miles == b.summary.total_miles
    assert a.events[-1].end_mile == b.events[-1].end_mile


@given(trip.map(lambda t: dataclasses.replace(t, cycle_used_min=0)))
def test_inv_17_cycle_zero_short_trips_never_restart(inp):
    result = plan(inp)
    on_duty = sum(e.end_min_abs - e.start_min_abs for e in result.events if e.status in (Status.D, Status.ON))
    assume(on_duty < 4200)
    assert Kind.RESTART not in [e.kind for e in result.events]


@given(trip)
def test_every_sheet_is_24_hours_and_starts_where_the_last_ended(inp):
    """P4: totals equal the sum of the drawn segments; sheets are contiguous with one another."""
    result = plan(inp)
    for d, sheet in enumerate(result.sheets):
        assert sum(sheet.totals.values()) == 1440
        assert sum(s.end_min - s.start_min for s in sheet.segments) == 1440, f"sheet {d}"
        if d:
            assert abs(sheet.from_mile - result.sheets[d - 1].to_mile) < 1e-9


@given(trip)
def test_never_crashes_with_anything_but_a_typed_error(inp):
    """No input inside the documented range may raise (validation is exercised in test_validation)."""
    plan(inp)


@given(midnight_trip())
def test_inv_16_on_duty_today_never_exceeds_a(inp):
    """S-13: an ON or D event crossing midnight counts (clipped) in that sheet's A and C."""
    result = plan(inp)
    assert not audit_recap_bound(result, inp), fmt(audit_recap_bound(result, inp))
