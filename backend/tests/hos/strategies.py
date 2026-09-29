"""Hypothesis strategies for engine inputs (TEST_PLAN 3.1).

`trip` covers the whole documented input range. The targeted strategies push the inputs onto the
boundaries where HOS engines break: 8 / 11 / 14 hour landings, the 68.75..70 h cycle band, fuel at
1,000 mi, midnight crossings, and raw ORS-shaped floats (meters / 1609.344, seconds / 60).
"""

from math import ceil

from hypothesis import strategies as st

from hos.models import Leg, TripInput

cycle_min = st.integers(0, 280).map(lambda q: q * 15)  # 0..70 h, step 0.25
start_min = st.integers(0, 95).map(lambda q: q * 15)  # 00:00..23:45
MAX_MPH = 75.0


def _leg(dist: float, minutes: float) -> Leg:
    return Leg(dist, minutes, "A, ST", "B, ST")


@st.composite
def _free_leg(draw, allow_zero: bool) -> Leg:
    if allow_zero and draw(st.integers(0, 9)) == 0:
        return Leg(0.0, 0.0, "A, ST", "B, ST")  # about 10 % zero-length first leg
    dist = draw(st.floats(0.1, 3000, allow_nan=False, allow_infinity=False))
    mph = draw(st.floats(20, MAX_MPH))
    return _leg(dist, dist / mph * 60)  # raw float minutes, like ORS


trip = st.builds(
    TripInput,
    legs=st.tuples(_free_leg(True), _free_leg(False)),
    cycle_used_min=cycle_min,
    start_min=start_min,
)


def _leg_from_minutes(draw, minutes: float, mph_low: float = 30.0) -> Leg:
    mph = draw(st.floats(mph_low, MAX_MPH))
    return _leg(minutes * mph / 60, minutes)


_BOUNDARY_MINUTES = [465, 480, 495, 645, 660, 675, 825, 840, 855]
_BOUNDARY_FRACTIONS = [0.0, 0.01, 14.99]
_BOUNDARY_CYCLES = [4125, 4155, 4170, 4185, 4200]


@st.composite
def boundary_trip(draw) -> TripInput:
    """Leg durations land on or 1 tick around 8 / 11 / 14 h; cycles sit in the 68.75..70 h band."""

    def minutes():
        return draw(st.sampled_from(_BOUNDARY_MINUTES)) + draw(st.sampled_from(_BOUNDARY_FRACTIONS))

    first = Leg(0.0, 0.0, "A, ST", "B, ST") if draw(st.booleans()) else _leg_from_minutes(draw, minutes())
    second = _leg_from_minutes(draw, minutes())
    cycle = draw(st.one_of(st.sampled_from(_BOUNDARY_CYCLES), cycle_min))
    return TripInput((first, second), cycle, draw(start_min))


_FUEL_DISTANCES = [999.9, 1000.0, 1000.1, 1999.9, 2000.0, 2000.1, 2999.9, 3000.0, 500.0, 1500.0]


@st.composite
def fuel_trip(draw) -> TripInput:
    """Distances at multiples of 1,000 mi +- 0.1; durations on a 15 min line, or 1 min off it."""

    def leg(dist: float) -> Leg:
        floor_min = dist / MAX_MPH * 60
        grid = 15 * ceil(floor_min / 15) + 15 * draw(st.integers(0, 40))
        offset = draw(st.sampled_from([0, 0, 1, -1]))
        return _leg(dist, max(1, grid + offset) if grid + offset >= floor_min else grid)

    first = (
        Leg(0.0, 0.0, "A, ST", "B, ST")
        if draw(st.booleans())
        else leg(draw(st.sampled_from(_FUEL_DISTANCES)))
    )
    return TripInput((first, leg(draw(st.sampled_from(_FUEL_DISTANCES)))), draw(cycle_min), draw(start_min))


@st.composite
def midnight_trip(draw) -> TripInput:
    """Starts near midnight and grid-aligned durations, so event boundaries fall on 1440 k."""
    first_minutes = draw(st.integers(0, 24)) * 15
    first = (
        Leg(0.0, 0.0, "A, ST", "B, ST")
        if first_minutes == 0
        else _leg(first_minutes * 55 / 60, float(first_minutes))
    )
    second_minutes = draw(st.integers(1, 120)) * 15
    second = _leg(second_minutes * draw(st.sampled_from([30, 45, 55, 60, 75])) / 60, float(second_minutes))
    start = draw(st.sampled_from([0, 1350, 1365, 1380, 1395, 1410, 1425, 480]))
    return TripInput((first, second), draw(cycle_min), start)


@st.composite
def raw_ors_trip(draw) -> TripInput:
    """Distances from integer meters / 1609.344 and durations from integer seconds / 60 (ORS shape)."""

    def leg(allow_zero: bool) -> Leg:
        if allow_zero and draw(st.integers(0, 9)) == 0:
            return Leg(0.0, 0.0, "A, ST", "B, ST")
        meters = draw(st.integers(200, 4_800_000))
        mph = draw(st.floats(20, MAX_MPH))
        seconds = max(1, round(meters / 1609.344 / mph * 3600))
        return _leg(meters / 1609.344, seconds / 60)

    return TripInput((leg(True), leg(False)), draw(cycle_min), draw(start_min))


ALL_TRIPS = {
    "trip": trip,
    "boundary_trip": boundary_trip(),
    "fuel_trip": fuel_trip(),
    "midnight_trip": midnight_trip(),
    "raw_ors_trip": raw_ors_trip(),
}
