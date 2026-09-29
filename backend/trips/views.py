"""Thin views: validate, delegate, respond."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from trips.serializers import ErrorResponseSerializer, HealthResponseSerializer


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
