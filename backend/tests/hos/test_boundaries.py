"""Boundary examples B-01 to B-20 (TEST_PLAN 2.5) plus the cycle and midnight edges of the QA break list.

Every case runs plan() and then the independent audit (helpers.run), then asserts its own outcome.
"""

import pytest

from hos import Kind, Status, TripInput, plan
from tests.hos.audit import assert_clean
from tests.hos.helpers import after, drive_minutes, kinds, of_kind, run, trip, tuples

ZERO = (0, 0)
LEGS_8B = ((180, 198), (1100, 1020))


def test_b01_cycle_zero_short_trip_has_no_restart():
    _, res = run((100, 100), (200, 200), 0)
    assert kinds(res).count("restart") == 0
    assert res.sheets[0].recap.a_last_7 == res.sheets[0].recap.on_duty_today


def test_b02_cycle_quarter_hour_adds_15_to_every_a_and_c():
    _, base = run(*LEGS_8B, cycle_h=0)
    _, plus = run(*LEGS_8B, cycle_h=0.25)
    assert [s.recap.a_last_7 - b.recap.a_last_7 for s, b in zip(plus.sheets, base.sheets, strict=True)] == [
        15,
        15,
    ]
    assert [s.recap.c_last_8 - b.recap.c_last_8 for s, b in zip(plus.sheets, base.sheets, strict=True)] == [
        15,
        15,
    ]
    assert tuples(plus) == tuples(base)


def test_b03_cycle_60_restart_only_when_the_trip_needs_more_than_10_hours_on_duty():
    _, short = run((100, 100), (200, 200), 60)  # 30 + 105 + 60 + 200 + 60 = 455 min on duty
    assert kinds(short).count("restart") == 0
    _, long = run(*LEGS_8B, cycle_h=60)
    assert kinds(long).count("restart") >= 1


@pytest.mark.parametrize("cycle_h", [69.5, 69.75])
def test_b04_b05_cycle_69_5_and_above_restarts_at_start(cycle_h):
    _, res = run(*LEGS_8B, cycle_h=cycle_h)
    assert (res.events[0].kind, res.events[0].start_min_abs, res.events[0].end_min_abs) == (
        Kind.RESTART,
        0,
        2040,
    )
    assert [w.code for w in res.warnings] == ["CYCLE_RESTART_AT_START"]
    assert all(e.status != Status.D for e in res.events if e.start_min_abs < 2040)


def test_b06_cycle_70_no_driving_before_2070():
    _, res = run(*LEGS_8B, cycle_h=70)
    assert min(e.start_min_abs for e in res.events if e.status == Status.D) == 2070


def test_b07_cycle_69_25_pre_trip_then_15_minutes_then_restart():
    _, res = run(*LEGS_8B, cycle_h=69.25)
    assert tuples(res)[1:4] == [
        (480, 510, "ON", "pre_trip"),
        (510, 525, "D", "drive"),
        (525, 2565, "OFF", "restart"),
    ]


def test_b08_zero_length_first_leg_pickup_is_note_only_at_mile_zero():
    _, res = run(ZERO, (532, 523), 30)
    pickup = of_kind(res, Kind.PICKUP)[0]
    assert (pickup.start_mile, pickup.end_mile) == (0.0, 0.0)
    remark = next(r for r in res.sheets[0].remarks if r.note == "Pickup")
    assert remark.status_change is False


def test_b09_tiny_second_leg_is_one_15_minute_drive_on_one_sheet():
    _, res = run(ZERO, (0.2, 0.4))
    assert drive_minutes(res) == 15
    assert res.summary.total_miles == 0.2
    assert len(res.sheets) == 1
    assert res.events[-3].end_mile == pytest.approx(0.2, abs=1e-3)


def test_b10_drive_landing_on_480_at_the_pickup_needs_no_break():
    _, res = run((480, 480), (100, 100))
    assert Kind.BREAK not in [e.kind for e in res.events]
    assert tuples(res)[2:4] == [(510, 990, "D", "drive"), (990, 1050, "ON", "pickup")]


