"""Normalized, versioned cache keys and TTLs (docs/ARCHITECTURE.md section 7).

Keys are hashes of normalized input, so a client cannot address another key's slot. Bump
`KEY_VERSION` when the parsed value shape changes.
"""

from __future__ import annotations

import hashlib
import math
import unicodedata
from dataclasses import dataclass

KEY_VERSION = "ors:v1"
DIRECTIONS_OPTIONS_VERSION = "1"  # bump when the request options (radiuses, units...) change

_HOUR = 3600
_DAY = 24 * _HOUR


class InvalidTextError(ValueError):
    """Text contains control or format characters (Unicode Cc / Cf) or is empty."""


@dataclass(frozen=True, slots=True)
class Ttl:
    hit_s: int
    not_found_s: int


GEOCODE_TTL = Ttl(hit_s=7 * _DAY, not_found_s=10 * 60)
AUTOCOMPLETE_TTL = Ttl(hit_s=_DAY, not_found_s=_HOUR)
REVERSE_TTL = Ttl(hit_s=30 * _DAY, not_found_s=_HOUR)
DIRECTIONS_TTL = Ttl(hit_s=_DAY, not_found_s=10 * 60)


def clean_text(text: str) -> str:
    """NFC, trim, collapse whitespace, reject Cc/Cf. This exact text is what ORS receives."""
    collapsed = " ".join(unicodedata.normalize("NFC", text).split())
    if not collapsed:
        raise InvalidTextError("empty text")
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in collapsed):
        raise InvalidTextError("control or format character")
    return collapsed


def normalize_text(text: str) -> str:
    """`clean_text` plus lowercase: the cache-key form."""
    return clean_text(text).lower()


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _rounded(value: float, places: int) -> str:
    if not math.isfinite(value):
        raise ValueError("coordinate must be finite")
    return f"{round(value, places) + 0.0:.{places}f}"  # + 0.0 turns -0.0 into 0.0


def geocode_key(text: str) -> str:
    return f"{KEY_VERSION}:geocode:{_digest(normalize_text(text))}"


def autocomplete_key(text: str) -> str:
    return f"{KEY_VERSION}:ac:{_digest(normalize_text(text))}"


def reverse_key(lat: float, lng: float) -> str:
    return f"{KEY_VERSION}:rev:{_rounded(lat, 2)}:{_rounded(lng, 2)}"


def directions_key(profile: str, start: tuple[float, float], end: tuple[float, float]) -> str:
    """`start` and `end` are (lat, lng), rounded to 5 dp (about 1 m)."""
    coords = [_rounded(v, 5) for v in (*start, *end)]
    return f"{KEY_VERSION}:dir:{profile}:{_digest(DIRECTIONS_OPTIONS_VERSION, *coords)}"
