"""Service test setup: clean caches, fake ORS key, no real sleeping (same as the adapter tests)."""

from __future__ import annotations

import pytest
from django.core.cache import caches

from routing import ors_client
from tests.routing.conftest import TEST_KEY
from tests.trips.services.helpers import FakeOrs


@pytest.fixture(autouse=True)
def _service_env(settings, monkeypatch):
    settings.ORS_API_KEY = TEST_KEY
    for alias in ("default", "geo", "routes"):
        caches[alias].clear()
    monkeypatch.setattr(ors_client, "_sleep", lambda _s: None)
    yield
    for alias in ("default", "geo", "routes"):
        caches[alias].clear()


@pytest.fixture
def ors(_block_real_network) -> FakeOrs:
    """A respx-backed fake ORS over the real adapter."""
    return FakeOrs(_block_real_network)
