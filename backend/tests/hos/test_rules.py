"""One rule per test on minimal synthetic legs (TEST_PLAN 2.3). Legs run at 60 mph: 1 mi = 1 min.

Timeline reminder for start 08:00 and a zero-length first leg: pre-trip 480-510, pickup 510-570,
driving begins at 570. Every result is also run through the independent audit (helpers.run).
"""

import pytest

from hos import Kind, Status, TripInput, plan
from tests.hos.audit import assert_clean
from tests.hos.helpers import after, drive_minutes, kinds, of_kind, run, trip, tuples

ZERO = (0, 0)


def test_r_11h_driving_limit_then_break_then_rest():
    _, res = run(ZERO, (900, 900))
    assert tuples(res)[:9] == [
        (0, 480, "OFF", "off_before_start"),
        (480, 510, "ON", "pre_trip"),
        (510, 570, "ON", "pickup"),
        (570, 1050, "D", "drive"),  # 8 h
        (1050, 1080, "OFF", "break"),
        (1080, 1260, "D", "drive"),  # 3 h more: 11 h in the shift
        (1260, 1860, "SB", "rest"),
        (1860, 1890, "ON", "pre_trip"),
        (1890, 2130, "D", "drive"),
    ]
    rest = of_kind(res, Kind.REST)[0]
    assert rest.reason == "10-hr rest: 11 hr driving limit reached"
    assert rest.note == "10-hr rest (sleeper)"


def test_r_8h_break_exactly_after_480_minutes_of_driving():
    _, res = run(ZERO, (600, 600))
    assert tuples(res)[3:8] == [
        (570, 1050, "D", "drive"),
        (1050, 1080, "OFF", "break"),
        (1080, 1200, "D", "drive"),
        (1200, 1260, "ON", "dropoff"),
        (1260, 1440, "OFF", "off_after_end"),
    ]
    brk = of_kind(res, Kind.BREAK)[0]
    assert brk.reason == "30-min break required after 8 hr driving"


def test_r_8h_cover_a_pickup_after_450_minutes_needs_no_standalone_break():
    _, res = run((450, 450), (195, 195))
    assert Kind.BREAK not in [e.kind for e in res.events]
    assert tuples(res)[2:6] == [
        (510, 960, "D", "drive"),
        (960, 1020, "ON", "pickup"),
        (1020, 1215, "D", "drive"),
        (1215, 1275, "ON", "dropoff"),
    ]


def test_r_70_restart_right_at_the_cap_and_nothing_drives_inside_it():
    _, res = run((180, 198), (1100, 1020), 62)
    restart = of_kind(res, Kind.RESTART)[0]
    assert (restart.start_min_abs, restart.end_min_abs) == (960, 3000)
    assert restart.reason == "34-hr restart: 70 hr cycle limit reached"
    assert not [e for e in res.events if e.status == Status.D and e.start_min_abs < 3000 <= e.end_min_abs]
    assert after(res, Kind.RESTART).kind == Kind.PRE_TRIP


def test_r_70_on_duty_past_70_is_legal_but_driving_is_not():
    """Cycle 67.75 h: 70 h is reached exactly as the drive arrives at the pickup (arrive wins)."""
    _, res = run((100, 100), (50, 50), 67.75)
    assert tuples(res)[:7] == [
        (0, 480, "OFF", "off_before_start"),
        (480, 510, "ON", "pre_trip"),
        (510, 615, "D", "drive"),
        (615, 675, "ON", "pickup"),  # on duty at 70 h + 1 h: legal
        (675, 2715, "OFF", "restart"),  # driving is not
        (2715, 2745, "ON", "pre_trip"),
        (2745, 2805, "D", "drive"),
    ]


def test_r_34_restart_resets_every_clock():
    _, res = run((180, 198), (1100, 1020), 62)
    after_restart = [e for e in res.events if e.start_min_abs >= 3000]
    first_drive = next(e for e in after_restart if e.status == Status.D)
    # fresh 8 h counter and fresh 11 h counter after the restart: a full 480 min block
    assert first_drive.end_min_abs - first_drive.start_min_abs == 480


def test_r_a10_restart_replaces_rest_when_the_cycle_cannot_cover_the_trip():
    _, res = run((180, 198), (1100, 1020), 55)  # fixture 8g
    assert kinds(res).count("rest") == 0 and kinds(res).count("restart") == 1
    restart = of_kind(res, Kind.RESTART)[0]
    assert restart.reason == "34-hr restart: cycle hours left do not cover the rest of the trip"


def test_r_a10_rest_stays_a_rest_when_the_cycle_covers_the_trip():
    _, res = run((180, 198), (1100, 1020), 20)  # fixture 8b
    assert kinds(res).count("rest") == 1 and kinds(res).count("restart") == 0


