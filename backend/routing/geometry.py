"""Pure geometry helpers: polyline decode, haversine, rescaled interpolation.

Coordinates are (lat, lng) everywhere after decoding. Distances are miles at the
public boundary; ORS meters are converted in exactly one place (``METERS_PER_MILE``).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

import polyline as _polyline

METERS_PER_MILE = 1609.344
EARTH_RADIUS_M = 6_371_008.8

LatLng = tuple[float, float]


def decode_polyline(encoded: str, precision: int = 5) -> list[LatLng]:
    """Decode an encoded polyline to ``[(lat, lng), ...]``. Empty string gives []."""
    if not encoded:
        return []
    return [(float(lat), float(lng)) for lat, lng in _polyline.decode(encoded, precision)]


def haversine_m(a: LatLng, b: LatLng) -> float:
    """Great-circle distance in meters between two (lat, lng) points."""
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def cumulative_haversine_m(points: list[LatLng]) -> list[float]:
    """Cumulative haversine meters per vertex, starting at 0.0."""
    cum = [0.0] if points else []
    for prev, cur in zip(points, points[1:], strict=False):
        cum.append(cum[-1] + haversine_m(prev, cur))
    return cum


@dataclass(frozen=True, slots=True)
class LegGeometry:
    """Decoded leg with cumulative distances rescaled to the ORS leg distance."""

    points: tuple[LatLng, ...]
    cum_miles: tuple[float, ...]  # rescaled, cum_miles[-1] == length_miles when points >= 2
    length_miles: float  # ORS leg distance in miles (engine miles)
    scale: float  # leg.distance_m / haversine_length_m (1.0 if degenerate)


def build_leg_geometry(encoded: str, distance_m: float, precision: int = 5) -> LegGeometry:
    """Decode once and rescale so the last vertex sits at exactly ``distance_m``."""
    return build_leg_geometry_from_points(decode_polyline(encoded, precision), distance_m)


def build_leg_geometry_from_points(points: list[LatLng], distance_m: float) -> LegGeometry:
    length_miles = max(0.0, distance_m) / METERS_PER_MILE
    cum_m = cumulative_haversine_m(points)
    hav = cum_m[-1] if cum_m else 0.0
    if hav <= 0.0:
        return LegGeometry(tuple(points), tuple(0.0 for _ in points), length_miles, 1.0)
    scale = max(0.0, distance_m) / hav
    cum_miles: list[float] = []
    running = 0.0
    for c in cum_m:
        # running max + cap keeps values non-decreasing and <= length despite float rounding
        running = min(max(running, c * scale / METERS_PER_MILE), length_miles)
        cum_miles.append(running)
    cum_miles[-1] = length_miles  # exact endpoint, no float drift
    return LegGeometry(tuple(points), tuple(cum_miles), length_miles, scale)


def interpolate(leg: LegGeometry, miles_from_leg_start: float) -> LatLng:
    """Point at ``miles_from_leg_start`` along the leg; clamps outside [0, length].

    Raises ValueError for an empty geometry or non-finite miles."""
    pts, cum = leg.points, leg.cum_miles
    if not pts:
        raise ValueError("cannot interpolate an empty geometry")
    if not math.isfinite(miles_from_leg_start):
        raise ValueError("miles_from_leg_start must be finite")
    if len(pts) == 1 or cum[-1] <= 0.0 or miles_from_leg_start <= 0.0:
        return pts[0]
    if miles_from_leg_start >= cum[-1]:
        return pts[-1]
    i = bisect_right(cum, miles_from_leg_start)  # cum[i-1] <= d < cum[i]
    lo, hi = cum[i - 1], cum[i]
    if hi <= lo:
        return pts[i]
    f = (miles_from_leg_start - lo) / (hi - lo)
    (lat0, lng0), (lat1, lng1) = pts[i - 1], pts[i]
    return (lat0 + (lat1 - lat0) * f, lng0 + (lng1 - lng0) * f)
