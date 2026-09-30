"""plan_trip over the real ORS adapter with respx (docs/ARCHITECTURE.md section 4). No real network."""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

import httpx
import pytest

import hos
from config.logging import JsonFormatter
from routing.errors import (
    LocationNotFound,
    RouteNotFound,
    TripTooLong,
    UpstreamAuthError,
    UpstreamQuotaExhausted,
    UpstreamRateLimited,
    UpstreamUnavailable,
)
from tests.trips.services.helpers import (
    BALTIMORE,
    CHICAGO,
    DENVER,
    INDIANAPOLIS,
    NEWARK,
    RICHMOND,
    error_response,
    place,
    request,
)
from tests.trips.services.invariants import assert_invariants
from trips.errors import ApiError, ErrorCode
from trips.services import plan_trip as plan_trip_module
from trips.services.plan_trip import MAX_REVERSE_CALLS, plan_trip

RICHMOND_PLACE = place("Richmond, VA", RICHMOND)
NEWARK_PLACE = place("Newark, NJ", NEWARK)
CHICAGO_PLACE = place("Chicago, IL", CHICAGO)
DALLAS = (32.7767, -96.7970)


def short_trip(ors, **kwargs):
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.leg(BALTIMORE, NEWARK, 185.4, 3.18)
    ors.text("Baltimore, MD", "Baltimore", "MD", BALTIMORE)
    return plan_trip(request(RICHMOND_PLACE, "Baltimore, MD", NEWARK_PLACE, cycle=10, **kwargs))


def long_trip(
    ors,
    *,
    cycle: float = 20,
    date=dt.date(2026, 10, 5),
    start=dt.time(8, 0),
    miles: float = 1030.0,
    mph: float = 62,
):
    ors.leg(CHICAGO, INDIANAPOLIS, 183.0, 3.0)
    ors.leg(INDIANAPOLIS, DENVER, miles, miles / mph)
    return plan_trip(
        request(
            CHICAGO_PLACE,
            place("Indianapolis, IN", INDIANAPOLIS),
            place("Denver, CO", DENVER),
            cycle=cycle,
            date=date,
            start=start,
        )
    )


# ---- happy paths (API_CONTRACT 5.3 example) ----


def test_short_trip_matches_the_contract_example(ors):
    body = short_trip(ors)
    assert_invariants(body, start_date=dt.date(2026, 10, 5))
    trip = body["trip"]
    assert trip["places"]["pickup"] == {
        "label": "Baltimore, MD",
        "lat": BALTIMORE[0],
        "lng": BALTIMORE[1],
        "source": "geocoded",
    }
    assert trip["places"]["current"]["source"] == "input"
    assert trip["timezone"] == {
        "name": "America/New_York",
        "abbreviation": "EDT",
        "utc_offset": "-04:00",
        "utc_offset_min": -240,
    }
    assert trip["start_at"] == "2026-10-05T08:00:00-04:00" and trip["warnings"] == []
    assert [a["id"] for a in trip["assumptions"]] == [f"A{i}" for i in range(1, 18)]
    assert "Richmond, VA, UTC-04:00" in trip["assumptions"][2]["text"]
    assert trip["log_header"]["main_office_address"] == "Richmond, VA"

    route = body["route"]
    assert route["profile"] == "driving-hgv" and route["distance_mi"] == 337.7
    assert [(x["distance_mi"], x["duration_h"], x["planned_driving_h"]) for x in route["legs"]] == [
        (152.3, 2.62, 2.75),
        (185.4, 3.18, 3.25),
    ]
    assert all(x["polyline"] for x in route["legs"])

    assert [(s["kind"], s["label"], s["arrive_at"][11:16], s["cumulative_mi"]) for s in body["stops"]] == [
        ("start", "Richmond, VA", "08:00", 0.0),
        ("pickup", "Baltimore, MD", "11:15", 152.3),
        ("dropoff", "Newark, NJ", "15:30", 337.7),
        ("end", "Newark, NJ", "16:30", 337.7),
    ]
    day = body["days"][0]
    assert day["totals"] == {"off": 15.5, "sleeper": 0.0, "driving": 6.0, "on_duty": 2.5}
    assert [(r["minute"], r["location_label"], r["note"]) for r in day["remarks"]] == [
        (480, "Richmond, VA", "Pre-trip inspection"),
        (510, "Richmond, VA", "Driving"),
        (675, "Baltimore, MD", "Pickup"),
        (735, "Baltimore, MD", "Driving"),
        (930, "Newark, NJ", "Dropoff"),
        (990, "Newark, NJ", "Off duty"),
    ]
    assert day["recap"] == {
        "on_duty_today": 8.5,
        "a_last7": 18.5,
        "b_available_tomorrow": 51.5,
        "c_last8": 18.5,
        "restart_note": None,
    }
    assert body["summary"] == {
        "total_distance_mi": 337.7,
        "driving_h": 6.0,
        "on_duty_not_driving_h": 2.5,
        "on_duty_total_h": 8.5,
        "trip_duration_h": 8.5,
        "arrival_at": "2026-10-05T15:30:00-04:00",
        "released_at": "2026-10-05T16:30:00-04:00",
        "sheet_count": 1,
        "cycle_used_start_h": 10.0,
        "cycle_used_end_h": 18.5,
        "counts": {"fuel": 0, "break": 0, "rest": 0, "restart": 0},
    }


