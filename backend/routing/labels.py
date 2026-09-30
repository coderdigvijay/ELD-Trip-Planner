"""Pure "City, ST" label building and fallbacks for remark locations."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from routing.geometry import METERS_PER_MILE, LatLng, haversine_m

REUSE_RADIUS_MILES = 10.0
ROUND_DP = 2
NEAR_MAX_MILES = 150.0


@dataclass(frozen=True, slots=True)
class KnownLabel:
    point: LatLng
    label: str


MAX_LABEL_CHARS = 120
STREET_LAYERS = frozenset({"address", "venue"})


def _clean(value: Any) -> str | None:
    """Upstream text is untrusted: NFC, collapse whitespace, drop Cc/Cf, cap the length."""
    if not isinstance(value, str):
        return None
    text = " ".join(unicodedata.normalize("NFC", value).split())
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))
    return text[:MAX_LABEL_CHARS].strip() or None


def _city(props: Mapping[str, Any], *keys: str) -> str | None:
    return next((t for t in (_clean(props.get(k)) for k in keys) if t), None)


def label_from_properties(props: Mapping[str, Any]) -> str | None:
    """Build "City, ST" from Pelias feature properties, or None if unusable."""
    place = _city(props, "locality", "localadmin", "county", "name")
    region = _clean(props.get("region_a"))
    if place and region:
        return f"{place}, {region}"
    full = _clean(props.get("label"))
    if full:
        cleaned = full.removesuffix(", USA").removesuffix(", United States").strip()
        return cleaned or None
    return None


def street_label_from_properties(props: Mapping[str, Any]) -> str | None:
    """Autocomplete label: "<name or street>, City, ST" for addresses and venues, else "City, ST"."""
    if props.get("layer") not in STREET_LAYERS:
        return label_from_properties(props)
    name = _clean(props.get("name"))
    city = _city(props, "locality", "localadmin", "county")
    region = _clean(props.get("region_a"))
    if not (name and city and region):
        return label_from_properties(props)
    parts = [name, city, region]
    return ", ".join(p for i, p in enumerate(parts) if i == 0 or p != parts[i - 1])


def coordinate_label(point: LatLng) -> str:
    """Last-resort label: "lat, lng" at 2 dp."""
    return f"{point[0]:.{ROUND_DP}f}, {point[1]:.{ROUND_DP}f}"


def _miles(a: LatLng, b: LatLng) -> float:
    return haversine_m(a, b) / METERS_PER_MILE


def nearest_known(point: LatLng, known: Iterable[KnownLabel]) -> tuple[KnownLabel, float] | None:
    best: tuple[KnownLabel, float] | None = None
    for k in known:
        d = _miles(point, k.point)
        if best is None or d < best[1]:
            best = (k, d)
    return best


def reuse_known_label(
    point: LatLng, known: Iterable[KnownLabel], radius_miles: float = REUSE_RADIUS_MILES
) -> str | None:
    """Label of the nearest known place if within ``radius_miles``, else None."""
    hit = nearest_known(point, known)
    return hit[0].label if hit and hit[1] <= radius_miles else None


def fallback_label(point: LatLng, known: Iterable[KnownLabel]) -> str:
    """``near <nearest known label>`` when it is within NEAR_MAX_MILES, else "lat, lng"."""
    hit = nearest_known(point, known)
    return f"near {hit[0].label}" if hit and hit[1] <= NEAR_MAX_MILES else coordinate_label(point)


def round_point(point: LatLng, dp: int = ROUND_DP) -> LatLng:
    # +0.0 normalizes -0.0 so cache keys are stable
    return (round(point[0], dp) + 0.0, round(point[1], dp) + 0.0)


def dedupe_points(points: Iterable[LatLng], dp: int = ROUND_DP) -> list[LatLng]:
    """Round to ``dp`` and dedupe, preserving first-seen order."""
    return list(dict.fromkeys(round_point(p, dp) for p in points))
