"""The pure response builder (docs/API_CONTRACT.md 4.2 and 5.2): no HTTP, invariants 1 to 17 on many trips."""

from __future__ import annotations

import copy
import datetime as dt
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import hos
from tests.trips.services.invariants import assert_invariants
from trips.services.response import (
    Bounds,
    LegView,
    MileGrid,
    PlaceView,
    PointInfo,
    ResponseBuildError,
    ResponseInput,
    Timing,
    autocomplete_response,
    build_plan_response,
    required_point_keys,
)

PLACES = (
    PlaceView("Chicago, IL", 41.87811, -87.6298, "input"),
    PlaceView("Indianapolis, IN", 39.7684, -86.15804, "geocoded"),
    PlaceView("Denver, CO", 39.73924, -104.99025, "input"),
)
CENTRAL = dt.timezone(dt.timedelta(hours=-5))
TIMING = Timing("America/Chicago", "CDT", -300, "-05:00", dt.datetime(2026, 10, 5, tzinfo=CENTRAL))
BOX = Bounds(39.0, -105.0, 42.0, -86.0)


def make_input(l0, l1, *, cycle_h=0.0, start=480, profile="driving-hgv", points=None) -> ResponseInput:
    """`l0` and `l1` are (miles, minutes)."""
    trip = hos.TripInput(
        (
            hos.Leg(l0[0], l0[1], PLACES[0].label, PLACES[1].label),
            hos.Leg(l1[0], l1[1], PLACES[1].label, PLACES[2].label),
        ),
        round(cycle_h * 60),
        start,
    )
    return ResponseInput(
        places=PLACES,
        legs=(LegView("" if l0[0] == 0 else "abc", *l0, BOX), LegView("def", *l1, BOX)),
        profile=profile,
        plan=hos.plan(trip),
        points=points or {},
        timing=TIMING,
        cycle_used_h=cycle_h,
        log_header={"driver_name": "Jo Driver"},
    )


def build(l0, l1, **kwargs) -> dict:
    base = make_input(l0, l1, **kwargs)
    points = {k: PointInfo(40.0 + k / 1e6, -95.0, f"Mid {k}", "geocoded") for k in required_point_keys(base)}
    return build_plan_response(replace(base, points=points))