def test_place_inputs_make_no_geocode_calls_and_free_text_geocodes_once(ors):
    short_trip(ors)
    assert ors.search.call_count == 1  # only "Baltimore, MD"
    assert ors.hgv.call_count == 2 and ors.reverse.call_count == 0


def test_multi_day_trip_holds_every_invariant_and_labels_mid_route_places(ors):
    body = long_trip(ors)
    assert_invariants(body, start_date=dt.date(2026, 10, 5))
    kinds = [s["kind"] for s in body["stops"]]
    assert "rest" in kinds and "fuel" in kinds and body["summary"]["sheet_count"] >= 2
    assert body["trip"]["timezone"]["utc_offset"] == "-05:00"
    mid = [s for s in body["stops"] if s["kind"] in ("fuel", "rest", "break")]
    assert all(s["label"] for s in mid)
    assert {s["label_source"] for s in mid} <= {"geocoded", "nearby"}
    assert body["trip"]["warnings"] == []
    assert 0 < len(ors.reverse_points) <= MAX_REVERSE_CALLS
    # stop markers sit on the route, not at the origin
    rest = next(s for s in body["stops"] if s["kind"] == "rest")
    assert CHICAGO[0] - 3 < rest["lat"] < CHICAGO[0] + 3 and rest["lng"] != CHICAGO[1]


def test_every_day_sheet_totals_24_hours_and_splits_a_midnight_drive(ors):
    body = long_trip(ors, start=dt.time(15, 0))
    assert_invariants(body)
    assert all(sum(d["totals"].values()) == 24 for d in body["days"])


def test_same_request_gives_the_same_body(ors):
    first = long_trip(ors)
    second = long_trip(ors)
    assert first == second


# ---- warnings ----


@pytest.mark.parametrize("cycle", [69.5, 70])
def test_cycle_at_or_above_69_5_opens_with_a_restart_and_ignores_start_time(ors, cycle):
    early = long_trip(ors, cycle=cycle, start=dt.time(8, 0))
    late = long_trip(ors, cycle=cycle, start=dt.time(23, 45))
    assert_invariants(early)
    assert early == late
    assert [w["code"] for w in early["trip"]["warnings"]] == ["CYCLE_RESTART_AT_START"]
    assert early["stops"][0]["reason"] == "34-hr restart: 70 hr cycle at 69.5 hr or more at trip start"
    assert early["trip"]["start_at"] == "2026-10-06T10:00:00-05:00"
    assert early["days"][0]["recap"]["restart_note"] == "34-hr restart ends 10/06 10:00"


def test_cycle_69_25_does_not_restart_at_the_start(ors):
    body = long_trip(ors, cycle=69.25)
    assert_invariants(body)
    assert body["stops"][0]["kind"] == "start"


def test_car_profile_fallback_warns_and_routes_every_leg_as_car(ors):
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.leg(BALTIMORE, NEWARK, 185.4, 3.18, car_only=True)
    ors.text("Baltimore, MD", "Baltimore", "MD", BALTIMORE)
    body = plan_trip(request(RICHMOND_PLACE, "Baltimore, MD", NEWARK_PLACE, cycle=10))
    assert_invariants(body)
    assert body["route"]["profile"] == "driving-car"
    assert [w["code"] for w in body["trip"]["warnings"]] == ["CAR_PROFILE_USED"]
    assert ors.car.call_count == 1


