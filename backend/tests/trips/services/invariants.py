"""API_CONTRACT section 9 response invariants 1 to 17, asserted on a response DTO.

Written against the JSON shape only (no engine imports) so it is an independent check of both the
engine output and the response builder. Invariant 18 (determinism) is a test of its own.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

DAY = 1440
MIN_DRIVE_LIMIT, WINDOW_LIMIT, BREAK_DRIVE_LIMIT, CYCLE_LIMIT = 660, 840, 480, 4200
REST_MIN, RESTART_MIN, BREAK_MIN = 600, 2040, 30
FUEL_LIMIT_MI = 1000.0
NOTES = {
    "start": "Pre-trip inspection",
    "pickup": "Pickup",
    "dropoff": "Dropoff",
    "fuel": "Fuel",
    "break": "30-min break",
    "rest": "10-hr rest (sleeper)",
    "restart": "34-hr restart",
    "end": "Released from duty",
}
STATUSES = ("off", "sleeper", "driving", "on_duty")


def d1(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def parse(stamp: str) -> dt.datetime:
    return dt.datetime.fromisoformat(stamp)


def assert_invariants(body: dict, *, start_date: dt.date | None = None) -> None:
    trip, stops = body["trip"], body["stops"]
    timeline, days, summary = body["timeline"], body["days"], body["summary"]
    offset = dt.timezone(dt.timedelta(minutes=trip["timezone"]["utc_offset_min"]))
    day0 = dt.datetime.combine(dt.date.fromisoformat(days[0]["date"]), dt.time(0), tzinfo=offset)

    _sheets(body, day0, start_date)
    _timeline(timeline, days)
    _stops(stops, summary, timeline)
    _miles(body)
    _times(body, day0, offset)
    _trip_start_restart(body, day0)
    _hos(body)


def _sheets(body: dict, day0: dt.datetime, start_date: dt.date | None) -> None:
    days, summary, trip = body["days"], body["summary"], body["trip"]
    # 1
    for i, day in enumerate(days):
        assert day["date"] == (day0 + dt.timedelta(days=i)).date().isoformat()
        assert day["sheet_index"] == i + 1
    assert summary["sheet_count"] == len(days)
    if start_date is not None:
        assert days[0]["date"] == start_date.isoformat()
    start_at = parse(trip["start_at"])
    restart_first = body["stops"][0]["kind"] == "restart"
    assert start_at.date() == (day0 + dt.timedelta(days=1 if restart_first else 0)).date()
    previous = None
    for day in days:
        segs = day["segments"]
        # 2 and 3
        assert segs[0]["start_min"] == 0 and segs[-1]["end_min"] == DAY
        for a, b in zip(segs, segs[1:], strict=False):
            assert a["end_min"] == b["start_min"]
        for s in segs:
            assert s["end_min"] > s["start_min"]
            assert s["start_min"] % 15 == 0 and s["end_min"] % 15 == 0
            assert s["stationary"] == (s["stop_id"] is not None)  # 4
        for a, b in zip(segs, segs[1:], strict=False):
            assert (a["status"], a["stop_id"]) != (b["status"], b["stop_id"])
        # 5
        minutes = dict.fromkeys(STATUSES, 0)
        for s in segs:
            minutes[s["status"]] += s["end_min"] - s["start_min"]
        for name in STATUSES:
            assert day["totals"][name] == minutes[name] / 60
            assert (minutes[name] % 15) == 0
        assert sum(day["totals"].values()) == 24
        # 6
        _remarks(day, previous)
        previous = segs[-1]
        # 8
        recap, totals = day["recap"], day["totals"]
        assert recap["on_duty_today"] == totals["driving"] + totals["on_duty"]
        assert recap["a_last7"] == recap["c_last8"]
        if recap["restart_note"] is not None:
            assert recap["b_available_tomorrow"] == 70
        else:
            assert recap["b_available_tomorrow"] == max(0, 70 - recap["a_last7"])
    _restart_notes(body)


def _remarks(day: dict, previous: dict | None) -> None:
    segs, remarks = day["segments"], day["remarks"]
    minutes = [r["minute"] for r in remarks]
    assert minutes == sorted(set(minutes))
    starts = {s["start_min"] for s in segs}
    assert all(m in starts and m % 15 == 0 and 0 <= m < DAY for m in minutes)
    expected = set()
    for i, seg in enumerate(segs):
        if i > 0:
            if (seg["status"], seg["stop_id"]) != (segs[i - 1]["status"], segs[i - 1]["stop_id"]):
                expected.add(seg["start_min"])
        elif previous is not None:
            if (seg["status"], seg["stop_id"]) != (previous["status"], previous["stop_id"]):
                expected.add(0)
        elif seg["note"] == "34-hr restart" or seg["status"] != "off":
            # sheet 1: only a trip-start restart, or a shift that begins at 00:00 (HOS_ENGINE_SPEC S-14)
            expected.add(0)
    assert set(minutes) == expected
    by_start = {s["start_min"]: s for s in segs}
    for r in remarks:
        assert r["note"] == by_start[r["minute"]]["note"]
        assert r["location_label"]


def _restart_notes(body: dict) -> None:
    trip_offset = dt.timezone(dt.timedelta(minutes=body["trip"]["timezone"]["utc_offset_min"]))
    restarts = [s for s in body["stops"] if s["kind"] == "restart"]
    for day in body["days"]:
        midnight = dt.datetime.combine(dt.date.fromisoformat(day["date"]), dt.time(0), tzinfo=trip_offset)
        midnight += dt.timedelta(days=1)
        inside = [r for r in restarts if parse(r["arrive_at"]) < midnight < _restart_end(r, body)]
        note = day["recap"]["restart_note"]
        assert (note is not None) == bool(inside)
        if inside:
            assert note == f"34-hr restart ends {_restart_end(inside[0], body):%m/%d %H:%M}"


def _restart_end(stop: dict, body: dict) -> dt.datetime:
    """End of the restart itself (a mid-trip stop's depart_at includes the pre-trip that follows)."""
    return parse(stop["arrive_at"]) + dt.timedelta(minutes=34 * 60)


def _timeline(timeline: list[dict], days: list[dict]) -> None:
    # 9
    assert timeline[0]["start_min"] == 0 and timeline[-1]["end_min"] == len(days) * DAY
    for a, b in zip(timeline, timeline[1:], strict=False):
        assert a["end_min"] == b["start_min"]
    rebuilt: dict[int, list[tuple]] = {i: [] for i in range(len(days))}
    for period in timeline:
        cursor = period["start_min"]
        while cursor < period["end_min"]:
            sheet = cursor // DAY
            end = min(period["end_min"], (sheet + 1) * DAY)
            rebuilt[sheet].append(
                (cursor - sheet * DAY, end - sheet * DAY, period["status"], period["note"], period["stop_id"])
            )
            cursor = end
    for i, day in enumerate(days):
        got = [(s["start_min"], s["end_min"], s["status"], s["note"], s["stop_id"]) for s in day["segments"]]
        merged: list[tuple] = []
        for seg in rebuilt[i]:
            if merged and merged[-1][2:] == seg[2:]:
                merged[-1] = (merged[-1][0], seg[1], *merged[-1][2:])
            else:
                merged.append(seg)
        assert got == merged


def _stops(stops: list[dict], summary: dict, timeline: list[dict]) -> None:
    # 10
    kinds = [s["kind"] for s in stops]
    for once in ("start", "pickup", "dropoff", "end"):
        assert kinds.count(once) == 1
    arrivals = [parse(s["arrive_at"]) for s in stops]
    assert arrivals == sorted(arrivals)
    miles = [s["cumulative_mi"] for s in stops]
    assert miles == sorted(miles)
    assert [s["id"] for s in stops] == [f"s{i + 1}" for i in range(len(stops))]
    for s in stops:
        assert s["note"] == NOTES[s["kind"]]
        assert s["label"] and s["label_source"] in ("input", "geocoded", "nearby", "coordinates")
    counts = summary["counts"]
    for kind in ("fuel", "break", "rest", "restart"):
        assert counts[kind] == kinds.count(kind)
    ids = {s["id"] for s in stops}
    assert {p["stop_id"] for p in timeline if p["stop_id"]} <= ids
    assert stops[-1]["kind"] == "end" and stops[-1]["duration_h"] == 0.0


def _miles(body: dict) -> None:
    route, summary, days = body["route"], body["summary"], body["days"]
    # 11
    assert route["distance_mi"] == summary["total_distance_mi"]
    assert abs(sum(leg["distance_mi"] for leg in route["legs"]) - route["distance_mi"]) <= 0.1 + 1e-9
    planned = sum(leg["planned_driving_h"] for leg in route["legs"])
    assert route["planned_driving_h"] == planned == summary["driving_h"]
    # 7
    assert sum(d1(d["miles_driven"]) for d in days) == d1(summary["total_distance_mi"])
    assert all(d["miles_driven"] >= 0 for d in days)
    stops = body["stops"]
    assert stops[-1]["cumulative_mi"] == route["distance_mi"]
    assert next(s for s in stops if s["kind"] == "dropoff")["cumulative_mi"] == route["distance_mi"]
    assert next(s for s in stops if s["kind"] == "pickup")["cumulative_mi"] == route["legs"][0]["distance_mi"]
    # per-day miles agree with the timeline's prorated miles within rounding
    for i, day in enumerate(days):
        assert abs(day["miles_driven"] - _prorated_miles(body["timeline"], i)) <= 0.21


def _prorated_miles(timeline: list[dict], sheet: int) -> float:
    low, high = sheet * DAY, (sheet + 1) * DAY
    total = 0.0
    for p in timeline:
        if p["status"] != "driving" or p["end_min"] <= low or p["start_min"] >= high:
            continue
        span = p["end_min"] - p["start_min"]
        clipped = min(p["end_min"], high) - max(p["start_min"], low)
        total += (p["end_mi"] - p["start_mi"]) * clipped / span
    return total


def _times(body: dict, day0: dt.datetime, offset: dt.timezone) -> None:
    # 12
    def check(stamp: str, minute: int) -> None:
        parsed = parse(stamp)
        assert parsed.utcoffset() == offset.utcoffset(None)
        assert parsed == day0 + dt.timedelta(minutes=minute)

    for p in body["timeline"]:
        check(p["start_at"], p["start_min"])
        check(p["end_at"], p["end_min"])
    for s in body["stops"] + [body["trip"]]:
        for key in ("arrive_at", "depart_at", "start_at"):
            if key in s:
                assert parse(s[key]).utcoffset() == offset.utcoffset(None)
                assert (parse(s[key]) - day0).total_seconds() % 900 == 0
    summary = body["summary"]
    for key in ("arrival_at", "released_at"):
        assert parse(summary[key]).utcoffset() == offset.utcoffset(None)
    # trip.start_at is the start stop's arrival, released_at the end stop's
    start = next(s for s in body["stops"] if s["kind"] == "start")
    assert body["trip"]["start_at"] == start["arrive_at"]
    assert summary["arrival_at"] == next(s for s in body["stops"] if s["kind"] == "dropoff")["arrive_at"]
    assert summary["released_at"] == body["stops"][-1]["arrive_at"]
    assert (
        summary["trip_duration_h"]
        == (parse(summary["released_at"]) - parse(body["trip"]["start_at"])).total_seconds() / 3600
    )


def _trip_start_restart(body: dict, day0: dt.datetime) -> None:
    # 13
    trip, stops, days = body["trip"], body["stops"], body["days"]
    warned = any(w["code"] == "CYCLE_RESTART_AT_START" for w in trip["warnings"])
    should = trip["cycle_used_start_h"] >= 69.5
    assert warned == should
    if should:
        first = stops[0]
        assert (
            first["kind"] == "restart" and parse(first["arrive_at"]) == day0 and first["duration_h"] == 34.0
        )
        assert first["depart_at"] == stops[1]["arrive_at"] == trip["start_at"]
        assert stops[1]["kind"] == "start"
        assert body["timeline"][0]["stop_id"] == first["id"]
        assert [r["note"] for r in days[0]["remarks"]] == ["34-hr restart"] and days[0]["remarks"][0][
            "minute"
        ] == 0
    else:
        assert stops[0]["kind"] == "start"
        assert not any(s["kind"] == "restart" and s["arrive_at"] < stops[0]["arrive_at"] for s in stops)


def _hos(body: dict) -> None:
    """14 to 17 over the unsplit timeline."""
    cycle = round(body["trip"]["cycle_used_start_h"] * 60)
    drive_since_rest = drive_since_break = 0
    window_start: int | None = None
    off_run = 0
    non_drive_run = 0
    for p in body["timeline"]:
        length = p["end_min"] - p["start_min"]
        if p["status"] == "driving":
            if window_start is None:
                window_start = p["start_min"]
            assert p["end_min"] <= window_start + WINDOW_LIMIT, "14-hour window"
            drive_since_rest += length
            drive_since_break += length
            assert drive_since_rest <= MIN_DRIVE_LIMIT, "11-hour driving"
            assert drive_since_break <= BREAK_DRIVE_LIMIT, "8-hour break rule"
            cycle += length
            assert cycle <= CYCLE_LIMIT, "70-hour cycle"
            off_run = non_drive_run = 0
            continue
        if p["status"] == "on_duty":
            if window_start is None:
                window_start = p["start_min"]
            cycle += length
            assert cycle <= CYCLE_LIMIT, "cycle on duty"
            off_run = 0
        else:
            off_run += length
        non_drive_run += length
        if non_drive_run >= BREAK_MIN:
            drive_since_break = 0
        if off_run >= REST_MIN:
            drive_since_rest, window_start = 0, None
        if off_run >= RESTART_MIN:
            cycle = 0
    # 17: miles between fuel stops
    fuel = [s["cumulative_mi"] for s in body["stops"] if s["kind"] == "fuel"]
    points = [0.0, *fuel, body["route"]["distance_mi"]]
    for a, b in zip(points, points[1:], strict=False):
        assert b - a <= FUEL_LIMIT_MI + 0.1
