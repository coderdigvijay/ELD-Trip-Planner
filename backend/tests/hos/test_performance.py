"""Engine timing budgets (TEST_PLAN section 9): coast to coast < 50 ms, the huge trip B-17 < 200 ms.

Median of 5 timed runs after one warm-up, so import and first-call costs do not count.
"""

import statistics
import time

import pytest

from hos import plan
from tests.hos.helpers import trip

COAST_TO_COAST = trip((50, 54.5), (2800, 3054.5), 40)
HUGE = trip((3000, 9000), (3000, 9000), 0)


def median_ms(inp, repeats: int = 5) -> float:
    plan(inp)
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        plan(inp)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def test_coast_to_coast_under_50_ms():
    ms = median_ms(COAST_TO_COAST)
    assert ms < 50, f"coast to coast took {ms:.1f} ms (budget 50 ms)"


def test_b17_huge_trip_under_200_ms():
    ms = median_ms(HUGE)
    assert ms < 200, f"6,000 mi at 20 mph took {ms:.1f} ms (budget 200 ms)"


@pytest.mark.parametrize("cycle_min", [0, 2400, 4170, 4200])
def test_short_trip_is_fast(cycle_min):
    ms = median_ms(trip((180, 198), (1100, 1020), cycle_min / 60))
    assert ms < 20, f"8b legs took {ms:.1f} ms"


def test_worst_valid_inputs_finish_within_one_second():
    """The slowest inputs validation still allows: two near-14-day legs, and 6,000 mi over two 14-day legs."""
    slow_two = trip((1600.0, 19200.0), (1600.0, 19200.0))
    slow_6000 = trip((3000.0, 20160.0), (3000.0, 20160.0))
    for inp in (slow_two, slow_6000):
        start = time.perf_counter()
        result = plan(inp)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"took {elapsed:.2f} s"
        assert result.sheets
