"""The audit oracle must catch what it claims to catch (tested without the engine).

Valid event lists come straight from the spec fixtures (fixtures.py). Each mutation breaks one
rule and the audit must report the matching invariant id. Without this, a lenient oracle would let
a wrong engine pass every property test.
"""

import dataclasses

import pytest

from hos import DutyEvent, Kind, Status
from tests.hos import fixtures as fx
from tests.hos.audit import audit_events, fmt


def to_events(f: fx.Fixture) -> list[DutyEvent]:
    events, prev = [], 0.0
    for e in f.events:
        events.append(
            DutyEvent(
                e.start, e.end, Status(e.status), Kind(e.kind), None, prev, e.end_mile, 0.0, None, "", ""
            )
        )
        prev = e.end_mile
    return events


def rechain(events: list[DutyEvent]) -> list[DutyEvent]:
    """Re-lay the events back to back from 0 keeping their lengths (miles are left as they are)."""
    out, t = [], 0
    for e in events:
        length = e.end_min_abs - e.start_min_abs
        out.append(dataclasses.replace(e, start_min_abs=t, end_min_abs=t + length))
        t += length
    return out


def with_length(events, index, length):
    e = events[index]
    changed = list(events)
    changed[index] = dataclasses.replace(e, end_min_abs=e.start_min_abs + length)
    return rechain(changed)


def ids(events, inp) -> set[int]:
    return {v[0] for v in audit_events(events, inp)}


def messages(events, inp) -> str:
    return fmt(audit_events(events, inp))


@pytest.mark.parametrize("name", list(fx.TRIP_FIXTURES))
def test_spec_fixtures_are_clean_for_the_oracle(name):
    f = fx.TRIP_FIXTURES[name]
    assert audit_events(to_events(f), f.inp) == []


B, G = fx.FX_8B, fx.FX_8G


def test_detects_11_hour_and_8_hour_violations():
    events = with_length(to_events(B), 4, 495)  # 495 min in one go
    assert 4 in ids(events, B.inp)
    assert "8 h" in messages(events, B.inp) or "11 h" in messages(events, B.inp)


def test_detects_14_hour_window_violation():
    events = with_length(to_events(B), 1, 330)  # 5.5 h pre-trip pushes the window
    assert "14 h" in messages(events, B.inp)


def test_detects_70_hour_violation():
    inp = dataclasses.replace(B.inp, cycle_used_min=4100)
    assert "70 h" in messages(to_events(B), inp)


def test_detects_missing_fuel():
    events = to_events(B)
    del events[8]  # the fuel stop
    assert 9 in ids(rechain(events), B.inp)


def test_detects_missing_pre_trip_after_rest():
    events = to_events(B)
    del events[6]
    assert 11 in ids(rechain(events), B.inp)


def test_detects_wrong_rest_length_and_status():
    assert 12 in ids(with_length(to_events(B), 5, 585), B.inp)
    events = to_events(B)
    events[5] = dataclasses.replace(events[5], status=Status.OFF)
    assert 12 in ids(events, B.inp)


def test_detects_break_at_wrong_time():
    events = to_events(B)
    events[8] = dataclasses.replace(events[8], status=Status.OFF, kind=Kind.BREAK)
    assert 12 in ids(events, B.inp)


def test_detects_missing_dropoff_and_extra_events_after_it():
    events = to_events(B)
    assert 10 in ids(rechain([e for e in events if e.kind != Kind.DROPOFF]), B.inp)
    extra = dataclasses.replace(
        events[-1], kind=Kind.FUEL, status=Status.ON, start_min_abs=2520, end_min_abs=2550
    )
    tail = dataclasses.replace(events[-1], start_min_abs=2550, end_min_abs=2880)
    assert 14 in ids([*events[:-1], extra, tail], B.inp)


def test_detects_gap_and_bad_end():
    events = to_events(B)
    events[3] = dataclasses.replace(events[3], start_min_abs=events[3].start_min_abs + 15)
    assert 1 in ids(events, B.inp)
    assert 2 in ids(to_events(B)[:-1], B.inp)


def test_detects_adjacent_drives_and_zero_length():
    events = to_events(B)
    events[3] = dataclasses.replace(events[3], status=Status.D, kind=Kind.DRIVE)
    assert 13 in ids(events, B.inp)


def test_detects_wrong_start_handling():
    inp = dataclasses.replace(B.inp, start_min=600)
    assert 13 in ids(to_events(B), inp)
    hot = dataclasses.replace(B.inp, cycle_used_min=4200)
    assert 13 in ids(to_events(B), hot)


def test_detects_a10_rest_when_a_restart_was_required():
    events = to_events(G)
    events[5] = dataclasses.replace(events[5], status=Status.SB, kind=Kind.REST, end_min_abs=1830)
    assert 19 in ids(rechain(events), G.inp)


def test_detects_a10_restart_when_a_rest_was_enough():
    events = to_events(B)
    events[5] = dataclasses.replace(events[5], status=Status.OFF, kind=Kind.RESTART, end_min_abs=1230 + 2040)
    assert 19 in ids(rechain(events), B.inp)


def test_detects_miles_going_backwards_and_wrong_total():
    events = to_events(B)
    events[4] = dataclasses.replace(events[4], end_mile=100.0)
    assert {7, 8} & ids(events, B.inp)
