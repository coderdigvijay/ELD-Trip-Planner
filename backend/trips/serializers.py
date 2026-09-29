"""Serializers. Step 1 has only the response shapes needed by the OpenAPI schema."""

from rest_framework import serializers

from trips.errors import ErrorCode


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok"])
    api_version = serializers.ChoiceField(choices=["1"])


class FieldErrorSerializer(serializers.Serializer):
    field = serializers.CharField()
    message = serializers.CharField()


class ErrorBodySerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=[code.value for code in ErrorCode])
    message = serializers.CharField()
    field = serializers.CharField(required=False)
    details = FieldErrorSerializer(many=True, required=False)
    retry_after_s = serializers.IntegerField(required=False, min_value=1, max_value=300)
    request_id = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorBodySerializer()
