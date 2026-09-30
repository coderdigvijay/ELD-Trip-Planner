"""Deadline value object (docs/ARCHITECTURE.md section 4)."""

import pytest

from routing.deadline import Deadline
from routing.errors import DeadlineExceeded


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_default_is_25_seconds_and_counts_down():
    clock = FakeClock()
    deadline = Deadline(clock=clock)
    assert deadline.remaining() == 25.0
    clock.now += 10
    assert deadline.remaining() == 15.0
    assert not deadline.expired


def test_timeout_is_min_of_cap_and_remaining():
    clock = FakeClock()
    deadline = Deadline(clock=clock)
    timeout = deadline.http_timeout()
    assert (timeout.read, timeout.connect) == (10.0, 3.0)
    clock.now += 23
    timeout = deadline.http_timeout()
    assert (timeout.read, timeout.connect) == (2.0, 2.0)


def test_expired_deadline_raises_and_timeout_stays_positive():
    clock = FakeClock()
    deadline = Deadline(1.0, clock=clock)
    clock.now += 5
    assert deadline.remaining() == 0.0 and deadline.expired
    assert deadline.http_timeout().read > 0
    with pytest.raises(DeadlineExceeded):
        deadline.ensure_time_left()