SCENARIOS = {
    "short": ((183.0, 180.0), (185.4, 190.8), 10, 480),
    "two_days": ((183.0, 180.0), (1030.0, 990.0), 20, 480),
    "week": ((183.0, 180.0), (2500.0, 2600.0), 0, 480),
    "zero_first_leg": ((0.0, 0.0), (600.0, 600.0), 30, 480),
    "start_restart_70": ((183.0, 180.0), (1030.0, 990.0), 70, 480),
    "start_restart_69_5": ((183.0, 180.0), (400.0, 400.0), 69.5, 1425),
    "near_limit_mid_restart": ((100.0, 100.0), (900.0, 900.0), 60, 480),
    "late_start": ((183.0, 180.0), (1030.0, 990.0), 5, 1425),
    "midnight_start": ((183.0, 180.0), (300.0, 300.0), 5, 0),
    "tiny_second_leg": ((50.0, 50.0), (0.3, 1.0), 5, 480),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_invariant_holds(name):
    l0, l1, cycle, start = SCENARIOS[name]
    body = build(l0, l1, cycle_h=cycle, start=start)
    assert_invariants(body, start_date=dt.date(2026, 10, 5))


@settings(max_examples=40)
@given(
    l0=st.floats(0, 400).map(lambda m: round(m, 1)),
    l1=st.floats(1, 3000).map(lambda m: round(m, 1)),
    mph=st.integers(35, 70),
    cycle=st.integers(0, 280).map(lambda q: q / 4),
    start=st.integers(0, 95).map(lambda q: q * 15),
)
def test_invariants_hold_for_random_trips(l0, l1, mph, cycle, start):
    body = build((l0, l0 / mph * 60), (l1, l1 / mph * 60), cycle_h=cycle, start=start)
    assert_invariants(body)


def test_contract_fragment_5_5_trip_start_restart():
    body = build((183.0, 180.0), (1030.0, 990.0), cycle_h=70, start=480)
    first, second = body["stops"][:2]
    assert (first["id"], first["kind"], first["arrive_at"], first["depart_at"], first["duration_h"]) == (
        "s1",
        "restart",
        "2026-10-05T00:00:00-05:00",
        "2026-10-06T10:00:00-05:00",
        34.0,
    )
    assert (first["cumulative_mi"], first["leg_index"], first["label"]) == (0.0, 0, "Chicago, IL")
    assert (second["kind"], second["arrive_at"], second["duration_h"]) == (
        "start",
        "2026-10-06T10:00:00-05:00",
        0.5,
    )
    assert body["trip"]["warnings"] == [
        {
            "code": "CYCLE_RESTART_AT_START",
            "message": (
                "Cycle at 69.5 hr or more: the trip starts with a 34-hr restart from 00:00, "
                "so the requested start time is not used."
            ),
        }
    ]
    day = body["days"][0]
    assert day["segments"] == [
        {
            "start_min": 0,
            "end_min": 1440,
            "status": "off",
            "location_label": "Chicago, IL",
            "note": "34-hr restart",
            "stationary": True,
            "stop_id": "s1",
        }
    ]
    assert day["remarks"] == [{"minute": 0, "location_label": "Chicago, IL", "note": "34-hr restart"}]
    assert day["recap"] == {
        "on_duty_today": 0.0,
        "a_last7": 70.0,
        "b_available_tomorrow": 70.0,
        "c_last8": 70.0,
        "restart_note": "34-hr restart ends 10/06 10:00",
    }
    assert (
        body["days"][1]["segments"][0]["stop_id"] == "s1" and body["days"][1]["remarks"][0]["minute"] == 600
    )


def test_contract_fragment_5_4_sheet_starting_mid_rest():
    body = build((183.0, 180.0), (1030.0, 990.0), cycle_h=20)
    day2 = body["days"][1]
    assert [(s["status"], s["note"], s["stop_id"]) for s in day2["segments"][:2]] == [
        ("sleeper", "10-hr rest (sleeper)", "s3"),
        ("on_duty", "Pre-trip inspection", "s3"),
    ]
    assert (
        day2["remarks"][0]["minute"] == day2["segments"][1]["start_min"]
    )  # none at 00:00: the rest continues
    rest = body["stops"][2]
    assert rest["kind"] == "rest" and rest["duration_h"] == 10.5 and rest["duty_status"] == "sleeper"


def test_mid_route_places_are_keyed_by_mile_and_stops_come_first():
    base = make_input((183.0, 180.0), (1030.0, 990.0), cycle_h=20)
    keys = required_point_keys(base)
    grid = MileGrid.for_legs(183.0, 1030.0)
    assert keys and not any(grid.is_anchor(k) for k in keys) and len(keys) == len(set(keys))
    rest = next(e for e in base.plan.events if e.kind == hos.Kind.REST)
    assert keys[0] == grid.key(rest.start_mile)


def test_missing_point_is_a_bug_not_a_silent_blank():
    with pytest.raises(KeyError):
        build_plan_response(make_input((183.0, 180.0), (1030.0, 990.0), cycle_h=20))


def test_car_profile_and_approximated_labels_add_warnings_in_contract_order():
    base = make_input((183.0, 180.0), (400.0, 400.0), cycle_h=70, profile="driving-car")
    keys = required_point_keys(base)
    points = {k: PointInfo(40.0, -95.0, "near Chicago, IL", "nearby") for k in keys}
    body = build_plan_response(replace(base, points=points, labels_approximated=True))
    assert [w["code"] for w in body["trip"]["warnings"]] == [
        "CYCLE_RESTART_AT_START",
        "CAR_PROFILE_USED",
        "LABELS_APPROXIMATED",
    ]
    assert body["route"]["profile"] == "driving-car"


def test_log_header_defaults_and_assumptions_are_complete():
    body = build((183.0, 180.0), (185.4, 190.8), cycle_h=10)
    header = body["trip"]["log_header"]
    assert set(header) == {
        "driver_name",
        "carrier_name",
        "main_office_address",
        "home_terminal_address",
        "truck_number",
        "trailer_number",
        "shipping_doc",
        "shipper_commodity",
    }
    assert header["driver_name"] == "Jo Driver" and header["carrier_name"] == ""
    assert header["main_office_address"] == header["home_terminal_address"] == "Chicago, IL"
    assert all(a["text"] for a in body["trip"]["assumptions"]) and len(body["trip"]["assumptions"]) == 17


def test_route_bounds_union_and_zero_leg_polyline():
    body = build((0.0, 0.0), (600.0, 600.0))
    assert body["route"]["legs"][0]["polyline"] == "" and body["route"]["legs"][1]["polyline"] == "def"
    assert body["route"]["bounds"] == {"south": 39.0, "west": -105.0, "north": 42.0, "east": -86.0}


def test_body_contains_only_json_types():
    body = build((183.0, 180.0), (1030.0, 990.0), cycle_h=20)
    assert json.loads(json.dumps(body)) == body


@pytest.mark.parametrize(
    "tamper",
    [
        lambda b: b["days"][0]["segments"][1].update(start_min=495),
        lambda b: b["days"][0]["totals"].update(off=1.0),
        lambda b: b["days"][0]["remarks"].pop(),
        lambda b: b["summary"].update(total_distance_mi=1.0),
        lambda b: b["stops"][1].update(note="Fuel"),
        lambda b: b["timeline"][2].update(stop_id="s9"),
        lambda b: b["trip"]["warnings"].append({"code": "CYCLE_RESTART_AT_START", "message": ""}),
    ],
)
def test_the_invariant_checker_catches_tampering(tamper):
    body = copy.deepcopy(build((183.0, 180.0), (185.4, 190.8), cycle_h=10))
    assert_invariants(body)
    tamper(body)
    with pytest.raises(AssertionError):
        assert_invariants(body)


def test_build_error_is_a_runtime_error():
    assert issubclass(ResponseBuildError, RuntimeError)


# ---- autocomplete (API_CONTRACT 4.2) ----


def test_autocomplete_response_caps_at_five_and_rounds_coordinates():
    places = [SimpleNamespace(label=f"City {i}, ST", lat=37.5407234 + i, lng=-77.4360512) for i in range(7)]
    body = autocomplete_response(places)
    assert len(body["items"]) == 5
    assert body["items"][0] == {"label": "City 0, ST", "lat": 37.54072, "lng": -77.43605}


def test_autocomplete_response_empty():
    assert autocomplete_response([]) == {"items": []}
