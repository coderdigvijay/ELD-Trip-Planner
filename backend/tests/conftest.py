"""Shared test setup: Hypothesis profiles and no real network."""

import os

import pytest
import respx
from hypothesis import HealthCheck, settings

_COMMON = {"deadline": None, "suppress_health_check": [HealthCheck.too_slow]}
settings.register_profile("dev", max_examples=100, **_COMMON)
settings.register_profile("ci", max_examples=500, derandomize=True, **_COMMON)
settings.register_profile("deep", max_examples=20_000, **_COMMON)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture(autouse=True)
def _block_real_network():
    """Any httpx request that is not mocked fails the test (never call real ORS)."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        yield router
