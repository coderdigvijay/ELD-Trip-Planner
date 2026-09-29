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
