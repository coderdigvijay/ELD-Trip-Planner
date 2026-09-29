"""The simulation (HOS_ENGINE_SPEC section 4): drive until the next limit, resolve, repeat."""

from dataclasses import dataclass, field
from fractions import Fraction
from math import ceil, floor, isfinite

from .exact import MileSpan, as_float, ceil15, floor15, to_fraction
from .models import (
    DutyEvent,
    EngineWarning,
    HosEngineError,
    HosInputError,
    Kind,
    Leg,
    Status,
    TripInput,
)
from .rules import (
    BREAK_AFTER_MIN,
    BREAK_MIN,
    CYCLE_LIMIT_MIN,
    CYCLE_RESTART_AT_START,
    DAY_MIN,
    DRIVE_LIMIT_MIN,
    FUEL_MAX_MILES,
    FUEL_STOP_MIN,
    GRID,
    MAX_LABEL_LEN,
    MAX_LEG_DURATION_MIN,
    MAX_SPEED_MPH,
    MAX_STEPS_PER_LEG,
    MIN_SPEED_MPH,
    PRE_TRIP_MIN,
    REST_MIN,
    RESTART_MIN,
    START_MIN_MAX,
    START_RESTART_THRESHOLD_MIN,
    STOP_MIN,
    WINDOW_MIN,
)

Legs = tuple[Leg, Leg]

REASON_11H = "10-hr rest: 11 hr driving limit reached"
REASON_14H = "10-hr rest: 14 hr window reached"
REASON_A17 = "10-hr rest: not enough of the 14-hr window left for the required break"
REASON_70H = "34-hr restart: 70 hr cycle limit reached"
REASON_A10 = "34-hr restart: cycle hours left do not cover the rest of the trip"
REASON_START = "34-hr restart: 70 hr cycle at 69.5 hr or more at trip start"
START_WARNING = EngineWarning(
    CYCLE_RESTART_AT_START,
    "Cycle at 69.5 hr or more: the trip starts with a 34-hr restart from 00:00, "
    "so the requested start time is not used.",
)


@dataclass
class SimState:
    """Mutable counters of section 3 plus the position. Tests may build it via `for_test`."""

    t: int
    drive_in_shift: int
    shift_start: int | None
    drive_since_break: int
    cycle_on_duty: int
    miles_since_fuel: Fraction
    nondriving_run: int
    off_run: int
    trip_mile: Fraction
    leg_index: int | None
    leg_done: int
    leg_start_mile: Fraction
    events: list[DutyEvent]
    spans: list[MileSpan] = field(default_factory=list)

    @classmethod
    def for_test(cls, **fields: object) -> "SimState":
        """Fresh-shift defaults for every field not given. No consistency checking."""
        fresh: dict[str, object] = {
            "t": 0,
            "drive_in_shift": 0,
            "shift_start": None,
            "drive_since_break": 0,
            "cycle_on_duty": 0,
            "miles_since_fuel": Fraction(0),
            "nondriving_run": 0,
            "off_run": 0,
            "trip_mile": Fraction(0),
            "leg_index": 0,
            "leg_done": 0,
            "leg_start_mile": Fraction(0),
            "events": [],
            "spans": [],
        }
        return cls(**{**fresh, **fields})  # type: ignore[arg-type]


@dataclass(frozen=True)
class SimResult:
    events: tuple[DutyEvent, ...]
    spans: tuple[MileSpan, ...]
    warnings: tuple[EngineWarning, ...]


# ---------------------------------------------------------------- validation


