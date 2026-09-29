"""HosInputError paths (TEST_PLAN 2.4, HOS_ENGINE_SPEC section 2 validation).

HosInputError means our bug or bad upstream data (the service maps it to INTERNAL), so every
rejected input must raise it, never return a plan and never leak a different exception type.
"""

import math

import pytest

from hos import HosInputError, Leg, TripInput, plan

OK0 = Leg(180.0, 198.0, "A, ST", "B, ST")
OK1 = Leg(1100.0, 1020.0, "B, ST", "C, ST")


def make(l0=OK0, l1=OK1, cycle=1200, start=480) -> TripInput:
    return TripInput((l0, l1), cycle, start)


@pytest.mark.parametrize("cycle", [-15, 4201, 4215, 7, 1, 14, 4199])
def test_bad_cycle_names_the_field(cycle):
    with pytest.raises(HosInputError, match="cycle_used_min"):
        plan(make(cycle=cycle))


@pytest.mark.parametrize("start", [-15, 1440, 1430, 1, 14, 1426, 2000])
def test_bad_start_names_the_field(start):
    with pytest.raises(HosInputError, match="start_min"):
        plan(make(start=start))


@pytest.mark.parametrize("cycle", [0, 15, 4155, 4170, 4200])
def test_cycle_edges_accepted(cycle):
    assert plan(make(cycle=cycle)).events


@pytest.mark.parametrize("start", [0, 15, 480, 1410, 1425])
def test_start_edges_accepted(start):
    assert plan(make(start=start)).events


@pytest.mark.parametrize(
    "leg",
    [
        Leg(-1.0, 60.0, "A", "B"),
        Leg(60.0, -1.0, "A", "B"),
        Leg(-0.0001, 0.0, "A", "B"),
        Leg(0.0, 5.0, "A", "B"),  # distance 0 with duration > 0
        Leg(5.0, 0.0, "A", "B"),  # duration 0 with distance > 0
        Leg(101.0, 60.0, "A", "B"),  # 101 mph
    ],
)
@pytest.mark.parametrize("slot", [0, 1])
def test_bad_leg_raises(leg, slot):
    legs = [OK0, OK1]
    legs[slot] = leg
    with pytest.raises(HosInputError):
        plan(TripInput(tuple(legs), 1200, 480))


def test_exactly_100_mph_is_accepted_and_101_is_not():
    assert plan(make(l0=Leg(100.0, 60.0, "A", "B")))
    with pytest.raises(HosInputError):
        plan(make(l0=Leg(100.01, 60.0, "A", "B")))


def test_speed_is_checked_against_the_rounded_up_duration():
    """0.02 mi in 0.07 min looks like 17 mph raw but is 0.08 mph on the 15 min grid: legal (S-5)."""
    assert plan(make(l0=Leg(0.02, 0.07, "A", "B")))
    # 150 mi in 89 min rounds up to 90 min: exactly 100 mph, legal.
    assert plan(make(l0=Leg(150.0, 89.0, "A", "B")))
    with pytest.raises(HosInputError):
        plan(make(l0=Leg(151.0, 89.0, "A", "B")))  # 151 mi / 90 min = 100.7 mph


def test_leg_1_must_have_distance():
    with pytest.raises(HosInputError):
        plan(make(l1=Leg(0.0, 0.0, "B", "C")))


def test_leg_0_may_be_zero_length():
    assert plan(make(l0=Leg(0.0, 0.0, "A", "A")))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["distance", "duration"])
@pytest.mark.parametrize("slot", [0, 1])
def test_nan_and_inf_raise_instead_of_propagating(bad, field, slot):
    leg = Leg(bad, 60.0, "A", "B") if field == "distance" else Leg(60.0, bad, "A", "B")
    legs = [OK0, OK1]
    legs[slot] = leg
    with pytest.raises(HosInputError):
        plan(TripInput(tuple(legs), 1200, 480))


def test_wrong_number_of_legs_raises_a_typed_error():
    with pytest.raises(HosInputError):
        plan(TripInput((OK0,), 1200, 480))  # type: ignore[arg-type]
    with pytest.raises(HosInputError):
        plan(TripInput((OK0, OK1, OK1), 1200, 480))  # type: ignore[arg-type]


def test_hos_input_error_is_a_value_error_not_a_bare_exception():
    assert issubclass(HosInputError, ValueError)


