"""Data models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


ReminderStatus = Literal["active", "snoozed", "done", "archived", "skipped"]


@dataclass
class User:
    """Telegram user."""

    telegram_id: int
    timezone: str
    quiet_start: str  # HH:MM format
    quiet_end: str  # HH:MM format
    default_escalation_profile: str
    created_at: datetime
    id: int | None = None


@dataclass
class Category:
    """Reminder category."""

    user_id: int
    name: str
    id: int | None = None


@dataclass
class Reminder:
    """A reminder with escalation nagging."""

    user_id: int
    title: str
    due_at: datetime  # UTC
    status: ReminderStatus
    escalation_profile: str
    next_nag_at: datetime | None = None  # UTC, precomputed for efficiency
    nag_count: int = 0
    description: str | None = None
    amount: float | None = None
    currency: str | None = None
    category_id: int | None = None
    is_recurring: bool = False
    rrule: str | None = None  # iCalendar RRULE string
    custom_escalation: str | None = None  # JSON override
    snoozed_until: datetime | None = None  # UTC
    last_nagged_at: datetime | None = None  # UTC
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None


@dataclass
class NagHistory:
    """Audit trail of sent nags."""

    reminder_id: int
    sent_at: datetime  # UTC
    telegram_message_id: int
    escalation_tier: str
    nag_count: int
    id: int | None = None


@dataclass
class SnoozeLog:
    """Tracks snooze behavior for analytics."""

    reminder_id: int
    snoozed_at: datetime  # UTC
    duration_minutes: int
    id: int | None = None


@dataclass
class ParsedReminder:
    """Result from natural language parsing."""

    title: str
    due_at: datetime | None = None
    amount: float | None = None
    currency: str | None = None
    is_recurring: bool = False
    rrule: str | None = None
    category: str | None = None
    confidence: float = 0.0  # 0-1 score
