"""Worked fixtures 8a to 8h (HOS_ENGINE_SPEC section 8) with the exact numbers from the spec.

Each trip fixture is asserted piece by piece (events, miles, segments, totals, recap, remarks,
brackets, summary, warnings) so a failure names what differs, then run through the independent audit.
"""

import pytest

from hos import DutyEvent, Kind, Status, TripInput, plan
from tests.hos import fixtures as fx
from tests.hos.audit import assert_clean, audit_summary, fmt

NAMES = list(fx.TRIP_FIXTURES)


@pytest.fixture(scope="module")
def results():
    return {name: plan(f.inp) for name, f in fx.TRIP_FIXTURES.items()}


def merged(segments):
    """Consecutive same-status segments drawn as one line, as the spec lists them."""
    out: list[list] = []
    for s in segments:
        if out and out[-1][0] == s.status and out[-1][2] == s.start_min:
            out[-1][2] = s.end_min
        else:
            out.append([str(s.status), s.start_min, s.end_min])
    return [tuple(x) for x in out]


# --------------------------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_events_match_spec_table(name, results):
    f, res = fx.TRIP_FIXTURES[name], results[name]
    got = [(e.start_min_abs, e.end_min_abs, str(e.status), str(e.kind)) for e in res.events]
    want = [(e.start, e.end, e.status, e.kind) for e in f.events]
    assert got == want


@pytest.mark.parametrize("name", NAMES)
def test_event_miles_match_spec_table(name, results):
    f, res = fx.TRIP_FIXTURES[name], results[name]
    prev = 0.0
    for got, want in zip(res.events, f.events, strict=True):
        assert got.start_mile == pytest.approx(prev, abs=1e-3), f"event {want.start}-{want.end} start_mile"
        assert got.end_mile == pytest.approx(want.end_mile, abs=1e-3), (
            f"event {want.start}-{want.end} end_mile"
        )
        prev = want.end_mile


@pytest.mark.parametrize("name", NAMES)
def test_audit_is_clean(name, results):
    assert_clean(results[name], fx.TRIP_FIXTURES[name].inp)


@pytest.mark.parametrize("name", NAMES)
def test_summary_block(name, results):
    f, s = fx.TRIP_FIXTURES[name], results[name].summary
    x = f.summary
    assert (s.arrive_dropoff_min_abs, s.complete_min_abs, s.sheet_count) == (x.arrive, x.complete, x.sheets)
    assert (s.fuel_stops, s.breaks, s.rests, s.restarts) == (x.fuel, x.breaks, x.rests, x.restarts)
    assert s.total_miles == x.total_miles
    assert s.cycle_end_min == x.cycle_end


@pytest.mark.parametrize("name", NAMES)
def test_summary_agrees_with_independent_recount(name, results):
    violations = audit_summary(results[name], fx.TRIP_FIXTURES[name].inp)
    assert not violations, fmt(violations)


@pytest.mark.parametrize("name", NAMES)
def test_warnings(name, results):
    f = fx.TRIP_FIXTURES[name]
    assert tuple(w.code for w in results[name].warnings) == f.warnings


@pytest.mark.parametrize("name", NAMES)
def test_deterministic(name, results):
    assert plan(fx.TRIP_FIXTURES[name].inp) == results[name]


# --------------------------------------------------------------------------------------------
# sheets
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_sheet_count_and_every_sheet_is_24_hours(name, results):
    f, res = fx.TRIP_FIXTURES[name], results[name]
    assert len(res.sheets) == len(f.sheets)
    for sheet in res.sheets:
        assert sum(sheet.totals.values()) == 1440
        assert sheet.segments[0].start_min == 0 and sheet.segments[-1].end_min == 1440


@pytest.mark.parametrize("name", NAMES)
def test_sheet_totals(name, results):
    for d, (sheet, want) in enumerate(zip(results[name].sheets, fx.TRIP_FIXTURES[name].sheets, strict=True)):
        off, sb, drive, on = (fx.mins(h) for h in want.totals)
        assert sheet.totals == {Status.OFF: off, Status.SB: sb, Status.D: drive, Status.ON: on}, f"day {d}"


@pytest.mark.parametrize("name", NAMES)
def test_sheet_segments(name, results):
    for d, (sheet, want) in enumerate(zip(results[name].sheets, fx.TRIP_FIXTURES[name].sheets, strict=True)):
        assert merged(sheet.segments) == fx.parse_segments(want.segments), f"day {d}"


@pytest.mark.parametrize("name", NAMES)
def test_sheet_miles_today(name, results):
    got = [round(s.miles_today, 1) for s in results[name].sheets]
    want = [s.miles for s in fx.TRIP_FIXTURES[name].sheets]
    assert got == want
    assert round(sum(got), 1) == results[name].summary.total_miles