def test_validation_happens_before_any_work_no_partial_output():
    with pytest.raises(HosInputError):
        plan(make(cycle=4201, start=1430))


# --- T2 review rulings: types, limits, fail-fast ---------------------------------------------------


@pytest.mark.parametrize("minutes", [20160.01, 30000.0, 1e9])
def test_duration_above_14_days_rejected(minutes):
    with pytest.raises(HosInputError, match="duration"):
        plan(make(l1=Leg(minutes * 0.5, minutes, "A", "B")))


def test_duration_of_exactly_14_days_is_accepted():
    assert plan(make(l1=Leg(20160.0 * 0.1, 20160.0, "A", "B")))


@pytest.mark.parametrize("miles", [10.0, 100.0, 1666.0])
def test_average_speed_below_5_mph_rejected(miles):
    with pytest.raises(HosInputError, match="speed|mph"):
        plan(make(l1=Leg(miles, miles / 4.99 * 60, "A", "B")))


def test_average_speed_of_exactly_5_mph_is_accepted():
    assert plan(make(l1=Leg(50.0, 600.0, "A", "B")))


BAD_TRIPS = {
    "legs None": lambda: TripInput(None, 1200, 480),  # type: ignore[arg-type]
    "legs dict": lambda: TripInput({"a": OK0, "b": OK1}, 1200, 480),  # type: ignore[arg-type]
    "legs str": lambda: TripInput("ab", 1200, 480),  # type: ignore[arg-type]
    "leg None": lambda: TripInput((None, OK1), 1200, 480),  # type: ignore[arg-type]
    "leg dict": lambda: TripInput((OK0, {"distance_mi": 5}), 1200, 480),  # type: ignore[arg-type]
    "leg str": lambda: TripInput((OK0, "leg"), 1200, 480),  # type: ignore[arg-type]
    "distance str": lambda: make(l0=Leg("180", 198.0, "A", "B")),  # type: ignore[arg-type]
    "distance None": lambda: make(l0=Leg(None, 198.0, "A", "B")),  # type: ignore[arg-type]
    "duration dict": lambda: make(l0=Leg(180.0, {}, "A", "B")),  # type: ignore[arg-type]
    "distance bool": lambda: make(l0=Leg(True, 60.0, "A", "B")),  # type: ignore[arg-type]
    "duration bool": lambda: make(l0=Leg(60.0, True, "A", "B")),  # type: ignore[arg-type]
    "from_label int": lambda: make(l0=Leg(180.0, 198.0, 5, "B")),  # type: ignore[arg-type]
    "to_label None": lambda: make(l0=Leg(180.0, 198.0, "A", None)),  # type: ignore[arg-type]
    "label 201 chars": lambda: make(l0=Leg(180.0, 198.0, "x" * 201, "B")),
    "cycle bool": lambda: make(cycle=True),  # type: ignore[arg-type]
    "cycle str": lambda: make(cycle="1200"),  # type: ignore[arg-type]
    "cycle None": lambda: make(cycle=None),  # type: ignore[arg-type]
    "cycle float": lambda: make(cycle=1200.0),  # type: ignore[arg-type]
    "start bool": lambda: make(start=False),  # type: ignore[arg-type]
    "start None": lambda: make(start=None),  # type: ignore[arg-type]
    "huge float": lambda: make(l0=Leg(1e308, 1e308, "A", "B")),
    "overflow distance": lambda: make(l0=Leg(1e400, 60.0, "A", "B")),
}


@pytest.mark.parametrize("name", list(BAD_TRIPS))
def test_wrong_types_and_shapes_raise_hos_input_error_only(name):
    with pytest.raises(HosInputError):
        plan(BAD_TRIPS[name]())


def test_label_of_exactly_200_chars_is_accepted():
    assert plan(make(l0=Leg(180.0, 198.0, "x" * 200, "y" * 200)))


@pytest.mark.parametrize(
    "leg", [Leg(1e12, 1e12, "A", "B"), Leg(1.0, 1e9, "A", "B"), Leg(1e300, 1e6, "A", "B")]
)
def test_absurd_legs_fail_fast(leg):
    import time

    start = time.perf_counter()
    with pytest.raises(HosInputError):
        plan(make(l1=leg))
    assert time.perf_counter() - start < 0.2
