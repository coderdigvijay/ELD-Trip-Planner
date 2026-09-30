"""ORS adapter tests over respx (docs/TEST_PLAN.md section 4, O-01..O-29). No real network."""

from __future__ import annotations

import json
import logging
import sys

import httpx
import polyline
import pytest
from django.core.cache import caches

from config.logging import JsonFormatter
from routing import budgets, ors_client
from routing.errors import (
    DeadlineExceeded,
    LocationNotFound,
    RouteNotFound,
    RoutingError,
    TripTooLong,
    UnsupportedLocation,
    UpstreamAuthError,
    UpstreamBadRequest,
    UpstreamBadResponse,
    UpstreamQuotaExhausted,
    UpstreamRateLimited,
    UpstreamUnavailable,
)
from routing.models import METERS_PER_MILE, LegRoute, Place
from tests.routing.conftest import BASE, TEST_KEY
from trips.services.deadline import Deadline

START = Place("Richmond, VA", 37.54072, -77.43605)
END = Place("Charlotte, NC", 35.22709, -80.84313)
SECRET_TEXT = "Secretville Zzyzx Rd"

GOOD_ROUTE = {
    "routes": [
        {
            "summary": {"distance": 160934.4, "duration": 5400.0},
            "geometry": "_p~iF~ps|U_ulLnnqC",
            "segments": [{"distance": 160934.4, "duration": 5400.0}],
        }
    ]
}
HGV_URL = f"{BASE}/v2/directions/driving-hgv/json"
CAR_URL = f"{BASE}/v2/directions/driving-car/json"


def ok(payload=GOOD_ROUTE) -> httpx.Response:
    return httpx.Response(200, json=payload)


def ors_error(status: int, code: int) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": "secret upstream text"}})


def feature(lng, lat, **props) -> dict:
    base = {"layer": "locality", "locality": "Richmond", "region_a": "VA", "name": "Richmond"}
    return {"geometry": {"coordinates": [lng, lat]}, "properties": {**base, **props}}


def geocode_ok(*features) -> httpx.Response:
    return httpx.Response(200, json={"features": list(features)})


def leg(deadline: Deadline | None = None) -> LegRoute:
    return ors_client.directions_leg(START, END, deadline or Deadline())


# ---- directions: retries, O-01 .. O-05 ----


def test_o01_connect_timeout_twice(ors, naps):
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.ConnectTimeout("t"), httpx.ConnectTimeout("t")]
    with pytest.raises(UpstreamUnavailable):
        leg()
    assert route.call_count == 2
    assert len(naps) == 1 and 0.2 <= naps[0] <= 0.8  # jittered
    assert caches["routes"].get("anything") is None


def test_o02_read_timeout_then_success(ors):
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.ReadTimeout("t"), ok()]
    assert leg().profile == "driving-hgv"
    assert route.call_count == 2


def test_o03_500_then_success(ors):
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.Response(500), ok()]
    assert leg().distance_m == 160934.4
    assert route.call_count == 2


def test_o04_502_twice(ors):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(UpstreamUnavailable):
        leg()
    assert route.call_count == 2


def test_o05_retry_after_beyond_the_deadline_is_not_waited_for(ors, naps):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(503, headers={"Retry-After": "120"}))
    with pytest.raises(UpstreamUnavailable):
        leg(Deadline(20))
    assert route.call_count == 1
    assert naps == []


def test_503_retry_after_inside_the_deadline_is_honoured(ors, naps):
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.Response(503, headers={"Retry-After": "3"}), ok()]
    leg()
    assert naps == [3.0]


# ---- 429 / 403 / 401, O-06 .. O-09 ----


def test_o06_429_with_reset_inside_deadline_then_success(ors, naps):
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.Response(429, headers={"x-ratelimit-reset": "3"}), ok()]
    leg()
    assert route.call_count == 2 and naps == [3.0]


def test_429_epoch_reset_is_converted_to_seconds(ors, naps, monkeypatch):
    monkeypatch.setattr(ors_client.time, "time", lambda: 1_800_000_000.0)
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.Response(429, headers={"x-ratelimit-reset": "1800000004"}), ok()]
    leg()
    assert naps == [4.0]


