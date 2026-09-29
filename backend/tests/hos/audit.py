"""Independent HOS audit oracle (TEST_PLAN 3.3, HOS_ENGINE_SPEC section 7).

Re-derives the 11 / 14 / 8 / 70 / 34 / 10 rules, fuel spacing, sheet splitting, miles, remarks,
brackets and the recap from the raw event list and the input legs ONLY. It imports data classes
from ``hos.models`` and nothing else from the engine (no simulator, no rules constants, no helpers),
and it uses a different formulation (single forward scan, exact Fractions rebuilt from the legs).

Every check returns ``(invariant_id, event_index_or_None, message)`` tuples. An empty list means
the plan is clean.
"""

from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from math import ceil

from hos.models import DutyEvent, Kind, PlanResult, Status, TripInput

Violation = tuple[int, int | None, str]

# Rule constants, restated on purpose (the oracle must not import the engine's).
GRID = 15
DAY = 1440
REST = 600
RESTART = 2040
WINDOW = 840
DRIVE_LIMIT = 660
BREAK_AFTER = 480
BREAK = 30
CYCLE_LIMIT = 4200
CYCLE_CEILING = CYCLE_LIMIT + 90
FUEL_MAX = Fraction(1000)
PRE_TRIP = 30
STOP = 60
START_RESTART_CYCLE = 4170  # 4200 - cycle < 45, cycle on the 15 min grid
MILE_TOL = 0.002  # output miles are rounded to 3 dp

NOTES = {
    Kind.OFF_BEFORE_START: "Off duty",
    Kind.PRE_TRIP: "Pre-trip inspection",
    Kind.DRIVE: "Driving",
    Kind.PICKUP: "Pickup",
    Kind.DROPOFF: "Dropoff",
    Kind.FUEL: "Fuel",
    Kind.BREAK: "30-min break",
    Kind.REST: "10-hr rest (sleeper)",
    Kind.RESTART: "34-hr restart",
    Kind.OFF_AFTER_END: "Off duty",
}
BRACKET_EXCLUDED = {Kind.OFF_BEFORE_START, Kind.OFF_AFTER_END}


def ceil15(x: float) -> int:
    return GRID * ceil(Fraction(str(x)) / GRID)