@pytest.mark.parametrize("name", NAMES)
def test_sheet_recap(name, results):
    for d, (sheet, want) in enumerate(zip(results[name].sheets, fx.TRIP_FIXTURES[name].sheets, strict=True)):
        rc = sheet.recap
        got = (rc.on_duty_today, rc.a_last_7, rc.b_available_tomorrow, rc.c_last_8, rc.restart_note)
        exp = (
            fx.mins(want.today),
            fx.mins(want.a),
            fx.mins(want.b),
            fx.mins(want.c),
            want.note,
        )
        assert got == exp, f"day {d} recap (today, A, B, C, note)"


@pytest.mark.parametrize("name", NAMES)
def test_sheet_remarks_and_brackets_where_the_spec_lists_them(name, results):
    for d, (sheet, want) in enumerate(zip(results[name].sheets, fx.TRIP_FIXTURES[name].sheets, strict=True)):
        if want.remarks is not None:
            assert [r.minute for r in sheet.remarks] == fx.parse_times(want.remarks), f"day {d} remarks"
        if want.brackets is not None:
            assert list(sheet.brackets) == fx.parse_brackets(want.brackets), f"day {d} brackets"


# --------------------------------------------------------------------------------------------
# reasons and notes (PRD US4: why did the stop happen)
# --------------------------------------------------------------------------------------------


def _reasons(res):
    return {(e.start_min_abs, str(e.kind)): (e.note, e.reason) for e in res.events}


def test_8b_reasons(results):
    r = _reasons(results["8b"])
    assert r[(1230, "rest")] == ("10-hr rest (sleeper)", "10-hr rest: 11 hr driving limit reached")
    assert r[(2160, "fuel")] == ("Fuel", "Fuel: 1,000 mi limit")
    assert r[(720, "pickup")] == ("Pickup", "Pickup (1 hr on duty)")
    assert r[(2460, "dropoff")] == ("Dropoff", "Dropoff (1 hr on duty)")
    assert r[(2520, "off_after_end")] == ("Off duty", "Trip complete")
    assert r[(480, "pre_trip")][0] == "Pre-trip inspection"
    assert r[(510, "drive")] == ("Driving", "")


def test_8b_has_no_standalone_break_and_no_restart(results):
    kinds = [e.kind for e in results["8b"].events]
    assert Kind.BREAK not in kinds and Kind.RESTART not in kinds


def test_8c_reasons(results):
    r = _reasons(results["8c"])
    assert r[(960, "restart")] == ("34-hr restart", "34-hr restart: 70 hr cycle limit reached")
    assert r[(3510, "break")] == ("30-min break", "30-min break required after 8 hr driving")


def test_8c_restart_is_70_cap_not_a_rest(results):
    drive_before = next(e for e in results["8c"].events if e.end_min_abs == 960)
    assert drive_before.status == Status.D and drive_before.end_min_abs - drive_before.start_min_abs == 180


def test_8c_break_not_rest_with_5_5_hours_of_window_left(results):
    """Break due at 3510 in a shift that began at 3000: 330 min of window left, so no A17 rest."""
    kinds = [str(e.kind) for e in results["8c"].events]
    assert "break" in kinds
    i = kinds.index("break")
    assert kinds[i + 1] == "drive"


def test_8e_start_restart_spans_midnight_to_10am_and_supersedes_start(results):
    res = results["8e"]
    first = res.events[0]
    assert (first.start_min_abs, first.end_min_abs, first.kind, first.status) == (
        0,
        2040,
        Kind.RESTART,
        Status.OFF,
    )
    assert first.reason == "34-hr restart: 70 hr cycle at 69.5 hr or more at trip start"
    assert all(e.kind != Kind.OFF_BEFORE_START for e in res.events)
    assert res.events[1].start_min_abs == 2040
    assert res.sheets[0].remarks[0].minute == 0
    assert res.sheets[0].remarks[0].status_change is False
    assert res.sheets[0].remarks[0].note == "34-hr restart"
    assert res.warnings[0].code == "CYCLE_RESTART_AT_START"
    assert res.warnings[0].message


def test_8e_events_2_to_11_are_8b_shifted_by_1560(results):
    shifted = [(e.start_min_abs - 1560, e.end_min_abs - 1560, e.kind) for e in results["8e"].events[1:-1]]
    original = [(e.start_min_abs, e.end_min_abs, e.kind) for e in results["8b"].events[1:-1]]
    assert shifted == original