def test_b11_drive_landing_on_660_at_the_pickup_then_rest_then_pre_trip():
    _, res = run((660, 660), (100, 100))
    k = kinds(res)
    i = k.index("pickup")
    assert k[i : i + 3] == ["pickup", "rest", "pre_trip"]
    assert kinds(res).count("break") == 1  # the 8 h break happens inside the leg
    assert of_kind(res, Kind.REST)[0].reason == "10-hr rest: 11 hr driving limit reached"


def test_b12_drive_landing_on_11h_at_the_dropoff_no_rest_after_it():
    """The 14 h window cannot bind from plan() (S-12); the 11 h landing is the reachable variant."""
    _, res = run(ZERO, (660, 660))
    k = kinds(res)
    assert k[-2:] == ["dropoff", "off_after_end"]
    assert "rest" not in k and "restart" not in k


def test_b12b_window_is_never_the_binding_limit_from_plan():
    """S-12: on-duty-not-driving inside a shift is at most 180 min, so 660 + 180 = 840 exactly at worst."""
    _, res = run((300, 300), (1500, 1500), 10)
    rests = [e for e in res.events if e.kind in (Kind.REST, Kind.RESTART)]
    assert rests, "trip must be long enough to need rests"
    assert all("14 hr window" not in e.reason for e in rests)


def test_b13_start_2345_pre_trip_crosses_midnight():
    _, res = run((10, 15), (20, 30), start=1425)
    day0, day1 = res.sheets[0], res.sheets[1]
    assert day0.totals[Status.ON] == 15 and day0.totals[Status.OFF] == 1425
    assert (day1.segments[0].start_min, day1.segments[0].end_min, day1.segments[0].status) == (
        0,
        15,
        Status.ON,
    )
    assert day1.remarks[0].minute > 0  # the pre-trip merely continues past midnight: no remark at 00:00
    assert [r.minute for r in day0.remarks] == [1425]


def test_b14_start_2330_drive_starts_exactly_at_midnight_with_a_remark():
    _, res = run((30, 30), (60, 60), start=1410)
    day1 = res.sheets[1]
    first = day1.remarks[0]
    assert first.minute == 0 and first.status == Status.D and first.status_change is True
    assert res.sheets[0].segments[-1].end_min == 1440


def test_b15_drive_crossing_midnight_splits_the_miles_by_interpolation():
    _, res = run(ZERO, (600, 600), start=1200)
    day0, day1 = res.sheets[0], res.sheets[1]
    d0 = day0.segments[-1]
    assert d0.status == Status.D and d0.end_min == 1440
    assert d0.end_mile == pytest.approx(150.0, abs=1e-3)  # 1290..1440 at 1 mi/min
    assert day1.segments[0].status == Status.D
    assert day1.segments[0].start_mile == pytest.approx(150.0, abs=1e-3)
    assert day0.miles_today == 150.0
    assert day0.miles_today + day1.miles_today == 600.0
    assert day1.remarks[0].minute > 0  # crossing midnight is not a change of status


def test_b16_coast_to_coast():
    inp, res = run((50, 54.5), (2800, 3054.5), 40)
    k = kinds(res)
    assert k.count("fuel") >= 2
    assert k.count("restart") == 1
    assert len(res.sheets) >= 4
    assert_clean(res, inp)


def test_b17_huge_trip_completes_without_hitting_the_progress_guard():
    inp, res = run((3000, 9000), (3000, 9000), 0)
    assert len(res.sheets) >= 20
    assert res.summary.total_miles == 6000.0


def test_b18_restart_ending_exactly_at_midnight():
    _, res = run((600, 600), (100, 100), 64)
    restart = of_kind(res, Kind.RESTART)[0]
    assert (restart.start_min_abs, restart.end_min_abs) == (840, 2880)
    assert res.sheets[0].recap.restart_note and not res.sheets[1].recap.restart_note
    assert res.sheets[1].recap.a_last_7 == 0


def test_b19_fuel_exactly_at_1000_on_a_grid_line_arrive_wins():
    _, res = run(ZERO, (1000, 900))
    assert Kind.FUEL not in [e.kind for e in res.events]


