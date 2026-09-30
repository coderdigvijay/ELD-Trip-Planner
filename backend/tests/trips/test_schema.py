import json
from pathlib import Path

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

OPENAPI_FILE = Path(__file__).resolve().parents[2] / "openapi.json"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_schema_renders_openapi_json(client):
    response = client.get("/api/v1/schema")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/vnd.oai.openapi+json")
    assert response["Cache-Control"] == "no-store"
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/health" in schema["paths"]
    components = schema["components"]["schemas"]
    for name in ("HealthResponse", "ErrorResponse", "ErrorBody", "FieldError", "ErrorCode"):
        assert name in components
    assert "NOT_FOUND" in components["ErrorCode"]["enum"]


def test_docs_page_and_script_are_self_hosted(client):
    page = client.get("/api/v1/docs")
    assert page.status_code == 200
    html = page.content.decode()
    assert "swagger-ui-bundle.js" in html
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert "cdn" not in html.lower()
    assert "script-src" not in page["Content-Security-Policy"]
    assert "default-src 'self'" in page["Content-Security-Policy"]

    script = client.get("/api/v1/docs?script=")
    assert script.status_code == 200
    assert script["Content-Type"].startswith("application/javascript")


def test_docs_assets_are_served_and_traversal_is_blocked(client):
    ok = client.get("/api/v1/docs-assets/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui.css")
    assert ok.status_code == 200
    bad = client.get("/api/v1/docs-assets/../../settings.py")
    assert bad.status_code == 400
    assert bad["Content-Type"].startswith("application/json")
    assert "site-packages" not in bad.content.decode()
    missing = client.get("/api/v1/docs-assets/nope.js")
    assert missing.status_code == 404
    assert missing["Content-Type"].startswith("application/json")


def test_committed_openapi_json_is_current(tmp_path):
    """Drift guard: regenerate with `make schema` after any response shape change."""
    generated = tmp_path / "openapi.json"
    call_command("spectacular", "--format", "openapi-json", "--validate", "--file", str(generated))
    assert json.loads(OPENAPI_FILE.read_text()) == json.loads(generated.read_text())


# --- API surface (docs/API_CONTRACT.md sections 2, 5 and 10) ------------------------------------------


@pytest.fixture(scope="module")
def spec():
    return json.loads(OPENAPI_FILE.read_text())


def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _refs(value)


def test_no_dangling_refs(spec):
    components = spec["components"]["schemas"]
    for ref in set(_refs(spec)):
        assert ref.removeprefix("#/components/schemas/") in components, ref


def test_endpoints_and_operations(spec):
    assert set(spec["paths"]) == {
        "/api/v1/health",
        "/api/v1/places/autocomplete",
        "/api/v1/trips/plan",
    }
    assert set(spec["paths"]["/api/v1/trips/plan"]) == {"post"}
    assert set(spec["paths"]["/api/v1/places/autocomplete"]) == {"get"}


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/v1/trips/plan", "post", {"200", "400", "422", "429", "500", "503"}),
        ("/api/v1/places/autocomplete", "get", {"200", "400", "429", "500", "503"}),
    ],
)
def test_every_error_status_is_documented_with_error_response(spec, path, method, statuses):
    responses = spec["paths"][path][method]["responses"]
    assert set(responses) == statuses
    for status in statuses - {"200"}:
        schema = responses[status]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ErrorResponse"}
    for status in ("429", "503"):
        assert "Retry-After" in responses[status]["headers"]


def test_contract_component_names_exist(spec):
    names = set(spec["components"]["schemas"])
    expected = {
        "PlanTripRequest", "PlaceInput", "LocationInput", "LogHeader", "PlanTripResponse", "TripMeta",
        "ResolvedPlace", "TimezoneInfo", "Assumption", "Warning", "Route", "RouteLeg", "Bounds", "Stop",
        "TimelineEvent", "LogDay", "LogSegment", "LogRemark", "LogTotals", "LogRecap", "TripSummary",
        "StopCounts", "AutocompleteResponse", "PlaceSuggestion", "HealthResponse", "ErrorResponse",
        "ErrorBody", "FieldError", "DutyStatus", "StopKind", "LabelSource", "RouteProfile", "ErrorCode",
    }  # fmt: skip
    assert expected <= names, expected - names


def test_location_input_is_string_or_place_input(spec):
    schemas = spec["components"]["schemas"]
    one_of = schemas["LocationInput"]["oneOf"]
    assert {"type": "string", "minLength": 3, "maxLength": 200} in one_of
    assert {"$ref": "#/components/schemas/PlaceInput"} in one_of
    request = schemas["PlanTripRequest"]
    for field in ("current_location", "pickup_location", "dropoff_location"):
        assert request["properties"][field] == {"$ref": "#/components/schemas/LocationInput"}
    assert set(request["required"]) == {
        "current_location", "pickup_location", "dropoff_location", "current_cycle_used_hours",
    }  # fmt: skip


def test_request_limits_are_in_the_schema(spec):
    props = spec["components"]["schemas"]["PlanTripRequest"]["properties"]
    assert (props["current_cycle_used_hours"]["minimum"], props["current_cycle_used_hours"]["maximum"]) == (
        0,
        70,
    )
    place = spec["components"]["schemas"]["PlaceInput"]["properties"]
    assert place["lat"]["maximum"] == 90
    assert place["label"]["maxLength"] == 200
    header = spec["components"]["schemas"]["LogHeaderRequest"]["properties"]
    assert header["driver_name"]["maxLength"] == 80


def test_response_enums_and_nullable_fields(spec):
    schemas = spec["components"]["schemas"]
    assert schemas["DutyStatus"]["enum"] == ["off", "sleeper", "driving", "on_duty"]
    assert "break" in schemas["StopCounts"]["properties"]
    assert schemas["LogSegment"]["properties"]["stop_id"]["nullable"] is True
    assert schemas["LogRecap"]["properties"]["restart_note"]["nullable"] is True
    assert set(schemas["PlanTripResponse"]["required"]) == {
        "trip", "route", "stops", "timeline", "days", "summary",
    }  # fmt: skip
