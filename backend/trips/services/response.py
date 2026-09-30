"""Pure response builders (docs/API_CONTRACT.md 4.2 and 5.2). No I/O, no clock, no Django.

`build_plan_response` turns the engine result plus already-resolved places, legs and mid-route
labels into the JSON-ready DTO. `required_point_keys` runs the same walk against a recorder to
list, in priority order, every mid-route position that still needs a label, so the service can
reverse-geocode exactly those and nothing else.

Miles are keyed in thousandths (`MileGrid.key`): the engine reports cumulative miles at 3 dp, and
positions within one thousandth of the current, pickup or dropoff mile snap to that place.
"""

from __future__ import annotations

import datetime as dt
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any

import hos
from hos.exact import as_float, ceil15, round_half_up, to_fraction
from hos.models import DutyEvent, Kind, Status
from hos.rules import DAY_MIN

Dto = dict[str, Any]

LABEL_INPUT, LABEL_GEOCODED, LABEL_NEARBY, LABEL_COORDINATES = "input", "geocoded", "nearby", "coordinates"
COORD_DP = 5

STATUS_NAME = {Status.OFF: "off", Status.SB: "sleeper", Status.D: "driving", Status.ON: "on_duty"}

# Stop kind -> (duty_status, note, leg_index or None = from the engine event). API_CONTRACT 5.2 table.
STOP_TABLE: dict[str, tuple[str, str]] = {
    "start": ("on_duty", "Pre-trip inspection"),
    "pickup": ("on_duty", "Pickup"),
    "dropoff": ("on_duty", "Dropoff"),
    "fuel": ("on_duty", "Fuel"),
    "break": ("off", "30-min break"),
    "rest": ("sleeper", "10-hr rest (sleeper)"),
    "restart": ("off", "34-hr restart"),
    "end": ("off", "Released from duty"),
}
_KIND_TO_STOP = {
    Kind.PICKUP: "pickup",
    Kind.DROPOFF: "dropoff",
    Kind.FUEL: "fuel",
    Kind.BREAK: "break",
    Kind.REST: "rest",
    Kind.RESTART: "restart",
}
END_REASON = "Trip complete"

WARNING_CAR = {
    "code": "CAR_PROFILE_USED",
    "message": "No truck route was found, so a car route was used. Real truck restrictions may differ.",
}
WARNING_LABELS = {
    "code": "LABELS_APPROXIMATED",
    "message": "Some log remark places are shown as 'near' a known place or as coordinates.",
}

_ASSUMPTION_TEXT = {
    "A1": "You are off duty from midnight until the trip starts, with fresh 11- and 14-hour clocks.",
    "A2": "The trip starts on the trip date at your start time (default 08:00), on a 15-minute step.",
    "A3": "All times use the home terminal's time ({home}) for the whole trip.",
    "A4": "Each shift starts with a 30-minute pre-trip inspection (on duty).",
    "A5": "There is no separate post-trip block; the 1-hour dropoff covers it.",
    "A6": "Pickup and dropoff each take 1 hour on duty.",
    "A7": "Fueling takes 30 minutes on duty, at least every 1,000 miles. The truck starts full.",
    "A8": "Any 30 consecutive minutes not driving meet the break rule, else 30 minutes off duty are added.",
    "A9": "Each 10-hour rest is logged as Sleeper Berth.",
    "A10": (
        "A 34-hour restart (off duty) is taken when the 70-hour limit blocks driving, or when a 10-hour rest "
        "is due and the cycle hours left do not cover the rest of the trip."
    ),
    "A11": "None of your previous cycle hours expire during the trip (conservative).",
    "A12": "Driving time for each leg comes from truck routing (OpenRouteService, heavy goods vehicle).",
    "A13": "Everything is planned on a 15-minute grid, rounding toward compliance.",
    "A14": "No split sleeper, adverse conditions, short-haul, personal conveyance or pilot programs.",
    "A15": "You are off duty after the dropoff until midnight of the last day.",
    "A16": "Driving resumes as soon as it is legal.",
    "A17": (
        "If a due 30-minute break would leave less than 15 minutes of driving in the 14-hour window, "
        "the plan takes the 10-hour rest instead."
    ),
}

LOG_HEADER_KEYS = (
    "driver_name",
    "carrier_name",
    "main_office_address",
    "home_terminal_address",
    "truck_number",
    "trailer_number",
    "shipping_doc",
    "shipper_commodity",
)


class ResponseBuildError(RuntimeError):
    """The engine output broke a response invariant. Always our bug (the service maps it to INTERNAL)."""