@pytest.mark.parametrize(
    ("headers", "expected"), [({}, 60.0), ({"x-ratelimit-reset": "7"}, 7.0), ({"retry-after": "9"}, 9.0)]
)
def test_o07_429_twice(ors, headers, expected):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(429, headers=headers))
    with pytest.raises(UpstreamRateLimited) as info:
        leg()
    assert route.call_count == 2
    assert info.value.retry_after_s == expected


def test_429_reset_beyond_the_deadline_is_not_retried(ors):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(429, headers={"x-ratelimit-reset": "50"}))
    with pytest.raises(UpstreamRateLimited):
        leg(Deadline(20))
    assert route.call_count == 1


def test_o08_403_is_daily_quota_without_retry(ors):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(403))
    with pytest.raises(UpstreamQuotaExhausted) as info:
        leg()
    assert route.call_count == 1
    assert info.value.scope == "day" and info.value.retry_after_s is None


def test_o09_401_is_a_config_error_logged_critical_without_the_key(ors, caplog):
    caplog.set_level(logging.DEBUG)
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(401, text=f"bad key {TEST_KEY}"))
    with pytest.raises(UpstreamAuthError) as info:
        leg()
    assert route.call_count == 1
    assert TEST_KEY not in str(info.value)
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)
    assert TEST_KEY not in caplog.text


def test_missing_key_fails_without_calling_ors(ors, settings):
    settings.ORS_API_KEY = ""
    route = ors.post(HGV_URL)
    with pytest.raises(UpstreamAuthError):
        leg()
    assert route.call_count == 0


# ---- malformed bodies, O-10 .. O-12 ----


def test_o10_non_json_body(ors):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(200, text="not json"))
    with pytest.raises(UpstreamBadResponse):
        leg()
    assert route.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"routes": []},
        {"routes": [{"geometry": "abc"}]},
        {"routes": [{"summary": {"duration": 1}, "geometry": "abc"}]},
        {"routes": [{"summary": {"distance": 1, "duration": 1}, "geometry": ""}]},
        {"routes": [{"summary": {"distance": "12", "duration": 1}, "geometry": "abc"}]},
        {"routes": [{"summary": {"distance": True, "duration": 1}, "geometry": "abc"}]},
        {"routes": [{"summary": {"distance": 1, "duration": 1}, "geometry": "abc", "segments": [{}, {}]}]},
        [],
    ],
)
def test_o11_missing_or_empty_routes_and_fields(ors, payload):
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(UpstreamBadResponse):
        leg()
    assert route.call_count == 1


@pytest.mark.parametrize("raw", ["-5", "NaN", "Infinity", "-Infinity"])
def test_o12_negative_and_non_finite_distance(ors, raw):
    body = f'{{"routes":[{{"summary":{{"distance":{raw},"duration":10}},"geometry":"abc"}}]}}'
    ors.post(HGV_URL).mock(return_value=httpx.Response(200, content=body.encode()))
    with pytest.raises(UpstreamBadResponse):
        leg()


# ---- profiles and codes, O-13 .. O-18 ----


def test_o13_2009_falls_back_to_car_once_and_caches_the_result(ors):
    hgv = ors.post(HGV_URL).mock(return_value=ors_error(404, 2009))
    car = ors.post(CAR_URL).mock(return_value=ok())
    result = leg()
    assert result.profile == "driving-car"
    assert (hgv.call_count, car.call_count) == (1, 1)
    car_body = json.loads(car.calls.last.request.content)
    assert "options" not in car_body
    assert json.loads(hgv.calls.last.request.content)["options"] == {"vehicle_type": "hgv"}
    assert leg() == result  # cached: no more calls
    assert (hgv.call_count, car.call_count) == (1, 1)


def test_o14_2010_on_both_profiles_is_route_not_found_and_negative_cached(ors):
    hgv = ors.post(HGV_URL).mock(return_value=ors_error(404, 2010))
    car = ors.post(CAR_URL).mock(return_value=ors_error(404, 2010))
    with pytest.raises(RouteNotFound):
        leg()
    assert (hgv.call_count, car.call_count) == (1, 1)
    with pytest.raises(RouteNotFound):
        leg()
    assert (hgv.call_count, car.call_count) == (1, 1)


