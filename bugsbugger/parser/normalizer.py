"""Date and time normalization."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bugsbugger.parser.patterns import MONTH_NAMES, WEEKDAY_NAMES
from bugsbugger.utils.time_utils import to_utc


def normalize_relative_date(value: int, unit: str, timezone: str) -> datetime:
    """Normalize relative date (in X days/weeks/months)."""
    now = datetime.now(ZoneInfo(timezone))
    unit = unit.lower()

    if unit in ['minute', 'min', 'minutes', 'mins']:
        result = now + timedelta(minutes=value)
    elif unit in ['hour', 'hours']:
        result = now + timedelta(hours=value)
    elif unit in ['day', 'days']:
        result = now + timedelta(days=value)
    elif unit in ['week', 'weeks']:
        result = now + timedelta(weeks=value)
    elif unit in ['month', 'months']:
        # Approximate month as 30 days
        result = now + timedelta(days=value * 30)
    elif unit in ['year', 'years']:
        result = now + timedelta(days=value * 365)
    else:
        raise ValueError(f"Unknown time unit: {unit}")

    return to_utc(result, timezone)


def normalize_specific_date(day: int, month_name: str, timezone: str, year: int | None = None) -> datetime:
    """Normalize specific date (March 15, 15th March)."""
    now = datetime.now(ZoneInfo(timezone))

    month = MONTH_NAMES.get(month_name.lower())
    if not month:
        raise ValueError(f"Unknown month: {month_name}")

    if year is None:
        year = now.year
        # If date is in the past this year, assume next year
        try:
            date = datetime(year, month, day, 9, 0, tzinfo=ZoneInfo(timezone))
            if date < now:
                year += 1
        except ValueError:
            # Invalid date (e.g., Feb 30), use next year
            year += 1

    date = datetime(year, month, day, 9, 0, tzinfo=ZoneInfo(timezone))
    return to_utc(date, timezone)


def normalize_day_of_month(day: int, timezone: str) -> datetime:
    """Normalize day of month (1st, 15th, etc.) to next occurrence."""
    now = datetime.now(ZoneInfo(timezone))

    # Try this month first
    try:
        date = datetime(now.year, now.month, day, 9, 0, tzinfo=ZoneInfo(timezone))
        if date >= now:
            return to_utc(date, timezone)
    except ValueError:
        pass  # Day doesn't exist in this month

    # Try next month
    next_month = now.month + 1
    year = now.year
    if next_month > 12:
        next_month = 1
        year += 1

    try:
        date = datetime(year, next_month, day, 9, 0, tzinfo=ZoneInfo(timezone))
        return to_utc(date, timezone)
    except ValueError:
        # Day doesn't exist in next month either, try month after
        next_month += 1
        if next_month > 12:
            next_month = 1
            year += 1
        date = datetime(year, next_month, day, 9, 0, tzinfo=ZoneInfo(timezone))
        return to_utc(date, timezone)


def normalize_next_weekday(weekday_name: str, timezone: str) -> datetime:
    """Normalize 'next Monday', etc."""
    now = datetime.now(ZoneInfo(timezone))
    target_weekday = WEEKDAY_NAMES.get(weekday_name.lower())

    if target_weekday is None:
        raise ValueError(f"Unknown weekday: {weekday_name}")

    # Calculate days until target weekday
    days_ahead = target_weekday - now.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7

    result = now + timedelta(days=days_ahead)
    result = result.replace(hour=9, minute=0, second=0, microsecond=0)
    return to_utc(result, timezone)


def normalize_tomorrow(timezone: str) -> datetime:
    """Get tomorrow at 9am."""
    now = datetime.now(ZoneInfo(timezone))
    tomorrow = now + timedelta(days=1)
    tomorrow = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    return to_utc(tomorrow, timezone)


def normalize_today(timezone: str, hour: int = 17, minute: int = 0) -> datetime:
    """Get today at specified time (default 5pm)."""
    now = datetime.now(ZoneInfo(timezone))
    today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If time already passed, use tomorrow
    if today < now:
        today += timedelta(days=1)

    return to_utc(today, timezone)
