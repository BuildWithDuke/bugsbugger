"""RRULE-based recurrence handling."""

from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.rrule import rrule, rrulestr


def parse_rrule(rrule_str: str) -> rrule:
    """Parse an RRULE string into an rrule object."""
    return rrulestr(rrule_str)


def get_next_occurrence(due_at: datetime, rrule_str: str) -> datetime:
    """Get the next occurrence after due_at based on RRULE.

    Args:
        due_at: Current due date (timezone-aware)
        rrule_str: RRULE string (e.g., "FREQ=MONTHLY;BYMONTHDAY=1")

    Returns:
        Next occurrence as timezone-aware datetime
    """
    # Parse the RRULE
    rule = parse_rrule(f"DTSTART:{due_at.isoformat()}\nRRULE:{rrule_str}")

    # Get the next occurrence after due_at
    # rrule.after() returns the first occurrence after the given datetime
    next_date = rule.after(due_at)

    if next_date is None:
        raise ValueError("No next occurrence found")

    # Ensure timezone info is preserved
    if next_date.tzinfo is None and due_at.tzinfo is not None:
        next_date = next_date.replace(tzinfo=due_at.tzinfo)

    return next_date


def build_rrule_from_text(recurrence_text: str) -> str | None:
    """Build an RRULE string from natural language.

    Examples:
        "every day" -> "FREQ=DAILY"
        "every week" -> "FREQ=WEEKLY"
        "every month" -> "FREQ=MONTHLY"
        "every year" -> "FREQ=YEARLY"
        "every 2 weeks" -> "FREQ=WEEKLY;INTERVAL=2"
        "every 1st" -> "FREQ=MONTHLY;BYMONTHDAY=1"
        "every monday" -> "FREQ=WEEKLY;BYDAY=MO"

    Returns:
        RRULE string or None if not recognized
    """
    text = recurrence_text.lower().strip()

    # Simple frequencies
    if 'daily' in text or text == 'every day':
        return "FREQ=DAILY"
    elif 'weekly' in text or text == 'every week':
        return "FREQ=WEEKLY"
    elif 'monthly' in text or text == 'every month':
        return "FREQ=MONTHLY"
    elif 'yearly' in text or 'annually' in text or text == 'every year':
        return "FREQ=YEARLY"

    # Every N units
    import re
    match = re.match(r'every\s+(\d+)\s+(day|week|month|year)s?', text)
    if match:
        interval = match.group(1)
        unit = match.group(2)
        freq_map = {
            'day': 'DAILY',
            'week': 'WEEKLY',
            'month': 'MONTHLY',
            'year': 'YEARLY',
        }
        freq = freq_map.get(unit)
        if freq:
            return f"FREQ={freq};INTERVAL={interval}"

    # Every specific day of month (1st, 15th, etc.)
    match = re.match(r'every\s+(\d{1,2})(?:st|nd|rd|th)?', text)
    if match:
        day = match.group(1)
        return f"FREQ=MONTHLY;BYMONTHDAY={day}"

    # Every weekday
    weekday_map = {
        'monday': 'MO',
        'tuesday': 'TU',
        'wednesday': 'WE',
        'thursday': 'TH',
        'friday': 'FR',
        'saturday': 'SA',
        'sunday': 'SU',
    }

    for day_name, day_code in weekday_map.items():
        if day_name in text:
            return f"FREQ=WEEKLY;BYDAY={day_code}"

    return None