def test_b20_fuel_due_in_under_15_minutes_at_a_leg_start_is_taken_at_the_pickup():
    _, res = run((999.9, 999.9), (50, 50))
    order = [e.kind for e in res.events]
    assert Kind.FUEL not in order[: order.index(Kind.PICKUP)]
    nxt = after(res, Kind.PICKUP)
    assert nxt.kind == Kind.FUEL and nxt.end_min_abs - nxt.start_min_abs == 30


@pytest.mark.parametrize("cycle_min", [4125, 4140, 4155, 4170, 4185, 4200])
@pytest.mark.parametrize("start", [0, 480, 1425])
def test_cycle_band_near_70_hours_is_always_legal(cycle_min, start):
    inp = TripInput(trip((180, 198), (1100, 1020)).legs, cycle_min, start)
    assert_clean(plan(inp), inp)


@pytest.mark.parametrize("drive", [465, 480, 495, 645, 660, 675, 825, 840, 855])
def test_drive_lengths_around_8_11_and_14_hours(drive):
    _, res = run(ZERO, (drive, drive))
    assert drive_minutes(res) == drive


@pytest.mark.parametrize("miles", [999.9, 1000.0, 1000.1, 1999.9, 2000.0, 2000.1, 3000.0])
def test_fuel_spacing_around_multiples_of_1000_miles(miles):
    run(ZERO, (miles, miles * 1.1))
    run((miles, miles * 1.1), (50, 50))


def test_one_second_over_a_grid_line_rounds_up_a_full_tick():
    _, exact = run(ZERO, (210, 210.0))
    _, over = run(ZERO, (210, 210.0 + 1 / 60))
    assert drive_minutes(over) - drive_minutes(exact) == 15


def test_three_legs_of_1000_miles_each_are_at_most_1000_apart():
    inp, res = run(ZERO, (3000, 3000))
    fuel = [e.start_mile for e in of_kind(res, Kind.FUEL)]
    marks = [0.0, *fuel, 3000.0]
    assert all(b - a <= 1000.0 + 1e-6 for a, b in zip(marks, marks[1:], strict=False))
    assert len(fuel) >= 2


def test_two_different_starts_same_legs_same_driving():
    _, a = run(*LEGS_8B, cycle_h=20, start=0)
    _, b = run(*LEGS_8B, cycle_h=20, start=1425)
    assert drive_minutes(a) == drive_minutes(b)
    assert a.summary.total_miles == b.summary.total_miles


def test_multi_day_every_sheet_is_24_hours():
    _, res = run(ZERO, (3000, 3000), 30)
    assert len(res.sheets) >= 5
    assert all(sum(s.totals.values()) == 1440 for s in res.sheets)


def test_s13_pre_trip_crossing_midnight_counts_clipped_in_a_and_c_of_both_sheets():
    _, res = run((10, 15), (20, 30), start=1425)
    day0, day1 = (s.recap for s in res.sheets[:2])
    assert (day0.on_duty_today, day0.a_last_7, day0.c_last_8, day0.b_available_tomorrow) == (15, 15, 15, 4185)
    assert day0.restart_note is False
    # whole trip on duty: pre-trip 30 + drive 15 + pickup 60 + drive 30 + dropoff 60 = 195
    assert (day1.on_duty_today, day1.a_last_7, day1.c_last_8) == (180, 195, 195)


def test_s13_drive_crossing_midnight_counts_clipped_in_a_and_c():
    _, res = run(ZERO, (600, 600), start=1200)
    day0 = res.sheets[0].recap
    # pre-trip 30 + pickup 60 + 150 min of the drive before 24:00
    assert (day0.on_duty_today, day0.a_last_7, day0.c_last_8, day0.b_available_tomorrow) == (
        240,
        240,
        240,
        3960,
    )
    day1 = res.sheets[1].recap
    assert day1.a_last_7 == day1.on_duty_today + 240


def test_s13_a_crossing_event_adds_to_the_prior_cycle_not_replaces_it():
    _, res = run(ZERO, (300, 300), cycle_h=20, start=1200)
    day0 = res.sheets[0].recap
    assert day0.a_last_7 == 20 * 60 + day0.on_duty_today