def test_reverse_geocode_cap_falls_back_to_near_labels_and_warns(ors):
    body = long_trip(ors, cycle=0, miles=5800.0, mph=45)
    assert_invariants(body)
    assert len(ors.reverse_points) == MAX_REVERSE_CALLS
    assert len(set(ors.reverse_points)) == MAX_REVERSE_CALLS
    assert [w["code"] for w in body["trip"]["warnings"]] == ["LABELS_APPROXIMATED"]
    sources = {s["label_source"] for s in body["stops"]}
    assert "nearby" in sources or "coordinates" in sources
    assert any(s["label"].startswith("near ") for s in body["stops"])


@pytest.mark.parametrize("status", [403, 429, 500])
def test_reverse_geocode_failure_never_fails_the_plan(ors, status):
    ors.reverse_status = status
    body = long_trip(ors)
    assert_invariants(body)
    assert [w["code"] for w in body["trip"]["warnings"]] == ["LABELS_APPROXIMATED"]
    assert all(s["label"] for s in body["stops"])
    fallback = [s for s in body["stops"] if s["label_source"] in ("nearby", "coordinates")]
    assert fallback and all(s["label"].startswith("near ") or "," in s["label"] for s in fallback)


def test_zero_length_first_leg_makes_no_directions_call_for_it(ors):
    ors.leg(RICHMOND, NEWARK, 340.0, 5.9)
    ors.leg(RICHMOND, RICHMOND, 0.0, 0.0)
    body = plan_trip(request(RICHMOND_PLACE, place("Richmond Yard, VA", RICHMOND), NEWARK_PLACE))
    assert_invariants(body)
    assert ors.hgv.call_count == 1
    leg0 = body["route"]["legs"][0]
    assert (leg0["distance_mi"], leg0["duration_h"], leg0["polyline"]) == (0.0, 0.0, "")
    assert [s["kind"] for s in body["stops"]][:2] == ["start", "pickup"]
    assert body["stops"][1]["label"] == "Richmond Yard, VA"
    remarks = body["days"][0]["remarks"]
    assert [r["note"] for r in remarks][:3] == ["Pre-trip inspection", "Pickup", "Driving"]


def test_current_equal_to_dropoff_round_trip_is_allowed(ors):
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.leg(BALTIMORE, RICHMOND, 152.3, 2.62)
    body = plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), RICHMOND_PLACE))
    assert_invariants(body)
    assert body["stops"][-1]["label"] == "Richmond, VA"


def test_start_at_midnight_starts_with_a_shift(ors):
    body = long_trip(ors, start=dt.time(0, 0))
    assert_invariants(body)
    assert body["days"][0]["segments"][0]["note"] == "Pre-trip inspection"


# ---- time handling (ARCHITECTURE 10) ----


@pytest.mark.parametrize(
    ("date", "offset"),
    [(dt.date(2026, 10, 30), "-04:00"), (dt.date(2026, 3, 7), "-05:00"), (dt.date(2026, 11, 1), "-05:00")],
)
def test_offset_is_frozen_when_the_trip_crosses_a_dst_change(ors, monkeypatch, date, offset):
    monkeypatch.setattr(
        plan_trip_module, "_utc_now", lambda: dt.datetime.combine(date, dt.time(12), tzinfo=dt.UTC)
    )
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.leg(BALTIMORE, DALLAS, 1370.0, 22.0)
    body = plan_trip(
        request(
            RICHMOND_PLACE,
            place("Baltimore, MD", BALTIMORE),
            place("Dallas, TX", DALLAS),
            date=date,
            start=dt.time(15, 0),
        )
    )
    assert_invariants(body, start_date=date)
    assert body["trip"]["timezone"]["utc_offset"] == offset
    assert {s["arrive_at"][-6:] for s in body["stops"]} == {offset}
    assert {p["start_at"][-6:] for p in body["timeline"]} == {offset}
    assert len(body["days"]) >= 3 and all(sum(d["totals"].values()) == 24 for d in body["days"])
    stamps = [d["date"] for d in body["days"]]
    assert stamps == [(date + dt.timedelta(days=i)).isoformat() for i in range(len(stamps))]


@pytest.mark.parametrize("days", [-31, 366])
def test_start_date_outside_the_home_zone_window_is_a_validation_error(ors, days):
    today = plan_trip_module._utc_now().astimezone(ZoneInfo("America/New_York")).date()
    with pytest.raises(ApiError) as caught:
        short_trip(ors, date=today + dt.timedelta(days=days))
    assert caught.value.code is ErrorCode.VALIDATION_ERROR and caught.value.field == "start_date"


