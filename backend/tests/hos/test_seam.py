"""Test-only simulator state seam (HOS_ENGINE_SPEC 4.9, TEST_PLAN S-12).

The 14 h cap alone and the A17 branch cannot be reached from plan(), so hypothesis never exercises
them. These tests build a SimState directly. Every field is passed explicitly so the tests do not
depend on the defaults of `SimState.for_test`.
"""

from fractions import Fraction

import pytest

from hos import Kind, Leg, Status
from hos.simulator import SimState, drive_step, resolve

LONG_LEG = Leg(600.0, 600.0, "A, ST", "B, ST")
LEGS = (LONG_LEG, Leg(100.0, 100.0, "B, ST", "C, ST"))

REASON_A17 = "10-hr rest: not enough of the 14-hr window left for the required break"


def state(**over) -> SimState:
    base = {
        "t": 1200,
        "drive_in_shift": 0,
        "shift_start": 600,
        "drive_since_break": 0,
        "cycle_on_duty": 600,
        "miles_since_fuel": Fraction(0),
        "nondriving_run": 0,
        "off_run": 0,
        "trip_mile": Fraction(0),
        "leg_index": 0,
        "leg_done": 0,
        "leg_start_mile": Fraction(0),
        "events": [],
    }
    return SimState.for_test(**{**base, **over})


def summary(st: SimState):
    return [(e.start_min_abs, e.end_min_abs, str(e.status), str(e.kind)) for e in st.events]


def test_seam_symbols_are_not_part_of_the_public_api():
    import hos

    for name in ("SimState", "drive_step", "resolve", "for_test"):
        assert not hasattr(hos, name)
        assert name not in hos.__all__


def test_r_14h_window_cap_binds_alone_then_sleeper_rest():
    st = state(t=1200, shift_start=600, drive_in_shift=300)  # 600 elapsed, 300 driven
    drive_step(st, LEGS)
    assert summary(st) == [
        (1200, 1440, "D", "drive"),
        (1440, 2040, "SB", "rest"),
    ]  # 240 = 14h cap < 360 = 11h cap
    assert st.events[1].reason == "10-hr rest: 14 hr window reached"
    assert st.events[0].end_min_abs - 600 == 840  # no D minute at or after window minute 840


def test_r_14h_tie_with_11h_reports_the_11_hour_reason():
    st = state(t=1440, shift_start=600, drive_in_shift=660)
    resolve(st, {"11h", "14h"}, LEGS)
    assert st.events[0].reason == "10-hr rest: 11 hr driving limit reached"


@pytest.mark.parametrize("elapsed", [810, 825, 835])
def test_r_a17_break_with_too_little_window_becomes_a_rest(elapsed):
    st = state(t=2000, shift_start=2000 - elapsed, drive_in_shift=480, drive_since_break=480)
    drive_step(st, LEGS)
    assert summary(st) == [(2000, 2600, "SB", "rest")]
    assert st.events[0].reason == REASON_A17


@pytest.mark.parametrize("elapsed", [795, 780, 600])
def test_r_a17_break_with_15_or_more_minutes_of_window_left_after_it_stays_a_break(elapsed):
    st = state(t=2000, shift_start=2000 - elapsed, drive_in_shift=480, drive_since_break=480)
    drive_step(st, LEGS)
    assert summary(st) == [(2000, 2030, "OFF", "break")]
    assert st.events[0].reason == "30-min break required after 8 hr driving"


def test_r_a17_no_break_then_rest_pair_on_the_log():
    st = state(t=2000, shift_start=2000 - 820, drive_in_shift=480, drive_since_break=480)
    drive_step(st, LEGS)
    assert [e.kind for e in st.events] == [Kind.REST]


def test_r_a10_upgrade_restart_when_a17_rest_cannot_be_covered_by_the_cycle():
    st = state(t=2000, shift_start=2000 - 810, drive_in_shift=480, drive_since_break=480, cycle_on_duty=4100)
    drive_step(st, LEGS)
    assert summary(st) == [(2000, 4040, "OFF", "restart")]
    assert st.events[0].reason == "34-hr restart: cycle hours left do not cover the rest of the trip"


def test_r_a10_no_upgrade_when_14_hours_or_more_of_cycle_remain():
    st = state(
        t=2000, shift_start=2000 - 810, drive_in_shift=480, drive_since_break=480, cycle_on_duty=4200 - 840
    )
    drive_step(st, LEGS)
    assert [e.kind for e in st.events] == [Kind.REST]


def test_r_a10_no_upgrade_when_the_cycle_covers_the_remaining_work():
    """cycle_left 700 < 840 but remaining work is only ~ (100 min drive + 120 stops + 30) = 250."""
    short = (Leg(20.0, 20.0, "A, ST", "B, ST"), Leg(20.0, 20.0, "B, ST", "C, ST"))
    st = state(
        t=2000, shift_start=2000 - 810, drive_in_shift=480, drive_since_break=480, cycle_on_duty=4200 - 700
    )
    drive_step(st, short)
    assert [e.kind for e in st.events] == [Kind.REST]


def test_resolve_arrive_returns_without_any_event_even_with_other_limits_hit():
    st = state(drive_in_shift=660)
    resolve(st, {"arrive", "11h", "fuel", "70h"}, LEGS)
    assert st.events == []


def test_resolve_fuel_covers_the_break():
    st = state(drive_since_break=480, shift_start=1200 - 300)
    resolve(st, {"fuel", "break"}, LEGS)
    assert [e.kind for e in st.events] == [Kind.FUEL]
    assert st.events[0].status == Status.ON and st.events[0].reason == "Fuel: 1,000 mi limit"
    assert st.drive_since_break == 0  # 30 min on duty resets the 8 h counter


def test_resolve_fuel_then_70h_restart_in_order():
    st = state(cycle_on_duty=4200, shift_start=1200 - 300)
    resolve(st, {"fuel", "70h"}, LEGS)
    assert [e.kind for e in st.events] == [Kind.FUEL, Kind.RESTART]
    assert st.events[1].reason == "34-hr restart: 70 hr cycle limit reached"


def test_resolve_70h_wins_over_11h():
    st = state(cycle_on_duty=4200, drive_in_shift=660)
    resolve(st, {"70h", "11h"}, LEGS)
    assert [e.kind for e in st.events] == [Kind.RESTART]


def test_restart_resets_every_counter():
    st = state(cycle_on_duty=4200, drive_in_shift=400, drive_since_break=300)
    resolve(st, {"70h"}, LEGS)
    assert (st.cycle_on_duty, st.drive_in_shift, st.drive_since_break, st.shift_start) == (0, 0, 0, None)


def test_rest_resets_shift_but_not_the_cycle():
    st = state(cycle_on_duty=1000, drive_in_shift=660)
    resolve(st, {"11h"}, LEGS)
    assert (st.drive_in_shift, st.drive_since_break, st.shift_start, st.cycle_on_duty) == (0, 0, None, 1000)
    assert st.t == 1200 + 600


def test_next_step_after_a_rest_starts_with_a_pre_trip():
    st = state(drive_in_shift=660)
    resolve(st, {"11h"}, LEGS)
    drive_step(st, LEGS)
    assert [e.kind for e in st.events][:2] == [Kind.REST, Kind.PRE_TRIP]
    assert st.events[1].start_min_abs == st.events[0].end_min_abs
