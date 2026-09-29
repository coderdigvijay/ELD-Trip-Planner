"""Frozen data model of the HOS engine (HOS_ENGINE_SPEC section 2)."""

from dataclasses import dataclass
from enum import StrEnum


class HosInputError(ValueError):
    """The engine input is invalid. Always our bug or bad upstream data (maps to INTERNAL in the service)."""


class HosEngineError(RuntimeError):
    """The simulation could not make progress. Always an engine bug."""


class Status(StrEnum):
    """Duty status, log lines 1..4."""

    OFF = "OFF"
    SB = "SB"
    D = "D"
    ON = "ON"


class Kind(StrEnum):
    """Why an event exists. Values are snake_case."""

    PRE_TRIP = "pre_trip"
    DRIVE = "drive"
    PICKUP = "pickup"
    DROPOFF = "dropoff"
    FUEL = "fuel"
    BREAK = "break"
    REST = "rest"
    RESTART = "restart"
    OFF_BEFORE_START = "off_before_start"
    OFF_AFTER_END = "off_after_end"


@dataclass(frozen=True)
class Leg:
    distance_mi: float  # >= 0, exact: ORS meters / 1609.344, never rounded by the caller
    duration_min: float  # >= 0, exact: ORS seconds / 60, never rounded by the caller
    from_label: str  # "Chicago, IL"
    to_label: str


@dataclass(frozen=True)
class TripInput:
    legs: tuple[Leg, Leg]  # [current -> pickup, pickup -> dropoff]
    cycle_used_min: int  # 0..4200, multiple of 15
    start_min: int = 480  # local minute on day 0, multiple of 15, 0..1425


@dataclass(frozen=True)
class DutyEvent:
    start_min_abs: int  # minutes from 00:00 day 0
    end_min_abs: int  # exclusive; > start
    status: Status
    kind: Kind
    leg_index: int | None  # 0 or 1 while on/after that leg's route; None before any leg starts
    start_mile: float  # cumulative trip miles (rounded to 3 dp at output only)
    end_mile: float  # == start_mile unless status is D
    leg_mile: float  # miles into leg_index at end of event
    location_label: str | None  # known label by the rule in 5.3, or None
    note: str  # remark text
    reason: str  # why the stop happened, "" for drive / pre_trip

    @property
    def stationary(self) -> bool:
        return self.status != Status.D


@dataclass(frozen=True)
class Segment:
    """An event clipped to one sheet."""

    start_min: int  # 0..1440 local to the sheet
    end_min: int
    status: Status
    kind: Kind
    start_mile: float
    end_mile: float


@dataclass(frozen=True)
class Remark:
    minute: int  # 0..1439 local to the sheet
    status: Status  # the status that begins here
    status_change: bool  # False = note-only remark (same status, new kind)
    mile: float
    leg_index: int | None
    leg_mile: float
    location_label: str | None
    note: str


@dataclass(frozen=True)
class Recap:
    """70 hr / 8 day side, minutes."""

    on_duty_today: int  # lines 3 + 4 of this sheet
    a_last_7: int
    b_available_tomorrow: int
    c_last_8: int
    restart_note: bool  # a restart is in progress at this sheet's 24:00


@dataclass(frozen=True)
class DaySheet:
    day_index: int
    segments: tuple[Segment, ...]  # contiguous 0..1440
    totals: dict[Status, int]  # OFF, SB, D, ON minutes; sum == 1440
    miles_today: float  # 1 dp
    from_mile: float  # position at 00:00
    to_mile: float  # position at 24:00
    remarks: tuple[Remark, ...]
    brackets: tuple[tuple[int, int], ...]  # (start_min, end_min) local
    recap: Recap


@dataclass(frozen=True)
class Summary:
    total_miles: float  # exact trip total rounded once, half up, 1 dp
    total_drive_min: int
    total_on_duty_min: int
    start_min_abs: int
    arrive_dropoff_min_abs: int  # dropoff start
    complete_min_abs: int  # dropoff end
    sheet_count: int
    fuel_stops: int
    breaks: int
    rests: int
    restarts: int
    cycle_end_min: int  # cycle_on_duty at dropoff end


@dataclass(frozen=True)
class EngineWarning:
    code: str  # stable code, the service copies it to trip.warnings
    message: str


@dataclass(frozen=True)
class PlanResult:
    events: tuple[DutyEvent, ...]
    sheets: tuple[DaySheet, ...]
    summary: Summary
    warnings: tuple[EngineWarning, ...]  # () or (CYCLE_RESTART_AT_START,)