def test_r_fuel_stops_every_990_and_1980_miles_on_a_2505_mile_leg():
    _, res = run(ZERO, (2505, 2505))
    fuel = of_kind(res, Kind.FUEL)
    assert [round(f.start_mile, 1) for f in fuel] == [990.0, 1980.0]
    assert all(f.status == Status.ON and f.end_min_abs - f.start_min_abs == 30 for f in fuel)
    assert all(f.reason == "Fuel: 1,000 mi limit" for f in fuel)


def test_r_fuel_arrive_no_fuel_before_pickup_fuel_right_after_it():
    """Leg 0 of exactly 1000 mi: the arrival wins over the fuel cap, fuel is taken after the pickup."""
    _, res = run((1000, 900), (10, 10))
    events = list(res.events)
    pickup = next(i for i, e in enumerate(events) if e.kind == Kind.PICKUP)
    assert Kind.FUEL not in [e.kind for e in events[:pickup]]
    assert events[pickup + 1].kind == Kind.FUEL
    assert events[pickup + 2].kind == Kind.DRIVE


def test_r_fuel_drop_no_fuel_when_the_1000th_mile_is_the_dropoff():
    _, res = run(ZERO, (1000, 900))
    assert Kind.FUEL not in [e.kind for e in res.events]
    assert [e.kind for e in res.events][-2:] == [Kind.DROPOFF, Kind.OFF_AFTER_END]


def test_r_a1_off_before_start_with_fresh_clocks():
    _, res = run(ZERO, (900, 900), start=360)
    assert tuples(res)[:2] == [(0, 360, "OFF", "off_before_start"), (360, 390, "ON", "pre_trip")]
    first_rest = of_kind(res, Kind.REST)[0]
    driven_before_rest = sum(
        e.end_min_abs - e.start_min_abs
        for e in res.events
        if e.status == Status.D and e.end_min_abs <= first_rest.start_min_abs
    )
    assert driven_before_rest == 660  # a full 11 h despite only 6 h of visible off-duty time


def test_r_a1_start_at_midnight_has_no_off_before_start():
    _, res = run(ZERO, (60, 60), start=0)
    assert res.events[0].kind == Kind.PRE_TRIP and res.events[0].start_min_abs == 0
    assert Kind.OFF_BEFORE_START not in [e.kind for e in res.events]
    remarks = res.sheets[0].remarks  # S-14: the pre-trip at 00:00 is a real change; the pickup is note-only
    assert [(r.minute, r.status_change, r.note) for r in remarks[:2]] == [
        (0, True, "Pre-trip inspection"),
        (30, False, "Pickup"),
    ]


@pytest.mark.parametrize(
    ("l0", "l1", "cycle"),
    [
        (ZERO, (2500, 2500), 0),
        ((50, 54.5), (2800, 3054.5), 40),
        ((180, 198), (1100, 1020), 62),
        ((180, 198), (1100, 1020), 55),
    ],
)
def test_r_a4_a_pre_trip_starts_every_shift(l0, l1, cycle):
    _, res = run(l0, l1, cycle)
    k = kinds(res)
    assert k.count("pre_trip") == 1 + k.count("rest") + k.count("restart")


def test_r_a4_with_a_start_restart_the_restart_replaces_the_first_shift_gap():
    _, res = run((180, 198), (1100, 1020), 70)
    k = kinds(res)
    assert k.count("pre_trip") == k.count("rest") + k.count("restart")


def test_r_a6_pickup_and_dropoff_are_one_hour_on_duty():
    _, res = run((180, 198), (1100, 1020), 20)
    for kind in (Kind.PICKUP, Kind.DROPOFF):
        (ev,) = of_kind(res, kind)
        assert ev.status == Status.ON and ev.end_min_abs - ev.start_min_abs == 60
    assert of_kind(res, Kind.PICKUP)[0].start_mile == pytest.approx(180.0, abs=1e-3)
    assert of_kind(res, Kind.DROPOFF)[0].start_mile == pytest.approx(1280.0, abs=1e-3)


def test_r_a9_rest_is_sleeper_berth_for_600_minutes():
    _, res = run((180, 198), (1100, 1020), 20)
    (rest,) = of_kind(res, Kind.REST)
    assert rest.status == Status.SB and rest.end_min_abs - rest.start_min_abs == 600


def test_r_a9_restart_is_off_duty_for_2040_minutes():
    _, res = run((180, 198), (1100, 1020), 62)
    (restart,) = of_kind(res, Kind.RESTART)
    assert restart.status == Status.OFF and restart.end_min_abs - restart.start_min_abs == 2040


