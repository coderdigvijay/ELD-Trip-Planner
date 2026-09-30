"""Global ORS spend budgets (docs/API_CONTRACT.md section 8.3).

Every ORS call, retries and the driving-car fallback included, spends one unit first. Fixed windows
(current UTC minute and UTC day) in the `budgets` cache alias. Numbers live only in API_CONTRACT 8.3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from django.core.cache import caches

from routing.errors import UpstreamQuotaExhausted

BUDGET_CACHE_ALIAS = "budgets"


@dataclass(frozen=True, slots=True)
class Budget:
    per_minute: int
    per_day: int


BUDGETS: dict[str, Budget] = {
    "directions": Budget(per_minute=36, per_day=1_800),
    "geocode": Budget(per_minute=90, per_day=900),
    "autocomplete": Budget(per_minute=90, per_day=900),
    "reverse": Budget(per_minute=90, per_day=900),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _bump(key: str, ttl_s: int) -> int:
    cache = caches[BUDGET_CACHE_ALIAS]
    cache.add(key, 0, timeout=ttl_s)
    try:
        return cache.incr(key)
    except ValueError:  # the key expired between add and incr
        cache.set(key, 1, timeout=ttl_s)
        return 1


def spend(kind: str) -> None:
    """Take one unit of `kind` or raise UpstreamQuotaExhausted without calling ORS."""
    budget = BUDGETS[kind]
    now = _utcnow()
    minute_key = f"ors:budget:{kind}:m:{now:%Y%m%d%H%M}"
    if _bump(minute_key, 90) > budget.per_minute:
        raise UpstreamQuotaExhausted(kind, scope="minute", retry_after_s=60 - now.second)
    day_key = f"ors:budget:{kind}:d:{now:%Y%m%d}"
    if _bump(day_key, 26 * 3600) > budget.per_day:
        raise UpstreamQuotaExhausted(kind, scope="day")
