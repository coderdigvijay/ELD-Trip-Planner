"""Split events into midnight-bounded day sheets (HOS_ENGINE_SPEC section 5)."""

from bisect import bisect_left, bisect_right
from fractions import Fraction
from math import ceil

from .exact import MileSpan, as_float, round_half_up, to_fraction
from .models import DaySheet, DutyEvent, Kind, Remark, Segment, Status
from .recap import CycleTimeline, build_recap
from .rules import DAY_MIN

_BRACKET_EXCLUDED = (Kind.OFF_BEFORE_START, Kind.OFF_AFTER_END)


def spans_from_events(events: tuple[DutyEvent, ...]) -> tuple[MileSpan, ...]:
    """Exact spans rebuilt from the rounded floats (used when events do not come from the simulator)."""
    return tuple(
        MileSpan(to_fraction(e.start_mile), to_fraction(e.end_mile), to_fraction(e.leg_mile)) for e in events
    )


def _mile_at(event: DutyEvent, span: MileSpan, minute: int) -> Fraction:
    """Exact cumulative mile inside `event` at absolute `minute`."""
    length = event.end_min_abs - event.start_min_abs
    return span.start + (span.end - span.start) * (minute - event.start_min_abs) / length


def _trip_mile_at(timeline: CycleTimeline, spans: tuple[MileSpan, ...], minute: int) -> Fraction:
    index = bisect_left(timeline.ends, minute)
    if index >= len(spans):
        return spans[-1].end
    return _mile_at(timeline.events[index], spans[index], max(minute, timeline.starts[index]))


def _tenths(value: Fraction) -> int:
    return int(round_half_up(value, 1) * 10)


def _clip_segments(
    timeline: CycleTimeline, spans: tuple[MileSpan, ...], low: int, high: int
) -> tuple[Segment, ...]:
    first = bisect_right(timeline.ends, low)
    last = bisect_left(timeline.starts, high)
    segments = []
    for event, span in zip(timeline.events[first:last], spans[first:last], strict=True):
        start, end = max(event.start_min_abs, low), min(event.end_min_abs, high)
        if start >= end:
            continue
        segments.append(
            Segment(
                start - low,
                end - low,
                event.status,
                event.kind,
                as_float(_mile_at(event, span, start), 3),
                as_float(_mile_at(event, span, end), 3),
            )
        )
    return tuple(segments)


def _totals(segments: tuple[Segment, ...]) -> dict[Status, int]:
    totals = dict.fromkeys(Status, 0)
    for segment in segments:
        totals[segment.status] += segment.end_min - segment.start_min
    return totals


def _remark_kind(events: tuple[DutyEvent, ...], index: int) -> bool | None:
    """True = status change, False = note-only, None = no remark for the event at `index`."""
    event = events[index]
    if index == 0:
        if event.status != Status.OFF:
            return True
        return False if event.kind == Kind.RESTART else None
    previous = events[index - 1]
    if previous.status != event.status:
        return True
    return False if previous.kind != event.kind else None


def _remark(event: DutyEvent, span: MileSpan, status_change: bool) -> Remark:
    length_miles = span.end - span.start
    return Remark(
        minute=event.start_min_abs % DAY_MIN,
        status=event.status,
        status_change=status_change,
        mile=event.start_mile,
        leg_index=event.leg_index,
        leg_mile=as_float(span.leg_end - length_miles, 3),
        location_label=event.location_label,
        note=event.note,
    )


def _remarks(timeline: CycleTimeline, spans: tuple[MileSpan, ...], low: int, high: int) -> tuple[Remark, ...]:
    remarks = []
    for index in range(bisect_left(timeline.starts, low), bisect_left(timeline.starts, high)):
        change = _remark_kind(timeline.events, index)
        if change is not None:
            remarks.append(_remark(timeline.events[index], spans[index], change))
    return tuple(remarks)


def stationary_runs(events: tuple[DutyEvent, ...]) -> tuple[tuple[int, int], ...]:
    """Maximal runs of consecutive stationary events, absolute minutes (section 5.5)."""
    runs: list[list[int]] = []
    previous_in_run = False
    for event in events:
        in_run = event.stationary and event.kind not in _BRACKET_EXCLUDED
        if in_run and previous_in_run:
            runs[-1][1] = event.end_min_abs
        elif in_run:
            runs.append([event.start_min_abs, event.end_min_abs])
        previous_in_run = in_run
    return tuple((start, end) for start, end in runs)


def _brackets(
    runs: tuple[tuple[int, int], ...], run_bounds: tuple[list[int], list[int]], low: int, high: int
) -> tuple[tuple[int, int], ...]:
    starts, ends = run_bounds
    indexes = range(bisect_right(ends, low), bisect_left(starts, high))
    return tuple((max(runs[i][0], low) - low, min(runs[i][1], high) - low) for i in indexes)


def split_days(
    events: tuple[DutyEvent, ...],
    spans: tuple[MileSpan, ...] | None = None,
    cycle_used_min: int = 0,
) -> tuple[DaySheet, ...]:
    """One DaySheet per calendar day from 00:00 of day 0 to the end of the last event."""
    exact = spans if spans is not None else spans_from_events(events)
    timeline = CycleTimeline(events, cycle_used_min)
    runs = stationary_runs(events)
    run_bounds = ([start for start, _ in runs], [end for _, end in runs])
    sheets = []
    for day in range(ceil(events[-1].end_min_abs / DAY_MIN)):
        low, high = day * DAY_MIN, (day + 1) * DAY_MIN
        segments = _clip_segments(timeline, exact, low, high)
        totals = _totals(segments)
        first, last = (
            _tenths(_trip_mile_at(timeline, exact, low)),
            _tenths(_trip_mile_at(timeline, exact, high)),
        )
        sheets.append(
            DaySheet(
                day_index=day,
                segments=segments,
                totals=totals,
                miles_today=float(Fraction(last - first, 10)),
                from_mile=float(Fraction(first, 10)),
                to_mile=float(Fraction(last, 10)),
                remarks=_remarks(timeline, exact, low, high),
                brackets=_brackets(runs, run_bounds, low, high),
                recap=build_recap(timeline, day, totals),
            )
        )
    return tuple(sheets)
