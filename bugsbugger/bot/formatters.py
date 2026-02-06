"""Message text formatters."""

from datetime import datetime
from zoneinfo import ZoneInfo

from bugsbugger.db.models import Reminder, User
from bugsbugger.utils.time_utils import format_relative_time, from_utc


def format_reminder(reminder: Reminder, user: User, show_id: bool = True) -> str:
    """Format a reminder as a message."""
    lines = []

    # Title and ID
    if show_id:
        lines.append(f"<b>{reminder.title}</b> (ID: {reminder.id})")
    else:
        lines.append(f"<b>{reminder.title}</b>")

    # Due date
    due_local = from_utc(reminder.due_at, user.timezone)
    due_str = due_local.strftime("%b %d, %Y at %I:%M %p")
    relative = format_relative_time(reminder.due_at, datetime.now(ZoneInfo("UTC")))
    lines.append(f"📅 Due: {due_str} ({relative})")

    # Recurring
    if reminder.is_recurring and reminder.rrule:
        lines.append(f"🔁 Recurring: {reminder.rrule}")

    # Amount
    if reminder.amount:
        currency = reminder.currency or "USD"
        lines.append(f"💰 Amount: {currency} {reminder.amount:.2f}")

    # Description
    if reminder.description:
        lines.append(f"\n{reminder.description}")

    # Status info
    if reminder.status == "snoozed" and reminder.snoozed_until:
        snoozed_local = from_utc(reminder.snoozed_until, user.timezone)
        lines.append(f"\n⏸ Snoozed until {snoozed_local.strftime('%I:%M %p')}")

    return "\n".join(lines)


def format_reminder_list(reminders: list[Reminder], user: User) -> str:
    """Format a list of reminders."""
    if not reminders:
        return "You have no active reminders."

    lines = [f"<b>Your Reminders ({len(reminders)})</b>\n"]

    for reminder in reminders:
        status_emoji = {
            "active": "🔔",
            "snoozed": "⏸",
            "done": "✓",
            "archived": "📦",
        }.get(reminder.status, "")

        due_local = from_utc(reminder.due_at, user.timezone)
        relative = format_relative_time(reminder.due_at)

        lines.append(
            f"{status_emoji} <b>{reminder.title}</b> (ID: {reminder.id})\n"
            f"   Due: {due_local.strftime('%b %d')} ({relative})"
        )

    return "\n\n".join(lines)


def format_nag_message(reminder: Reminder, user: User, tier_name: str) -> str:
    """Format a nag message with urgency."""
    urgency_emoji = {
        "gentle": "🔔",
        "reminder": "🔔",
        "early": "🔔",
        "moderate": "⚠️",
        "approaching": "⚠️",
        "urgent": "🚨",
        "due_soon": "🚨",
        "critical": "🔥",
        "overdue": "💥",
    }

    emoji = urgency_emoji.get(tier_name, "🔔")
    tier_text = tier_name.upper() if tier_name in ["critical", "overdue"] else tier_name.title()

    header = f"{emoji} <b>{tier_text} Reminder</b> {emoji}\n\n"
    return header + format_reminder(reminder, user, show_id=True)


def format_welcome_message() -> str:
    """Format the welcome message for /start."""
    return """
<b>Welcome to BugsBugger!</b> 🐰

I'll nag you about bills, deadlines, and events with escalating frequency until you mark them done.

<b>Quick Start:</b>
• /add - Create a reminder (guided)
• Send me plain text like "rent due 1st every month $1500"
• /list - See all your reminders
• /help - Full command list

I won't shut up until you pay attention. Let's get started!
""".strip()


def format_help_message() -> str:
    """Format the help message."""
    return """
<b>BugsBugger Commands 🐰</b>

<b>Creating Reminders:</b>
/add - Guided reminder creation
/quick &lt;text&gt; - Quick add: <code>/quick rent due 1st $1500</code>
Or just send plain text: "credit card payment due 15th every month"

<b>Managing Reminders:</b>
/list [page] - All active reminders
/upcoming - Dashboard (next 7 days)
/done &lt;id&gt; - Mark reminder as done
/snooze &lt;id&gt; [mins] - Snooze a reminder
/edit &lt;id&gt; - Edit a reminder
/delete &lt;id&gt; - Delete a reminder

<b>Organization:</b>
/category - List all categories
/category add &lt;name&gt; - Create category
/category delete &lt;name&gt; - Remove category

<b>Settings & Info:</b>
/settings - View all settings
/timezone &lt;tz&gt; - Set timezone (e.g., America/Toronto)
/quiet &lt;start&gt; &lt;end&gt; - Set quiet hours (e.g., 23:00 07:00)
/escalation &lt;profile&gt; - Set nag intensity (standard/gentle/aggressive)
/stats - Your statistics & insights

<b>Tips:</b>
• When I nag you, use the buttons to quickly mark done or snooze
• Recurring reminders auto-roll forward when marked done
• Set your timezone and quiet hours for best experience
• The bot gets more aggressive as deadlines approach!
""".strip()
