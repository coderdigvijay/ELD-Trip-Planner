"""Exact arithmetic helpers: grid rounding and half-up decimal rounding on Fractions."""

from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor

from .rules import GRID


def to_fraction(value: float | int | Fraction) -> Fraction:
    """Convert a float exactly as its shortest decimal repr (ORS values are decimals, not binary noise)."""
    return value if isinstance(value, Fraction) else Fraction(str(value))


def ceil15(value: float | int | Fraction) -> int:
    return GRID * ceil(to_fraction(value) / GRID)


def floor15(value: float | int | Fraction) -> int:
    return GRID * floor(to_fraction(value) / GRID)


def round_half_up(value: Fraction, digits: int) -> Fraction:
    scale = 10**digits
    return Fraction(floor(value * scale + Fraction(1, 2)), scale)


def as_float(value: Fraction, digits: int) -> float:
    """Half-up rounding to `digits` decimals, returned as a float (output dataclasses only)."""
    return float(round_half_up(value, digits))


@dataclass(frozen=True)
class MileSpan:
    """Exact miles of one DutyEvent, kept beside the rounded output floats."""

    start: Fraction
    end: Fraction
    leg_end: Fraction  # miles into the event's leg at the end of the event
