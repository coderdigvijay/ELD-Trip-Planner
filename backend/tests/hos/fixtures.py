"""Worked fixtures 8a to 8h, transcribed from docs/HOS_ENGINE_SPEC.md section 8.

Hours in the spec tables are kept as hours here and converted to minutes on use, so a typo is
easy to compare against the spec. Segment lists use the spec's own text notation.
"""

import re
from dataclasses import dataclass, field

from hos.models import Leg, TripInput

_SEG = re.compile(r"(OFF|SB|D|ON) (\d\d):(\d\d)-(\d\d):(\d\d)")
_BRK = re.compile(r"(\d\d):(\d\d)-(\d\d):(\d\d)")


def hm(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def mins(hours: float) -> int:
    return round(hours * 60)


def parse_segments(text: str) -> list[tuple[str, int, int]]:
    return [(m[1], hm(f"{m[2]}:{m[3]}"), hm(f"{m[4]}:{m[5]}")) for m in _SEG.finditer(text)]


def parse_brackets(text: str) -> list[tuple[int, int]]:
    return [(hm(f"{m[1]}:{m[2]}"), hm(f"{m[3]}:{m[4]}")) for m in _BRK.finditer(text)]


def parse_times(text: str) -> list[int]:
    return [hm(t) for t in text.split()]


@dataclass(frozen=True)
class Ev:
    start: int
    end: int
    status: str
    kind: str
    end_mile: float


@dataclass(frozen=True)
class SheetX:
    """Expected sheet. Totals order OFF / SB / D / ON in hours. `remarks` and `brackets` may be None."""

    totals: tuple[float, float, float, float]
    miles: float
    today: float
    a: float
    b: float
    c: float
    note: bool
    segments: str
    remarks: str | None = None
    brackets: str | None = None


@dataclass(frozen=True)
class SummaryX:
    arrive: int
    complete: int
    sheets: int
    fuel: int
    breaks: int
    rests: int
    restarts: int
    total_miles: float
    cycle_end: int  # minutes


@dataclass(frozen=True)
class Fixture:
    name: str
    legs: tuple[Leg, Leg]
    cycle_min: int
    start_min: int
    events: tuple[Ev, ...]
    sheets: tuple[SheetX, ...]
    summary: SummaryX
    warnings: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)

    @property
    def inp(self) -> TripInput:
        return TripInput(self.legs, self.cycle_min, self.start_min)


def E(start, end, status, kind, end_mile):  # noqa: N802 - terse table rows
    return Ev(start, end, status, kind, end_mile)


# --- 8b: Chicago -> Indianapolis -> Denver, cycle 20, start 08:00 -------------------------------
LEGS_8B = (
    Leg(180.0, 198.0, "Chicago, IL", "Indianapolis, IN"),
    Leg(1100.0, 1020.0, "Indianapolis, IN", "Denver, CO"),
)

FX_8B = Fixture(
    "8b",
    LEGS_8B,
    20 * 60,
    480,
    (
        E(0, 480, "OFF", "off_before_start", 0.0),
        E(480, 510, "ON", "pre_trip", 0.0),
        E(510, 720, "D", "drive", 180.0),
        E(720, 780, "ON", "pickup", 180.0),
        E(780, 1230, "D", "drive", 665.294),
        E(1230, 1830, "SB", "rest", 665.294),
        E(1830, 1860, "ON", "pre_trip", 665.294),
        E(1860, 2160, "D", "drive", 988.824),
        E(2160, 2190, "ON", "fuel", 988.824),
        E(2190, 2460, "D", "drive", 1280.0),
        E(2460, 2520, "ON", "dropoff", 1280.0),
        E(2520, 2880, "OFF", "off_after_end", 1280.0),
    ),
    (
        SheetX(
            (8.0, 3.5, 11.0, 1.5),
            665.3,
            12.5,
            32.5,
            37.5,
            32.5,
            False,
            "OFF 00:00-08:00, ON 08:00-08:30, D 08:30-12:00, ON 12:00-13:00, D 13:00-20:30, SB 20:30-24:00",
            "08:00 08:30 12:00 13:00 20:30",
            "08:00-08:30, 12:00-13:00, 20:30-24:00",
        ),
        SheetX(
            (6.0, 6.5, 9.5, 2.0),
            614.7,
            11.5,
            44.0,
            26.0,
            44.0,
            False,
            "SB 00:00-06:30, ON 06:30-07:00, D 07:00-12:00, ON 12:00-12:30, D 12:30-17:00, "
            "ON 17:00-18:00, OFF 18:00-24:00",
            "06:30 07:00 12:00 12:30 17:00 18:00",
            "00:00-07:00, 12:00-12:30, 17:00-18:00",
        ),
    ),
    SummaryX(2460, 2520, 2, 1, 0, 1, 0, 1280.0, 2640),
)

