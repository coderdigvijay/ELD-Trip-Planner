"""Extra routes that exist only in tests, to exercise the error handler paths."""

from django.urls import include, path
from rest_framework import serializers
from rest_framework.exceptions import Throttled
from rest_framework.views import APIView

from trips.errors import ApiError, ErrorCode


class _Boom(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        raise RuntimeError("secret internal detail /srv/app/thing.py")


class _Typed(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        raise ApiError(ErrorCode.LOCATION_NOT_FOUND, "We couldn't find it.", field="pickup_location")


class _Throttled(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        raise Throttled(wait=9999.2)


class _Body(serializers.Serializer):
    cycle = serializers.FloatField(min_value=0, max_value=70)


class _Post(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        serializer = _Body(data=request.data)
        serializer.is_valid(raise_exception=True)
        return


urlpatterns = [
    path("boom", _Boom.as_view()),
    path("typed", _Typed.as_view()),
    path("throttled", _Throttled.as_view()),
    path("post", _Post.as_view()),
    path("", include("config.urls")),
]

handler400 = "trips.errors.handler400"
handler404 = "trips.errors.handler404"
handler500 = "trips.errors.handler500"
