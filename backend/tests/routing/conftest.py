"""Shared fixtures for adapter tests: clean caches, fake key, no real sleeping, ORS mock helpers."""

from __future__ import annotations

import pytest
from django.core.cache import caches

from routing import ors_client

TEST_KEY = "TEST_ORS_KEY_do_not_log"
BASE = "https://api.openrouteservice.org"


@pytest.fixture(autouse=True)
def _adapter_env(settings, monkeypatch):
    settings.ORS_API_KEY = TEST_KEY
    for alias in ("default", "geo", "routes", "budgets"):
        caches[alias].clear()
    naps: list[float] = []
    monkeypatch.setattr(ors_client, "_sleep", naps.append)
    yield naps
    for alias in ("default", "geo", "routes", "budgets"):
        caches[alias].clear()


@pytest.fixture
def naps(_adapter_env) -> list[float]:
    """Seconds the adapter asked to sleep between attempts."""
    return _adapter_env


@pytest.fixture
def ors(_block_real_network):
    """The respx router from the root conftest (unmocked requests still fail the test)."""
    return _block_real_network