# --- 8c: same legs, cycle 62 ----------------------------------------------------------------------
FX_8C = Fixture(
    "8c",
    LEGS_8B,
    62 * 60,
    480,
    (
        E(0, 480, "OFF", "off_before_start", 0.0),
        E(480, 510, "ON", "pre_trip", 0.0),
        E(510, 720, "D", "drive", 180.0),
        E(720, 780, "ON", "pickup", 180.0),
        E(780, 960, "D", "drive", 374.118),
        E(960, 3000, "OFF", "restart", 374.118),
        E(3000, 3030, "ON", "pre_trip", 374.118),
        E(3030, 3510, "D", "drive", 891.765),
        E(3510, 3540, "OFF", "break", 891.765),
        E(3540, 3630, "D", "drive", 988.824),
        E(3630, 3660, "ON", "fuel", 988.824),
        E(3660, 3750, "D", "drive", 1085.882),
        E(3750, 4350, "SB", "rest", 1085.882),
        E(4350, 4380, "ON", "pre_trip", 1085.882),
        E(4380, 4560, "D", "drive", 1280.0),
        E(4560, 4620, "ON", "dropoff", 1280.0),
        E(4620, 5760, "OFF", "off_after_end", 1280.0),
    ),
    (
        SheetX(
            (16.0, 0.0, 6.5, 1.5),
            374.1,
            8.0,
            70.0,
            70.0,
            70.0,
            True,
            "OFF 00:00-08:00, ON 08:00-08:30, D 08:30-12:00, ON 12:00-13:00, D 13:00-16:00, OFF 16:00-24:00",
        ),
        SheetX((24.0, 0.0, 0.0, 0.0), 0.0, 0.0, 70.0, 70.0, 70.0, True, "OFF 00:00-24:00"),
        SheetX(
            (2.5, 9.5, 11.0, 1.0),
            711.8,
            12.0,
            12.0,
            58.0,
            12.0,
            False,
            "OFF 00:00-02:00, ON 02:00-02:30, D 02:30-10:30, OFF 10:30-11:00, D 11:00-12:30, "
            "ON 12:30-13:00, D 13:00-14:30, SB 14:30-24:00",
        ),
        SheetX(
            (19.0, 0.5, 3.0, 1.5),
            194.1,
            4.5,
            16.5,
            53.5,
            16.5,
            False,
            "SB 00:00-00:30, ON 00:30-01:00, D 01:00-04:00, ON 04:00-05:00, OFF 05:00-24:00",
        ),
    ),
    SummaryX(4560, 4620, 4, 1, 1, 1, 1, 1280.0, 990),
)

# --- 8d: short local trip, cycle 10 ---------------------------------------------------------------
LEGS_8D = (
    Leg(42.0, 52.0, "Chicago, IL", "Joliet, IL"),
    Leg(125.0, 128.0, "Joliet, IL", "Milwaukee, WI"),
)
FX_8D = Fixture(
    "8d",
    LEGS_8D,
    10 * 60,
    480,
    (
        E(0, 480, "OFF", "off_before_start", 0.0),
        E(480, 510, "ON", "pre_trip", 0.0),
        E(510, 570, "D", "drive", 42.0),
        E(570, 630, "ON", "pickup", 42.0),
        E(630, 765, "D", "drive", 167.0),
        E(765, 825, "ON", "dropoff", 167.0),
        E(825, 1440, "OFF", "off_after_end", 167.0),
    ),
    (
        SheetX(
            (18.25, 0.0, 3.25, 2.5),
            167.0,
            5.75,
            15.75,
            54.25,
            15.75,
            False,
            "OFF 00:00-08:00, ON 08:00-08:30, D 08:30-09:30, ON 09:30-10:30, D 10:30-12:45, "
            "ON 12:45-13:45, OFF 13:45-24:00",
            "08:00 08:30 09:30 10:30 12:45 13:45",
            "08:00-08:30, 09:30-10:30, 12:45-13:45",
        ),
    ),
    SummaryX(765, 825, 1, 0, 0, 0, 0, 167.0, 945),
)

