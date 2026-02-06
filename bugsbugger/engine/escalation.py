"""Escalation tier logic and next-nag-time computation."""

from datetime import datetime, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo

from bugsbugger.db.models import Reminder, User
from bugsbugger.utils.constants import ESCALATION_PROFILES, EscalationTier
from bugsbugger.utils.time_utils import is_in_quiet_hours, next_quiet_end


def get_escalation_profile(profile_name: str) -> List[EscalationTier]:
    """Get escalation tiers for a profile."""
    return ESCALATION_PROFILES.get(profile_name, ESCALATION_PROFILES["standard"])


def get_current_tier(
    reminder: Reminder, now: datetime | None = None
) -> Tuple[EscalationTier, int]:
    """Determine the current escalation tier for a reminder.

    Tiers define when nagging starts (days_before_due).
    We use the tier whose threshold we've crossed but haven't crossed the next one yet.

    Example for standard profile:
    - 10 days before: No nagging yet (or use first tier if already active)
    - 5 days before: gentle tier (crossed 7.0 threshold)
    - 2 days before: moderate tier (crossed 3.0 threshold)
    - 0.5 days before: urgent tier (crossed 1.0 threshold)
    - 0.01 days before: critical tier (crossed 0.042 threshold)
    - -1 days (overdue): overdue tier (past due)

    Returns:
        Tuple of (tier, tier_index)
    """
    if now is None:
        now = datetime.now(ZoneInfo("UTC"))

    # Get the escalation profile
    profile = get_escalation_profile(reminder.escalation_profile)

    # Calculate days until due (can be negative for overdue)
    time_until_due = reminder.due_at - now
    days_until_due = time_until_due.total_seconds() / 86400

    # Check if overdue (past due date)
    if days_until_due < 0:
        # Find the overdue tier (the one with negative days_before_due)
        for i, tier in enumerate(profile):
            if tier.days_before_due < 0:
                return tier, i
        # Fallback to last tier if no explicit overdue tier
        return profile[-1], len(profile) - 1

    # Find the appropriate tier by checking which threshold we've crossed
    # Check from most urgent to least urgent (backwards through list)
    for i in range(len(profile) - 1, -1, -1):
        tier = profile[i]
        # Skip overdue tiers (negative thresholds)
        if tier.days_before_due < 0:
            continue
        # If we're at or past this tier's threshold, use it
        if days_until_due <= tier.days_before_due:
            return tier, i

    # If we haven't crossed any threshold, use the first (gentlest) tier
    return profile[0], 0


def compute_next_nag_time(
    reminder: Reminder, user: User, now: datetime | None = None
) -> datetime | None:
    """Compute when the next nag should be sent.

    Takes into account:
    - Current escalation tier
    - Quiet hours
    - Snooze status

    Returns:
        Next nag datetime (UTC), or None if reminder shouldn't nag
    """
    if now is None:
        now = datetime.now(ZoneInfo("UTC"))

    # Don't nag if not active
    if reminder.status != "active":
        return None

    # If snoozed, return snoozed_until
    if reminder.status == "snoozed" and reminder.snoozed_until:
        return reminder.snoozed_until

    # Get current tier
    tier, _ = get_current_tier(reminder, now)

    # Calculate next nag time based on interval
    if reminder.last_nagged_at:
        # Add interval to last nag time
        next_nag = reminder.last_nagged_at + timedelta(minutes=tier.nag_interval_minutes)
    else:
        # First nag: start nagging at the tier's trigger time
        days_before = tier.days_before_due
        if days_before < 0:
            # Overdue tier - nag immediately
            next_nag = now
        else:
            # Calculate when to start this tier
            trigger_time = reminder.due_at - timedelta(days=days_before)
            next_nag = max(trigger_time, now)

    # Adjust for quiet hours
    if is_in_quiet_hours(next_nag, user.quiet_start, user.quiet_end, user.timezone):
        next_nag = next_quiet_end(next_nag, user.quiet_start, user.quiet_end, user.timezone)

    return next_nag


def should_send_nag(reminder: Reminder, now: datetime | None = None) -> bool:
    """Check if a reminder is due for nagging right now.

    Args:
        reminder: The reminder to check
        now: Current time (UTC), defaults to utcnow()

    Returns:
        True if a nag should be sent
    """
    if now is None:
        now = datetime.now(ZoneInfo("UTC"))

    if reminder.status != "active":
        return False

    if reminder.next_nag_at is None:
        return False

    return reminder.next_nag_at <= now
