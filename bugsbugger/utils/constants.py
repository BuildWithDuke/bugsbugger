"""Constants and default values."""

from dataclasses import dataclass


@dataclass
class EscalationTier:
    """Defines a single tier in an escalation profile."""

    name: str
    days_before_due: float  # Can be negative for overdue
    nag_interval_minutes: int


# Default escalation profiles
ESCALATION_PROFILES = {
    "standard": [
        EscalationTier("gentle", 7.0, 1440),  # 3-7 days before: once/day
        EscalationTier("moderate", 3.0, 720),  # 1-3 days before: twice/day
        EscalationTier("urgent", 1.0, 120),  # Due day: every 2 hours
        EscalationTier("critical", 0.042, 30),  # Due within hour: every 30 min
        EscalationTier("overdue", -999.0, 15),  # Past due: every 15 min
    ],
    "gentle": [
        EscalationTier("reminder", 7.0, 2880),  # Week before: every 2 days
        EscalationTier("approaching", 2.0, 1440),  # 2 days before: once/day
        EscalationTier("due_soon", 1.0, 360),  # Due day: every 6 hours
        EscalationTier("overdue", -999.0, 180),  # Past due: every 3 hours
    ],
    "aggressive": [
        EscalationTier("early", 14.0, 1440),  # 2 weeks before: once/day
        EscalationTier("moderate", 7.0, 480),  # Week before: 3x/day
        EscalationTier("urgent", 3.0, 120),  # 3 days before: every 2 hours
        EscalationTier("critical", 1.0, 30),  # Due day: every 30 min
        EscalationTier("overdue", -999.0, 10),  # Past due: every 10 min
    ],
}

# Default categories (seeded for new users)
DEFAULT_CATEGORIES = [
    "bills",
    "subscriptions",
    "birthdays",
    "goals",
    "business_leads",
]

# Limits
MAX_REMINDERS_PER_USER = 500
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000

# Default quiet hours (24-hour format)
DEFAULT_QUIET_START = "23:00"
DEFAULT_QUIET_END = "07:00"

# Default timezone
DEFAULT_TIMEZONE = "UTC"