# --- 8e: trip 8b at cycle 70 -----------------------------------------------------------------------
_SHIFT_8E = 1560
FX_8E = Fixture(
    "8e",
    LEGS_8B,
    70 * 60,
    480,
    (
        E(0, 2040, "OFF", "restart", 0.0),
        E(2040, 2070, "ON", "pre_trip", 0.0),
        E(2070, 2280, "D", "drive", 180.0),
        E(2280, 2340, "ON", "pickup", 180.0),
        E(2340, 2790, "D", "drive", 665.294),
        E(2790, 3390, "SB", "rest", 665.294),
        E(3390, 3420, "ON", "pre_trip", 665.294),
        E(3420, 3720, "D", "drive", 988.824),
        E(3720, 3750, "ON", "fuel", 988.824),
        E(3750, 4020, "D", "drive", 1280.0),
        E(4020, 4080, "ON", "dropoff", 1280.0),
        E(4080, 4320, "OFF", "off_after_end", 1280.0),
    ),
    (
        SheetX(
            (24.0, 0.0, 0.0, 0.0), 0.0, 0.0, 70.0, 70.0, 70.0, True, "OFF 00:00-24:00", "00:00", "00:00-24:00"
        ),
        SheetX(
            (10.0, 1.5, 11.0, 1.5),
            665.3,
            12.5,
            12.5,
            57.5,
            12.5,
            False,
            "OFF 00:00-10:00, ON 10:00-10:30, D 10:30-14:00, ON 14:00-15:00, D 15:00-22:30, SB 22:30-24:00",
            None,
            "00:00-10:30, 14:00-15:00, 22:30-24:00",
        ),
        SheetX(
            (4.0, 8.5, 9.5, 2.0),
            614.7,
            11.5,
            24.0,
            46.0,
            24.0,
            False,
            "SB 00:00-08:30, ON 08:30-09:00, D 09:00-14:00, ON 14:00-14:30, D 14:30-19:00, "
            "ON 19:00-20:00, OFF 20:00-24:00",
        ),
    ),
    SummaryX(4020, 4080, 3, 1, 0, 1, 1, 1280.0, 1440),
    warnings=("CYCLE_RESTART_AT_START",),
)

# --- 8f: zero-length first leg, standalone break, cycle 30 -----------------------------------------
LEGS_8F = (
    Leg(0.0, 0.0, "Chicago, IL", "Chicago, IL (shipper)"),
    Leg(532.0, 523.0, "Chicago, IL (shipper)", "Memphis, TN"),
)
FX_8F = Fixture(
    "8f",
    LEGS_8F,
    30 * 60,
    480,
    (
        E(0, 480, "OFF", "off_before_start", 0.0),
        E(480, 510, "ON", "pre_trip", 0.0),
        E(510, 570, "ON", "pickup", 0.0),
        E(570, 1050, "D", "drive", 486.4),
        E(1050, 1080, "OFF", "break", 486.4),
        E(1080, 1125, "D", "drive", 532.0),
        E(1125, 1185, "ON", "dropoff", 532.0),
        E(1185, 1440, "OFF", "off_after_end", 532.0),
    ),
    (
        SheetX(
            (12.75, 0.0, 8.75, 2.5),
            532.0,
            11.25,
            41.25,
            28.75,
            41.25,
            False,
            "OFF 00:00-08:00, ON 08:00-09:30, D 09:30-17:30, OFF 17:30-18:00, D 18:00-18:45, "
            "ON 18:45-19:45, OFF 19:45-24:00",
            "08:00 08:30 09:30 17:30 18:00 18:45 19:45",
            "08:00-09:30, 17:30-18:00, 18:45-19:45",
        ),
    ),
    SummaryX(1125, 1185, 1, 0, 1, 0, 0, 532.0, 2475),
)

# --- 8g: revised A10, trip 8b at cycle 55 ----------------------------------------------------------
FX_8G = Fixture(
    "8g",
    LEGS_8B,
    55 * 60,
    480,
    (
        E(0, 480, "OFF", "off_before_start", 0.0),
        E(480, 510, "ON", "pre_trip", 0.0),
        E(510, 720, "D", "drive", 180.0),
        E(720, 780, "ON", "pickup", 180.0),
        E(780, 1230, "D", "drive", 665.294),
        E(1230, 3270, "OFF", "restart", 665.294),
        E(3270, 3300, "ON", "pre_trip", 665.294),
        E(3300, 3600, "D", "drive", 988.824),
        E(3600, 3630, "ON", "fuel", 988.824),
        E(3630, 3900, "D", "drive", 1280.0),
        E(3900, 3960, "ON", "dropoff", 1280.0),
        E(3960, 4320, "OFF", "off_after_end", 1280.0),
    ),
    (
        SheetX(
            (11.5, 0.0, 11.0, 1.5),
            665.3,
            12.5,
            67.5,
            70.0,
            67.5,
            True,
            "OFF 00:00-08:00, ON 08:00-08:30, D 08:30-12:00, ON 12:00-13:00, D 13:00-20:30, OFF 20:30-24:00",
            "08:00 08:30 12:00 13:00 20:30",
            "08:00-08:30, 12:00-13:00, 20:30-24:00",
        ),
        SheetX((24.0, 0.0, 0.0, 0.0), 0.0, 0.0, 67.5, 70.0, 67.5, True, "OFF 00:00-24:00", "", "00:00-24:00"),
        SheetX(
            (12.5, 0.0, 9.5, 2.0),
            614.7,
            11.5,
            11.5,
            58.5,
            11.5,
            False,
            "OFF 00:00-06:30, ON 06:30-07:00, D 07:00-12:00, ON 12:00-12:30, D 12:30-17:00, "
            "ON 17:00-18:00, OFF 18:00-24:00",
            "06:30 07:00 12:00 12:30 17:00 18:00",
            "00:00-07:00, 12:00-12:30, 17:00-18:00",
        ),
    ),
    SummaryX(3900, 3960, 3, 1, 0, 0, 1, 1280.0, 690),
)