def test_o15_2004_is_trip_too_long_without_car_retry(ors):
    hgv = ors.post(HGV_URL).mock(return_value=ors_error(400, 2004))
    with pytest.raises(TripTooLong):
        leg()
    assert hgv.call_count == 1


def test_o16_two_legs_over_6000_miles():
    a = LegRoute("x", 3000.05 * METERS_PER_MILE, 1.0, "driving-hgv")
    ors_client.ensure_total_within_limit([LegRoute("x", 3000 * METERS_PER_MILE, 1.0, "driving-hgv")] * 2)
    with pytest.raises(TripTooLong):
        ors_client.ensure_total_within_limit([a, a])


def test_o17_2099_is_transient_and_retried_once(ors):
    route = ors.post(HGV_URL).mock(return_value=ors_error(500, 2099))
    with pytest.raises(UpstreamUnavailable):
        leg()
    assert route.call_count == 2


def test_other_4xx_is_our_bug(ors):
    route = ors.post(HGV_URL).mock(return_value=ors_error(400, 2003))
    with pytest.raises(UpstreamBadRequest):
        leg()
    assert route.call_count == 1


def test_o18_zero_length_leg_makes_no_call(ors):
    same = Place("x", START.lat + 0.000004, START.lng - 0.000004)  # equal at 5 dp
    result = ors_client.directions_leg(START, same, Deadline())
    assert (result.distance_m, result.duration_s) == (0.0, 0.0)
    assert result.profile == "driving-hgv"
    assert result.polyline == polyline.encode([(37.54072, -77.43605)] * 2)


def test_directions_request_shape(ors):
    route = ors.post(HGV_URL).mock(return_value=ok())
    leg()
    request = route.calls.last.request
    assert json.loads(request.content) == {
        "coordinates": [[START.lng, START.lat], [END.lng, END.lat]],
        "units": "m",
        "instructions": False,
        "radiuses": [-1, -1],
        "options": {"vehicle_type": "hgv"},
    }


# ---- geocode, O-19 .. O-21 ----


def test_o19_empty_features_is_location_not_found_and_cached(ors):
    route = ors.get(f"{BASE}/geocode/search").mock(return_value=geocode_ok())
    with pytest.raises(LocationNotFound) as info:
        ors_client.geocode_search("Nowhere", "current", Deadline())
    assert info.value.field == "current" and route.call_count == 1
    with pytest.raises(LocationNotFound):
        ors_client.geocode_search(" nowhere ", "pickup", Deadline())
    assert route.call_count == 1


def test_o20_honolulu_is_unsupported(ors):
    ors.get(f"{BASE}/geocode/search").mock(
        return_value=geocode_ok(feature(-157.85, 21.31, locality="Honolulu", region_a="HI"))
    )
    with pytest.raises(UnsupportedLocation) as info:
        ors_client.geocode_search("Honolulu", "dropoff", Deadline())
    assert info.value.field == "dropoff" and info.value.label == "Honolulu, HI"


def test_o21_spent_geocode_budget_makes_no_call(ors, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "geocode", budgets.Budget(0, 900))
    route = ors.get(f"{BASE}/geocode/search")
    with pytest.raises(UpstreamQuotaExhausted):
        ors_client.geocode_search("Dallas, TX", "current", Deadline())
    assert route.call_count == 0


def test_geocode_success_parses_lng_lat_order_and_label(ors):
    ors.get(f"{BASE}/geocode/search").mock(
        return_value=geocode_ok(feature(-77.43605, 37.54072, label="Richmond, VA, USA"))
    )
    place = ors_client.geocode_search("Richmond VA", "current", Deadline())
    assert place == Place("Richmond, VA", 37.54072, -77.43605)