@pytest.mark.parametrize("start", [0, 480, 600, 1425])
@pytest.mark.parametrize("cycle", [4170, 4185, 4200])
def test_8e_variants_start_is_superseded(start, cycle):
    base = plan(TripInput(fx.LEGS_8B, 4200, 480))
    res = plan(TripInput(fx.LEGS_8B, cycle, start))
    assert res.events == base.events
    assert [w.code for w in res.warnings] == ["CYCLE_RESTART_AT_START"]


def test_8e_cycle_69_5_only_day_0_recap_differs():
    base = plan(TripInput(fx.LEGS_8B, 4200, 480))
    res = plan(TripInput(fx.LEGS_8B, 4170, 480))
    rc = res.sheets[0].recap
    assert (rc.on_duty_today, rc.a_last_7, rc.b_available_tomorrow, rc.c_last_8, rc.restart_note) == (
        0,
        fx.mins(69.5),
        4200,
        fx.mins(69.5),
        True,
    )
    assert res.sheets[1].recap == base.sheets[1].recap


def test_8e_cycle_69_25_does_not_restart_at_start():
    res = plan(TripInput(fx.LEGS_8B, 4155, 480))
    assert res.warnings == ()
    assert res.events[0].kind == Kind.OFF_BEFORE_START
    assert res.events[1].kind == Kind.PRE_TRIP and res.events[1].start_min_abs == 480


def test_8f_labels_zero_length_first_leg_uses_kind_rule(results):
    """S-8: pickup label by kind even at mile 0; the pre-trip at mile 0 gets the current label."""
    res = results["8f"]
    by_minute = {r.minute: r for r in res.sheets[0].remarks}
    assert by_minute[480].location_label == "Chicago, IL"
    assert by_minute[510].location_label == "Chicago, IL (shipper)"
    assert by_minute[510].status_change is False  # ON -> ON: note-only
    assert by_minute[510].note == "Pickup"
    assert by_minute[570].location_label == "Chicago, IL (shipper)"  # leg 1 at mile 0 -> pickup label
    assert by_minute[1050].location_label is None  # mid-route: service reverse-geocodes
    assert by_minute[1125].location_label == "Memphis, TN"
    assert by_minute[1185].location_label == "Memphis, TN"
    pre = next(e for e in res.events if e.kind == Kind.PRE_TRIP)
    assert (pre.leg_index, pre.leg_mile) == (0, 0.0)


def test_8f_break_reason_and_window(results):
    res = results["8f"]
    brk = next(e for e in res.events if e.kind == Kind.BREAK)
    assert (brk.start_min_abs, brk.end_min_abs, brk.status) == (1050, 1080, Status.OFF)
    assert brk.reason == "30-min break required after 8 hr driving"
    first_pre_trip = next(e for e in res.events if e.kind == Kind.PRE_TRIP)
    last_drive = [e for e in res.events if e.status == Status.D][-1]
    assert last_drive.end_min_abs - first_pre_trip.start_min_abs == 645  # window 08:00 to 18:45 = 10.75 h


def test_8g_restart_reason_and_saving(results):
    res = results["8g"]
    restart = next(e for e in res.events if e.kind == Kind.RESTART)
    assert (restart.start_min_abs, restart.end_min_abs) == (1230, 3270)
    assert restart.reason == "34-hr restart: cycle hours left do not cover the rest of the trip"
    assert res.summary.arrive_dropoff_min_abs == 3900
    old_rule_arrival = 4530
    assert old_rule_arrival - res.summary.arrive_dropoff_min_abs == 630  # 10.5 h earlier
    assert [e.kind for e in res.events].count(Kind.REST) == 0


def test_8g_remarks_day0_include_restart_note(results):
    day0 = results["8g"].sheets[0]
    assert day0.remarks[-1].minute == 20 * 60 + 30
    assert day0.remarks[-1].note == "34-hr restart"
    assert day0.remarks[-1].status_change is True


def test_8h_restart_ends_exactly_at_midnight_is_complete(results):
    res = results["8h"]
    restart = next(e for e in res.events if e.kind == Kind.RESTART)
    assert (restart.start_min_abs, restart.end_min_abs) == (840, 2880)
    day1 = res.sheets[1].recap
    assert day1.restart_note is False
    assert (day1.a_last_7, day1.c_last_8, day1.b_available_tomorrow) == (0, 0, 4200)
    day0 = res.sheets[0].recap
    assert day0.restart_note is True and day0.b_available_tomorrow == 4200 and day0.a_last_7 == 4200


def test_8h_real_change_at_midnight_gets_a_remark_at_minute_zero(results):
    day2 = results["8h"].sheets[2]
    assert [r.minute for r in day2.remarks][:2] == [0, 30]
    first = day2.remarks[0]
    assert first.status == Status.ON and first.status_change is True and first.note == "Pre-trip inspection"
    assert [r.minute for r in day2.remarks] == fx.parse_times("00:00 00:30 05:00 06:00 07:45 08:45")


