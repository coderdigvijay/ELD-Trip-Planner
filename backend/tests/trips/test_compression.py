"""Responses are gzip-compressed on request without losing the security or cache headers."""

import gzip
import json

SCHEMA_URL = "/api/v1/schema"


def test_large_response_is_gzipped_when_accepted(client):
    plain = client.get(SCHEMA_URL)
    zipped = client.get(SCHEMA_URL, HTTP_ACCEPT_ENCODING="gzip")
    assert zipped["Content-Encoding"] == "gzip"
    assert "Content-Encoding" not in plain
    assert len(zipped.content) < len(plain.content)
    assert json.loads(gzip.decompress(zipped.content)) == json.loads(plain.content)


def test_gzip_keeps_no_store_csp_and_request_id(client):
    response = client.get(SCHEMA_URL, HTTP_ACCEPT_ENCODING="gzip")
    assert response["Content-Encoding"] == "gzip"
    assert response["Cache-Control"] == "no-store"
    assert response["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert response["X-Request-ID"]
    assert "Accept-Encoding" in response["Vary"]


def test_not_gzipped_without_accept_encoding(client):
    assert "Content-Encoding" not in client.get(SCHEMA_URL)
