"""Shared API test setup: clean caches (throttle and in-flight counters) and a stub plan service."""

import datetime as dt
from unittest import mock

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

PLAN_URL = "/api/v1/trips/plan"
PLACES_URL = "/api/v1/places/autocomplete"
TODAY = dt.date(2026, 10, 1)
PLAN_OK = {"trip": {}, "route": {}, "stops": [], "timeline": [], "days": [], "summary": {}}


@pytest.fixture(autouse=True)
def _clean_caches():
    for alias in caches:
        caches[alias].clear()
    yield
    for alias in caches:
        caches[alias].clear()


@pytest.fixture(autouse=True)
def _frozen_today(monkeypatch):
    monkeypatch.setattr("trips.serializers.today_utc", lambda: TODAY)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def plan_service():
    """Patches the service the view calls; tests read `.call_args` for the validated dict."""
    with mock.patch("trips.views.plan_trip", return_value=PLAN_OK) as patched:
        yield patched


@pytest.fixture
def autocomplete_service():
    result = {"items": [{"label": "Richmond, VA", "lat": 37.54072, "lng": -77.43605}]}
    with mock.patch("trips.views.autocomplete", return_value=result) as patched:
        yield patched


def valid_payload(**overrides):
    body = {
        "current_location": {"label": "Richmond, VA", "lat": 37.54072, "lng": -77.43605},
        "pickup_location": "Baltimore, MD",
        "dropoff_location": {"label": "Newark, NJ", "lat": 40.73566, "lng": -74.17237},
        "current_cycle_used_hours": 10,
        "start_date": "2026-10-05",
        "start_time": "08:00",
        "log_header": {"driver_name": "John Doe", "carrier_name": "John Doe's Transportation"},
    }
    body.update(overrides)
    return body


def post_plan(client, body, **extra):
    return client.post(PLAN_URL, body, format="json", **extra)
