"""Response shapes for the OpenAPI schema only (docs/API_CONTRACT.md 5.2 and section 10).

The views return the service's plain dict; these classes describe it so the generated TypeScript
types match the contract field for field. Names map to the component names in contract section 10.
"""

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from trips.types import DutyStatus, LabelSource, RouteProfile, StopKind


class PlaceSuggestionSerializer(serializers.Serializer):
    label = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class AutocompleteResponseSerializer(serializers.Serializer):
    items = PlaceSuggestionSerializer(many=True)


class ResolvedPlaceSerializer(serializers.Serializer):
    label = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    source = serializers.ChoiceField(choices=LabelSource.choices)


class ResolvedPlacesSerializer(serializers.Serializer):
    current = ResolvedPlaceSerializer()
    pickup = ResolvedPlaceSerializer()
    dropoff = ResolvedPlaceSerializer()


class TimezoneInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    abbreviation = serializers.CharField()
    utc_offset = serializers.CharField()
    utc_offset_min = serializers.IntegerField()


@extend_schema_serializer(component_name="LogHeader")
class LogHeaderResponseSerializer(serializers.Serializer):
    driver_name = serializers.CharField(allow_blank=True)
    carrier_name = serializers.CharField(allow_blank=True)
    main_office_address = serializers.CharField(allow_blank=True)
    home_terminal_address = serializers.CharField(allow_blank=True)
    truck_number = serializers.CharField(allow_blank=True)
    trailer_number = serializers.CharField(allow_blank=True)
    shipping_doc = serializers.CharField(allow_blank=True)
    shipper_commodity = serializers.CharField(allow_blank=True)


class AssumptionSerializer(serializers.Serializer):
    id = serializers.CharField()
    text = serializers.CharField()


class WarningSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="Open enum: CYCLE_RESTART_AT_START, CAR_PROFILE_USED, LABELS_APPROXIMATED."
    )
    message = serializers.CharField()


class TripMetaSerializer(serializers.Serializer):
    places = ResolvedPlacesSerializer()
    timezone = TimezoneInfoSerializer()
    start_at = serializers.CharField(help_text="ISO 8601 with the frozen trip offset.")
    cycle_used_start_h = serializers.FloatField()
    log_header = LogHeaderResponseSerializer()
    assumptions = AssumptionSerializer(many=True)
    warnings = WarningSerializer(many=True)


class BoundsSerializer(serializers.Serializer):
    south = serializers.FloatField()
    west = serializers.FloatField()
    north = serializers.FloatField()
    east = serializers.FloatField()


class RouteLegSerializer(serializers.Serializer):
    index = serializers.IntegerField(min_value=0, max_value=1)
    from_label = serializers.CharField()
    to_label = serializers.CharField()
    distance_mi = serializers.FloatField()
    duration_h = serializers.FloatField()
    planned_driving_h = serializers.FloatField()
    polyline = serializers.CharField(allow_blank=True, help_text="Encoded polyline, precision 5.")
    bounds = BoundsSerializer()


class RouteSerializer(serializers.Serializer):
    profile = serializers.ChoiceField(choices=RouteProfile.choices)
    distance_mi = serializers.FloatField()
    planned_driving_h = serializers.FloatField()
    bounds = BoundsSerializer()
    legs = RouteLegSerializer(many=True)


class StopSerializer(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.ChoiceField(choices=StopKind.choices)
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    label = serializers.CharField()
    label_source = serializers.ChoiceField(choices=LabelSource.choices)
    arrive_at = serializers.CharField()
    depart_at = serializers.CharField()
    duration_h = serializers.FloatField()
    duty_status = serializers.ChoiceField(choices=DutyStatus.choices)
    cumulative_mi = serializers.FloatField()
    leg_index = serializers.IntegerField(min_value=0, max_value=1)
    note = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)


class TimelineEventSerializer(serializers.Serializer):
    start_min = serializers.IntegerField()
    end_min = serializers.IntegerField()
    start_at = serializers.CharField()
    end_at = serializers.CharField()
    status = serializers.ChoiceField(choices=DutyStatus.choices)
    stop_id = serializers.CharField(allow_null=True)
    start_label = serializers.CharField()
    end_label = serializers.CharField()
    start_mi = serializers.FloatField()
    end_mi = serializers.FloatField()
    note = serializers.CharField()


class LogSegmentSerializer(serializers.Serializer):
    start_min = serializers.IntegerField(min_value=0, max_value=1440)
    end_min = serializers.IntegerField(min_value=0, max_value=1440)
    status = serializers.ChoiceField(choices=DutyStatus.choices)
    location_label = serializers.CharField()
    note = serializers.CharField()
    stationary = serializers.BooleanField()
    stop_id = serializers.CharField(allow_null=True)


class LogRemarkSerializer(serializers.Serializer):
    minute = serializers.IntegerField(min_value=0, max_value=1439)
    location_label = serializers.CharField()
    note = serializers.CharField()


class LogTotalsSerializer(serializers.Serializer):
    off = serializers.FloatField()
    sleeper = serializers.FloatField()
    driving = serializers.FloatField()
    on_duty = serializers.FloatField()


class LogRecapSerializer(serializers.Serializer):
    on_duty_today = serializers.FloatField()
    a_last7 = serializers.FloatField()
    b_available_tomorrow = serializers.FloatField()
    c_last8 = serializers.FloatField()
    restart_note = serializers.CharField(allow_null=True)


class LogDaySerializer(serializers.Serializer):
    date = serializers.CharField(help_text="YYYY-MM-DD in the frozen trip offset.")
    sheet_index = serializers.IntegerField(min_value=1)
    from_label = serializers.CharField()
    to_label = serializers.CharField()
    miles_driven = serializers.FloatField()
    segments = LogSegmentSerializer(many=True)
    remarks = LogRemarkSerializer(many=True)
    totals = LogTotalsSerializer()
    recap = LogRecapSerializer()


class StopCountsSerializer(serializers.Serializer):
    fuel = serializers.IntegerField()
    # `break` is a Python keyword, so it is declared through the class namespace.
    vars()["break"] = serializers.IntegerField()
    rest = serializers.IntegerField()
    restart = serializers.IntegerField()


class TripSummarySerializer(serializers.Serializer):
    total_distance_mi = serializers.FloatField()
    driving_h = serializers.FloatField()
    on_duty_not_driving_h = serializers.FloatField()
    on_duty_total_h = serializers.FloatField()
    trip_duration_h = serializers.FloatField()
    arrival_at = serializers.CharField()
    released_at = serializers.CharField()
    sheet_count = serializers.IntegerField(min_value=1)
    cycle_used_start_h = serializers.FloatField()
    cycle_used_end_h = serializers.FloatField()
    counts = StopCountsSerializer()


class PlanTripResponseSerializer(serializers.Serializer):
    trip = TripMetaSerializer()
    route = RouteSerializer()
    stops = StopSerializer(many=True)
    timeline = TimelineEventSerializer(many=True)
    days = LogDaySerializer(many=True)
    summary = TripSummarySerializer()
