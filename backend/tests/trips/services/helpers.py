"""Fake ORS over respx and request builders for the service tests. No real network."""

from __future__ import annotations

import datetime as dt
import json
import math
from typing import Any

import httpx
import polyline

from routing.models import METERS_PER_MILE

BASE = "https://api.openrouteservice.org"
HGV_URL = f"{BASE}/v2/directions/driving-hgv/json"
CAR_URL = f"{BASE}/v2/directions/driving-car/json"
SEARCH_URL = f"{BASE}/geocode/search"
REVERSE_URL = f"{BASE}/geocode/reverse"
AUTOCOMPLETE_URL = f"{BASE}/geocode/autocomplete"

RICHMOND = (37.54072, -77.43605)
BALTIMORE = (39.29038, -76.61219)
NEWARK = (40.73566, -74.17237)
CHICAGO = (41.87811, -87.62980)
INDIANAPOLIS = (39.76840, -86.15804)
DENVER = (39.73924, -104.99025)

DEFAULT_HEADER = {
    "driver_name": "",
    "carrier_name": "",
    "main_office_address": "",
    "home_terminal_address": "",
    "truck_number": "",
    "trailer_number": "",
    "shipping_doc": "",
    "shipper_commodity": "",
}


def place(label: str, point: tuple[float, float]) -> dict:
    return {"label": label, "lat": point[0], "lng": point[1]}


def request(
    current: Any,
    pickup: Any,
    dropoff: Any,
    *,
    cycle: float = 0,
    date: dt.date | None = dt.date(2026, 10, 5),
    start: dt.time = dt.time(8, 0),
    header: dict | None = None,
) -> dict:
    return {
        "current_location": current,
        "pickup_location": pickup,
        "dropoff_location": dropoff,
        "current_cycle_used_hours": cycle,
        "start_date": date,
        "start_time": start,
        "log_header": {**DEFAULT_HEADER, **(header or {})},
    }


def curve(a: tuple[float, float], b: tuple[float, float], steps: int = 24) -> list[tuple[float, float]]:
    """A gently bowed line from a to b with `steps + 1` vertices (a realistic small route geometry)."""
    points = []
    for i in range(steps + 1):
        f = i / steps
        bow = 0.02 * math.sin(math.pi * f)
        points.append((round(a[0] + (b[0] - a[0]) * f + bow, 5), round(a[1] + (b[1] - a[1]) * f - bow, 5)))
    points[0], points[-1] = a, b
    return points


def route_payload(a: tuple[float, float], b: tuple[float, float], miles: float, hours: float) -> dict:
    distance, duration = miles * METERS_PER_MILE, hours * 3600
    return {
        "routes": [
            {
                "summary": {"distance": distance, "duration": duration},
                "geometry": polyline.encode(curve(a, b), 5),
                "segments": [{"distance": distance, "duration": duration}],
            }
        ]
    }


def feature(lng: float, lat: float, **props: str) -> dict:
    base = {"layer": "locality", "locality": "Nowhere", "region_a": "ST", "name": "Nowhere"}
    return {"geometry": {"coordinates": [lng, lat]}, "properties": {**base, **props}}


def error_response(status: int, code: int) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": "secret upstream text"}})


def _key(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 5), round(point[1], 5))


class FakeOrs:
    """Answers directions, geocode search and reverse geocode from small tables."""

    def __init__(self, router) -> None:
        self.router = router
        self.legs: dict[tuple, tuple[float, float]] = {}
        self.car_only: set[tuple] = set()
        self.texts: dict[str, tuple[str, str, tuple[float, float]]] = {}
        self.reverse_points: list[tuple[float, float]] = []
        self.reverse_status = 200
        self.hgv = router.post(HGV_URL).mock(side_effect=self._directions(car=False))
        self.car = router.post(CAR_URL).mock(side_effect=self._directions(car=True))
        self.search = router.get(SEARCH_URL).mock(side_effect=self._search)
        self.reverse = router.get(REVERSE_URL).mock(side_effect=self._reverse)

    def leg(self, a, b, miles: float, hours: float, *, car_only: bool = False) -> None:
        self.legs[(_key(a), _key(b))] = (miles, hours)
        if car_only:
            self.car_only.add((_key(a), _key(b)))

    def text(self, text: str, locality: str, region: str, point: tuple[float, float]) -> None:
        self.texts[text.lower()] = (locality, region, point)

    def _directions(self, *, car: bool):
        def respond(request: httpx.Request) -> httpx.Response:
            (lng1, lat1), (lng2, lat2) = json.loads(request.content)["coordinates"]
            a, b = _key((lat1, lng1)), _key((lat2, lng2))
            miles, hours = self.legs[(a, b)]
            if (a, b) in self.car_only and not car:
                return error_response(404, 2009)
            return httpx.Response(200, json=route_payload(a, b, miles, hours))

        return respond

    def _search(self, request: httpx.Request) -> httpx.Response:
        text = request.url.params["text"].lower()
        if text not in self.texts:
            return httpx.Response(200, json={"features": []})
        locality, region, (lat, lng) = self.texts[text]
        return httpx.Response(
            200, json={"features": [feature(lng, lat, locality=locality, region_a=region, name=locality)]}
        )

    def _reverse(self, request: httpx.Request) -> httpx.Response:
        lat, lng = float(request.url.params["point.lat"]), float(request.url.params["point.lon"])
        self.reverse_points.append((lat, lng))
        if self.reverse_status != 200:
            return httpx.Response(self.reverse_status)
        name = f"Town {int(abs(lat) * 100)}-{int(abs(lng) * 100)}"
        return httpx.Response(200, json={"features": [feature(lng, lat, locality=name, region_a="MO")]})