@pytest.mark.parametrize("days", [-30, 0, 365])
def test_start_date_window_edges_are_accepted(ors, days):
    today = plan_trip_module._utc_now().astimezone(ZoneInfo("America/New_York")).date()
    assert_invariants(short_trip(ors, date=today + dt.timedelta(days=days)))


def test_missing_start_date_means_today_in_the_home_zone(ors):
    body = short_trip(ors, date=None)
    assert_invariants(body)
    today = dt.datetime.now(dt.UTC).date()
    assert abs((dt.date.fromisoformat(body["days"][0]["date"]) - today).days) <= 1


# ---- failures: adapter exceptions propagate, user errors are ApiError ----


def test_pickup_equal_to_dropoff_is_a_validation_error_before_any_directions_call(ors):
    with pytest.raises(ApiError) as caught:
        plan_trip(request(RICHMOND_PLACE, NEWARK_PLACE, place("Newark again", NEWARK)))
    assert caught.value.code is ErrorCode.VALIDATION_ERROR and caught.value.field == "dropoff_location"
    assert ors.hgv.call_count == 0


def test_ors_returning_a_zero_second_leg_is_a_validation_error(ors):
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.leg(BALTIMORE, NEWARK, 0.0, 0.0)
    with pytest.raises(ApiError) as caught:
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))
    assert caught.value.code is ErrorCode.VALIDATION_ERROR and caught.value.field == "dropoff_location"


def test_unknown_free_text_is_location_not_found_naming_the_field(ors):
    with pytest.raises(LocationNotFound) as caught:
        plan_trip(request("Nowhere at all", NEWARK_PLACE, RICHMOND_PLACE))
    assert caught.value.field == "current_location"


def test_first_failing_field_wins_regardless_of_thread_timing(ors):
    with pytest.raises(LocationNotFound) as caught:
        plan_trip(request("Nowhere one", NEWARK_PLACE, "Nowhere two"))
    assert caught.value.field == "current_location"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(429, headers={"x-ratelimit-reset": "50"}), UpstreamRateLimited),
        (httpx.Response(403), UpstreamQuotaExhausted),
        (httpx.Response(401), UpstreamAuthError),
        (httpx.Response(503), UpstreamUnavailable),
        (error_response(400, 2004), TripTooLong),
    ],
)
def test_directions_failures_raise_the_adapter_exception(ors, response, expected):
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.hgv.mock(return_value=response)
    with pytest.raises(expected):
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))


def test_route_not_found_when_hgv_and_car_are_both_unroutable(ors):
    ors.hgv.mock(return_value=error_response(404, 2010))
    ors.car.mock(return_value=error_response(404, 2010))
    with pytest.raises(RouteNotFound):
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))


def test_total_over_6000_miles_is_trip_too_long(ors):
    ors.leg(RICHMOND, BALTIMORE, 3100.0, 50.0)
    ors.leg(BALTIMORE, NEWARK, 3000.0, 48.0)
    with pytest.raises(TripTooLong):
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))


def test_engine_rejection_of_route_derived_data_is_trip_too_long(ors):
    ors.leg(RICHMOND, BALTIMORE, 500.0, 1.0)  # 500 mph
    ors.leg(BALTIMORE, NEWARK, 185.4, 3.18)
    with pytest.raises(ApiError) as caught:
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))
    assert caught.value.code is ErrorCode.TRIP_TOO_LONG


def test_tiny_slow_leg_is_clamped_to_the_speed_floor_not_a_500(ors):
    ors.leg(RICHMOND, BALTIMORE, 0.01, 5 / 60)  # 10 m in 5 s
    ors.leg(BALTIMORE, NEWARK, 185.4, 3.18)
    body = plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))
    assert_invariants(body)


def test_slow_leg_reports_the_raw_ors_duration_but_plans_with_the_floor(ors):
    ors.leg(RICHMOND, BALTIMORE, 100.0, 100.0)  # 1 mph: the engine floors it at 5 mph (20 h)
    ors.leg(BALTIMORE, NEWARK, 185.4, 3.18)
    body = plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))
    first = body["route"]["legs"][0]
    assert first["duration_h"] == 100.0
    assert first["planned_driving_h"] == 20.0


