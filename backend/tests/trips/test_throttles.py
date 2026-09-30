"""Request throttles, client identity and in-flight guards (API_CONTRACT section 8)."""

from unittest import mock

import pytest
from django.core.cache import caches
from django.test import override_settings

from tests.trips.conftest import PLACES_URL, PLAN_URL, post_plan, valid_payload
from trips.inflight import GLOBAL_SLOTS, PlanInflightGuard
from trips.throttles import client_ident

IP_A = {"REMOTE_ADDR": "10.0.0.1"}


def _plan(client, ip="203.0.113.7", **extra):
    return post_plan(client, valid_payload(), HTTP_X_FORWARDED_FOR=ip, **extra)


def _places(client, ip="203.0.113.7"):
    return client.get(PLACES_URL, {"q": "abc"}, HTTP_X_FORWARDED_FOR=ip)


# --- per IP and global request throttles -----------------------------------------------------------


def test_eleventh_plan_in_a_minute_is_429_with_retry_hint(client, plan_service):
    for _ in range(10):
        assert _plan(client).status_code == 200
    response = _plan(client)
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert error["message"].startswith("Too many trip plans from your network. Wait ")
    assert 1 <= error["retry_after_s"] <= 300
    assert response["Retry-After"] == str(error["retry_after_s"])
    assert response["Cache-Control"] == "no-store"
    assert error["request_id"] == response["X-Request-ID"]
    assert plan_service.call_count == 10


def test_other_ips_are_not_affected_by_one_ips_limit(client, plan_service):
    for _ in range(11):
        _plan(client, ip="203.0.113.7")
    assert _plan(client, ip="203.0.113.8").status_code == 200


def test_global_plan_minute_bucket(client, plan_service):
    codes = [_plan(client, ip=f"198.51.100.{i}").status_code for i in range(20)]
    assert codes[:18] == [200] * 18
    assert codes[18:] == [429, 429]
    response = _plan(client, ip="198.51.100.99")
    assert response.json()["error"]["message"].startswith("The planner is at its request limit. Wait ")


def test_daily_plan_cap_per_ip_clamps_retry_after(client, plan_service):
    cache = caches["default"]
    now = 1_000_000.0
    with mock.patch("rest_framework.throttling.SimpleRateThrottle.timer", return_value=now):
        cache.set("throttle_plan_ip_day_203.0.113.7", [now - 60 * i for i in range(100)], 86400)
        response = _plan(client)
    assert response.status_code == 429
    assert response.json()["error"]["retry_after_s"] == 300
    assert response["Retry-After"] == "300"


def test_autocomplete_per_ip_minute_limit_and_message(client, autocomplete_service):
    for _ in range(60):
        assert _places(client).status_code == 200
    response = _places(client)
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["message"].startswith("Too many place searches from your network. Wait ")
    assert "Retry-After" in response


def test_autocomplete_global_minute_limit(client, autocomplete_service):
    codes = [_places(client, ip=f"192.0.2.{i}").status_code for i in range(92)]
    assert codes.count(200) == 90
    assert codes[-1] == 429


def test_plan_and_autocomplete_buckets_are_independent(client, plan_service, autocomplete_service):
    for _ in range(11):
        _plan(client)
    assert _places(client).status_code == 200


def test_health_is_never_throttled(client):
    assert all(client.get("/api/v1/health").status_code == 200 for _ in range(150))


def test_schema_and_docs_use_default_ip_throttle(client):
    codes = [client.get("/api/v1/schema", HTTP_X_FORWARDED_FOR="203.0.113.50").status_code for _ in range(32)]
    assert codes[:30] == [200] * 30
    assert codes[30:] == [429, 429]
    docs = client.get("/api/v1/docs", HTTP_X_FORWARDED_FOR="203.0.113.50")
    assert docs.status_code == 429
    assert docs.json()["error"]["code"] == "RATE_LIMITED"


def test_docs_assets_are_throttled_not_open(client):
    url = "/api/v1/docs-assets/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui.css"
    first = client.get(url, HTTP_X_FORWARDED_FOR="203.0.113.60")
    assert first.status_code == 200
    assert first["Cache-Control"]
    caches["default"].set("throttle_docs_assets_ip_203.0.113.60", [__import__("time").time()] * 120, 60)
    assert client.get(url, HTTP_X_FORWARDED_FOR="203.0.113.60").status_code == 429


def test_docs_assets_missing_file_is_json_404(client):
    response = client.get("/api/v1/docs-assets/nope.css", HTTP_ACCEPT="text/css")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- client identity -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("xff", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("1.1.1.1, 203.0.113.7", "203.0.113.7"),  # NUM_PROXIES=1: only the last hop is trusted
        ("2001:db8:1:2:aaaa:bbbb:cccc:dddd", "2001:db8:1:2::"),
        ("2001:db8:1:2:1111:2222:3333:4444", "2001:db8:1:2::"),
        ("::ffff:203.0.113.9", "203.0.113.9"),
        ("not-an-ip", "10.0.0.1"),
    ],
)
def test_client_ident(rf, xff, expected):
    from rest_framework.request import Request

    request = Request(rf.get("/", HTTP_X_FORWARDED_FOR=xff, REMOTE_ADDR="10.0.0.1"))
    assert client_ident(request) == expected


