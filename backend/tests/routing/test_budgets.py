"""Global ORS spend budgets (docs/API_CONTRACT.md section 8.3)."""

from datetime import UTC, datetime

import pytest

from routing import budgets
from routing.errors import UpstreamQuotaExhausted


@pytest.fixture
def clock(monkeypatch):
    now = {"t": datetime(2026, 9, 30, 12, 0, 20, tzinfo=UTC)}
    monkeypatch.setattr(budgets, "_utcnow", lambda: now["t"])
    return now


def test_contract_numbers():
    assert budgets.BUDGETS["directions"] == budgets.Budget(36, 1_800)
    for kind in ("geocode", "autocomplete", "reverse"):
        assert budgets.BUDGETS[kind] == budgets.Budget(90, 900)


def test_spend_up_to_the_minute_limit_then_minute_error_with_retry_hint(clock, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "geocode", budgets.Budget(2, 100))
    budgets.spend("geocode")
    budgets.spend("geocode")
    with pytest.raises(UpstreamQuotaExhausted) as info:
        budgets.spend("geocode")
    assert info.value.scope == "minute"
    assert info.value.retry_after_s == 40  # 60 - 20 s into the minute


def test_minute_window_rolls_over(clock, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "reverse", budgets.Budget(1, 100))
    budgets.spend("reverse")
    clock["t"] = datetime(2026, 9, 30, 12, 1, 0, tzinfo=UTC)
    budgets.spend("reverse")


def test_daily_limit_has_no_retry_hint(clock, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "directions", budgets.Budget(100, 2))
    budgets.spend("directions")
    clock["t"] = datetime(2026, 9, 30, 12, 5, 0, tzinfo=UTC)
    budgets.spend("directions")
    clock["t"] = datetime(2026, 9, 30, 12, 9, 0, tzinfo=UTC)
    with pytest.raises(UpstreamQuotaExhausted) as info:
        budgets.spend("directions")
    assert info.value.scope == "day"
    assert info.value.retry_after_s is None


def test_kinds_have_independent_counters(clock, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "geocode", budgets.Budget(1, 10))
    budgets.spend("geocode")
    budgets.spend("directions")


def test_counters_live_in_their_own_cache_so_throttle_churn_cannot_reset_them(clock, monkeypatch):
    from django.core.cache import caches

    monkeypatch.setitem(budgets.BUDGETS, "geocode", budgets.Budget(1, 100))
    budgets.spend("geocode")
    for i in range(5_000):  # far past the default alias MAX_ENTRIES
        caches["default"].set(f"throttle:{i}", i)
    with pytest.raises(UpstreamQuotaExhausted):
        budgets.spend("geocode")
    assert budgets.BUDGET_CACHE_ALIAS == "budgets"