@pytest.mark.parametrize(
    "bad",
    [
        {"geometry": {"coordinates": [float("nan"), 30.0]}, "properties": {"label": "X, TX, USA"}},
        {"geometry": {"coordinates": [-80.0]}, "properties": {}},
        {"geometry": {"coordinates": [-80.0, 300.0]}, "properties": {"label": "X, TX, USA"}},
        "junk",
    ],
)
def test_geocode_malformed_feature_is_bad_response(ors, bad):
    ors.get(f"{BASE}/geocode/search").mock(
        return_value=httpx.Response(200, content=json.dumps({"features": [bad]}).encode())
    )
    with pytest.raises(UpstreamBadResponse):
        ors_client.geocode_search("Dallas", "current", Deadline())


def test_upstream_label_is_sanitized(ors):
    ors.get(f"{BASE}/geocode/search").mock(
        return_value=geocode_ok(feature(-97.0, 32.8, locality="Dal​las\x00", name="x" * 500, region_a="TX"))
    )
    assert ors_client.geocode_search("Dallas", "current", Deadline()).label == "Dallas, TX"


# ---- reverse, O-22 ----


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403),
        httpx.Response(429),
        httpx.Response(200, text="junk"),
        httpx.Response(200, json={"features": "no"}),
        httpx.ReadTimeout("t"),
    ],
)
def test_o22_reverse_failures_are_swallowed(ors, response):
    ors.get(f"{BASE}/geocode/reverse").mock(side_effect=[response, response])
    assert ors_client.reverse_label(37.5, -77.4, Deadline()) is None


def test_reverse_uses_coarse_layers_rounds_and_caches(ors):
    route = ors.get(f"{BASE}/geocode/reverse").mock(
        return_value=geocode_ok(feature(-77.44, 37.54, locality="Richmond"))
    )
    assert ors_client.reverse_label(37.5449, -77.4351, Deadline()) == "Richmond, VA"
    assert ors_client.reverse_label(37.5401, -77.4399, Deadline()) == "Richmond, VA"
    assert route.call_count == 1
    params = route.calls.last.request.url.params
    assert params["layers"] == "locality,localadmin,county"
    assert params["size"] == "1"
    assert params["point.lat"] == "37.54" and params["point.lon"] == "-77.44"


def test_reverse_empty_result_is_negative_cached(ors):
    route = ors.get(f"{BASE}/geocode/reverse").mock(return_value=geocode_ok())
    assert ors_client.reverse_label(40.0, -100.0, Deadline()) is None
    assert ors_client.reverse_label(40.0, -100.0, Deadline()) is None
    assert route.call_count == 1


def test_reverse_spent_budget_is_none_not_an_error(ors, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "reverse", budgets.Budget(0, 900))
    route = ors.get(f"{BASE}/geocode/reverse")
    assert ors_client.reverse_label(40.0, -100.0, Deadline()) is None
    assert route.call_count == 0


# ---- autocomplete, O-24 ----


def test_o24_autocomplete_error_is_one_attempt_with_a_5s_timeout(ors):
    route = ors.get(f"{BASE}/geocode/autocomplete").mock(return_value=httpx.Response(500))
    with pytest.raises(UpstreamUnavailable):
        ors_client.autocomplete("Richm")
    assert route.call_count == 1
    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["read"] <= 5.0 and timeout["connect"] == 3.0


def test_autocomplete_filters_outside_lower_48_caps_at_five_and_caches(ors):
    features = [feature(-77.4 - i / 10, 37.5) for i in range(7)]
    features.insert(1, feature(-149.9, 61.2, locality="Anchorage", region_a="AK"))
    route = ors.get(f"{BASE}/geocode/autocomplete").mock(return_value=geocode_ok(*features))
    items = ors_client.autocomplete("Richm")
    assert len(items) == 5 and all(p.label == "Richmond, VA" for p in items)
    assert ors_client.autocomplete("  RICHM ") == items
    assert route.call_count == 1
    params = route.calls.last.request.url.params
    assert params["layers"] == "locality,address,venue,postalcode"
    assert params["boundary.country"] == "US" and params["size"] == "5"


def test_autocomplete_street_label_and_empty_result_cached_short(ors):
    street = feature(-77.4, 37.5, layer="address", name="123 Main St")
    ors.get(f"{BASE}/geocode/autocomplete").mock(return_value=geocode_ok(street))
    assert ors_client.autocomplete("123 main")[0].label == "123 Main St, Richmond, VA"
    assert ors_client.autocomplete("zzzzqq​") == ()  # invalid text never reaches ORS


