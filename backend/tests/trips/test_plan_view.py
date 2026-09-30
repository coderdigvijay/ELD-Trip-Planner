"""POST /api/v1/trips/plan: success, error model and service error mapping (API_CONTRACT 5 and 6)."""

import logging
import re
from unittest import mock

import pytest

from hos import HosEngineError, HosInputError
from routing import errors as re_
from tests.trips.conftest import PLAN_OK, PLAN_URL, post_plan, valid_payload
from trips.errors import ApiError, ErrorCode


def test_happy_path(client, plan_service):
    response = post_plan(client, valid_payload())
    assert response.status_code == 200
    assert response.json() == PLAN_OK
    assert response["Cache-Control"] == "no-store"
    assert response["Content-Type"] == "application/json"
    assert re.fullmatch(r"[0-9a-f]{16}", response["X-Request-ID"])
    plan_service.assert_called_once()


def test_client_supplied_request_id_is_ignored(client, plan_service):
    response = post_plan(client, valid_payload(), HTTP_X_REQUEST_ID="attacker\ninjected")
    assert response["X-Request-ID"] != "attacker\ninjected"


def _error_of(client, exc, **overrides):
    with mock.patch("trips.views.plan_trip", side_effect=exc):
        response = post_plan(client, valid_payload(**overrides))
    return response, response.json()["error"]


@pytest.mark.parametrize(
    ("exc", "status", "code", "field", "retry"),
    [
        (re_.LocationNotFound("pickup_location"), 422, "LOCATION_NOT_FOUND", "pickup_location", None),
        (
            re_.UnsupportedLocation("dropoff_location", "Toronto, ON"),
            422,
            "UNSUPPORTED_LOCATION",
            "dropoff_location",
            None,
        ),
        (re_.RouteNotFound(), 422, "ROUTE_NOT_FOUND", None, None),
        (re_.TripTooLong(), 422, "TRIP_TOO_LONG", None, None),
        (re_.UpstreamRateLimited(retry_after_s=42), 503, "UPSTREAM_QUOTA_EXCEEDED", None, 42),
        (re_.UpstreamRateLimited(retry_after_s=9999), 503, "UPSTREAM_QUOTA_EXCEEDED", None, 300),
        (re_.UpstreamRateLimited(retry_after_s=0.2), 503, "UPSTREAM_QUOTA_EXCEEDED", None, 1),
        (
            re_.UpstreamQuotaExhausted("directions", scope="minute", retry_after_s=17),
            503,
            "UPSTREAM_QUOTA_EXCEEDED",
            None,
            17,
        ),
        (re_.UpstreamQuotaExhausted("directions", scope="day"), 503, "UPSTREAM_QUOTA_EXCEEDED", None, None),
        (re_.UpstreamQuotaExhausted("geocode", scope="day"), 503, "UPSTREAM_QUOTA_EXCEEDED", None, None),
        (re_.UpstreamUnavailable(), 503, "UPSTREAM_UNAVAILABLE", None, None),
        (re_.DeadlineExceeded(), 503, "UPSTREAM_UNAVAILABLE", None, None),
        (re_.UpstreamAuthError(), 503, "UPSTREAM_UNAVAILABLE", None, None),
        (re_.UpstreamBadResponse(), 503, "UPSTREAM_UNAVAILABLE", None, None),
        (re_.UpstreamBadRequest(), 500, "INTERNAL", None, None),
        (re_.RoutingError("x"), 500, "INTERNAL", None, None),
        (HosInputError("distance must be >= 0 /srv/hos/x.py"), 500, "INTERNAL", None, None),
        (HosEngineError("no progress"), 500, "INTERNAL", None, None),
        (RuntimeError("boom /srv/app.py"), 500, "INTERNAL", None, None),
        (ApiError(ErrorCode.TRIP_TOO_LONG, "custom"), 422, "TRIP_TOO_LONG", None, None),
    ],
)
def test_service_errors_map_to_contract_codes(client, exc, status, code, field, retry):
    response, error = _error_of(client, exc)
    assert response.status_code == status
    assert error["code"] == code
    assert error.get("field") == field
    assert error.get("retry_after_s") == retry
    assert (response.headers.get("Retry-After") == str(retry)) if retry else "Retry-After" not in response
    assert response["Cache-Control"] == "no-store"
    assert error["request_id"] == response["X-Request-ID"]
    assert set(error) <= {"code", "message", "field", "details", "retry_after_s", "request_id"}


@pytest.mark.parametrize("secret", ["/srv", "Traceback", "Exception", "Error", "hos.", "http"])
def test_error_messages_leak_nothing(client, secret):
    leaky = [
        RuntimeError("/srv/app.py Traceback"),
        HosInputError("Exception in hos.simulator"),
        re_.UpstreamBadRequest(),
        re_.UpstreamAuthError(),
    ]
    for exc in leaky:
        _, error = _error_of(client, exc)
        assert secret not in error["message"]


def test_location_not_found_echoes_only_validated_text(client):
    response, error = _error_of(
        client, re_.LocationNotFound("pickup_location"), pickup_location="  Nowhere  ville "
    )
    assert error["message"] == (
        'We couldn\'t find "Nowhere ville". Check the spelling or pick a suggestion from the list.'
    )
    assert response.status_code == 422


def test_location_not_found_uses_label_of_place_input(client):
    place = {"label": "Nowhereville, ZZ", "lat": 40.0, "lng": -100.0}
    _, error = _error_of(client, re_.LocationNotFound("current_location"), current_location=place)
    assert "Nowhereville, ZZ" in error["message"]


def test_quota_messages_follow_contract(client):
    _, day = _error_of(client, re_.UpstreamQuotaExhausted("geocode", scope="day"))
    assert day["message"].startswith("Place lookup has reached its daily limit.")
    _, minute = _error_of(client, re_.UpstreamQuotaExhausted("directions", scope="minute", retry_after_s=17))
    assert (
        minute["message"]
        == "The routing service is at its per-minute limit. Wait 17 seconds, then try again."
    )
    _, down = _error_of(client, re_.DeadlineExceeded())
    assert down["message"] == "The routing service is not responding. Try again in a minute."
    _, boom = _error_of(client, RuntimeError("x"))
    assert boom["message"].startswith("The planner hit an unexpected error. Try again.")
    assert boom["request_id"] in boom["message"]


def test_engine_error_is_logged_with_request_id_not_returned(client, caplog):
    with caplog.at_level(logging.ERROR, logger="eld.errors"):
        response, error = _error_of(client, HosInputError("average speed over 100 mph"))
    assert response.status_code == 500
    assert "100 mph" not in response.content.decode()
    assert any(r.exc_info for r in caplog.records)


def test_error_envelope_for_unknown_path_and_405(client):
    missing = client.get("/api/v1/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert missing["Cache-Control"] == "no-store"
    wrong = client.delete(PLAN_URL)
    assert wrong.status_code == 405
    assert wrong.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert wrong["Cache-Control"] == "no-store"


def test_validation_errors_do_not_reach_the_service_and_release_the_slot(client, plan_service):
    assert post_plan(client, valid_payload(current_cycle_used_hours=99)).status_code == 400
    assert post_plan(client, valid_payload()).status_code == 200  # the in-flight slot was released
    plan_service.assert_called_once()


def test_options_preflight_is_answered_by_cors_not_the_body_check(client):
    response = client.options(
        PLAN_URL,
        HTTP_ORIGIN="http://localhost:5173",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
    )
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"
