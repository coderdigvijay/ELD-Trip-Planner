"""Structured JSON logging (stdlib only) and the per-request correlation id.

The request id lives in a ContextVar so every log line emitted while a request is
handled carries it, without passing it through call signatures.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import httpx

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Attributes every LogRecord has. Anything else was passed via `extra=` and is emitted.
_RESERVED = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RedactRequestFilter(logging.Filter):
    """django.request attaches `request=<WSGIRequest: GET '/path?query'>` (user text) to its records.

    Drop it, and drop the bare status-code duplicates: the request middleware writes the one request
    line with our request id. Records that carry a traceback are kept (minus the request object).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in ("request", "response"):
            record.__dict__.pop(attr, None)
        return record.exc_info is not None


def _sensitive_httpx_strings(exc: BaseException | None) -> list[str]:
    """Message, URL and query of every httpx error in the exception chain (they embed user text)."""
    found: list[str] = []
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, httpx.HTTPError):
            found.append(str(exc))
            try:
                url = exc.request.url  # type: ignore[attr-defined]  # raises RuntimeError when unset
                found.extend([str(url), url.query.decode("utf-8", "replace")])
            except (RuntimeError, AttributeError):
                pass
        exc = exc.__cause__ or exc.__context__
    return [s for s in found if len(s) > 3]


class JsonFormatter(logging.Formatter):
    def formatException(self, ei: Any) -> str:  # noqa: N802 - stdlib override
        """Traceback without locals, with httpx messages, URLs and queries redacted (ARCHITECTURE 11)."""
        text = super().formatException(ei)
        for secret in sorted(_sensitive_httpx_strings(ei[1]), key=len, reverse=True):
            text = text.replace(secret, "<redacted>")
        return text

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def build_logging_config(level: str) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "config.logging.RequestIdFilter"},
            "redact_request": {"()": "config.logging.RedactRequestFilter"},
        },
        "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
                "filters": ["request_id"],
            }
        },
        "root": {"handlers": ["stdout"], "level": level},
        "loggers": {
            # An httpx error message embeds the full URL (user text, query string).
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            # Django logs the request path on 4xx; our middleware writes the one request line.
            "django.request": {"level": "ERROR", "filters": ["redact_request"]},
        },
    }
