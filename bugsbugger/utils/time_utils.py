"""Time and timezone utilities."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def to_utc(dt: datetime, tz: str) -> datetime:
    """Convert a timezone-aware datetime to UTC."""
    if dt.tzinfo is None:
        # Assume it's in the given timezone
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(ZoneInfo("UTC"))


def from_utc(dt: datetime, tz: str) -> datetime:
    """Convert a UTC datetime to the given timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz))


def is_in_quiet_hours(
    dt: datetime, quiet_start: str, quiet_end: str, tz: str
) -> bool:
    """Check if a datetime falls within quiet hours.

    Args:
        dt: The datetime to check (UTC)
        quiet_start: Start time in HH:MM format (24-hour)
        quiet_end: End time in HH:MM format (24-hour)
        tz: User's timezone

    Returns:
        True if the datetime is within quiet hours
    """
    # Convert to user's timezone
    local_dt = from_utc(dt, tz)
    local_time = local_dt.time()

    start = time.fromisoformat(quiet_start)
    end = time.fromisoformat(quiet_end)

    # Handle overnight quiet hours (e.g., 23:00 to 07:00)
    if start <= end:
        return start <= local_time <= end
    else:
        return local_time >= start or local_time <= end


def next_quiet_end(dt: datetime, quiet_start: str, quiet_end: str, tz: str) -> datetime:
    """Get the next time quiet hours end.

    Args:
        dt: The current datetime (UTC)
        quiet_start: Start time in HH:MM format
        quiet_end: End time in HH:MM format
        tz: User's timezone

    Returns:
        The next datetime when quiet hours end (UTC)
    """
    local_dt = from_utc(dt, tz)
    end_time = time.fromisoformat(quiet_end)

    # Create datetime for today's quiet end
    quiet_end_today = datetime.combine(local_dt.date(), end_time)
    quiet_end_today = quiet_end_today.replace(tzinfo=ZoneInfo(tz))

    # If we've passed today's quiet end, use tomorrow's
    if local_dt >= quiet_end_today:
        quiet_end_today += timedelta(days=1)

    return to_utc(quiet_end_today, tz)


def format_duration(minutes: int) -> str:
    """Format minutes into a human-readable duration.

    Examples:
        15 -> "15 minutes"
        60 -> "1 hour"
        90 -> "1.5 hours"
        1440 -> "1 day"
    """
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif minutes < 1440:
        hours = minutes / 60
        if hours == int(hours):
            return f"{int(hours)} hour{'s' if hours != 1 else ''}"
        return f"{hours:.1f} hours"
    else:
        days = minutes / 1440
        if days == int(days):
            return f"{int(days)} day{'s' if days != 1 else ''}"
        return f"{days:.1f} days"


def format_relative_time(dt: datetime, now: datetime | None = None) -> str:
    """Format a datetime relative to now.

    Examples:
        "in 5 minutes"
        "in 2 hours"
        "tomorrow"
        "2 days overdue"
    """
    if now is None:
        now = datetime.now(ZoneInfo("UTC"))

    delta = dt - now
    total_seconds = delta.total_seconds()

    if total_seconds < 0:
        # Overdue
        abs_seconds = abs(total_seconds)
        if abs_seconds < 3600:
            minutes = int(abs_seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} overdue"
        elif abs_seconds < 86400:
            hours = int(abs_seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} overdue"
        else:
            days = int(abs_seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} overdue"
    else:
        # Future
        if total_seconds < 3600:
            minutes = int(total_seconds / 60)
            return f"in {minutes} minute{'s' if minutes != 1 else ''}"
        elif total_seconds < 86400:
            hours = int(total_seconds / 3600)
            return f"in {hours} hour{'s' if hours != 1 else ''}"
        elif total_seconds < 172800:  # 2 days
            return "tomorrow"
        else:
            days = int(total_seconds / 86400)
            return f"in {days} days"
