import json
import re

import pytest
from django.test import Client
from rest_framework.test import APIClient

from trips.errors import ErrorCode, clamp_retry_after, flatten_validation_errors

URLCONF = "tests.trips.urls_for_tests"


@pytest.fixture
def client() -> APIClient:
    return APIClient(raise_request_exception=False)


def error_of(response) -> dict:
    return json.loads(response.content)["error"]


def assert_envelope(response, status: int, code: ErrorCode) -> dict:
    assert response.status_code == status
    assert response["Content-Type"].startswith("application/json")
    assert response["Cache-Control"] == "no-store"
    error = error_of(response)
    assert error["code"] == code.value
    assert error["request_id"] == response["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{16}", error["request_id"])
    return error


def test_unknown_path_is_json_not_found(client):
    response = client.get("/api/v1/does-not-exist")
    error = assert_envelope(response, 404, ErrorCode.NOT_FOUND)
    assert error["message"] == "There is no API endpoint at this address."


def test_unknown_path_outside_api_is_json_not_found(client):
    assert_envelope(client.get("/admin/"), 404, ErrorCode.NOT_FOUND)


def test_trailing_slash_is_not_redirected(client):
    assert_envelope(client.get("/api/v1/health/"), 404, ErrorCode.NOT_FOUND)


def test_wrong_method_is_method_not_allowed(client):
    response = client.post("/api/v1/health", {}, format="json")
    error = assert_envelope(response, 405, ErrorCode.METHOD_NOT_ALLOWED)
    assert error["message"] == "This endpoint does not accept POST requests."


def test_incoming_request_id_is_ignored(client):
    response = client.get("/api/v1/nope", HTTP_X_REQUEST_ID="attacker-\nINJECT")
    assert response["X-Request-ID"] != "attacker-\nINJECT"
    assert error_of(response)["request_id"] == response["X-Request-ID"]


def test_every_request_gets_a_distinct_id(client):
    ids = {client.get("/api/v1/health")["X-Request-ID"] for _ in range(20)}
    assert len(ids) == 20


def test_disallowed_host_is_json_bad_request():
    response = Client(raise_request_exception=False).get("/api/v1/health", HTTP_HOST="evil.example")
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")
    assert response["Cache-Control"] == "no-store"


class TestHandlers:
    @pytest.fixture(autouse=True)
    def _test_routes(self, settings):
        settings.ROOT_URLCONF = URLCONF

    def test_unhandled_exception_is_internal_without_leaks(self, client):
        response = client.get("/boom")
        error = assert_envelope(response, 500, ErrorCode.INTERNAL)
        assert error["request_id"] in error["message"]
        body = response.content.decode()
        for leak in ("RuntimeError", "secret internal detail", "/srv/app", "Traceback", "rest_framework"):
            assert leak not in body

    def test_api_error_renders_field_and_default_status(self, client):
        error = assert_envelope(client.get("/typed"), 422, ErrorCode.LOCATION_NOT_FOUND)
        assert error["field"] == "pickup_location"

    def test_throttled_has_clamped_retry_after_in_body_and_header(self, client):
        response = client.get("/throttled")
        error = assert_envelope(response, 429, ErrorCode.RATE_LIMITED)
        assert error["retry_after_s"] == 300
        assert response["Retry-After"] == "300"

    def test_validation_error_lists_every_field(self, client):
        response = client.post("/post", {"cycle": 99}, format="json")
        error = assert_envelope(response, 400, ErrorCode.VALIDATION_ERROR)
        assert error["field"] == "cycle"
        assert error["details"][0]["field"] == "cycle"

    def test_malformed_json_is_validation_error_not_500(self, client):
        response = client.generic("POST", "/post", "{not json", content_type="application/json")
        error = assert_envelope(response, 400, ErrorCode.VALIDATION_ERROR)
        assert error["message"] == "The request body is not valid JSON."

    def test_wrong_content_type_is_validation_error(self, client):
        response = client.generic("POST", "/post", "cycle=1", content_type="text/plain")
        assert_envelope(response, 400, ErrorCode.VALIDATION_ERROR)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(None, 1), (0, 1), (0.2, 1), (41.3, 42), (300, 300), (9999, 300)],
)
def test_clamp_retry_after(seconds, expected):
    assert clamp_retry_after(seconds) == expected


def test_flatten_validation_errors_builds_dot_paths():
    detail = {
        "pickup": {"lat": ["Too big."]},
        "stops": [{}, {"kind": ["Bad."]}],
        "non_field_errors": ["Same place."],
    }
    assert flatten_validation_errors(detail) == [
        {"field": "pickup.lat", "message": "Too big."},
        {"field": "stops.1.kind", "message": "Bad."},
        {"field": "", "message": "Same place."},
    ]


SECURITY_HEADERS = ("Cache-Control", "Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy")


def test_preflight_carries_no_store_and_security_headers(client):
    response = client.options(
        "/api/v1/trips/plan",
        HTTP_ORIGIN="http://localhost:5173",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )
    reference = client.get("/api/v1/health")
    assert response["Cache-Control"] == "no-store"
    for name in SECURITY_HEADERS:
        assert response[name] == reference[name] or name == "Cache-Control", name
    assert response["X-Request-ID"]


def test_disallowed_host_carries_security_headers():
    response = Client(raise_request_exception=False).get("/api/v1/health", HTTP_HOST="evil.example")
    for name in (*SECURITY_HEADERS, "X-Request-ID"):
        assert response[name], name


def test_forced_500_on_autocomplete_logs_no_query_text(client, caplog):
    from unittest import mock

    caplog.set_level("DEBUG")
    with mock.patch("trips.views.autocomplete", side_effect=RuntimeError("boom")):
        response = client.get("/api/v1/places/autocomplete?q=chicagosecret")
    assert response.status_code == 500
    assert caplog.records
    for record in caplog.records:
        blob = record.getMessage() + " " + " ".join(str(v) for v in vars(record).values())
        assert "chicagosecret" not in blob, record.name


def test_django_request_records_are_stripped_of_request_objects():
    import logging

    from config.logging import RedactRequestFilter

    record = logging.LogRecord(
        "django.request", logging.ERROR, "", 0, "Internal Server Error: /x", None, None
    )
    record.request = "<WSGIRequest: GET '/x?q=secret'>"
    assert not RedactRequestFilter().filter(record)  # bare status line: our middleware logs it
    assert not hasattr(record, "request")
    record.exc_info = (RuntimeError, RuntimeError("x"), None)
    assert RedactRequestFilter().filter(record)  # tracebacks are kept


@pytest.mark.parametrize("method", ["get", "post", "put", "delete", "options"])
def test_unknown_path_is_json_not_found_even_with_debug_on(client, settings, method):
    settings.DEBUG = True  # Django would otherwise render its HTML technical 404
    response = getattr(client, method)("/api/v1/nope")
    error = assert_envelope(response, 404, ErrorCode.NOT_FOUND)
    assert response["Content-Type"].startswith("application/json")
    assert "Traceback" not in response.content.decode() and "urlpattern" not in response.content.decode()
    assert error["request_id"] == response["X-Request-ID"]