def test_autocomplete_empty_is_200_style_and_not_found_ttl(ors, monkeypatch):
    ttls = []
    real_cache = caches["geo"]
    monkeypatch.setattr(type(real_cache), "set", lambda self, k, v, t=None, **kw: ttls.append(t))
    ors.get(f"{BASE}/geocode/autocomplete").mock(return_value=geocode_ok())
    assert ors_client.autocomplete("nothing here") == ()
    assert ttls == [3600]


def test_autocomplete_spent_budget(ors, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "autocomplete", budgets.Budget(0, 900))
    route = ors.get(f"{BASE}/geocode/autocomplete")
    with pytest.raises(UpstreamQuotaExhausted):
        ors_client.autocomplete("Richm")
    assert route.call_count == 0


# ---- deadline, O-25 ----


def test_o25_exhausted_deadline_makes_no_call(ors):
    route = ors.post(HGV_URL)
    with pytest.raises(DeadlineExceeded):
        leg(Deadline(0))
    assert route.call_count == 0
    assert issubclass(DeadlineExceeded, UpstreamUnavailable)


def test_per_call_timeout_is_min_of_cap_and_remaining(ors):
    route = ors.post(HGV_URL).mock(return_value=ok())
    leg(Deadline(4))
    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["read"] <= 4.0 and timeout["connect"] == pytest.approx(3.0, abs=0.01)
    route.reset()
    caches["routes"].clear()
    leg(Deadline(25))
    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["read"] == 10.0 and timeout["connect"] == 3.0


