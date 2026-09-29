"""Request context (id + one summary log line) and response headers for every path."""

import logging
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from config.logging import request_id_var

logger = logging.getLogger("eld.request")

REQUEST_ID_HEADER = "X-Request-ID"
_CSP_API = "default-src 'none'; frame-ancestors 'none'"
_CSP_DOCS = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
)
_HEALTH_PATH = "/api/v1/health"
_DOCS_PATH = "/api/v1/docs"


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


class RequestContextMiddleware:
    """Server-generated request id (an incoming X-Request-ID is ignored) plus the request log line.

    Logs method, route name, status, duration and the X-Forwarded-For hop count only: never the
    path, query string, client address or body (docs/ARCHITECTURE.md section 11).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            self._log(request, response, started)
            return response
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _log(request: HttpRequest, response: HttpResponse, started: float) -> None:
        match = request.resolver_match
        route = match.url_name if match else None
        level = logging.DEBUG if request.path == _HEALTH_PATH else logging.INFO
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        logger.log(
            level,
            "request",
            extra={
                "method": request.method,
                "route": route,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "xff_hops": len([p for p in xff.split(",") if p.strip()]),
            },
        )


class ResponseHeadersMiddleware:
    """Cache-Control and CSP defaults (docs/API_CONTRACT.md section 1, docs/DEPLOYMENT.md section 2).

    Every non-2xx response is forced to `no-store`, so a shared cache can never replay an error.
    Success responses default to `no-store` unless a view chose its own policy.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code >= 400 or "Cache-Control" not in response:
            response["Cache-Control"] = "no-store"
        docs = request.path.startswith(_DOCS_PATH) and response.status_code < 400
        response.setdefault("Content-Security-Policy", _CSP_DOCS if docs else _CSP_API)
        return response