def test_engine_rejection_uses_the_contract_wording(ors):
    ors.leg(RICHMOND, BALTIMORE, 500.0, 1.0)
    ors.leg(BALTIMORE, NEWARK, 185.4, 3.18)
    with pytest.raises(ApiError) as caught:
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))
    assert caught.value.message == "This trip is too long to plan (over 6,000 miles). Try a shorter route."


def test_leg_over_the_engine_duration_cap_is_trip_too_long(ors):
    ors.leg(RICHMOND, BALTIMORE, 152.3, 2.62)
    ors.leg(BALTIMORE, NEWARK, 1900.0, 400.0)  # 400 h, over 14 days of driving
    with pytest.raises(ApiError) as caught:
        plan_trip(request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE))
    assert caught.value.code is ErrorCode.TRIP_TOO_LONG and caught.value.http_status == 422


def test_engine_bug_is_internal(ors, monkeypatch):
    def boom(_inp):
        raise hos.HosEngineError("x")

    monkeypatch.setattr(hos, "plan", boom)
    with pytest.raises(ApiError) as caught:
        short_trip(ors)
    assert caught.value.code is ErrorCode.INTERNAL


# ---- observability (ARCHITECTURE 11) ----


def test_plan_completed_line_has_metrics_and_no_locations(ors, caplog):
    with caplog.at_level(logging.INFO, logger="eld.trips"):
        short_trip(ors)
    lines = [r for r in caplog.records if r.getMessage() == "plan_completed"]
    assert len(lines) == 1
    record = lines[0]
    assert (record.status, record.profile_used, record.days, record.total_miles) == (
        "ok",
        "driving-hgv",
        1,
        337.7,
    )
    assert set(record.steps_ms) >= {"resolve", "directions", "engine", "labels", "response"}
    text = JsonFormatter().format(record)
    for secret in ("Richmond", "Baltimore", "Newark", str(RICHMOND[0]), str(NEWARK[1])):
        assert secret not in text


def _plan_completed(caplog):
    return [r for r in caplog.records if r.getMessage() == "plan_completed"]


def test_plan_completed_counts_ors_calls_and_cache_hits_by_kind(ors, caplog):
    with caplog.at_level(logging.INFO, logger="eld.trips"):
        short_trip(ors)
        short_trip(ors)  # second identical plan: geocode and directions come from the caches
    first, second = _plan_completed(caplog)
    assert first.ors_calls["geocode"] == 1 and first.ors_calls["directions"] == 2
    assert first.cache_hits == {}
    assert second.ors_calls.get("geocode", 0) == 0 and second.ors_calls.get("directions", 0) == 0
    assert second.cache_hits["geocode"] == 1 and second.cache_hits["directions"] == 2
    for record in (first, second):
        text = JsonFormatter().format(record)
        for secret in ("Richmond", "Baltimore", "Newark", str(RICHMOND[0]), str(NEWARK[1]), "127.0.0.1"):
            assert secret not in text


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("route_not_found", "ROUTE_NOT_FOUND"),
        ("unavailable", "UPSTREAM_UNAVAILABLE"),
        ("location", "LOCATION_NOT_FOUND"),
    ],
)
def test_plan_completed_carries_the_api_code_for_routing_errors(ors, caplog, setup, code):
    if setup == "route_not_found":
        ors.hgv.mock(return_value=error_response(404, 2010))
        ors.car.mock(return_value=error_response(404, 2010))
        trip = request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE)
    elif setup == "unavailable":
        ors.hgv.mock(return_value=httpx.Response(503))
        trip = request(RICHMOND_PLACE, place("Baltimore, MD", BALTIMORE), NEWARK_PLACE)
    else:
        trip = request("Nowhere at all", NEWARK_PLACE, RICHMOND_PLACE)
    with caplog.at_level(logging.INFO, logger="eld.trips"), pytest.raises(Exception):  # noqa: B017,PT011
        plan_trip(trip)
    (record,) = _plan_completed(caplog)
    assert record.code == code


def test_failed_plan_still_logs_one_plan_completed_line(ors, caplog):
    with caplog.at_level(logging.INFO, logger="eld.trips"), pytest.raises(LocationNotFound):
        plan_trip(request("Nowhere at all", NEWARK_PLACE, RICHMOND_PLACE))
    lines = [r for r in caplog.records if r.getMessage() == "plan_completed"]
    assert len(lines) == 1 and lines[0].status == "error" and lines[0].error_class == "LocationNotFound"
    assert "Nowhere" not in JsonFormatter().format(lines[0])
