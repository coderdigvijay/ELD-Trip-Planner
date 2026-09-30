"""Per-request ORS counters for the plan_completed log line (docs/ARCHITECTURE.md section 11).

A ContextVar holds one mutable `RequestStats`; `plan_trip._parallel` copies the context into its worker
threads, so they all increment the same object. Counters are keyed by endpoint kind only: no location
text, coordinates or addresses ever enter this module.
"""

from __future__ import annotations

import threading
from collections import Counter
from contextvars import ContextVar, Token


class RequestStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: Counter[str] = Counter()
        self._hits: Counter[str] = Counter()

    def call(self, kind: str) -> None:
        with self._lock:
            self._calls[kind] += 1

    def hit(self, kind: str) -> None:
        with self._lock:
            self._hits[kind] += 1

    @property
    def ors_calls(self) -> dict[str, int]:
        with self._lock:
            return dict(self._calls)

    @property
    def cache_hits(self) -> dict[str, int]:
        with self._lock:
            return dict(self._hits)


_current: ContextVar[RequestStats | None] = ContextVar("request_stats", default=None)


def begin() -> tuple[RequestStats, Token]:
    stats = RequestStats()
    return stats, _current.set(stats)


def end(token: Token) -> None:
    _current.reset(token)


def record_call(kind: str) -> None:
    """One network attempt to ORS (a retry counts again). No-op outside a stats scope."""
    if (stats := _current.get()) is not None:
        stats.call(kind)


def record_cache_hit(kind: str) -> None:
    if (stats := _current.get()) is not None:
        stats.hit(kind)
