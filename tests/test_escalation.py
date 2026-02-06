"""Tests for escalation logic."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bugsbugger.db.models import Reminder, User
from bugsbugger.engine.escalation import (
    compute_next_nag_time,
    get_current_tier,
    get_escalation_profile,
)


def test_get_escalation_profile():
    """Test getting escalation profiles."""
    standard = get_escalation_profile("standard")
    assert len(standard) == 5
    assert standard[0].name == "gentle"
    assert standard[-1].name == "overdue"

    gentle = get_escalation_profile("gentle")
    assert len(gentle) == 4

    # Unknown profile defaults to standard
    unknown = get_escalation_profile("unknown")
    assert len(unknown) == 5


def test_get_current_tier():
    """Test tier selection based on time until due."""
    now = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("UTC"))

    # Create a reminder due in 5 days
    reminder = Reminder(
        user_id=1,
        title="Test",
        due_at=now + timedelta(days=5),
        status="active",
        escalation_profile="standard",
    )

    tier, idx = get_current_tier(reminder, now)
    assert tier.name == "gentle"  # 3-7 days before

    # Due in 2 days
    reminder.due_at = now + timedelta(days=2)
    tier, idx = get_current_tier(reminder, now)
    assert tier.name == "moderate"  # 1-3 days before

    # Due in 12 hours
    reminder.due_at = now + timedelta(hours=12)
    tier, idx = get_current_tier(reminder, now)
    assert tier.name == "urgent"  # Due day

    # Overdue by 1 hour
    reminder.due_at = now - timedelta(hours=1)
    tier, idx = get_current_tier(reminder, now)
    assert tier.name == "overdue"


def test_compute_next_nag_time_first_nag():
    """Test computing next nag time for first nag."""
    now = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("UTC"))

    user = User(
        telegram_id=12345,
        timezone="UTC",
        quiet_start="23:00",
        quiet_end="07:00",
        default_escalation_profile="standard",
        created_at=now,
    )

    # Reminder due in 5 days
    reminder = Reminder(
        user_id=1,
        title="Test",
        due_at=now + timedelta(days=5),
        status="active",
        escalation_profile="standard",
        last_nagged_at=None,
    )

    # Should start nagging at tier trigger time (7 days before due)
    # Since we're already past that, should nag now
    next_nag = compute_next_nag_time(reminder, user, now)
    assert next_nag is not None
    # Should be close to now
    assert abs((next_nag - now).total_seconds()) < 3600  # Within 1 hour


def test_compute_next_nag_time_subsequent():
    """Test computing next nag time for subsequent nags."""
    now = datetime(2026, 3, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    last_nag = datetime(2026, 2, 28, 10, 0, tzinfo=ZoneInfo("UTC"))  # 2 days ago at 10:00

    user = User(
        telegram_id=12345,
        timezone="UTC",
        quiet_start="23:00",
        quiet_end="07:00",
        default_escalation_profile="standard",
        created_at=now,
    )

    # Reminder due in 5 days, already nagged once
    reminder = Reminder(
        user_id=1,
        title="Test",
        due_at=now + timedelta(days=5),
        status="active",
        escalation_profile="standard",
        last_nagged_at=last_nag,
        nag_count=1,
    )

    # Current tier is "gentle" (1440 min = 24 hour interval)
    # Next nag should be last_nag + 24 hours = March 1 10:00 (which is now)
    # Since we're at that time, it should return now or very soon
    next_nag = compute_next_nag_time(reminder, user, now)
    assert next_nag is not None

    expected = last_nag + timedelta(minutes=1440)  # 24 hours after last nag
    # Should be very close to expected (10:00 UTC is outside quiet hours)
    assert abs((next_nag - expected).total_seconds()) < 60  # Within 1 minute


def test_compute_next_nag_time_inactive():
    """Test that inactive reminders don't get nag times."""
    now = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("UTC"))

    user = User(
        telegram_id=12345,
        timezone="UTC",
        quiet_start="23:00",
        quiet_end="07:00",
        default_escalation_profile="standard",
        created_at=now,
    )

    reminder = Reminder(
        user_id=1,
        title="Test",
        due_at=now + timedelta(days=5),
        status="done",  # Not active
        escalation_profile="standard",
    )

    next_nag = compute_next_nag_time(reminder, user, now)
    assert next_nag is None
