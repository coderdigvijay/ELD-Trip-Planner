"""Typed API errors and the single place that renders the error envelope.

Envelope and codes: docs/API_CONTRACT.md section 6 (the authority). Every failure leaves the API as
`{"error": {"code", "message", "request_id", ...}}` with `Cache-Control: no-store`. Messages are
written here, never taken from exceptions, so no stack trace, path, upstream body or dependency
name can reach a client.
"""

import logging
from enum import StrEnum
from typing import Any

from django.http import Http404, HttpRequest, JsonResponse
from rest_framework import exceptions as drf_exceptions

from config.logging import request_id_var

logger = logging.getLogger("eld.errors")

RETRY_AFTER_MIN_S = 1
RETRY_AFTER_MAX_S = 300


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    LOCATION_NOT_FOUND = "LOCATION_NOT_FOUND"
    UNSUPPORTED_LOCATION = "UNSUPPORTED_LOCATION"
    AMBIGUOUS_LOCATION = "AMBIGUOUS_LOCATION"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    TRIP_TOO_LONG = "TRIP_TOO_LONG"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_QUOTA_EXCEEDED = "UPSTREAM_QUOTA_EXCEEDED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    INTERNAL = "INTERNAL"


DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.LOCATION_NOT_FOUND: 422,
    ErrorCode.UNSUPPORTED_LOCATION: 422,
    ErrorCode.AMBIGUOUS_LOCATION: 422,
    ErrorCode.ROUTE_NOT_FOUND: 422,
    ErrorCode.TRIP_TOO_LONG: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.UPSTREAM_QUOTA_EXCEEDED: 503,
    ErrorCode.UPSTREAM_UNAVAILABLE: 503,
    ErrorCode.INTERNAL: 500,
}


def clamp_retry_after(seconds: float | None) -> int:
    """Whole seconds clamped to 1..300 (RESEARCH change log; API_CONTRACT section 6)."""
    if seconds is None:
        return RETRY_AFTER_MIN_S
    return max(RETRY_AFTER_MIN_S, min(RETRY_AFTER_MAX_S, int(-(-seconds // 1))))


class ApiError(Exception):
    """A failure with a stable code and a client-safe message. Raise it from services and views."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        http_status: int | None = None,
        field: str | None = None,
        details: list[dict[str, str]] | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status or DEFAULT_STATUS[code]
        self.field = field
        self.details = details
        self.retry_after_s = None if retry_after_s is None else clamp_retry_after(retry_after_s)


def error_response(error: ApiError) -> JsonResponse:
    body: dict[str, Any] = {"code": error.code.value, "message": error.message}
    if error.field:
        body["field"] = error.field
    if error.details:
        body["details"] = error.details
    if error.retry_after_s is not None:
        body["retry_after_s"] = error.retry_after_s
    body["request_id"] = request_id_var.get()
    response = JsonResponse({"error": body}, status=error.http_status)
    response["Cache-Control"] = "no-store"
    if error.retry_after_s is not None:
        response["Retry-After"] = str(error.retry_after_s)
    return response


def internal_error() -> ApiError:
    return ApiError(
        ErrorCode.INTERNAL,
        "The planner hit an unexpected error. Try again. "
        f"If it keeps happening, quote reference {request_id_var.get()}.",
    )


def flatten_validation_errors(detail: Any, path: str = "") -> list[dict[str, str]]:
    """DRF's nested ValidationError detail -> [{field, message}] with dot paths."""
    if isinstance(detail, dict):
        found: list[dict[str, str]] = []
        for key, value in detail.items():
            child = path if key == "non_field_errors" else f"{path}.{key}" if path else str(key)
            found.extend(flatten_validation_errors(value, child))
        return found
    if isinstance(detail, list):
        found = []
        for index, value in enumerate(detail):
            if isinstance(value, dict | list):
                found.extend(flatten_validation_errors(value, f"{path}.{index}" if path else str(index)))
            else:
                found.append({"field": path, "message": str(value)})
        return found
    return [{"field": path, "message": str(detail)}]


def _from_validation_error(exc: drf_exceptions.ValidationError) -> ApiError:
    details = flatten_validation_errors(exc.detail) or [{"field": "", "message": "The request is not valid."}]
    first = details[0]
    return ApiError(
        ErrorCode.VALIDATION_ERROR,
        first["message"],
        field=first["field"] or None,
        details=details,
    )


def to_api_error(exc: Exception, request: HttpRequest | None) -> ApiError:
    """Map any exception to an ApiError. Anything unrecognized becomes INTERNAL (and is logged)."""
    if isinstance(exc, ApiError):
        return exc
    if isinstance(exc, drf_exceptions.ValidationError):
        return _from_validation_error(exc)
    if isinstance(exc, drf_exceptions.ParseError):
        return ApiError(ErrorCode.VALIDATION_ERROR, "The request body is not valid JSON.")
    if isinstance(exc, drf_exceptions.UnsupportedMediaType):
        return ApiError(ErrorCode.VALIDATION_ERROR, "Send the request body as application/json.")
    if isinstance(exc, drf_exceptions.NotAcceptable):
        return ApiError(ErrorCode.VALIDATION_ERROR, "This endpoint only returns JSON.")
    if isinstance(exc, drf_exceptions.Throttled):
        wait = clamp_retry_after(exc.wait)
        return ApiError(
            ErrorCode.RATE_LIMITED,
            f"Too many requests from your network. Wait {wait} seconds, then try again.",
            retry_after_s=wait,
        )
    if isinstance(exc, drf_exceptions.MethodNotAllowed):
        method = request.method if request is not None else "this"
        return ApiError(ErrorCode.METHOD_NOT_ALLOWED, f"This endpoint does not accept {method} requests.")
    if isinstance(exc, Http404 | drf_exceptions.NotFound):
        return ApiError(ErrorCode.NOT_FOUND, "There is no API endpoint at this address.")
    logger.error(
        "unhandled_exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return internal_error()


def exception_handler(exc: Exception, context: dict[str, Any]) -> JsonResponse:
    """DRF EXCEPTION_HANDLER: always returns the envelope, never None (a None would re-raise)."""
    request = context.get("request")
    return error_response(to_api_error(exc, getattr(request, "_request", request)))


def handler400(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return error_response(ApiError(ErrorCode.VALIDATION_ERROR, "The request could not be processed."))


def handler404(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return error_response(to_api_error(Http404(), request))


def handler500(request: HttpRequest) -> JsonResponse:
    # Django calls this with no exception; the traceback was already logged by the request layer.
    return error_response(internal_error())