def round_half_up_1dp(x: Fraction) -> Decimal:
    return (Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class Trip:
    """Exact geometry of the input: leg durations on the grid and Fraction distances."""

    def __init__(self, inp: TripInput):
        self.inp = inp
        self.durs = [ceil15(leg.duration_min) for leg in inp.legs]
        self.dists = [Fraction(str(leg.distance_mi)) for leg in inp.legs]
        self.total_drive = sum(self.durs)
        self.total_miles = sum(self.dists, Fraction(0))

    def mile_after_driving(self, driven_min: int) -> Fraction:
        """Exact cumulative mile after `driven_min` minutes of driving (linear inside each leg)."""
        mile = Fraction(0)
        left = driven_min
        for dur, dist in zip(self.durs, self.dists, strict=True):
            if dur == 0:
                mile += dist
                continue
            used = min(left, dur)
            mile += dist * used / dur
            left -= used
        return mile


def driven_before(events: tuple[DutyEvent, ...] | list[DutyEvent], minute: int) -> int:
    """Driving minutes accumulated strictly before absolute `minute` (clips a crossing D event)."""
    total = 0
    for ev in events:
        if ev.status == Status.D and ev.start_min_abs < minute:
            total += min(ev.end_min_abs, minute) - ev.start_min_abs
    return total


def mile_at(trip: Trip, events, minute: int) -> Fraction:
    return trip.mile_after_driving(driven_before(events, minute))


# ---------------------------------------------------------------------------------------------
# Event-level invariants
# ---------------------------------------------------------------------------------------------


def _structure(events, inp) -> list[Violation]:
    """Invariants 1, 2, 13."""
    out: list[Violation] = []
    if not events:
        return [(1, None, "no events")]
    if events[0].start_min_abs != 0:
        out.append((1, 0, f"first event starts at {events[0].start_min_abs}, not 0"))
    for i, ev in enumerate(events):
        if ev.end_min_abs <= ev.start_min_abs:
            out.append((1, i, f"non-positive length {ev.start_min_abs}..{ev.end_min_abs}"))
        if ev.start_min_abs % GRID or ev.end_min_abs % GRID:
            out.append((1, i, f"off the 15 min grid {ev.start_min_abs}..{ev.end_min_abs}"))
        if i and ev.start_min_abs != events[i - 1].end_min_abs:
            out.append(
                (1, i, f"gap or overlap: prev ends {events[i - 1].end_min_abs}, starts {ev.start_min_abs}")
            )
        if i and ev.status == Status.D and events[i - 1].status == Status.D:
            out.append((13, i, "two adjacent D events"))
    if events[-1].end_min_abs % DAY:
        out.append((2, len(events) - 1, f"plan ends at {events[-1].end_min_abs}, not on a midnight"))

    starts_with_restart = inp.cycle_used_min >= START_RESTART_CYCLE
    first = events[0]
    if starts_with_restart:
        if not (first.kind == Kind.RESTART and first.start_min_abs == 0 and first.end_min_abs == RESTART):
            out.append((13, 0, "cycle >= 69.5 h: first event must be a restart [0, 2040)"))
        if any(e.kind == Kind.OFF_BEFORE_START for e in events):
            out.append((13, None, "off_before_start emitted together with a start restart"))
    else:
        for i, ev in enumerate(events):
            if ev.end_min_abs <= inp.start_min and ev.kind != Kind.OFF_BEFORE_START:
                out.append((13, i, "event before start_min is not off_before_start"))
        pre = [e for e in events if e.kind == Kind.PRE_TRIP]
        if not pre or pre[0].start_min_abs != inp.start_min:
            out.append((13, None, f"first pre-trip does not start at start_min {inp.start_min}"))
        obs = [e for e in events if e.kind == Kind.OFF_BEFORE_START]
        if inp.start_min == 0 and obs:
            out.append((13, None, "off_before_start emitted for start 00:00"))
        if inp.start_min > 0 and (
            len(obs) != 1 or (obs[0].start_min_abs, obs[0].end_min_abs) != (0, inp.start_min)
        ):
            out.append((13, None, "off_before_start must be exactly one event [0, start_min)"))
    return out


def _clocks(events, inp, trip: Trip) -> list[Violation]:
    """Invariants 4, 5, 9, 11, 12, 14, 19 by one forward scan over the raw events."""
    out: list[Violation] = []
    cycle = inp.cycle_used_min
    off_run = 0
    nd_run = 0
    shift_start: int | None = None
    drive_shift = 0
    since_break = 0
    pretrips_in_shift = 0
    driven = 0
    fuel_base = Fraction(0)  # trip mile at the last fuel event (truck starts full at mile 0)
    stops_done = 0
    dropoff_started = False
    last_d_cycle_end: int | None = None

    for i, ev in enumerate(events):
        length = ev.end_min_abs - ev.start_min_abs
        if length <= 0:
            continue
        mile_start = trip.mile_after_driving(driven)

        if dropoff_started and ev.kind in (Kind.FUEL, Kind.BREAK, Kind.REST, Kind.RESTART):
            out.append((14, i, f"{ev.kind} after the dropoff started"))

        if ev.status in (Status.D, Status.ON):
            new_shift = shift_start is None or off_run >= REST
            if new_shift:
                shift_start = ev.start_min_abs
                drive_shift = 0
                since_break = 0
                pretrips_in_shift = 0
                if not (ev.kind == Kind.PRE_TRIP and ev.status == Status.ON and length == PRE_TRIP):
                    out.append((11, i, f"shift starts with {ev.kind} ({length} min), not a 30 min pre_trip"))
        if ev.kind == Kind.PRE_TRIP:
            pretrips_in_shift += 1
            if pretrips_in_shift > 1:
                out.append((11, i, "second pre_trip inside one shift"))

        if ev.kind == Kind.REST and (ev.status != Status.SB or length != REST):
            out.append((12, i, f"rest must be SB 600, got {ev.status} {length}"))
        if ev.kind == Kind.RESTART and (ev.status != Status.OFF or off_run + length < RESTART):
            out.append((12, i, f"restart must be OFF and end a >= 2040 min run, run={off_run + length}"))
        if ev.kind == Kind.BREAK and (
            ev.status != Status.OFF or length != BREAK or since_break != BREAK_AFTER
        ):
            out.append(
                (
                    12,
                    i,
                    f"break must be OFF 30 at exactly 480 driven, got {ev.status} {length} at {since_break}",
                )
            )

        if ev.kind in (Kind.REST, Kind.RESTART):
            out.extend(
                _a10_check(ev, i, cycle, trip, driven, stops_done, mile_start - fuel_base, last_d_cycle_end)
            )

        # apply the event
        if ev.status == Status.D:
            driven += length
            drive_shift += length
            since_break += length
            nd_run = 0
            off_run = 0
            cycle += length
            last_d_cycle_end = cycle
            mile_end = trip.mile_after_driving(driven)
            if drive_shift > DRIVE_LIMIT:
                out.append((4, i, f"11 h exceeded: {drive_shift} min driven in shift"))
            if ev.end_min_abs - (shift_start or 0) > WINDOW:
                out.append(
                    (4, i, f"14 h window exceeded: D ends {ev.end_min_abs - (shift_start or 0)} min in")
                )
            if since_break > BREAK_AFTER:
                out.append((4, i, f"8 h exceeded: {since_break} min driven without a 30 min break"))
            if cycle > CYCLE_LIMIT:
                out.append((4, i, f"70 h exceeded while driving: cycle {cycle}"))
            if mile_end - fuel_base > FUEL_MAX:
                out.append((9, i, f"{float(mile_end - fuel_base):.3f} mi since fuel"))
        else:
            nd_run += length
            if nd_run >= BREAK:
                since_break = 0
            if ev.status == Status.ON:
                off_run = 0
                cycle += length
            else:
                off_run += length
                if off_run >= REST:
                    shift_start = None
                    drive_shift = 0
                    since_break = 0
                if off_run >= RESTART:
                    cycle = 0
        if ev.kind == Kind.FUEL:
            fuel_base = trip.mile_after_driving(driven)
        if ev.kind in (Kind.PICKUP, Kind.DROPOFF):
            stops_done += 1
        if ev.kind == Kind.DROPOFF:
            dropoff_started = True
        if cycle > CYCLE_CEILING:
            out.append((5, i, f"cycle {cycle} above 4290"))
        if cycle > CYCLE_LIMIT and ev.status == Status.D:
            out.append((5, i, f"cycle above 4200 through a {ev.status} event"))
    return out


def remaining_work(trip: Trip, driven: int, stops_done: int, miles_since_fuel: Fraction) -> int:
    """HOS_ENGINE_SPEC 4.7, re-derived from the events seen so far."""
    remaining_drive = trip.total_drive - driven
    remaining_miles = trip.total_miles - trip.mile_after_driving(driven)
    fuel_est = max(0, ceil((miles_since_fuel + remaining_miles) / 1000) - 1)
    return remaining_drive + STOP * (2 - stops_done) + BREAK * fuel_est + PRE_TRIP


def _a10_check(ev, i, cycle, trip, driven, stops_done, miles_since_fuel, last_d_cycle_end) -> list[Violation]:
    cycle_left = CYCLE_LIMIT - cycle
    work = remaining_work(trip, driven, stops_done, miles_since_fuel)
    if ev.kind == Kind.REST:
        if not (cycle_left >= WINDOW or cycle_left >= work):
            return [(19, i, f"rest taken with cycle_left={cycle_left} < 840 and < remaining_work={work}")]
        return []
    trip_start_restart = i == 0
    if trip_start_restart or last_d_cycle_end == CYCLE_LIMIT:
        return []
    if not (cycle_left < WINDOW and cycle_left < work):
        return [(19, i, f"restart taken with cycle_left={cycle_left}, remaining_work={work}")]
    return []


def _trip_shape(events, inp, trip: Trip) -> list[Violation]:
    """Invariants 6, 7 (event part), 8, 10, 14 (structure)."""
    out: list[Violation] = []
    total_d = sum(e.end_min_abs - e.start_min_abs for e in events if e.status == Status.D)
    if total_d != trip.total_drive:
        out.append((6, None, f"total D {total_d} != sum ceil15 leg durations {trip.total_drive}"))

    prev_end = 0.0
    driven = 0
    for i, ev in enumerate(events):
        if ev.start_mile < prev_end - 1e-9:
            out.append((8, i, f"mile went backwards: {prev_end} -> {ev.start_mile}"))
        if abs(ev.start_mile - prev_end) > 1e-9 and i:
            out.append((8, i, f"start_mile {ev.start_mile} != previous end_mile {prev_end}"))
        if ev.status != Status.D and ev.start_mile != ev.end_mile:
            out.append((8, i, "stationary event moves"))
        if ev.end_mile < ev.start_mile:
            out.append((8, i, "end_mile < start_mile"))
        if ev.status == Status.D:
            driven += ev.end_min_abs - ev.start_min_abs
        exact_end = float(trip.mile_after_driving(driven))
        if abs(ev.end_mile - exact_end) > MILE_TOL:
            out.append((7, i, f"end_mile {ev.end_mile} != exact {exact_end:.4f}"))
        prev_end = ev.end_mile
    if events and abs(events[-1].end_mile - float(trip.total_miles)) > MILE_TOL:
        out.append(
            (7, None, f"final mile {events[-1].end_mile} != sum of distances {float(trip.total_miles)}")
        )

    pickups = [i for i, e in enumerate(events) if e.kind == Kind.PICKUP]
    dropoffs = [i for i, e in enumerate(events) if e.kind == Kind.DROPOFF]
    if len(pickups) != 1 or len(dropoffs) != 1:
        out.append(
            (10, None, f"need exactly one pickup and one dropoff, got {len(pickups)} and {len(dropoffs)}")
        )
        return out
    p, d = events[pickups[0]], events[dropoffs[0]]
    for name, ev in (("pickup", p), ("dropoff", d)):
        if ev.status != Status.ON or ev.end_min_abs - ev.start_min_abs != STOP:
            out.append((10, None, f"{name} must be ON 60 min"))
    if pickups[0] > dropoffs[0]:
        out.append((10, None, "pickup after dropoff"))
    if abs(p.start_mile - float(trip.dists[0])) > MILE_TOL:
        out.append((10, pickups[0], f"pickup at mile {p.start_mile}, expected {float(trip.dists[0])}"))
    if abs(d.start_mile - float(trip.total_miles)) > MILE_TOL:
        out.append((10, dropoffs[0], f"dropoff at mile {d.start_mile}, expected {float(trip.total_miles)}"))
    for i, ev in enumerate(events):
        if ev.kind == Kind.OFF_AFTER_END and (i < dropoffs[0] or i != len(events) - 1):
            out.append((10, i, "off_after_end before the dropoff or not last"))
    tail = events[dropoffs[0] + 1 :]
    if tail and not (len(tail) == 1 and tail[0].kind == Kind.OFF_AFTER_END):
        out.append((14, dropoffs[0], "anything but off_after_end after the dropoff"))
    if (events[dropoffs[0]].end_min_abs % DAY != 0) != bool(tail):
        out.append((10, dropoffs[0], "off_after_end present iff the dropoff does not end on a midnight"))
    return out


def audit_events(events, inp: TripInput) -> list[Violation]:
    """All event-level invariants (1, 2, 4, 5, 6, 7 events, 8, 9, 10, 11, 12, 13, 14, 19)."""
    events = tuple(events)
    trip = Trip(inp)
    out = _structure(events, inp)
    if out and any(v[0] == 1 for v in out):
        return out  # the scans below assume a sane timeline
    out += _clocks(events, inp, trip)
    out += _trip_shape(events, inp, trip)
    return out


# ---------------------------------------------------------------------------------------------
# Sheets, remarks, brackets, recap
# ---------------------------------------------------------------------------------------------


def _cycle_at(events, inp, minute: int) -> int:
    """Cycle counter at `minute` (section 6, S-13).

    Every event ending at or before `minute` is applied with its reset. The on-duty part of an ON or D
    event still in progress at `minute` is added clipped to `minute`. A restart in progress adds nothing.
    """
    cycle = inp.cycle_used_min
    off_run = 0
    for ev in events:
        length = ev.end_min_abs - ev.start_min_abs
        if ev.end_min_abs > minute:
            if ev.start_min_abs < minute and ev.status in (Status.D, Status.ON):
                cycle += minute - ev.start_min_abs
            break
        if ev.status in (Status.D, Status.ON):
            cycle += length
            off_run = 0
        else:
            off_run += length
            if off_run >= RESTART:
                cycle = 0
    return cycle


def _expected_remarks(events, trip: Trip, inp):
    """(abs_minute, status, status_change, note, kind) per section 5.3."""
    out = []
    for i, ev in enumerate(events):
        if i == 0:
            if ev.kind == Kind.RESTART:
                out.append((ev.start_min_abs, ev.status, False, NOTES[ev.kind], ev.kind))
            elif (
                ev.kind == Kind.PRE_TRIP
            ):  # S-14: a trip that starts at 00:00 opens with a real status change
                out.append((ev.start_min_abs, ev.status, True, NOTES[ev.kind], ev.kind))
            continue
        prev = events[i - 1]
        if ev.status != prev.status:
            out.append((ev.start_min_abs, ev.status, True, NOTES[ev.kind], ev.kind))
        elif ev.kind != prev.kind:
            out.append((ev.start_min_abs, ev.status, False, NOTES[ev.kind], ev.kind))
    return out


def _expected_brackets(events, day: int):
    runs: list[list[int]] = []
    for ev in events:
        if ev.status == Status.D or ev.kind in BRACKET_EXCLUDED:
            continue
        if runs and runs[-1][1] == ev.start_min_abs:
            runs[-1][1] = ev.end_min_abs
        else:
            runs.append([ev.start_min_abs, ev.end_min_abs])
    lo, hi = day * DAY, (day + 1) * DAY
    return [(max(a, lo) - lo, min(b, hi) - lo) for a, b in runs if a < hi and b > lo]


def audit_sheets(result: PlanResult, inp: TripInput) -> list[Violation]:
    """Invariants 2 (sheet count), 3, 7 (daily miles), 15, 16, 20 against an independent re-split."""
    out: list[Violation] = []
    events = result.events
    trip = Trip(inp)
    end = events[-1].end_min_abs
    n_days = end // DAY
    if len(result.sheets) != n_days:
        return [(2, None, f"{len(result.sheets)} sheets for {n_days} days")]

    expected_remarks = _expected_remarks(events, trip, inp)
    total_rounded = round_half_up_1dp(trip.total_miles)
    miles_sum = Decimal(0)

    for d, sheet in enumerate(result.sheets):
        lo, hi = d * DAY, (d + 1) * DAY
        if sheet.day_index != d:
            out.append((3, None, f"sheet {d} has day_index {sheet.day_index}"))

        # 3: independent re-split
        want = []
        for ev in events:
            if ev.start_min_abs < hi and ev.end_min_abs > lo:
                a, b = max(ev.start_min_abs, lo), min(ev.end_min_abs, hi)
                want.append((a - lo, b - lo, ev.status, ev.kind, a, b))
        got = [(s.start_min, s.end_min, s.status, s.kind) for s in sheet.segments]
        if got != [w[:4] for w in want]:
            out.append((3, None, f"sheet {d}: segments differ from an independent split of the events"))
            continue
        pos = 0
        for s in sheet.segments:
            if s.start_min != pos:
                out.append((3, None, f"sheet {d}: segments not contiguous at {pos}"))
            pos = s.end_min
        if pos != DAY:
            out.append((3, None, f"sheet {d}: segments end at {pos}, not 1440"))
        totals = dict.fromkeys(Status, 0)
        for s in sheet.segments:
            totals[s.status] += s.end_min - s.start_min
        if dict(sheet.totals) != totals or sum(sheet.totals.values()) != DAY:
            out.append((3, None, f"sheet {d}: totals {dict(sheet.totals)} vs segments {totals}"))
        for seg, w in zip(sheet.segments, want, strict=True):
            if abs(seg.start_mile - float(mile_at(trip, events, w[4]))) > MILE_TOL:
                out.append((7, None, f"sheet {d}: segment start_mile {seg.start_mile} wrong at {w[4]}"))
            if abs(seg.end_mile - float(mile_at(trip, events, w[5]))) > MILE_TOL:
                out.append((7, None, f"sheet {d}: segment end_mile {seg.end_mile} wrong at {w[5]}"))

        # 7: miles per day (section 5.4)
        m_from = round_half_up_1dp(mile_at(trip, events, lo))
        m_to = round_half_up_1dp(mile_at(trip, events, hi))
        today = m_to - m_from
        miles_sum += today
        if abs(sheet.miles_today - float(today)) > 1e-6:
            out.append((7, None, f"sheet {d}: miles_today {sheet.miles_today}, expected {today}"))
        if abs(sheet.from_mile - float(mile_at(trip, events, lo))) > 0.06:
            out.append((7, None, f"sheet {d}: from_mile {sheet.from_mile} wrong"))
        if abs(sheet.to_mile - float(mile_at(trip, events, hi))) > 0.06:
            out.append((7, None, f"sheet {d}: to_mile {sheet.to_mile} wrong"))

        # 15 / 20: remarks
        want_r = [r for r in expected_remarks if lo <= r[0] < hi]
        got_r = [(r.minute + lo, r.status, r.status_change, r.note) for r in sheet.remarks]
        if got_r != [r[:4] for r in want_r]:
            out.append((15, None, f"sheet {d}: remarks {got_r} != expected {[r[:4] for r in want_r]}"))
        else:
            for r, (_, _, _, _, kind) in zip(sheet.remarks, want_r, strict=True):
                label = {
                    Kind.PICKUP: inp.legs[0].to_label,
                    Kind.DROPOFF: inp.legs[1].to_label,
                    Kind.OFF_AFTER_END: inp.legs[1].to_label,
                }.get(kind)
                if label is not None and r.location_label != label:
                    out.append(
                        (20, None, f"sheet {d}: {kind} remark label {r.location_label!r}, expected {label!r}")
                    )
                if abs(r.mile - float(mile_at(trip, events, r.minute + lo))) > MILE_TOL:
                    out.append((7, None, f"sheet {d}: remark at {r.minute} has mile {r.mile}"))

        # brackets (5.5)
        if list(sheet.brackets) != _expected_brackets(events, d):
            out.append(
                (15, None, f"sheet {d}: brackets {list(sheet.brackets)} != {_expected_brackets(events, d)}")
            )

        # 16: recap (section 6)
        a = _cycle_at(events, inp, hi)
        note = any(e.kind == Kind.RESTART and e.start_min_abs < hi < e.end_min_abs for e in events)
        on_duty = totals[Status.D] + totals[Status.ON]
        rc = sheet.recap
        want_b = CYCLE_LIMIT if note else max(0, CYCLE_LIMIT - a)
        if (rc.on_duty_today, rc.a_last_7, rc.c_last_8, rc.b_available_tomorrow, rc.restart_note) != (
            on_duty,
            a,
            a,
            want_b,
            note,
        ):
            out.append(
                (
                    16,
                    None,
                    f"sheet {d}: recap {rc} != today={on_duty} a=c={a} b={want_b} note={note}",
                )
            )

    out += audit_recap_bound(result, inp)
    if abs(float(miles_sum) - float(total_rounded)) > 1e-6:
        out.append((7, None, f"sum of miles_today {miles_sum} != rounded total {total_rounded}"))
    return out


def audit_recap_bound(result: PlanResult, inp: TripInput) -> list[Violation]:
    """Invariant 16 tail: `on_duty_today <= a` (holds since the S-13 ruling)."""
    return [
        (16, None, f"sheet {d}: on-duty today {s.recap.on_duty_today} above a={s.recap.a_last_7}")
        for d, s in enumerate(result.sheets)
        if s.recap.on_duty_today > s.recap.a_last_7
    ]


def audit_warnings(result: PlanResult, inp: TripInput) -> list[Violation]:
    codes = [w.code for w in result.warnings]
    want = ["CYCLE_RESTART_AT_START"] if inp.cycle_used_min >= START_RESTART_CYCLE else []
    return [] if codes == want else [(13, None, f"warnings {codes} != {want}")]


def audit(result: PlanResult | tuple[DutyEvent, ...] | list[DutyEvent], inp: TripInput) -> list[Violation]:
    """Full audit of a PlanResult, or event-level audit when given a bare event sequence."""
    if not isinstance(result, PlanResult):
        return audit_events(result, inp)
    out = audit_events(result.events, inp)
    if any(v[0] in (1, 2) for v in out):
        return out
    return out + audit_warnings(result, inp) + audit_sheets(result, inp)


def audit_summary(result: PlanResult, inp: TripInput) -> list[Violation]:
    """Summary block (kept separate from `audit`: its field meanings are less pinned than the rules)."""
    events, s = result.events, result.summary
    trip = Trip(inp)
    out: list[Violation] = []
    drop = next(e for e in events if e.kind == Kind.DROPOFF)
    checks = {
        "total_miles": (s.total_miles, float(round_half_up_1dp(trip.total_miles))),
        "total_drive_min": (s.total_drive_min, trip.total_drive),
        "total_on_duty_min": (
            s.total_on_duty_min,
            sum(e.end_min_abs - e.start_min_abs for e in events if e.status in (Status.D, Status.ON)),
        ),
        "arrive_dropoff_min_abs": (s.arrive_dropoff_min_abs, drop.start_min_abs),
        "complete_min_abs": (s.complete_min_abs, drop.end_min_abs),
        "sheet_count": (s.sheet_count, events[-1].end_min_abs // DAY),
        "fuel_stops": (s.fuel_stops, sum(e.kind == Kind.FUEL for e in events)),
        "breaks": (s.breaks, sum(e.kind == Kind.BREAK for e in events)),
        "rests": (s.rests, sum(e.kind == Kind.REST for e in events)),
        "restarts": (s.restarts, sum(e.kind == Kind.RESTART for e in events)),
        "cycle_end_min": (s.cycle_end_min, _cycle_at(events, inp, drop.end_min_abs)),
    }
    for name, (got, want) in checks.items():
        if got != want:
            out.append((0, None, f"summary.{name} = {got}, expected {want}"))
    return out


def fmt(violations: list[Violation], events=None) -> str:
    """Readable failure text, naming each invariant and the offending event."""
    lines = []
    for inv, idx, msg in violations[:10]:
        where = ""
        if events is not None and idx is not None and 0 <= idx < len(events):
            e = events[idx]
            where = f" @event {idx} [{e.start_min_abs}-{e.end_min_abs} {e.status} {e.kind}]"
        lines.append(f"invariant {inv}{where}: {msg}")
    return "\n".join(lines)


def assert_clean(result: PlanResult, inp: TripInput) -> None:
    violations = audit(result, inp)
    assert not violations, f"{len(violations)} violation(s) for {inp}\n{fmt(violations, result.events)}"


__all__ = [
    "audit",
    "audit_events",
    "audit_recap_bound",
    "audit_sheets",
    "audit_summary",
    "audit_warnings",
    "assert_clean",
    "ceil15",
    "fmt",
    "mile_at",
    "Trip",
]
