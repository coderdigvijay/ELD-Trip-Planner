"""Request serializers (input validation) and the error/health response shapes.

Rules: docs/API_CONTRACT.md sections 4.1, 5.1 and 7. `PlanTripSerializer.to_plan_request()` yields the
plain `trips.types.PlanRequest` dict that `plan_trip` receives. Response shapes for docs live in
`trips.response_serializers`.
"""

import datetime as dt
import math
import re
import unicodedata
from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from trips.errors import ApiError, ErrorCode
from trips.types import LogHeader, PlanRequest

LOWER_48_LAT = (24.0, 49.5)
LOWER_48_LNG = (-125.0, -66.5)
DEFAULT_START_TIME = dt.time(8, 0)
START_DATE_DAYS_BACK = 30
START_DATE_DAYS_AHEAD = 365
COORD_DECIMALS = 5

# Rejected in every string: Cc (control incl. CR/LF/TAB), Cf (zero-width, bidi), Cs (lone surrogates),
# Zl/Zp (line and paragraph separators, which would break "single line").
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_WHITESPACE = re.compile(r"\s+")
_DATE_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME_SHAPE = re.compile(r"\d{2}:\d{2}")

PICKUP_EQUALS_DROPOFF = "Pickup and dropoff are the same place. Choose a different dropoff."


def today_utc() -> dt.date:
    """Clock seam for tests. UTC date: the home-terminal zone is unknown until the service geocodes."""
    return dt.datetime.now(dt.UTC).date()


def normalize_text(value: str) -> str | None:
    """NFC, reject forbidden characters, trim, collapse whitespace. None when a forbidden char exists."""
    text = unicodedata.normalize("NFC", value)
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in text):
        return None
    return _WHITESPACE.sub(" ", text).strip()


class CleanTextField(serializers.CharField):
    """Single-line text. Strings only (numbers are not coerced). Length is checked after normalizing."""

    default_error_messages = {
        "invalid": "Enter text.",
        "characters": "Remove line breaks and control or invisible characters.",
    }

    def to_internal_value(self, data: Any) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        text = normalize_text(data)
        if text is None:
            self.fail("characters")
        return text


class FiniteNumberField(serializers.FloatField):
    """A finite JSON number. Booleans, strings, NaN and infinity are rejected before range checks."""

    def to_internal_value(self, data: Any) -> float:
        # bool is a subclass of int in Python, so it needs its own check.
        if isinstance(data, bool) or not isinstance(data, int | float):
            self.fail("invalid")
        try:
            value = float(data)
        except OverflowError:  # an integer literal too large for a float
            self.fail("invalid")
        if not math.isfinite(value):
            self.fail("invalid")
        return value


_CYCLE_MESSAGE = "Cycle hours must be between 0 and 70, in steps of 0.25."


class CycleHoursField(FiniteNumberField):
    """0 to 70 in steps of 0.25. One message for every failure (contract section 6)."""

    default_error_messages = dict.fromkeys(
        ("invalid", "min_value", "max_value", "required", "null"), _CYCLE_MESSAGE
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(min_value=0, max_value=70, **kwargs)

    def to_internal_value(self, data: Any) -> float:
        value = super().to_internal_value(data)
        if not (value * 4).is_integer():
            self.fail("invalid")
        return value


@extend_schema_field({"type": "string", "format": "date"})
class StartDateField(serializers.Field):
    default_error_messages = {
        "invalid": "Enter the start date as YYYY-MM-DD.",
        "range": "Start date must be within 30 days before and 365 days after today.",
    }

    def to_internal_value(self, data: Any) -> dt.date:
        if not isinstance(data, str) or not _DATE_SHAPE.fullmatch(data):
            self.fail("invalid")
        try:
            value = dt.date.fromisoformat(data)
        except ValueError:
            self.fail("invalid")
        today = today_utc()
        if (
            not today - dt.timedelta(days=START_DATE_DAYS_BACK)
            <= value
            <= today + dt.timedelta(days=START_DATE_DAYS_AHEAD)
        ):
            self.fail("range")
        return value

    def to_representation(self, value: dt.date) -> str:
        return value.isoformat()


@extend_schema_field({"type": "string", "pattern": "^([01][0-9]|2[0-3]):(00|15|30|45)$"})
class StartTimeField(serializers.Field):
    default_error_messages = {
        "invalid": "Enter the start time as HH:MM, like 08:15.",
        "grid": "Start time must be on a quarter hour, like 08:15.",
    }

    def to_internal_value(self, data: Any) -> dt.time:
        if not isinstance(data, str) or not _TIME_SHAPE.fullmatch(data):
            self.fail("invalid")
        hour, minute = int(data[:2]), int(data[3:])
        if hour > 23 or minute > 59:
            self.fail("invalid")
        if minute % 15:
            self.fail("grid")
        return dt.time(hour, minute)

    def to_representation(self, value: dt.time) -> str:
        return value.strftime("%H:%M")


@extend_schema_serializer(component_name="PlaceInput")
class PlaceInputSerializer(serializers.Serializer):
    """A place picked from autocomplete. Unknown keys are ignored (contract section 1)."""

    label = CleanTextField(min_length=1, max_length=200)
    lat = FiniteNumberField(min_value=-90, max_value=90)
    lng = FiniteNumberField(min_value=-180, max_value=180)


# The PlaceInput branch is declared here; the free-text `string` branch is added to the LocationInput
# component by trips.schema_hooks (a bare string is not a serializer, which drf-spectacular requires).
@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="LocationInput", serializers=[PlaceInputSerializer], resource_type_field_name=None
    )
)
class LocationInputField(serializers.Field):
    """`string | PlaceInput`. A string is free text to geocode; an object is a PlaceInput."""

    default_error_messages = {"invalid": "Enter a place name or pick one from the suggestions."}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._text = CleanTextField(min_length=3, max_length=200)
        self._place = PlaceInputSerializer()

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str):
            return self._text.run_validation(data)
        if isinstance(data, dict):
            return dict(self._place.run_validation(data))
        raise serializers.ValidationError(self.error_messages["invalid"])

    def to_representation(self, value: Any) -> Any:
        return value