@dataclass(frozen=True, slots=True)
class PlaceView:
    label: str
    lat: float
    lng: float
    source: str  # "input" | "geocoded"


@dataclass(frozen=True, slots=True)
class Bounds:
    south: float
    west: float
    north: float
    east: float

    def as_dto(self) -> Dto:
        return {
            "south": round(self.south, COORD_DP),
            "west": round(self.west, COORD_DP),
            "north": round(self.north, COORD_DP),
            "east": round(self.east, COORD_DP),
        }

    @classmethod
    def around(cls, points: Iterable[tuple[float, float]]) -> Bounds:
        pts = list(points)
        lats, lngs = [p[0] for p in pts], [p[1] for p in pts]
        return cls(min(lats), min(lngs), max(lats), max(lngs))

    def union(self, other: Bounds) -> Bounds:
        return Bounds(
            min(self.south, other.south),
            min(self.west, other.west),
            max(self.north, other.north),
            max(self.east, other.east),
        )


@dataclass(frozen=True, slots=True)
class LegView:
    polyline: str  # "" for a zero-length leg
    distance_mi: float  # exact, as passed to the engine
    duration_min: float  # exact, as passed to the engine
    bounds: Bounds
    ors_duration_min: float | None = None  # raw ORS estimate for duration_h; None = same as engine

    @property
    def reported_duration_min(self) -> float:
        return self.duration_min if self.ors_duration_min is None else self.ors_duration_min


@dataclass(frozen=True, slots=True)
class PointInfo:
    """A mid-route position with its label. `source` is geocoded, nearby or coordinates."""

    lat: float
    lng: float
    label: str
    source: str


@dataclass(frozen=True, slots=True)
class Timing:
    name: str
    abbreviation: str
    offset_minutes: int
    utc_offset: str  # "-04:00"
    day0: dt.datetime  # 00:00 of sheet 1, tz-aware in the frozen offset


@dataclass(frozen=True, slots=True)
class ResponseInput:
    places: tuple[PlaceView, PlaceView, PlaceView]
    legs: tuple[LegView, LegView]
    profile: str
    plan: hos.PlanResult
    points: Mapping[int, PointInfo]
    timing: Timing
    cycle_used_h: float
    log_header: Mapping[str, str]
    labels_approximated: bool = False


@dataclass(frozen=True, slots=True)
class MileGrid:
    """Snaps engine miles to integer thousandths and to the three known places."""

    pickup_key: int
    end_key: int
    pickup_tenths: float
    total_tenths: float

    @classmethod
    def for_legs(cls, leg0_mi: float, leg1_mi: float) -> MileGrid:
        first, total = to_fraction(leg0_mi), to_fraction(leg0_mi) + to_fraction(leg1_mi)
        return cls(
            pickup_key=int(round_half_up(first, 3) * 1000),
            end_key=int(round_half_up(total, 3) * 1000),
            pickup_tenths=as_float(first, 1),
            total_tenths=as_float(total, 1),
        )

    def key(self, mile: float) -> int:
        raw = round(mile * 1000)
        for anchor in (0, self.pickup_key, self.end_key):
            if abs(raw - anchor) <= 1:
                return anchor
        return raw

    def tenths(self, mile: float) -> float:
        key = self.key(mile)
        if key == 0:
            return 0.0
        if key == self.pickup_key:
            return self.pickup_tenths
        if key == self.end_key:
            return self.total_tenths
        return as_float(Fraction(key, 1000), 1)

    def is_anchor(self, key: int) -> bool:
        return key in (0, self.pickup_key, self.end_key)


@dataclass(frozen=True, slots=True)
class Where:
    label: str
    source: str
    lat: float
    lng: float


def hours(minutes: int | float) -> float:
    """Minutes to hours, 2 dp half up (every engine duration is on the 15 minute grid)."""
    return as_float(Fraction(str(minutes)) / 60, 2)


def _merge_key(row: Dto) -> tuple:
    return row["status"], row["stop_id"], row["note"]


