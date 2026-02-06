"""Tests for time utilities."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from bugsbugger.utils.time_utils import (
    format_duration,
    format_relative_time,
    from_utc,
    is_in_quiet_hours,
    to_utc,
)


def test_to_utc():
    """Test timezone conversion to UTC."""
    # Create a datetime in EDT (March is DST)
    dt = datetime(2026, 3, 15, 14, 30, tzinfo=ZoneInfo("America/New_York"))
    utc_dt = to_utc(dt, "America/New_York")

    assert utc_dt.tzinfo == ZoneInfo("UTC")
    # EDT is UTC-4, so 14:30 EDT = 18:30 UTC
    assert utc_dt.hour == 18


def test_from_utc():
    """Test timezone conversion from UTC."""
    # Create a UTC datetime
    dt = datetime(2026, 3, 15, 19, 30, tzinfo=ZoneInfo("UTC"))
    edt_dt = from_utc(dt, "America/New_York")

    assert edt_dt.tzinfo == ZoneInfo("America/New_York")
    assert edt_dt.hour == 15  # 19:30 UTC = 15:30 EDT


def test_is_in_quiet_hours_normal():
    """Test quiet hours detection (normal hours)."""
    # 3:00 AM UTC = 11:00 PM EDT (in quiet hours 23:00-07:00)
    dt = datetime(2026, 3, 15, 3, 0, tzinfo=ZoneInfo("UTC"))

    assert is_in_quiet_hours(dt, "23:00", "07:00", "America/New_York")


def test_is_in_quiet_hours_outside():
    """Test quiet hours detection (outside quiet hours)."""
    # 15:00 UTC = 10:00 AM EST (not in quiet hours)
    dt = datetime(2026, 3, 15, 15, 0, tzinfo=ZoneInfo("UTC"))

    assert not is_in_quiet_hours(dt, "23:00", "07:00", "America/New_York")


def test_format_duration():
    """Test duration formatting."""
    assert format_duration(15) == "15 minutes"
    assert format_duration(60) == "1 hour"
    assert format_duration(120) == "2 hours"
    assert format_duration(1440) == "1 day"
    assert format_duration(2880) == "2 days"


def test_format_relative_time():
    """Test relative time formatting."""
    now = datetime(2026, 3, 15, 12, 0, tzinfo=ZoneInfo("UTC"))

    # Future
    future_5min = datetime(2026, 3, 15, 12, 5, tzinfo=ZoneInfo("UTC"))
    assert format_relative_time(future_5min, now) == "in 5 minutes"

    # Overdue
    overdue_2h = datetime(2026, 3, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert format_relative_time(overdue_2h, now) == "2 hours overdue"
