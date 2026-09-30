"""Size-limited strict JSON parser (docs/API_CONTRACT.md 5.1 body limits, ARCHITECTURE Input hardening).

DRF's stock JSONParser reads the whole stream and accepts `NaN`/`Infinity`. This one reads at most
8,193 bytes, rejects the non-standard constants, and requires a top-level object.
"""

import json
from typing import Any

from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser

from trips.errors import ApiError, ErrorCode

MAX_BODY_BYTES = 8192
BODY_TOO_LARGE_MESSAGE = "The request body is larger than 8 KB."
NOT_JSON_MESSAGE = "The request body is not valid JSON."


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-standard JSON constant {name}")


class BoundedJSONParser(BaseParser):
    media_type = "application/json"
    renderer_class = None  # parsing only

    def parse(self, stream: Any, media_type: str | None = None, parser_context: Any = None) -> dict:
        raw = stream.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise ApiError(ErrorCode.VALIDATION_ERROR, BODY_TOO_LARGE_MESSAGE)
        try:
            data = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
            raise ParseError(NOT_JSON_MESSAGE) from exc
        if not isinstance(data, dict):
            raise ParseError(NOT_JSON_MESSAGE)
        return data