def test_retries_spend_the_budget_each_time(ors, monkeypatch):
    monkeypatch.setitem(budgets.BUDGETS, "directions", budgets.Budget(1, 100))
    route = ors.post(HGV_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(UpstreamQuotaExhausted):
        leg()
    assert route.call_count == 1  # the retry was stopped by the budget


# ---- request hygiene, O-26 ----


def test_o26_key_in_header_only_and_user_text_only_in_params(ors):
    route = ors.get(f"{BASE}/geocode/search").mock(
        return_value=geocode_ok(feature(-97.0, 32.8, locality="Dallas", region_a="TX"))
    )
    hostile = "Dallas&api_key=evil#../../admin?x=1"
    ors_client.geocode_search(hostile, "current", Deadline())
    request = route.calls.last.request
    assert request.headers["Authorization"] == TEST_KEY
    assert "api_key" not in request.url.params and TEST_KEY not in str(request.url)
    assert request.url.params["text"] == hostile
    assert (request.url.host, request.url.path) == ("api.openrouteservice.org", "/geocode/search")
    assert request.url.params["boundary.country"] == "US" and request.url.params["size"] == "1"


# ---- logging hygiene, O-27 ----


def _failure_scenarios(ors):
    boom = httpx.ConnectError(f"failed https://api.openrouteservice.org/geocode/search?text={SECRET_TEXT}")
    return [
        httpx.Response(401, text=TEST_KEY),
        httpx.Response(403, text=SECRET_TEXT),
        httpx.Response(429, text=SECRET_TEXT),
        httpx.Response(500, text=SECRET_TEXT),
        httpx.Response(400, json={"error": {"code": 2003, "message": SECRET_TEXT}}),
        httpx.Response(200, text=SECRET_TEXT),
        boom,
        httpx.ReadTimeout(SECRET_TEXT),
    ]


def test_o27_no_key_url_or_location_text_in_logs_or_exceptions(ors, caplog):
    caplog.set_level(logging.DEBUG)
    route = ors.get(f"{BASE}/geocode/search")
    for scenario in _failure_scenarios(ors):
        route.side_effect = [scenario, scenario]
        caplog.clear()
        with pytest.raises(Exception) as info:  # noqa: PT011
            ors_client.geocode_search(SECRET_TEXT, "current", Deadline())
        rendered = caplog.text + str(info.value) + repr(info.value)
        assert TEST_KEY not in rendered
        assert SECRET_TEXT not in rendered
        assert "api.openrouteservice.org" not in rendered
        assert "text=" not in rendered
    assert caches["geo"].get("x") is None


def test_log_lines_carry_class_status_and_kind_only(ors, caplog):
    caplog.set_level(logging.DEBUG)
    ors.post(HGV_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(UpstreamUnavailable):
        leg()
    record = next(r for r in caplog.records if r.getMessage() == "ors_call_failed")
    assert (record.endpoint_kind, record.error_class, record.upstream_status) == (
        "directions",
        "HTTPStatus",
        502,
    )


def test_low_quota_header_logs_a_warning(ors, caplog):
    caplog.set_level(logging.DEBUG)
    ors.post(HGV_URL).mock(
        return_value=httpx.Response(
            200, json=GOOD_ROUTE, headers={"x-ratelimit-remaining": "3", "x-ratelimit-limit": "40"}
        )
    )
    leg()
    assert any(r.getMessage() == "ors_quota_low" for r in caplog.records)


def test_json_formatter_redacts_httpx_messages_and_urls_in_tracebacks():
    url = f"https://api.openrouteservice.org/geocode/search?text={SECRET_TEXT.replace(' ', '%20')}"
    request = httpx.Request("GET", url)
    try:
        raise httpx.ConnectError(f"cannot reach {url} for {SECRET_TEXT}", request=request)
    except httpx.ConnectError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "unhandled", None, sys.exc_info())
    line = json.loads(JsonFormatter().format(record))
    assert "ConnectError" in line["exc"]
    assert (
        SECRET_TEXT not in line["exc"] and "%20" not in line["exc"] and "openrouteservice" not in line["exc"]
    )


# ---- caching, O-28 ----


def test_o28_second_identical_request_is_served_from_cache(ors):
    route = ors.post(HGV_URL).mock(return_value=ok())
    first = leg()
    assert leg() == first
    assert route.call_count == 1
    nearby = Place("x", START.lat + 0.000003, START.lng)  # same 5 dp key
    assert ors_client.directions_leg(nearby, END, Deadline()) == first
    assert route.call_count == 1


def test_o28_errors_are_never_cached(ors):
    route = ors.post(HGV_URL)
    route.side_effect = [httpx.Response(500), httpx.Response(500), ok()]
    with pytest.raises(UpstreamUnavailable):
        leg()
    assert leg().distance_m == 160934.4
    assert route.call_count == 3


@pytest.mark.parametrize(("status", "attempts"), [(401, 1), (403, 1), (429, 2), (500, 2)])
def test_o28_geocode_errors_are_never_cached(ors, status, attempts):
    route = ors.get(f"{BASE}/geocode/search")
    dallas = geocode_ok(feature(-97.0, 32.8, locality="Dallas", region_a="TX"))
    route.side_effect = [httpx.Response(status)] * attempts + [dallas]
    with pytest.raises(RoutingError):
        ors_client.geocode_search("Dallas", "current", Deadline())
    assert route.call_count == attempts
    assert ors_client.geocode_search("Dallas", "current", Deadline()).label == "Dallas, TX"
    assert route.call_count == attempts + 1


def test_cached_unsupported_place_still_raises_on_second_lookup(ors):
    route = ors.get(f"{BASE}/geocode/search").mock(
        return_value=geocode_ok(feature(-157.85, 21.31, locality="Honolulu", region_a="HI"))
    )
    for _ in range(2):
        with pytest.raises(UnsupportedLocation):
            ors_client.geocode_search("Honolulu", "current", Deadline())
    assert route.call_count == 1


def test_models_reject_bad_numbers():
    with pytest.raises(ValueError, match="finite"):
        LegRoute("x", float("nan"), 1.0, "driving-hgv")
    with pytest.raises(ValueError, match="non-negative"):
        LegRoute("x", -1.0, 1.0, "driving-hgv")
    with pytest.raises(ValueError, match="range"):
        Place("x", 91.0, 0.0)


# ---- T2 review fixes -------------------------------------------------------------------------------


class TrickleStream(httpx.SyncByteStream):
    """Sends one byte per `delay_s`: every chunk beats the per-chunk read timeout."""

    def __init__(self, total: int, delay_s: float) -> None:
        self.total, self.delay_s = total, delay_s

    def __iter__(self):
        import time

        for _ in range(self.total):
            time.sleep(self.delay_s)
            yield b" "


def test_slow_trickle_cannot_outlive_the_deadline(ors):
    import time

    ors.post(HGV_URL).mock(return_value=httpx.Response(200, stream=TrickleStream(50, 0.05)))
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded):
        leg(Deadline(0.3))
    assert time.monotonic() - started < 0.8  # would be 2.5 s if only the per-chunk timeout applied