class _Builder:
    def __init__(self, inp: ResponseInput) -> None:
        self.inp = inp
        self.events = inp.plan.events
        self.starts = [e.start_min_abs for e in self.events]
        self.grid = MileGrid.for_legs(inp.legs[0].distance_mi, inp.legs[1].distance_mi)
        self.stops: list[Dto] = []
        self.event_stop: list[str | None] = [None] * len(self.events)
        self._assign_stops()

    # ---- time helpers

    def at(self, minute: int) -> str:
        return (self.inp.timing.day0 + dt.timedelta(minutes=minute)).isoformat()

    # ---- places and labels

    def _place_index(self, e: DutyEvent) -> int:
        """Which known place the engine's label at the START of `e` came from (HOS_ENGINE_SPEC 5.3)."""
        if e.kind == Kind.PICKUP:
            return 1
        if e.kind in (Kind.DROPOFF, Kind.OFF_AFTER_END):
            return 2
        if e.leg_index is None:
            return 0
        if e.status == Status.D:
            return e.leg_index
        if e.leg_index == 0:
            return 0 if e.leg_mile == 0 else 1
        return 1 if e.leg_mile == 0 else 2

    def _where_key(self, key: int) -> Where:
        places = self.inp.places
        for anchor, place in (
            (self.grid.end_key, places[2]),
            (self.grid.pickup_key, places[1]),
            (0, places[0]),
        ):
            if key == anchor:
                return Where(place.label, place.source, place.lat, place.lng)
        info = self.inp.points[key]
        return Where(info.label, info.source, info.lat, info.lng)

    def where_event(self, e: DutyEvent) -> Where:
        """Place at the start of `e` (for non-driving events, the place of the whole event)."""
        if e.location_label is not None:
            place = self.inp.places[self._place_index(e)]
            return Where(e.location_label, place.source, place.lat, place.lng)
        return self._where_key(self.grid.key(e.start_mile))

    def where_mile(self, mile: float) -> Where:
        return self._where_key(self.grid.key(mile))

    def event_index(self, minute_abs: int) -> int:
        return bisect_right(self.starts, minute_abs) - 1

    # ---- stops

    def _assign_stops(self) -> None:
        seen_pre_trip = False
        current: dict[str, Any] | None = None
        for index, e in enumerate(self.events):
            kind = None
            if e.kind == Kind.PRE_TRIP and not seen_pre_trip:
                kind, seen_pre_trip = "start", True
            elif e.kind == Kind.PRE_TRIP:
                if current is None or current["last"] != index - 1:
                    raise ResponseBuildError("a mid-trip pre-trip does not follow a stop")
                current["last"] = index
                current["depart"] = e.end_min_abs
                self.event_stop[index] = current["id"]
                continue
            else:
                kind = _KIND_TO_STOP.get(e.kind)
            if kind is None:
                continue
            current = {
                "id": f"s{len(self.stops) + 1}",
                "kind": kind,
                "event": index,
                "last": index,
                "arrive": e.start_min_abs,
                "depart": e.end_min_abs,
            }
            self.event_stop[index] = current["id"]
            self.stops.append(current)

    def stops_dto(self) -> list[Dto]:
        rows = [self._stop_row(s) for s in self.stops]
        rows.append(self._end_row(f"s{len(self.stops) + 1}"))
        for a, b in zip(rows, rows[1:], strict=False):
            if a["arrive_at"] > b["arrive_at"] or a["cumulative_mi"] > b["cumulative_mi"]:
                raise ResponseBuildError("stops are not ordered by time and miles")
        return rows

    def _stop_row(self, stop: Dto) -> Dto:
        e = self.events[stop["event"]]
        kind = stop["kind"]
        where = self.where_event(e)
        status, note = STOP_TABLE[kind]
        if kind == "pickup":
            miles, leg = self.grid.pickup_tenths, 0
        elif kind == "dropoff":
            miles, leg = self.grid.total_tenths, 1
        elif kind == "start":
            miles, leg = self.grid.tenths(e.start_mile), 0
        else:
            miles, leg = self.grid.tenths(e.start_mile), e.leg_index or 0
        return {
            "id": stop["id"],
            "kind": kind,
            "lat": round(where.lat, COORD_DP),
            "lng": round(where.lng, COORD_DP),
            "label": where.label,
            "label_source": where.source,
            "arrive_at": self.at(stop["arrive"]),
            "depart_at": self.at(stop["depart"]),
            "duration_h": hours(stop["depart"] - stop["arrive"]),
            "duty_status": status,
            "cumulative_mi": miles,
            "leg_index": leg,
            "note": note,
            "reason": e.reason,
        }

    def _end_row(self, stop_id: str) -> Dto:
        summary = self.inp.plan.summary
        place = self.inp.places[2]
        status, note = STOP_TABLE["end"]
        released = self.at(summary.complete_min_abs)
        return {
            "id": stop_id,
            "kind": "end",
            "lat": round(place.lat, COORD_DP),
            "lng": round(place.lng, COORD_DP),
            "label": place.label,
            "label_source": place.source,
            "arrive_at": released,
            "depart_at": released,
            "duration_h": 0.0,
            "duty_status": status,
            "cumulative_mi": self.grid.total_tenths,
            "leg_index": 1,
            "note": note,
            "reason": END_REASON,
        }

    # ---- timeline

    def timeline_dto(self) -> list[Dto]:
        rows: list[Dto] = []
        for index, e in enumerate(self.events):
            start = self.where_event(e)
            end = self.where_mile(e.end_mile) if e.status == Status.D else start
            row = {
                "start_min": e.start_min_abs,
                "end_min": e.end_min_abs,
                "start_at": self.at(e.start_min_abs),
                "end_at": self.at(e.end_min_abs),
                "status": STATUS_NAME[e.status],
                "stop_id": self.event_stop[index],
                "start_label": start.label,
                "end_label": end.label,
                "start_mi": self.grid.tenths(e.start_mile),
                "end_mi": self.grid.tenths(e.end_mile),
                "note": e.note,
            }
            self._append_merged(rows, row, ("end_min", "end_at", "end_label", "end_mi"))
        return rows

    @staticmethod
    def _append_merged(rows: list[Dto], row: Dto, copy_from_new: tuple[str, ...]) -> None:
        if rows and _merge_key(rows[-1]) == _merge_key(row):
            for name in copy_from_new:
                rows[-1][name] = row[name]
        else:
            rows.append(row)

    # ---- days

    def days_dto(self) -> list[Dto]:
        return [self._day(sheet) for sheet in self.inp.plan.sheets]

    def _segment_ends(self, sheet_index: int, seg: hos.Segment) -> tuple[Where, Where, int]:
        """Place at the start and at the end of a clipped segment, and its event index."""
        base = sheet_index * DAY_MIN
        index = self.event_index(base + seg.start_min)
        e = self.events[index]
        start = self.where_event(e)
        if e.status == Status.D:
            if base + seg.start_min != e.start_min_abs:
                start = self.where_mile(seg.start_mile)
            return start, self.where_mile(seg.end_mile), index
        return start, start, index

    def _day(self, sheet: hos.DaySheet) -> Dto:
        rows: list[Dto] = []
        first_where = last_where = None
        for seg in sheet.segments:
            start, end, index = self._segment_ends(sheet.day_index, seg)
            first_where = first_where or start
            last_where = end
            e = self.events[index]
            row = {
                "start_min": seg.start_min,
                "end_min": seg.end_min,
                "status": STATUS_NAME[seg.status],
                "location_label": end.label,
                "note": e.note,
                "stationary": self.event_stop[index] is not None,
                "stop_id": self.event_stop[index],
            }
            self._append_merged(rows, row, ("end_min", "location_label"))
        if first_where is None or last_where is None:
            raise ResponseBuildError("a sheet has no segments")
        totals = sheet.totals
        return {
            "date": (self.inp.timing.day0 + dt.timedelta(days=sheet.day_index)).date().isoformat(),
            "sheet_index": sheet.day_index + 1,
            "from_label": first_where.label,
            "to_label": last_where.label,
            "miles_driven": sheet.miles_today,
            "segments": rows,
            "remarks": [self._remark(r) for r in sheet.remarks],
            "totals": {name: hours(totals[status]) for status, name in STATUS_NAME.items()},
            "recap": self._recap(sheet),
        }

    def _remark(self, remark: hos.Remark) -> Dto:
        label = remark.location_label
        if label is None:
            label = self.where_mile(remark.mile).label
        return {"minute": remark.minute, "location_label": label, "note": remark.note}

    def _recap(self, sheet: hos.DaySheet) -> Dto:
        recap = sheet.recap
        return {
            "on_duty_today": hours(recap.on_duty_today),
            "a_last7": hours(recap.a_last_7),
            "b_available_tomorrow": hours(recap.b_available_tomorrow),
            "c_last8": hours(recap.c_last_8),
            "restart_note": self._restart_note(sheet.day_index) if recap.restart_note else None,
        }

    def _restart_note(self, day_index: int) -> str:
        midnight = (day_index + 1) * DAY_MIN
        for e in self.events:
            if e.kind == Kind.RESTART and e.start_min_abs < midnight < e.end_min_abs:
                ends = self.inp.timing.day0 + dt.timedelta(minutes=e.end_min_abs)
                return f"34-hr restart ends {ends:%m/%d %H:%M}"
        raise ResponseBuildError("restart in progress but no restart event spans the midnight")

    # ---- trip, route, summary

    def trip_dto(self) -> Dto:
        inp, timing = self.inp, self.inp.timing
        current = inp.places[0]
        header = {key: (inp.log_header.get(key) or "") for key in LOG_HEADER_KEYS}
        for key in ("main_office_address", "home_terminal_address"):
            header[key] = header[key] or current.label
        warnings = [{"code": w.code, "message": w.message} for w in inp.plan.warnings]
        if inp.profile == "driving-car":
            warnings.append(dict(WARNING_CAR))
        if inp.labels_approximated:
            warnings.append(dict(WARNING_LABELS))
        home = f"{current.label}, UTC{timing.utc_offset}"
        return {
            "places": {
                name: {
                    "label": p.label,
                    "lat": round(p.lat, COORD_DP),
                    "lng": round(p.lng, COORD_DP),
                    "source": p.source,
                }
                for name, p in zip(("current", "pickup", "dropoff"), inp.places, strict=True)
            },
            "timezone": {
                "name": timing.name,
                "abbreviation": timing.abbreviation,
                "utc_offset": timing.utc_offset,
                "utc_offset_min": timing.offset_minutes,
            },
            "start_at": self.at(inp.plan.summary.start_min_abs),
            "cycle_used_start_h": float(inp.cycle_used_h),
            "log_header": header,
            "assumptions": [
                {"id": key, "text": text.format(home=home)} for key, text in _ASSUMPTION_TEXT.items()
            ],
            "warnings": warnings,
        }

    def route_dto(self) -> Dto:
        inp = self.inp
        legs, planned = [], []
        for index, leg in enumerate(inp.legs):
            minutes = ceil15(leg.duration_min)
            planned.append(minutes)
            legs.append(
                {
                    "index": index,
                    "from_label": inp.places[index].label,
                    "to_label": inp.places[index + 1].label,
                    "distance_mi": as_float(to_fraction(leg.distance_mi), 1),
                    "duration_h": as_float(to_fraction(leg.reported_duration_min) / 60, 2),
                    "planned_driving_h": hours(minutes),
                    "polyline": leg.polyline,
                    "bounds": leg.bounds.as_dto(),
                }
            )
        return {
            "profile": inp.profile,
            "distance_mi": self.grid.total_tenths,
            "planned_driving_h": hours(sum(planned)),
            "bounds": inp.legs[0].bounds.union(inp.legs[1].bounds).as_dto(),
            "legs": legs,
        }

    def summary_dto(self, days: list[Dto]) -> Dto:
        s = self.inp.plan.summary
        driving = s.total_drive_min
        other = s.total_on_duty_min - driving
        return {
            "total_distance_mi": self.grid.total_tenths,
            "driving_h": hours(driving),
            "on_duty_not_driving_h": hours(other),
            "on_duty_total_h": hours(s.total_on_duty_min),
            "trip_duration_h": hours(s.complete_min_abs - s.start_min_abs),
            "arrival_at": self.at(s.arrive_dropoff_min_abs),
            "released_at": self.at(s.complete_min_abs),
            "sheet_count": len(days),
            "cycle_used_start_h": float(self.inp.cycle_used_h),
            "cycle_used_end_h": days[-1]["recap"]["a_last7"],
            "counts": {"fuel": s.fuel_stops, "break": s.breaks, "rest": s.rests, "restart": s.restarts},
        }