def test_spoofed_leading_xff_entries_do_not_change_the_bucket(client, plan_service):
    for i in range(10):
        assert _plan(client, ip=f"66.66.66.{i}, 203.0.113.7").status_code == 200
    assert _plan(client, ip="77.77.77.77, 203.0.113.7").status_code == 429


def test_ipv6_addresses_in_one_slash_64_share_a_bucket(client, plan_service):
    for i in range(10):
        assert _plan(client, ip=f"2001:db8:1:2::{i + 1}").status_code == 200
    assert _plan(client, ip="2001:db8:1:2:ffff::1").status_code == 429
    assert _plan(client, ip="2001:db8:1:3::1").status_code == 200


@override_settings()
def test_num_proxies_is_configured_in_test_settings():
    from rest_framework.settings import api_settings

    assert api_settings.NUM_PROXIES == 1


# --- in-flight guards ------------------------------------------------------------------------------


def test_second_concurrent_plan_from_one_ip_is_429_retry_5(client):
    def reenter(_validated):
        inner = _plan(client)
        assert inner.status_code == 429
        error = inner.json()["error"]
        assert error["retry_after_s"] == 5
        assert inner["Retry-After"] == "5"
        assert error["message"] == (
            "Your previous trip is still being planned. Wait for it to finish, then try again."
        )
        return {"ok": True}

    with mock.patch("trips.views.plan_trip", side_effect=reenter):
        assert _plan(client).status_code == 200
    # slot released afterwards
    with mock.patch("trips.views.plan_trip", return_value={"ok": True}):
        assert _plan(client).status_code == 200


def test_fourth_global_concurrent_plan_is_429(client):
    refused = []
    level = {"n": 0}

    def nest(_validated):
        level["n"] += 1
        inner = _plan(client, ip=f"203.0.113.{100 + level['n']}")
        if inner.status_code == 429:
            refused.append(inner)
        return {"ok": True}

    with mock.patch("trips.views.plan_trip", side_effect=nest):
        assert _plan(client, ip="203.0.113.100").status_code == 200
    # The outer request and two nested ones hold the three slots; the third nested one is refused.
    assert len(refused) == 1
    error = refused[0].json()["error"]
    assert error["message"] == "The planner is busy with other trips. Wait 5 seconds, then try again."
    assert error["retry_after_s"] == 5
    assert refused[0]["Retry-After"] == "5"


def test_refused_global_slot_releases_the_ip_slot(client):
    cache = caches["default"]
    for slot in range(GLOBAL_SLOTS):
        cache.add(f"inflight:plan:global:{slot}", 1, 30)
    assert _plan(client).status_code == 429
    for slot in range(GLOBAL_SLOTS):
        cache.delete(f"inflight:plan:global:{slot}")
    with mock.patch("trips.views.plan_trip", return_value={"ok": True}):
        assert _plan(client).status_code == 200


@pytest.mark.parametrize("exc", [RuntimeError("boom"), KeyError("x")])
def test_crashing_plan_still_releases_its_slot(client, exc):
    with mock.patch("trips.views.plan_trip", side_effect=exc):
        assert _plan(client).status_code == 500
    with mock.patch("trips.views.plan_trip", return_value={"ok": True}):
        assert _plan(client).status_code == 200
    cache = caches["default"]
    assert not any(cache.get(f"inflight:plan:global:{i}") for i in range(GLOBAL_SLOTS))


def test_guard_context_manager_releases_on_exception(rf):
    from rest_framework.request import Request

    request = Request(rf.post(PLAN_URL, REMOTE_ADDR="10.0.0.1"))
    with pytest.raises(ValueError, match="x"), PlanInflightGuard(request):
        raise ValueError("x")
    with PlanInflightGuard(request):
        pass


# --- throttles apply to the allowed method only ----------------------------------------------------


def test_options_and_wrong_methods_do_not_consume_plan_or_places_buckets(client, plan_service):
    for i in range(3):
        for _ in range(10):
            client.options(PLAN_URL, HTTP_X_FORWARDED_FOR=f"198.51.100.{i}")
            client.get(PLAN_URL, HTTP_X_FORWARDED_FOR=f"198.51.100.{i}")
    assert _plan(client, ip="198.51.100.200").status_code == 200
    assert len(caches["default"].get("throttle_plan_global_min_global")) == 1  # only the POST


def test_post_to_autocomplete_does_not_consume_places_bucket(client, autocomplete_service):
    for _ in range(30):
        client.post(PLACES_URL, {}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.50")
    assert not caches["default"].get("throttle_places_global_min_global")


def test_other_methods_still_hit_the_default_ip_limit(client):
    codes = [client.options(PLAN_URL, HTTP_X_FORWARDED_FOR="203.0.113.60").status_code for _ in range(31)]
    assert codes[-1] == 429


# --- in-flight release is owner-checked ------------------------------------------------------------


def test_expired_guard_does_not_free_a_newer_owners_slot(rf):
    from rest_framework.request import Request

    request = Request(rf.post(PLAN_URL, REMOTE_ADDR="203.0.113.70"))
    cache = caches["default"]
    first = PlanInflightGuard(request)
    first.__enter__()
    cache.clear()  # slots expire while the first request is still running
    second = PlanInflightGuard(request)
    second.__enter__()
    first.__exit__(None, None, None)  # late release by the old owner
    with pytest.raises(Exception, match="still being planned"):
        PlanInflightGuard(request).__enter__()
    second.__exit__(None, None, None)
    PlanInflightGuard(request).__enter__()  # released properly now
