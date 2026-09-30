"""One request budget shared by every upstream call (docs/ARCHITECTURE.md section 4)."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from routing.errors import DeadlineExceeded

REQUEST_DEADLINE_S = 25.0
READ_CAP_S = 10.0
CONNECT_CAP_S = 3.0
_MIN_TIMEOUT_S = 0.001


class Deadline:
    """Monotonic countdown. The clock is injectable so tests can shrink or advance it."""

    def __init__(
        self, total_s: float = REQUEST_DEADLINE_S, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._clock = clock
        self._end = clock() + total_s

    def remaining(self) -> float:
        return max(0.0, self._end - self._clock())

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def ensure_time_left(self) -> None:
        if self.expired:
            raise DeadlineExceeded

    def http_timeout(self, read_cap_s: float = READ_CAP_S) -> httpx.Timeout:
        """`min(cap, remaining)` for read/write/pool, `min(3, remaining)` for connect."""
        remaining = max(self.remaining(), _MIN_TIMEOUT_S)
        return httpx.Timeout(min(read_cap_s, remaining), connect=min(CONNECT_CAP_S, remaining))
