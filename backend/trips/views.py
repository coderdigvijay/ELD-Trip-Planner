"""Thin views: throttle -> guard -> validate -> service -> render (docs/API_CONTRACT.md sections 3 to 8)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import drf_spectacular_sidecar
from django.core.exceptions import SuspiciousOperation
from django.views.static import serve
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from trips.errors import ApiError, ErrorCode
from trips.inflight import PlanInflightGuard
from trips.parsers import BODY_TOO_LARGE_MESSAGE, MAX_BODY_BYTES, NOT_JSON_MESSAGE, BoundedJSONParser
from trips.response_serializers import AutocompleteResponseSerializer, PlanTripResponseSerializer
from trips.serializers import (
    ErrorResponseSerializer,
    HealthResponseSerializer,
    PlanTripSerializer,
    validated_plan_request,
    validated_query,
)
from trips.service_errors import SERVICE_ERRORS, map_service_error
from trips.services.autocomplete import autocomplete
from trips.services.plan_trip import plan_trip
from trips.throttles import PLACES_THROTTLES, PLAN_THROTTLES, ContractThrottleMixin, DocsAssetsIpThrottle

NO_STORE = "no-store"
AUTOCOMPLETE_CACHE_CONTROL = "public, max-age=3600"
NOT_JSON_CONTENT_TYPE_MESSAGE = "Send the request body as JSON (Content-Type: application/json)."
_SIDECAR_STATIC = Path(drf_spectacular_sidecar.__file__).parent / "static"


_RETRY_AFTER = OpenApiParameter(
    "Retry-After",
    int,
    location=OpenApiParameter.HEADER,
    response=[429, 503],
    description="Seconds to wait, 1 to 300. Same value as error.retry_after_s.",
)


def _error(status_description: str) -> OpenApiResponse:
    return OpenApiResponse(ErrorResponseSerializer, description=status_description)


_COMMON_ERRORS = {
    404: _error("NOT_FOUND: there is no API endpoint at this address."),
    405: _error("METHOD_NOT_ALLOWED: this endpoint does not accept that HTTP method."),
    429: _error("Rate limited. Read retry_after_s or the Retry-After header."),
    500: _error("Unexpected error. Quote request_id."),
}
_UPSTREAM_ERRORS = {
    503: _error(
        "Routing service unavailable or out of quota (UPSTREAM_UNAVAILABLE, UPSTREAM_QUOTA_EXCEEDED)."
    ),
}


def _reject_bad_body_headers(request: Request) -> None:
    """Contract 5.1 steps 1 and 2: decided from headers alone, before any body byte is read."""
    length = request.META.get("CONTENT_LENGTH", "")
    if not length.isascii() or not length.isdigit() or int(length) > MAX_BODY_BYTES:
        raise ApiError(ErrorCode.VALIDATION_ERROR, BODY_TOO_LARGE_MESSAGE)
    media_type = (request.content_type or "").split(";")[0].strip().lower()
    if media_type != "application/json":
        raise ApiError(ErrorCode.VALIDATION_ERROR, NOT_JSON_CONTENT_TYPE_MESSAGE)
    if int(length) == 0:  # DRF skips the parser for an empty body, which would give per-field errors
        raise ApiError(ErrorCode.VALIDATION_ERROR, NOT_JSON_MESSAGE)


def _call_service(service: Callable[[Any], dict], argument: Any, validated: dict[str, Any]) -> dict:
    try:
        return service(argument)
    except SERVICE_ERRORS as exc:
        raise map_service_error(exc, validated) from exc


class HealthView(APIView):
    """Liveness and keep-warm. Never calls ORS, never throttled."""

    throttle_classes: list = []
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        operation_id="getHealth",
        summary="Liveness check",
        responses={
            200: HealthResponseSerializer,
            500: OpenApiResponse(ErrorResponseSerializer, description="Unexpected error"),
        },
    )
    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "api_version": "1"})


class NotFoundView(APIView):
    """Catch-all for unknown paths.

    With DEBUG on, Django answers an unrouted path with its HTML debug page, which breaks the JSON-only
    error contract on the dev server. A routed view goes through our exception handler instead.
    """

    throttle_classes: list = []
    authentication_classes: list = []
    permission_classes: list = []

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        raise NotFound


class PlanTripView(ContractThrottleMixin, APIView):
    """POST /api/v1/trips/plan."""

    parser_classes = [BoundedJSONParser]
    throttle_classes = PLAN_THROTTLES
    authentication_classes: list = []
    permission_classes: list = []

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        if request.method == "POST":
            _reject_bad_body_headers(request)
        super().initial(request, *args, **kwargs)

    @extend_schema(
        operation_id="planTrip",
        summary="Plan a trip with stops and daily log sheets",
        request=PlanTripSerializer,
        parameters=[_RETRY_AFTER],
        responses={
            200: OpenApiResponse(
                PlanTripResponseSerializer, description="The plan. Cache-Control: no-store."
            ),
            400: _error("VALIDATION_ERROR: the request must change. See field and details."),
            422: _error(
                "LOCATION_NOT_FOUND, UNSUPPORTED_LOCATION, ROUTE_NOT_FOUND or TRIP_TOO_LONG: "
                "the trip cannot be planned as entered."
            ),
            **_COMMON_ERRORS,
            **_UPSTREAM_ERRORS,
        },
    )
    def post(self, request: Request) -> Response:
        with PlanInflightGuard(request):
            validated = validated_plan_request(request.data)
            body = _call_service(plan_trip, validated, validated)
        response = Response(body)
        response["Cache-Control"] = NO_STORE
        return response


class AutocompleteView(ContractThrottleMixin, APIView):
    """GET /api/v1/places/autocomplete?q=."""

    throttled_method = "GET"
    throttle_classes = PLACES_THROTTLES
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        operation_id="autocompletePlaces",
        summary="US place suggestions",
        parameters=[
            OpenApiParameter(
                "q",
                {"type": "string", "minLength": 3, "maxLength": 100},
                required=True,
                description="3 to 100 characters after trimming. No control characters.",
            ),
            _RETRY_AFTER,
        ],
        responses={
            200: OpenApiResponse(
                AutocompleteResponseSerializer,
                description="At most 5 suggestions. Cache-Control: public, max-age=3600.",
            ),
            400: _error("VALIDATION_ERROR: q is missing, too short, too long or has control characters."),
            **_COMMON_ERRORS,
            **_UPSTREAM_ERRORS,
        },
    )
    def get(self, request: Request) -> Response:
        query = validated_query(request.query_params)
        result = _call_service(autocomplete, query, {"q": query})
        response = Response(AutocompleteResponseSerializer(result).data)
        response["Cache-Control"] = AUTOCOMPLETE_CACHE_CONTROL
        return response


class _AnyAccept(BaseContentNegotiation):
    """Static files: browsers send Accept headers our JSON renderer knows nothing about."""

    def select_parser(self, request: Request, parsers: list) -> Any:
        return parsers[0] if parsers else None

    def select_renderer(self, request: Request, renderers: list, format_suffix: str | None = None) -> Any:
        return renderers[0], renderers[0].media_type


@extend_schema(exclude=True)
class DocsAssetView(APIView):
    """Swagger UI static files, throttled so no route is open by accident (contract section 8.1)."""

    throttle_classes = [DocsAssetsIpThrottle]
    authentication_classes: list = []
    permission_classes: list = []
    content_negotiation_class = _AnyAccept

    def get(self, request: Request, path: str) -> Any:
        try:
            return serve(request._request, path, document_root=_SIDECAR_STATIC)
        except SuspiciousOperation as exc:  # path traversal attempt
            raise ApiError(ErrorCode.VALIDATION_ERROR, "The request could not be processed.") from exc