def build_plan_response(inp: ResponseInput) -> Dto:
    """The full 200 body of POST /trips/plan (API_CONTRACT 5.2)."""
    builder = _Builder(inp)
    stops = builder.stops_dto()
    timeline = builder.timeline_dto()
    days = builder.days_dto()
    return {
        "trip": builder.trip_dto(),
        "route": builder.route_dto(),
        "stops": stops,
        "timeline": timeline,
        "days": days,
        "summary": builder.summary_dto(days),
    }


class _Recorder(Mapping[int, PointInfo]):
    """Stands in for `points` to learn which mid-route keys the DTO will ask for, in first-use order."""

    def __init__(self) -> None:
        self.keys: list[int] = []

    def __getitem__(self, key: int) -> PointInfo:
        if key not in self.keys:
            self.keys.append(key)
        return PointInfo(0.0, 0.0, "", LABEL_COORDINATES)

    def __iter__(self):
        return iter(self.keys)

    def __len__(self) -> int:
        return len(self.keys)


def required_point_keys(inp: ResponseInput) -> list[int]:
    """Mid-route mile keys needing a label, stops first, then driving ends, then sheet edges and remarks."""
    recorder = _Recorder()
    build_plan_response(replace(inp, points=recorder))
    return list(recorder.keys)


def autocomplete_response(places: Iterable[Any]) -> Dto:
    """API_CONTRACT 4.2: at most 5 items, coordinates at 5 dp."""
    items = [
        {"label": p.label, "lat": round(p.lat, COORD_DP), "lng": round(p.lng, COORD_DP)}
        for p in list(places)[:5]
    ]
    return {"items": items}
