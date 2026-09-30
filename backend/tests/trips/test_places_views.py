"""GET /api/v1/places/autocomplete (docs/API_CONTRACT.md section 4)."""

import re
from unittest import mock

import pytest

from routing.errors import UpstreamQuotaExhausted, UpstreamUnavailable
from tests.trips.conftest import PLACES_URL


def _get(client, q, **extra):
    return client.get(PLACES_URL, {"q": q}, **extra)


def test_happy_path_shape_and_cache_control(client, autocomplete_service):
    response = _get(client, "Rich")
    assert response.status_code == 200
    assert response.json() == {"items": [{"label": "Richmond, VA", "lat": 37.54072, "lng": -77.43605}]}
    assert response["Cache-Control"] == "public, max-age=3600"
    assert re.fullmatch(r"[0-9a-f]{16}", response["X-Request-ID"])
    autocomplete_service.assert_called_once_with("Rich")


def test_empty_result_is_200_not_an_error(client):
    with mock.patch("trips.views.autocomplete", return_value={"items": []}):
        response = _get(client, "Zzzz")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_query_is_normalized_before_the_service(client, autocomplete_service):
    _get(client, "  Rich   mond ")
    autocomplete_service.assert_called_once_with("Rich mond")


@pytest.mark.parametrize("q", ["", "ab", "  a ", "x" * 101, "Ri\nch", "Ri​ch", "‮abc"])
def test_bad_q_is_400_with_field(client, autocomplete_service, q):
    response = _get(client, q)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["field"] == "q"
    assert response["Cache-Control"] == "no-store"
    autocomplete_service.assert_not_called()


def test_missing_q_is_400(client, autocomplete_service):
    response = client.get(PLACES_URL)
    assert response.status_code == 400
    assert response.json()["error"]["field"] == "q"


@pytest.mark.parametrize("q", ["abc", "x" * 100])
def test_length_boundaries_accepted(client, autocomplete_service, q):
    assert _get(client, q).status_code == 200


def test_only_five_items_shape_is_passed_through_the_serializer(client):
    items = [{"label": f"P{i}", "lat": 40.0, "lng": -100.0, "junk": "x"} for i in range(3)]
    with mock.patch("trips.views.autocomplete", return_value={"items": items}):
        body = _get(client, "abc").json()
    assert all(set(item) == {"label", "lat", "lng"} for item in body["items"])


@pytest.mark.parametrize(
    ("exc", "status", "code", "has_retry"),
    [
        (UpstreamUnavailable(), 503, "UPSTREAM_UNAVAILABLE", False),
        (
            UpstreamQuotaExhausted("autocomplete", scope="minute", retry_after_s=20),
            503,
            "UPSTREAM_QUOTA_EXCEEDED",
            True,
        ),
        (UpstreamQuotaExhausted("autocomplete", scope="day"), 503, "UPSTREAM_QUOTA_EXCEEDED", False),
    ],
)
def test_upstream_failures(client, exc, status, code, has_retry):
    with mock.patch("trips.views.autocomplete", side_effect=exc):
        response = _get(client, "abc")
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert ("retry_after_s" in error) is has_retry
    assert (response.headers.get("Retry-After") is not None) is has_retry
    assert response["Cache-Control"] == "no-store"


def test_unexpected_exception_is_500_without_leaks(client):
    with mock.patch("trips.views.autocomplete", side_effect=RuntimeError("/srv/secret.py boom")):
        response = _get(client, "abc")
    assert response.status_code == 500
    text = response.content.decode()
    assert "secret" not in text
    assert response.json()["error"]["code"] == "INTERNAL"


def test_post_is_405_json(client):
    response = client.post(PLACES_URL, {"q": "abc"}, format="json")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert response["Cache-Control"] == "no-store"


def test_get_on_plan_is_405(client):
    response = client.get("/api/v1/trips/plan")
    assert response.status_code == 405
    assert response.json()["error"]["message"] == "This endpoint does not accept GET requests."