def test_success_body_over_the_cap_is_bad_response(ors, monkeypatch):
    monkeypatch.setattr(ors_client, "MAX_BODY_BYTES", 100)
    ors.post(HGV_URL).mock(
        return_value=httpx.Response(200, content=b" " * 500 + json.dumps(GOOD_ROUTE).encode())
    )
    with pytest.raises(UpstreamBadResponse):
        leg()


def test_oversized_error_body_is_ignored_not_parsed(ors):
    huge = json.dumps({"error": {"code": 2004}, "pad": "x" * (ors_client.MAX_ERROR_BODY_BYTES + 10)})
    ors.post(HGV_URL).mock(return_value=httpx.Response(400, content=huge.encode()))
    with pytest.raises(UpstreamBadRequest):  # code 2004 was not read, so it is a plain 4xx
        leg()


def test_polyline_length_is_capped(ors, monkeypatch):
    monkeypatch.setattr(ors_client, "MAX_POLYLINE_CHARS", 5)
    ors.post(HGV_URL).mock(return_value=ok())
    with pytest.raises(UpstreamBadResponse):
        leg()
    assert caches["routes"].get("x") is None


@pytest.mark.parametrize("geometry", ["~~~~~~~~", "_p~iF", "_p~iF~ps|U_"])
def test_undecodable_polyline_is_bad_response_and_not_cached(ors, geometry):
    payload = json.loads(json.dumps(GOOD_ROUTE))
    payload["routes"][0]["geometry"] = geometry
    route = ors.post(HGV_URL).mock(return_value=ok(payload))
    with pytest.raises(UpstreamBadResponse):
        leg()
    with pytest.raises(UpstreamBadResponse):
        leg()
    assert route.call_count == 2  # nothing was cached


def test_polyline_with_out_of_range_points_is_bad_response(ors):
    payload = json.loads(json.dumps(GOOD_ROUTE))
    payload["routes"][0]["geometry"] = polyline.encode([(95.0, 10.0), (96.0, 11.0)])
    ors.post(HGV_URL).mock(return_value=ok(payload))
    with pytest.raises(UpstreamBadResponse):
        leg()


@pytest.mark.parametrize(
    "props",
    [
        {"country_a": "CAN", "region_a": "ON", "locality": "Toronto"},
        {"country_code": "CA", "region_a": "ON", "locality": "Toronto"},
    ],
)
def test_non_us_feature_inside_the_box_is_unsupported(ors, props):
    ors.get(f"{BASE}/geocode/search").mock(return_value=geocode_ok(feature(-79.4, 43.7, **props)))
    with pytest.raises(UnsupportedLocation):
        ors_client.geocode_search("Toronto", "current", Deadline())


def test_us_country_markers_pass_and_autocomplete_drops_non_us(ors):
    ors.get(f"{BASE}/geocode/autocomplete").mock(
        return_value=geocode_ok(
            feature(-77.4, 37.5, country_a="USA", country_code="US"),
            feature(-79.4, 43.7, country_a="CAN", locality="Toronto", region_a="ON"),
        )
    )
    assert [p.label for p in ors_client.autocomplete("Toron")] == ["Richmond, VA"]


def test_normalized_text_is_what_ors_receives(ors):
    route = ors.get(f"{BASE}/geocode/search").mock(
        return_value=geocode_ok(feature(-97.0, 32.8, locality="Dallas", region_a="TX"))
    )
    ors_client.geocode_search("  Dallas,\t TX \n", "current", Deadline())
    assert route.calls.last.request.url.params["text"] == "Dallas, TX"