@extend_schema_serializer(component_name="LogHeader")
class LogHeaderSerializer(serializers.Serializer):
    """Header text only; never affects HOS. Missing, null or blank all mean "use the default"."""

    driver_name = CleanTextField(max_length=80, allow_blank=True, allow_null=True, required=False)
    carrier_name = CleanTextField(max_length=100, allow_blank=True, allow_null=True, required=False)
    main_office_address = CleanTextField(max_length=150, allow_blank=True, allow_null=True, required=False)
    home_terminal_address = CleanTextField(max_length=150, allow_blank=True, allow_null=True, required=False)
    truck_number = CleanTextField(max_length=40, allow_blank=True, allow_null=True, required=False)
    trailer_number = CleanTextField(max_length=40, allow_blank=True, allow_null=True, required=False)
    shipping_doc = CleanTextField(max_length=60, allow_blank=True, allow_null=True, required=False)
    shipper_commodity = CleanTextField(max_length=100, allow_blank=True, allow_null=True, required=False)


class PlanTripSerializer(serializers.Serializer):
    current_location = LocationInputField()
    pickup_location = LocationInputField()
    dropoff_location = LocationInputField()
    current_cycle_used_hours = CycleHoursField()
    start_date = StartDateField(required=False)
    start_time = StartTimeField(required=False)
    log_header = LogHeaderSerializer(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> PlanRequest:
        _reject_same_pickup_and_dropoff(attrs["pickup_location"], attrs["dropoff_location"])
        for name in ("current_location", "pickup_location", "dropoff_location"):
            _require_lower_48(name, attrs[name])
        header = attrs.get("log_header") or {}
        return {
            "current_location": attrs["current_location"],
            "pickup_location": attrs["pickup_location"],
            "dropoff_location": attrs["dropoff_location"],
            "current_cycle_used_hours": attrs["current_cycle_used_hours"],
            "start_date": attrs.get("start_date"),
            "start_time": attrs.get("start_time", DEFAULT_START_TIME),
            "log_header": LogHeader(**{key: header.get(key) or "" for key in LogHeader.__annotations__}),
        }


def _reject_same_pickup_and_dropoff(pickup: Any, dropoff: Any) -> None:
    if _same_place(pickup, dropoff):
        raise serializers.ValidationError({"dropoff_location": [PICKUP_EQUALS_DROPOFF]})


def _same_place(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.casefold() == b.casefold()
    if isinstance(a, dict) and isinstance(b, dict):
        return (round(a["lat"], COORD_DECIMALS), round(a["lng"], COORD_DECIMALS)) == (
            round(b["lat"], COORD_DECIMALS),
            round(b["lng"], COORD_DECIMALS),
        )
    return False


def _require_lower_48(field: str, location: Any) -> None:
    if not isinstance(location, dict):
        return
    inside = (
        LOWER_48_LAT[0] <= location["lat"] <= LOWER_48_LAT[1]
        and LOWER_48_LNG[0] <= location["lng"] <= LOWER_48_LNG[1]
    )
    if not inside:
        raise ApiError(
            ErrorCode.UNSUPPORTED_LOCATION,
            "Trips must start, pick up and drop off in the lower 48 states. "
            f'"{location["label"]}" is outside that area.',
            field=field,
        )


class AutocompleteQuerySerializer(serializers.Serializer):
    q = CleanTextField(min_length=3, max_length=100)


def validated_plan_request(data: Any) -> PlanRequest:
    serializer = PlanTripSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data  # type: ignore[return-value]  # validate() returns the TypedDict


def validated_query(params: Any) -> str:
    serializer = AutocompleteQuerySerializer(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["q"]


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
