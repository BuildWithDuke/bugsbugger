"""Natural language parser - the main pipeline."""

import re
from datetime import datetime

from bugsbugger.db.models import ParsedReminder
from bugsbugger.engine.recurrence import build_rrule_from_text
from bugsbugger.parser.normalizer import (
    normalize_day_of_month,
    normalize_next_weekday,
    normalize_relative_date,
    normalize_specific_date,
    normalize_today,
    normalize_tomorrow,
)
from bugsbugger.parser.patterns import (
    AMOUNT_PATTERNS,
    CATEGORY_KEYWORDS,
    DATE_PATTERNS,
    RECURRENCE_PATTERNS,
)


def parse_reminder(text: str, timezone: str) -> ParsedReminder:
    """Parse natural language text into a ParsedReminder.

    Pipeline:
    1. Extract amount and currency
    2. Extract recurrence pattern
    3. Extract date
    4. Match category
    5. Extract title (what's left)

    Args:
        text: Natural language reminder text
        timezone: User's timezone

    Returns:
        ParsedReminder with extracted components and confidence score
    """
    original_text = text
    confidence = 0.0

    # 1. Extract amount and currency
    amount = None
    currency = None

    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            if len(match.groups()) == 2:  # Pattern with currency prefix
                currency = match.group(1)
                amount_str = match.group(2).replace(',', '')
            else:
                amount_str = match.group(1).replace(',', '')
                currency = 'USD'

            try:
                amount = float(amount_str)
                confidence += 0.2
                # Remove from text
                text = pattern.sub(' ', text)
                break
            except ValueError:
                pass

    # 2. Extract recurrence pattern
    is_recurring = False
    rrule = None

    for pattern in RECURRENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            recurrence_text = match.group(0)
            rrule = build_rrule_from_text(recurrence_text)
            if rrule:
                is_recurring = True
                confidence += 0.3
                # Remove from text
                text = pattern.sub(' ', text)
                break

    # 3. Extract date
    due_at = None

    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                # Relative dates
                if 'in ' in match.group(0).lower():
                    value = int(match.group(1))
                    unit = match.group(2)
                    due_at = normalize_relative_date(value, unit, timezone)

                # Tomorrow/today
                elif match.group(1).lower() == 'tomorrow':
                    due_at = normalize_tomorrow(timezone)
                elif match.group(1).lower() == 'today':
                    due_at = normalize_today(timezone)

                # Next weekday
                elif 'next' in match.group(0).lower():
                    weekday = match.group(1)
                    due_at = normalize_next_weekday(weekday, timezone)

                # Specific date (15th March, March 15)
                elif len(match.groups()) >= 2:
                    # Try both orders
                    try:
                        day = int(match.group(1))
                        month_name = match.group(2)
                        due_at = normalize_specific_date(day, month_name, timezone)
                    except (ValueError, KeyError):
                        try:
                            month_name = match.group(1)
                            day = int(match.group(2))
                            due_at = normalize_specific_date(day, month_name, timezone)
                        except (ValueError, KeyError):
                            pass

                # ISO date
                elif len(match.groups()) == 3:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    from zoneinfo import ZoneInfo
                    from bugsbugger.utils.time_utils import to_utc
                    dt = datetime(year, month, day, 9, 0, tzinfo=ZoneInfo(timezone))
                    due_at = to_utc(dt, timezone)

                # Day of month only
                else:
                    day = int(match.group(1))
                    due_at = normalize_day_of_month(day, timezone)

                if due_at:
                    confidence += 0.3
                    # Remove from text
                    text = pattern.sub(' ', text)
                    # Also remove "due", "by", "on" keywords
                    text = re.sub(r'\b(due|by|on)\s+', ' ', text, flags=re.IGNORECASE)
                    break

            except (ValueError, IndexError):
                continue

    # 4. Match category
    category = None
    text_lower = text.lower()

    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                category = cat_name
                confidence += 0.1
                break
        if category:
            break

    # 5. Extract title (clean up remaining text)
    title = text.strip()
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title)
    # Remove leading/trailing punctuation
    title = title.strip('.,!?;:')

    # If title is empty, use original text
    if not title:
        title = original_text[:50]  # Truncate if too long

    # Adjust confidence based on what we found
    if title:
        confidence += 0.1
    if due_at is None:
        confidence -= 0.2  # Lower confidence if no date found

    # Clamp confidence between 0 and 1
    confidence = max(0.0, min(1.0, confidence))

    return ParsedReminder(
        title=title,
        due_at=due_at,
        amount=amount,
        currency=currency,
        is_recurring=is_recurring,
        rrule=rrule,
        category=category,
        confidence=confidence,
    )