# --- 8h: restart ending exactly at 24:00 -----------------------------------------------------------
LEGS_8H = (
    Leg(600.0, 600.0, "Dallas, TX", "Little Rock, AR"),
    Leg(100.0, 100.0, "Little Rock, AR", "Memphis, TN"),
)
FX_8H = Fixture(
    "8h",
    LEGS_8H,
    64 * 60,
    480,
    (
        E(0, 480, "OFF", "off_before_start", 0.0),
        E(480, 510, "ON", "pre_trip", 0.0),
        E(510, 840, "D", "drive", 330.0),
        E(840, 2880, "OFF", "restart", 330.0),
        E(2880, 2910, "ON", "pre_trip", 330.0),
        E(2910, 3180, "D", "drive", 600.0),
        E(3180, 3240, "ON", "pickup", 600.0),
        E(3240, 3345, "D", "drive", 700.0),
        E(3345, 3405, "ON", "dropoff", 700.0),
        E(3405, 4320, "OFF", "off_after_end", 700.0),
    ),
    (
        SheetX(
            (18.0, 0.0, 5.5, 0.5),
            330.0,
            6.0,
            70.0,
            70.0,
            70.0,
            True,
            "OFF 00:00-08:00, ON 08:00-08:30, D 08:30-14:00, OFF 14:00-24:00",
        ),
        SheetX((24.0, 0.0, 0.0, 0.0), 0.0, 0.0, 0.0, 70.0, 0.0, False, "OFF 00:00-24:00"),
        SheetX(
            (15.25, 0.0, 6.25, 2.5),
            370.0,
            8.75,
            8.75,
            61.25,
            8.75,
            False,
            "ON 00:00-00:30, D 00:30-05:00, ON 05:00-06:00, D 06:00-07:45, ON 07:45-08:45, OFF 08:45-24:00",
        ),
    ),
    SummaryX(3345, 3405, 3, 0, 0, 0, 1, 700.0, 525),
)

# --- 8a: John Doe (feeds day_splitter directly; never through plan()) -----------------------------
# (start, end, status, kind, cumulative mile at end) per the spec table, HH:MM in the spec.
JOHN_DOE_ROWS = (
    ("00:00", "06:00", "OFF", "off_before_start", 0.0),
    ("06:00", "07:30", "ON", "pre_trip", 0.0),
    ("07:30", "09:00", "D", "drive", 67.742),
    ("09:00", "09:30", "ON", "fuel", 67.742),
    ("09:30", "12:00", "D", "drive", 180.645),
    ("12:00", "13:00", "OFF", "break", 180.645),
    ("13:00", "15:00", "D", "drive", 270.968),
    ("15:00", "15:30", "ON", "dropoff", 270.968),
    ("15:30", "16:00", "D", "drive", 293.548),
    ("16:00", "17:45", "SB", "rest", 293.548),
    ("17:45", "19:00", "D", "drive", 350.0),
    ("19:00", "21:00", "ON", "dropoff", 350.0),
    ("21:00", "24:00", "OFF", "off_after_end", 350.0),
)
JOHN_DOE_REMARKS = "06:00 07:30 09:00 09:30 12:00 13:00 15:00 15:30 16:00 17:45 19:00 21:00"
JOHN_DOE_BRACKETS = "06:00-07:30, 09:00-09:30, 12:00-13:00, 15:00-15:30, 16:00-17:45, 19:00-21:00"

TRIP_FIXTURES = {f.name: f for f in (FX_8B, FX_8C, FX_8D, FX_8E, FX_8F, FX_8G, FX_8H)}