@pytest.mark.parametrize(
    ("minutes", "grid"), [(197.2, 210), (210.0, 210), (210.01, 225), (0.07, 15), (14.99, 15)]
)
def test_r_a13_leg_duration_rounds_up_to_the_15_minute_grid(minutes, grid):
    dist = min(180.0, minutes * 1.5)  # keep the speed under the 100 mph guard
    _, res = run((dist, minutes), (60, 60))
    assert drive_minutes(res) == grid + 60


def test_r_a13_every_event_boundary_is_on_the_grid_for_awkward_floats():
    _, res = run((123.456, 141.732), (987.654, 866.43), 13.25)
    assert all(e.start_min_abs % 15 == 0 and e.end_min_abs % 15 == 0 for e in res.events)


def test_r_a15_off_after_end_until_midnight():
    _, res = run(ZERO, (360, 360))
    assert tuples(res)[-2:] == [(930, 990, "ON", "dropoff"), (990, 1440, "OFF", "off_after_end")]
    assert res.events[-1].reason == "Trip complete"


def test_r_a15_dropoff_ending_at_midnight_emits_no_off_after_end():
    _, res = run(ZERO, (480, 480), start=810)
    assert tuples(res)[-1] == (1380, 1440, "ON", "dropoff")
    assert Kind.OFF_AFTER_END not in [e.kind for e in res.events]
    assert len(res.sheets) == 1


def test_r_a16_next_shift_starts_the_minute_the_rest_ends():
    _, res = run((50, 50), (2000, 2000))
    for rest in of_kind(res, Kind.REST) + of_kind(res, Kind.RESTART):
        nxt = next(e for e in res.events if e.start_min_abs == rest.end_min_abs)
        assert nxt.kind == Kind.PRE_TRIP


@pytest.mark.parametrize("start", [0, 480, 1425])
@pytest.mark.parametrize("cycle_min", [4170, 4185, 4200])
def test_r_start_restart_always_spans_0_to_2040(cycle_min, start):
    res = plan(TripInput(trip((180, 198), (1100, 1020)).legs, cycle_min, start))
    first = res.events[0]
    assert (first.start_min_abs, first.end_min_abs, first.status, first.kind) == (
        0,
        2040,
        Status.OFF,
        Kind.RESTART,
    )
    assert res.events[1].kind == Kind.PRE_TRIP and res.events[1].start_min_abs == 2040
    assert [w.code for w in res.warnings] == ["CYCLE_RESTART_AT_START"]
    assert_clean(res, TripInput(trip((180, 198), (1100, 1020)).legs, cycle_min, start))


def test_r_6925_no_start_restart_pre_trip_15_minutes_of_driving_then_restart():
    _, res = run((100, 100), (100, 100), 69.25)
    assert tuples(res)[:5] == [
        (0, 480, "OFF", "off_before_start"),
        (480, 510, "ON", "pre_trip"),
        (510, 525, "D", "drive"),
        (525, 2565, "OFF", "restart"),
        (2565, 2595, "ON", "pre_trip"),
    ]
    assert res.warnings == ()


def test_r_a3_days_are_exactly_1440_minutes_even_for_long_trips():
    """No DST 23/25 h days exist inside the engine: minute 0 is a fixed-offset midnight (A3)."""
    _, res = run((50, 54.5), (2800, 3054.5), 40)
    for sheet in res.sheets:
        assert sheet.segments[-1].end_min == 1440
        assert sum(sheet.totals.values()) == 1440


def test_window_is_not_paused_by_breaks_or_fuel():
    """Breaks do not extend the 14 h window (PITFALLS 2): the audit checks every D end against it."""
    _, res = run((1000, 900), (1000, 900), 10)
    shift_start = None
    off_run = 0
    for e in res.events:
        if e.status in (Status.D, Status.ON):
            if shift_start is None or off_run >= 600:
                shift_start = e.start_min_abs
            off_run = 0
            if e.status == Status.D:
                assert e.end_min_abs - shift_start <= 840
        else:
            off_run += e.end_min_abs - e.start_min_abs


@pytest.mark.parametrize(
    ("l0", "l1", "cycle"),
    [
        (ZERO, (60, 60), 0),
        ((180, 198), (1100, 1020), 20),
        ((180, 198), (1100, 1020), 55),
        ((42, 52), (125, 128), 10),
    ],
)
def test_s14_start_at_midnight_gives_the_first_pre_trip_a_remark_at_minute_zero(l0, l1, cycle):
    _, res = run(l0, l1, cycle, start=0)
    first = res.sheets[0].remarks[0]
    assert (first.minute, first.status, first.status_change, first.note) == (
        0,
        Status.ON,
        True,
        "Pre-trip inspection",
    )


def test_s14_start_after_midnight_gives_no_remark_for_the_off_before_start_event():
    _, res = run(ZERO, (60, 60), start=480)
    assert res.sheets[0].remarks[0].minute == 480
