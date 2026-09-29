import pytest
from rest_framework.test import APIClient

ALLOWED = "http://localhost:5173"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_allowed_origin_is_echoed_and_headers_exposed(client):
    response = client.get("/api/v1/health", HTTP_ORIGIN=ALLOWED)
    assert response["Access-Control-Allow-Origin"] == ALLOWED
    assert "Access-Control-Allow-Credentials" not in response
    assert "X-Request-ID" in response["Access-Control-Expose-Headers"]


def test_other_origin_gets_no_cors_headers(client):
    response = client.get("/api/v1/health", HTTP_ORIGIN="https://evil.example")
    assert "Access-Control-Allow-Origin" not in response


def test_preflight_allows_only_intended_methods_and_headers(client):
    response = client.options(
        "/api/v1/trips/plan",
        HTTP_ORIGIN=ALLOWED,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
    )
    assert response["Access-Control-Allow-Origin"] == ALLOWED
    assert response["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
    assert response["Access-Control-Allow-Headers"] == "content-type"