def test_8h_day1_continuing_restart_has_no_remark(results):
    assert results["8h"].sheets[1].remarks == ()


def test_8b_remark_labels(results):
    d0 = {r.minute: r.location_label for r in results["8b"].sheets[0].remarks}
    assert d0 == {
        480: "Chicago, IL",
        510: "Chicago, IL",
        720: "Indianapolis, IN",
        780: "Indianapolis, IN",
        1230: None,
    }
    d1 = {r.minute: r.location_label for r in results["8b"].sheets[1].remarks}
    assert d1 == {390: None, 420: None, 720: None, 750: None, 1020: "Denver, CO", 1080: "Denver, CO"}


def test_8d_remark_labels(results):
    got = {r.minute: r.location_label for r in results["8d"].sheets[0].remarks}
    assert got == {
        480: "Chicago, IL",
        510: "Chicago, IL",
        570: "Joliet, IL",
        630: "Joliet, IL",
        765: "Milwaukee, WI",
        825: "Milwaukee, WI",
    }


def test_8d_no_fuel_break_rest(results):
    kinds = {e.kind for e in results["8d"].events}
    assert not kinds & {Kind.FUEL, Kind.BREAK, Kind.REST, Kind.RESTART}


# --------------------------------------------------------------------------------------------
# 8a: John Doe, day_splitter only (never plan())
# --------------------------------------------------------------------------------------------

_DOE_NOTE = {
    "off_before_start": "Off duty",
    "pre_trip": "Reported, loading, dispatch, pre-trip",
    "drive": "Driving",
    "fuel": "Fuel",
    "break": "Lunch",
    "dropoff": "Delivery",
    "rest": "Sleeper berth",
    "off_after_end": "Off duty",
}


def _doe_events() -> tuple[DutyEvent, ...]:
    events, prev_mile = [], 0.0
    for start, end, status, kind, mile in fx.JOHN_DOE_ROWS:
        events.append(
            DutyEvent(
                fx.hm(start),
                fx.hm(end),
                Status(status),
                Kind(kind),
                None,
                prev_mile,
                mile,
                0.0,
                "Richmond, VA",
                _DOE_NOTE[kind],
                "",
            )
        )
        prev_mile = mile
    return tuple(events)


def _split_doe(events):
    """Adapter: the day_splitter entry point is not pinned by the spec text (section 4.2 names `derive`)."""
    from hos import day_splitter

    if hasattr(day_splitter, "spans_from_events"):
        return day_splitter.split_days(events, day_splitter.spans_from_events(events), 0)
    return day_splitter.split_days(events, 0)


@pytest.fixture(scope="module")
def doe():
    return _split_doe(_doe_events())


def test_8a_one_sheet_24_hours(doe):
    assert len(doe) == 1
    sheet = doe[0]
    assert len(sheet.segments) == 13
    assert sheet.totals == {Status.OFF: 600, Status.SB: 105, Status.D: 465, Status.ON: 270}
    assert sum(sheet.totals.values()) == 1440


def test_8a_miles_and_on_duty(doe):
    sheet = doe[0]
    assert sheet.miles_today == 350.0
    assert sheet.recap.on_duty_today == 735  # 12.25 h


def test_8a_twelve_remarks_all_status_changes(doe):
    remarks = doe[0].remarks
    assert [r.minute for r in remarks] == fx.parse_times(fx.JOHN_DOE_REMARKS)
    assert len(remarks) == 12
    assert all(r.status_change for r in remarks)


def test_8a_six_brackets(doe):
    assert list(doe[0].brackets) == fx.parse_brackets(fx.JOHN_DOE_BRACKETS)


def test_8a_invariants_1_2_3_8_15(doe):
    events, sheet = _doe_events(), doe[0]
    assert events[0].start_min_abs == 0  # 1
    assert all(b.start_min_abs == a.end_min_abs for a, b in zip(events, events[1:], strict=False))
    assert all(e.start_min_abs % 15 == 0 and e.end_min_abs % 15 == 0 for e in events)
    assert events[-1].end_min_abs % 1440 == 0 and len(doe) == events[-1].end_min_abs // 1440  # 2
    assert [(s.start_min, s.end_min) for s in sheet.segments] == [
        (e.start_min_abs, e.end_min_abs) for e in events
    ]  # 3
    assert all(a.end_mile <= b.start_mile + 1e-9 for a, b in zip(events, events[1:], strict=False))  # 8
    changes = [e.start_min_abs for a, e in zip(events, events[1:], strict=False) if e.status != a.status]
    assert [r.minute for r in sheet.remarks] == changes  # 15
    for r in sheet.remarks:
        assert r.status == next(s.status for s in sheet.segments if s.start_min == r.minute)
