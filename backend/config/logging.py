"""Structured JSON logging (stdlib only) and the per-request correlation id.

The request id lives in a ContextVar so every log line emitted while a request is
handled carries it, without passing it through call signatures.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Attributes every LogRecord has. Anything else was passed via `extra=` and is emitted.
_RESERVED = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
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
        "filters": {"request_id": {"()": "config.logging.RequestIdFilter"}},
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
            "django.request": {"level": "ERROR"},
        },
    }
