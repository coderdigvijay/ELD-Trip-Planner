"""Value objects returned by the ORS adapter. Frozen, hashable, picklable (LocMem stores them)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from routing.geometry import METERS_PER_MILE

Profile = Literal["driving-hgv", "driving-car"]

MAX_TRIP_M = 6000 * METERS_PER_MILE

# Lower 48 bounding box (with a small margin). Coarse on purpose: Canada, Mexico and the
# Caribbean are already excluded upstream by boundary.country=US.
LOWER_48_LAT = (24.3, 49.6)
LOWER_48_LNG = (-125.1, -66.8)


def in_lower_48(lat: float, lng: float) -> bool:
    return LOWER_48_LAT[0] <= lat <= LOWER_48_LAT[1] and LOWER_48_LNG[0] <= lng <= LOWER_48_LNG[1]


@dataclass(frozen=True, slots=True)
class Place:
    label: str
    lat: float
    lng: float
    us: bool = True  # False when Pelias says the feature is not in the United States

    @property
    def plannable(self) -> bool:
        return self.us and in_lower_48(self.lat, self.lng)

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lat) and math.isfinite(self.lng)):
            raise ValueError("coordinates must be finite")
        if not (-90 <= self.lat <= 90 and -180 <= self.lng <= 180):
            raise ValueError("coordinates out of range")


@dataclass(frozen=True, slots=True)
class LegRoute:
    """One directions leg. `polyline` is the encoded ORS geometry (precision 1e5, [lat, lng])."""

    polyline: str
    distance_m: float
    duration_s: float
    profile: Profile

    def __post_init__(self) -> None:
        for value in (self.distance_m, self.duration_s):
            if not math.isfinite(value) or value < 0:
                raise ValueError("distance and duration must be finite and non-negative")

    @property
    def miles(self) -> float:
        return self.distance_m / METERS_PER_MILE
