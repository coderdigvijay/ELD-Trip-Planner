import re

import pytest
from rest_framework.test import APIClient

HEALTH = "/api/v1/health"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_health_returns_ok_json(client):
    response = client.get(HEALTH)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert response.json() == {"status": "ok", "api_version": "1"}


def test_health_is_not_cacheable_and_carries_request_id(client):
    response = client.get(HEALTH)
    assert response["Cache-Control"] == "no-store"
    assert re.fullmatch(r"[0-9a-f]{16}", response["X-Request-ID"])


def test_health_is_never_throttled(client):
    assert all(client.get(HEALTH).status_code == 200 for _ in range(200))


def test_health_never_calls_upstream(client, _block_real_network):  # noqa: PT019
    client.get(HEALTH)
    assert _block_real_network.calls.call_count == 0


def test_health_sets_api_security_headers(client):
    response = client.get(HEALTH)
    assert response["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert response["X-Content-Type-Options"] == "nosniff"
