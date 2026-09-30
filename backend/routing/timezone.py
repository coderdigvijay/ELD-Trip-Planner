"""Home-terminal zone and the frozen fixed UTC offset (ARCHITECTURE section 10). No ORS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

DEFAULT_START = time(8, 0)
FALLBACK_ZONE = "America/Chicago"


@dataclass(frozen=True, slots=True)
class FrozenTimezone:
    name: str  # IANA zone, display only
    abbreviation: str  # abbreviation at trip start, display only
    offset: timezone  # fixed offset used for the whole trip
    offset_minutes: int
    start: datetime  # start instant, tz-aware in ``offset``

    @property
    def utc_offset(self) -> str:
        return format_offset(self.offset_minutes)


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def zone_name_for(lat: float, lng: float) -> str:
    """IANA zone for coordinates (offline). Falls back to America/Chicago if unresolved."""
    return _finder().timezone_at(lat=lat, lng=lng) or FALLBACK_ZONE


def format_offset(minutes: int) -> str:
    sign = "-" if minutes < 0 else "+"
    hh, mm = divmod(abs(minutes), 60)
    return f"{sign}{hh:02d}:{mm:02d}"


def quantize_time(t: time, step_minutes: int = 15) -> time:
    """Round down to the 15 min grid."""
    total = (t.hour * 60 + t.minute) // step_minutes * step_minutes
    return time(total // 60, total % 60)


def freeze_timezone(zone_name: str, trip_date: date, start_time: time = DEFAULT_START) -> FrozenTimezone:
    """Read the zone's offset at trip date + start time and freeze it as a fixed offset."""
    zone: tzinfo = ZoneInfo(zone_name)
    local = datetime.combine(trip_date, quantize_time(start_time), tzinfo=zone)
    off = local.utcoffset() or timedelta(0)
    abbreviation = local.tzname() or format_offset(int(off.total_seconds() // 60))
    fixed = timezone(off)
    minutes = int(off.total_seconds() // 60)
    # Same wall clock, fixed offset (a gap/fold time resolves via the zone's offset read above).
    start = datetime.combine(trip_date, quantize_time(start_time), tzinfo=fixed)
    return FrozenTimezone(zone_name, abbreviation, fixed, minutes, start)


def home_terminal_timezone(
    lat: float, lng: float, trip_date: date | None = None, start_time: time = DEFAULT_START
) -> FrozenTimezone:
    """Resolve the zone from coordinates and freeze it. ``trip_date=None`` means today in that zone."""
    name = zone_name_for(lat, lng)
    if trip_date is None:
        trip_date = datetime.now(UTC).astimezone(ZoneInfo(name)).date()
    return freeze_timezone(name, trip_date, start_time)