def _check_grid(name: str, value: object, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high or value % GRID:
        raise HosInputError(f"{name} must be a multiple of {GRID} in [{low}, {high}], got {value!r}")


def _check_number(name: str, value: object) -> Fraction:
    """Exact non-negative finite value of an int, float or Fraction (never bool, str or None)."""
    if type(value) not in (int, float, Fraction):
        raise HosInputError(f"{name} must be an int, float or Fraction, got {type(value).__name__}")
    if type(value) is float and not isfinite(value):
        raise HosInputError(f"{name} must be finite")
    exact = to_fraction(value)
    if exact < 0:
        raise HosInputError(f"{name} must be >= 0")
    return exact


def _check_label(name: str, value: object) -> None:
    if type(value) is not str or len(value) > MAX_LABEL_LEN:
        raise HosInputError(f"{name} must be a str of at most {MAX_LABEL_LEN} characters")


def _check_leg(name: str, leg: object) -> None:
    if not isinstance(leg, Leg):
        raise HosInputError(f"{name} must be a Leg")
    distance = _check_number(f"{name} distance_mi", leg.distance_mi)
    duration = _check_number(f"{name} duration_min", leg.duration_min)
    _check_label(f"{name} from_label", leg.from_label)
    _check_label(f"{name} to_label", leg.to_label)
    if (distance == 0) != (duration == 0):
        raise HosInputError(f"{name}: distance is 0 iff duration is 0")
    if duration > MAX_LEG_DURATION_MIN:
        raise HosInputError(f"{name}: duration above {MAX_LEG_DURATION_MIN} min")
    if distance > 0:
        _check_speed(name, distance, duration)


def _check_speed(name: str, distance: Fraction, duration: Fraction) -> None:
    """Max speed uses the rounded-up duration (rounding only lowers it); min speed uses the raw one."""
    if distance * 60 / ceil15(duration) > MAX_SPEED_MPH:
        raise HosInputError(f"{name}: speed above {MAX_SPEED_MPH} mph")
    if distance * 60 / duration < MIN_SPEED_MPH:
        raise HosInputError(f"{name}: speed below {MIN_SPEED_MPH} mph")


def validate(inp: TripInput) -> None:
    _check_grid("cycle_used_min", inp.cycle_used_min, 0, CYCLE_LIMIT_MIN)
    _check_grid("start_min", inp.start_min, 0, START_MIN_MAX)
    if type(inp.legs) not in (tuple, list) or len(inp.legs) != 2:
        raise HosInputError("legs must be a tuple of exactly two Leg")
    _check_leg("leg 0", inp.legs[0])
    _check_leg("leg 1", inp.legs[1])
    if inp.legs[1].distance_mi <= 0:
        raise HosInputError("leg 1 (pickup to dropoff) must have distance > 0")


# ---------------------------------------------------------------- labels


def _label_on_leg(legs: Legs, leg_index: int, leg_mile: Fraction) -> str | None:
    start_label = legs[0].from_label if leg_index == 0 else legs[0].to_label
    end_label = legs[leg_index].to_label
    if leg_mile == 0:
        return start_label
    if leg_mile == to_fraction(legs[leg_index].distance_mi):
        return end_label
    return None


def label_for(legs: Legs, kind: Kind, leg_index: int | None, leg_mile: Fraction) -> str | None:
    """Known place name by the rule of section 5.3 (kind first, then position), else None."""
    if kind == Kind.PICKUP:
        return legs[0].to_label
    if kind in (Kind.DROPOFF, Kind.OFF_AFTER_END):
        return legs[1].to_label
    if leg_index is None:
        return legs[0].from_label
    return _label_on_leg(legs, leg_index, leg_mile)


# ---------------------------------------------------------------- emit


def _leg_dist_dur(state: SimState, legs: Legs) -> tuple[Fraction, int]:
    if state.leg_index is None:
        raise HosEngineError("driving before any leg started")
    leg = legs[state.leg_index]
    return to_fraction(leg.distance_mi), ceil15(leg.duration_min)


def _apply_driving(state: SimState, minutes: int, miles: Fraction) -> None:
    state.drive_in_shift += minutes
    state.drive_since_break += minutes
    state.miles_since_fuel += miles
    state.trip_mile += miles
    state.leg_done += minutes
    state.nondriving_run = 0
    state.off_run = 0


def _apply_nondriving(state: SimState, minutes: int) -> None:
    state.nondriving_run += minutes
    if state.nondriving_run >= BREAK_MIN:
        state.drive_since_break = 0


def _apply_on_duty(state: SimState, minutes: int) -> None:
    if state.shift_start is None:
        state.shift_start = state.t
    state.cycle_on_duty += minutes
    state.off_run = 0


def _apply_off(state: SimState, minutes: int) -> None:
    state.off_run += minutes
    if state.off_run >= REST_MIN:
        state.drive_in_shift = 0
        state.shift_start = None
        state.drive_since_break = 0
    if state.off_run >= RESTART_MIN:
        state.cycle_on_duty = 0


def _record(state: SimState, legs: Legs, event_args: tuple, miles: Fraction) -> None:
    status, kind, minutes, note, reason = event_args
    leg_mile_start = state.trip_mile - state.leg_start_mile
    start_mile, end_mile = state.trip_mile, state.trip_mile + miles
    leg_mile_end = leg_mile_start + miles
    state.events.append(
        DutyEvent(
            start_min_abs=state.t,
            end_min_abs=state.t + minutes,
            status=status,
            kind=kind,
            leg_index=state.leg_index,
            start_mile=as_float(start_mile, 3),
            end_mile=as_float(end_mile, 3),
            leg_mile=as_float(leg_mile_end, 3),
            location_label=label_for(legs, kind, state.leg_index, leg_mile_start),
            note=note,
            reason=reason,
        )
    )
    state.spans.append(MileSpan(start_mile, end_mile, leg_mile_end))


def emit(
    state: SimState, legs: Legs, status: Status, kind: Kind, minutes: int, note: str, reason: str
) -> None:
    """Append one event and apply it to the counters (section 4.1)."""
    if minutes <= 0 or minutes % GRID:
        raise HosEngineError(f"event length {minutes} is not a positive multiple of {GRID}")
    miles = Fraction(0)
    if status == Status.D:
        dist, dur = _leg_dist_dur(state, legs)
        miles = dist * minutes / dur
    _record(state, legs, (status, kind, minutes, note, reason), miles)
    if status == Status.D:
        _apply_driving(state, minutes, miles)
    else:
        _apply_nondriving(state, minutes)
    if status in (Status.D, Status.ON):
        _apply_on_duty(state, minutes)
    else:
        _apply_off(state, minutes)
    if kind == Kind.FUEL:
        state.miles_since_fuel = Fraction(0)
    state.t += minutes


# ---------------------------------------------------------------- resolve


def remaining_work(state: SimState, legs: Legs) -> int:
    """Lower bound on the on-duty minutes still needed after the decision minute (section 4.7)."""
    i = state.leg_index or 0
    durations = [ceil15(leg.duration_min) for leg in legs]
    distances = [to_fraction(leg.distance_mi) for leg in legs]
    remaining_drive = durations[i] - state.leg_done + sum(durations[i + 1 :])
    stops_left = STOP_MIN * (len(legs) - i)
    remaining_miles = distances[i] - (state.trip_mile - state.leg_start_mile) + sum(distances[i + 1 :])
    fuel_estimate = max(0, ceil((state.miles_since_fuel + remaining_miles) / FUEL_MAX_MILES) - 1)
    return remaining_drive + stops_left + FUEL_STOP_MIN * fuel_estimate + PRE_TRIP_MIN


def _take_restart(state: SimState, legs: Legs, reason: str) -> None:
    emit(state, legs, Status.OFF, Kind.RESTART, RESTART_MIN - state.off_run, "34-hr restart", reason)


def _take_rest(state: SimState, legs: Legs, reason: str) -> None:
    cycle_left = CYCLE_LIMIT_MIN - state.cycle_on_duty
    if cycle_left < WINDOW_MIN and cycle_left < remaining_work(state, legs):
        _take_restart(state, legs, REASON_A10)
        return
    emit(state, legs, Status.SB, Kind.REST, REST_MIN - state.off_run, "10-hr rest (sleeper)", reason)


def _take_break(state: SimState, legs: Legs) -> None:
    window_left = WINDOW_MIN - (state.t - (state.shift_start or 0))
    if window_left - BREAK_MIN < GRID:
        _take_rest(state, legs, REASON_A17)
        return
    emit(
        state,
        legs,
        Status.OFF,
        Kind.BREAK,
        BREAK_MIN,
        "30-min break",
        "30-min break required after 8 hr driving",
    )


def resolve(state: SimState, hit: set[str], legs: Legs) -> None:
    """Act on the limits that bind at this minute, in the order of section 4.4."""
    pending = set(hit)
    if "arrive" in pending:
        return
    if "fuel" in pending:
        emit(state, legs, Status.ON, Kind.FUEL, FUEL_STOP_MIN, "Fuel", "Fuel: 1,000 mi limit")
        pending.discard("break")
    if "70h" in pending:
        _take_restart(state, legs, REASON_70H)
    elif "11h" in pending or "14h" in pending:
        _take_rest(state, legs, REASON_11H if "11h" in pending else REASON_14H)
    elif "break" in pending:
        _take_break(state, legs)


# ---------------------------------------------------------------- driving


def _start_shift(state: SimState, legs: Legs) -> None:
    emit(state, legs, Status.ON, Kind.PRE_TRIP, PRE_TRIP_MIN, "Pre-trip inspection", "")


def _caps(state: SimState, legs: Legs) -> dict[str, int]:
    dist, dur = _leg_dist_dur(state, legs)
    shift_start = state.t if state.shift_start is None else state.shift_start
    fuel_miles = FUEL_MAX_MILES - state.miles_since_fuel
    return {
        "arrive": dur - state.leg_done,
        "11h": DRIVE_LIMIT_MIN - state.drive_in_shift,
        "14h": max(0, WINDOW_MIN - (state.t - shift_start)),
        "break": BREAK_AFTER_MIN - state.drive_since_break,
        "70h": max(0, CYCLE_LIMIT_MIN - state.cycle_on_duty),
        "fuel": floor15(floor(fuel_miles * dur / dist)),
    }


def drive_step(state: SimState, legs: Legs) -> None:
    """One iteration of the drive loop: pre-trip if needed, drive to the first limit, resolve."""
    if state.shift_start is None:
        _start_shift(state, legs)
    caps = _caps(state, legs)
    chunk = min(caps.values())
    if chunk > 0:
        emit(state, legs, Status.D, Kind.DRIVE, chunk, "Driving", "")
    resolve(state, {name for name, value in caps.items() if value == chunk}, legs)


def drive_leg(state: SimState, legs: Legs, index: int) -> None:
    state.leg_index = index
    state.leg_done = 0
    state.leg_start_mile = state.trip_mile
    dur = ceil15(legs[index].duration_min)
    for _ in range(MAX_STEPS_PER_LEG):
        if state.leg_done >= dur:
            return
        drive_step(state, legs)
    raise HosEngineError("no progress while driving a leg")


# ---------------------------------------------------------------- top level


def _fresh_state(inp: TripInput) -> SimState:
    return SimState.for_test(cycle_on_duty=inp.cycle_used_min, leg_index=None)


def _open_trip(state: SimState, inp: TripInput) -> tuple[EngineWarning, ...]:
    """Section 4.2 and 4.6: the restart at cycle >= 69.5 hr, else the off-duty time before the start."""
    if CYCLE_LIMIT_MIN - state.cycle_on_duty < START_RESTART_THRESHOLD_MIN:
        emit(state, inp.legs, Status.OFF, Kind.RESTART, RESTART_MIN, "34-hr restart", REASON_START)
        return (START_WARNING,)
    if inp.start_min > 0:
        emit(state, inp.legs, Status.OFF, Kind.OFF_BEFORE_START, inp.start_min, "Off duty", "")
    return ()


def _stop(state: SimState, legs: Legs, kind: Kind, label: str) -> None:
    emit(state, legs, Status.ON, kind, STOP_MIN, label, f"{label} (1 hr on duty)")


def simulate(inp: TripInput) -> SimResult:
    validate(inp)
    legs = tuple(inp.legs)
    state = _fresh_state(inp)
    warnings = _open_trip(state, inp)
    state.leg_index = 0
    _start_shift(state, legs)
    drive_leg(state, legs, 0)
    _stop(state, legs, Kind.PICKUP, "Pickup")
    drive_leg(state, legs, 1)
    _stop(state, legs, Kind.DROPOFF, "Dropoff")
    if state.t % DAY_MIN:
        emit(
            state,
            legs,
            Status.OFF,
            Kind.OFF_AFTER_END,
            DAY_MIN - state.t % DAY_MIN,
            "Off duty",
            "Trip complete",
        )
    return SimResult(tuple(state.events), tuple(state.spans), warnings)
