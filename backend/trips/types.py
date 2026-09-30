"""Typed shapes shared between the API layer (serializers) and services.

`PlanRequest` is exactly what `PlanTripSerializer.validated_data` yields (docs/API_CONTRACT.md 5.1),
converted to a plain dict, so `plan_trip(validated: PlanRequest)` never sees DRF types.
"""

import datetime as dt
from typing import TypedDict

from django.db.models import TextChoices

# start_date window, API_CONTRACT 5.1 and 7. One definition for the serializer and plan_trip.
START_DATE_DAYS_BACK = 30
START_DATE_DAYS_AHEAD = 365
_BACK, _AHEAD = START_DATE_DAYS_BACK, START_DATE_DAYS_AHEAD
START_DATE_RANGE_MESSAGE = f"Start date must be within {_BACK} days before and {_AHEAD} days after today."


class PlaceInput(TypedDict):
    """A place chosen from autocomplete. Text is NFC, trimmed, single line. lat/lng are floats in range
    and inside the lower-48 box (the serializer enforces the box, so it raises UNSUPPORTED_LOCATION-style
    422 before the service runs)."""

    label: str
    lat: float
    lng: float


# A location is either a PlaceInput dict or a normalized free-text string (3..200 chars) to geocode.
LocationInput = str | PlaceInput


class LogHeader(TypedDict):
    """All eight keys are always present. "" means "not supplied": the service applies the default
    (main_office_address and home_terminal_address default to the resolved current location label)."""

    driver_name: str
    carrier_name: str
    main_office_address: str
    home_terminal_address: str
    truck_number: str
    trailer_number: str
    shipping_doc: str
    shipper_commodity: str


class PlanRequest(TypedDict):
    current_location: LocationInput
    pickup_location: LocationInput
    dropoff_location: LocationInput
    current_cycle_used_hours: float  # 0..70, multiple of 0.25
    start_date: dt.date | None  # key always present; None means "today in the home-terminal zone"
    start_time: dt.time  # defaults to 08:00, on the 15 minute grid
    log_header: LogHeader


# Wire enums (docs/API_CONTRACT.md section 1). Also the source for the OpenAPI enum component names.
class DutyStatus(TextChoices):
    OFF = "off"
    SLEEPER = "sleeper"
    DRIVING = "driving"
    ON_DUTY = "on_duty"


class StopKind(TextChoices):
    START = "start"
    PICKUP = "pickup"
    DROPOFF = "dropoff"
    FUEL = "fuel"
    BREAK = "break"
    REST = "rest"
    RESTART = "restart"
    END = "end"


class LabelSource(TextChoices):
    INPUT = "input"
    GEOCODED = "geocoded"
    NEARBY = "nearby"
    COORDINATES = "coordinates"


class RouteProfile(TextChoices):
    HGV = "driving-hgv"
    CAR = "driving-car"
