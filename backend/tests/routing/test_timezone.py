from datetime import date, time, timedelta

import pytest

from routing.timezone import (
    format_offset,
    freeze_timezone,
    home_terminal_timezone,
    quantize_time,
    zone_name_for,
)


def test_zone_from_coordinates():
    assert zone_name_for(41.8781, -87.6298) == "America/Chicago"
    assert zone_name_for(40.7128, -74.0060) == "America/New_York"
    assert zone_name_for(34.05, -118.24) == "America/Los_Angeles"


def test_freeze_summer_and_winter():
    s = freeze_timezone("America/New_York", date(2026, 7, 1))
    assert (s.abbreviation, s.utc_offset, s.offset_minutes) == ("EDT", "-04:00", -240)
    assert s.start.isoformat() == "2026-07-01T08:00:00-04:00"
    w = freeze_timezone("America/New_York", date(2026, 1, 5))
    assert (w.abbreviation, w.utc_offset) == ("EST", "-05:00")


@pytest.mark.parametrize("day", [date(2026, 3, 7), date(2026, 3, 8), date(2026, 10, 31), date(2026, 11, 1)])
def test_dst_boundary_every_day_is_24h(day):
    fz = freeze_timezone("America/Chicago", day)
    for n in range(1, 6):
        d0 = fz.start.replace(hour=0, minute=0) + timedelta(days=n - 1)
        d1 = fz.start.replace(hour=0, minute=0) + timedelta(days=n)
        assert d1 - d0 == timedelta(hours=24)
    assert fz.start + timedelta(days=4) - fz.start == timedelta(days=4)
    assert fz.start.utcoffset() == fz.offset.utcoffset(None)


def test_day_before_and_after_spring_forward_differ_but_stay_frozen():
    before = freeze_timezone("America/Chicago", date(2026, 3, 7))
    after = freeze_timezone("America/Chicago", date(2026, 3, 8))
    assert before.utc_offset == "-06:00"
    assert after.utc_offset == "-05:00"
    assert (before.start + timedelta(days=3)).utcoffset() == timedelta(hours=-6)


def test_quantize_and_format():
    assert quantize_time(time(8, 22)) == time(8, 15)
    assert format_offset(330) == "+05:30"
    assert format_offset(-240) == "-04:00"


def test_home_terminal_helper():
    fz = home_terminal_timezone(41.8781, -87.6298, date(2026, 10, 5), time(6, 0))
    assert fz.name == "America/Chicago"
    assert fz.start.isoformat() == "2026-10-05T06:00:00-05:00"
    assert home_terminal_timezone(41.88, -87.63).start.tzinfo is not None
