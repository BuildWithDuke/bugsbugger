"""Command handlers."""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bugsbugger.bot.formatters import (
    format_help_message,
    format_reminder,
    format_reminder_list,
    format_welcome_message,
)
from bugsbugger.bot.keyboards import parsed_reminder_keyboard, reminder_actions_keyboard
from bugsbugger.db.models import Reminder
from bugsbugger.db.repository import Repository
from bugsbugger.engine.escalation import compute_next_nag_time
from bugsbugger.parser.nlp import parse_reminder

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    telegram_id = update.effective_user.id

    # Get or create user
    user = await repo.get_user_by_telegram_id(telegram_id)
    if user is None:
        user = await repo.create_user(telegram_id)
        logger.info(f"New user created: {telegram_id}")

    await update.message.reply_html(format_welcome_message())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return

    await update.message.reply_html(format_help_message())


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command - show all active reminders."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    reminders = await repo.get_reminders_by_user(user.id, status="active")  # type: ignore
    message = format_reminder_list(reminders, user)

    await update.message.reply_html(message)


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /done <id> command."""
    if not update.effective_user or not update.message:
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /done <reminder_id>")
        return

    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid reminder ID. Must be a number.")
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    reminder = await repo.get_reminder(reminder_id)

    if not reminder or reminder.user_id != user.id:
        await update.message.reply_text("Reminder not found.")
        return

    # Mark as done (will be handled by callbacks in Phase 2 with recurrence logic)
    reminder.status = "done"
    reminder.nag_count = 0
    reminder.next_nag_at = None
    await repo.update_reminder(reminder)

    await update.message.reply_html(
        f"✓ Marked done: <b>{reminder.title}</b>\n\n"
        + ("(Will recur next cycle)" if reminder.is_recurring else "")
    )


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete <id> command."""
    if not update.effective_user or not update.message:
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /delete <reminder_id>")
        return

    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid reminder ID. Must be a number.")
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    reminder = await repo.get_reminder(reminder_id)

    if not reminder or reminder.user_id != user.id:
        await update.message.reply_text("Reminder not found.")
        return

    await repo.delete_reminder(reminder_id)

    await update.message.reply_html(f"🗑 Deleted: <b>{reminder.title}</b>")


async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /upcoming command - dashboard of next 7 days."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    # Get all active reminders
    reminders = await repo.get_reminders_by_user(user.id, status="active")  # type: ignore

    # Filter to next 7 days
    now = datetime.utcnow()
    from datetime import timedelta

    upcoming = [
        r for r in reminders if r.due_at <= now + timedelta(days=7) and r.due_at >= now
    ]

    if not upcoming:
        await update.message.reply_text("No reminders due in the next 7 days.")
        return

    message = format_reminder_list(upcoming, user)
    await update.message.reply_html(f"<b>Upcoming (Next 7 Days)</b>\n\n{message}")


async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /timezone <timezone> command."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    # If no timezone provided, show current
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            f"<b>Current timezone:</b> {user.timezone}\n\n"
            "To change: <code>/timezone America/Toronto</code>\n\n"
            "Common timezones:\n"
            "• America/Toronto\n"
            "• America/New_York\n"
            "• America/Los_Angeles\n"
            "• America/Chicago\n"
            "• Europe/London\n"
            "• Europe/Paris\n"
            "• Asia/Tokyo\n"
            "• Australia/Sydney\n\n"
            "See full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        )
        return

    new_timezone = context.args[0]

    # Validate timezone
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(new_timezone)
    except Exception:
        await update.message.reply_text(
            f"Invalid timezone: {new_timezone}\n\n"
            "Use format like: America/Toronto, Europe/London, etc."
        )
        return

    # Update user timezone
    await repo.update_user_settings(user.id, timezone=new_timezone)  # type: ignore

    await update.message.reply_html(
        f"✓ Timezone updated to <b>{new_timezone}</b>\n\n"
        "Your reminders and quiet hours will now use this timezone."
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command - show current settings."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    await update.message.reply_html(
        f"<b>Your Settings</b>\n\n"
        f"🌍 Timezone: <code>{user.timezone}</code>\n"
        f"🌙 Quiet Hours: {user.quiet_start} - {user.quiet_end}\n"
        f"📊 Escalation Profile: {user.default_escalation_profile}\n\n"
        "<b>Commands to change:</b>\n"
        "• /timezone <code>America/Toronto</code>\n"
        "• /quiet <code>23:00 07:00</code>\n"
        "• /escalation <code>standard|gentle|aggressive</code>"
    )


async def quiet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quiet <start> <end> command."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    # If no args, show current
    if not context.args or len(context.args) < 2:
        await update.message.reply_html(
            f"<b>Current quiet hours:</b> {user.quiet_start} - {user.quiet_end}\n\n"
            "To change: <code>/quiet 23:00 07:00</code>"
        )
        return

    quiet_start = context.args[0]
    quiet_end = context.args[1]

    # Validate time format
    try:
        from datetime import time
        time.fromisoformat(quiet_start)
        time.fromisoformat(quiet_end)
    except Exception:
        await update.message.reply_text(
            "Invalid time format. Use HH:MM (24-hour format)\n\n"
            "Example: /quiet 23:00 07:00"
        )
        return

    # Update settings
    await repo.update_user_settings(
        user.id, quiet_start=quiet_start, quiet_end=quiet_end  # type: ignore
    )

    await update.message.reply_html(
        f"✓ Quiet hours updated to <b>{quiet_start} - {quiet_end}</b>\n\n"
        "I won't nag you during these hours."
    )


async def quick_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quick <text> command - natural language reminder creation."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    # Get the text after /quick
    if not context.args:
        await update.message.reply_html(
            "<b>/quick - Natural Language Reminders</b>\n\n"
            "Usage: <code>/quick &lt;reminder text&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "• /quick rent due 1st every month $1500\n"
            "• /quick credit card payment $500 due 15th\n"
            "• /quick gym every monday\n"
            "• /quick call mom tomorrow\n"
            "• /quick project deadline in 2 weeks"
        )
        return

    text = ' '.join(context.args)

    # Parse the text
    parsed = parse_reminder(text, user.timezone)

    # Store in context for confirmation
    context.user_data["parsed_reminder"] = parsed
    context.user_data["user"] = user

    # Format confirmation message
    message = "<b>📝 Parsed Reminder</b>\n\n"
    message += f"<b>Title:</b> {parsed.title}\n"

    if parsed.due_at:
        from bugsbugger.utils.time_utils import from_utc
        due_local = from_utc(parsed.due_at, user.timezone)
        message += f"<b>Due:</b> {due_local.strftime('%b %d, %Y at %I:%M %p')}\n"
    else:
        message += "<b>Due:</b> ⚠️ No date detected\n"

    if parsed.is_recurring and parsed.rrule:
        message += f"<b>Recurring:</b> ✓ ({parsed.rrule})\n"

    if parsed.amount:
        curr = parsed.currency or 'USD'
        message += f"<b>Amount:</b> {curr} {parsed.amount:.2f}\n"

    if parsed.category:
        message += f"<b>Category:</b> {parsed.category}\n"

    message += f"\n<b>Confidence:</b> {int(parsed.confidence * 100)}%\n"
    message += "\nLooks good?"

    await update.message.reply_html(message, reply_markup=parsed_reminder_keyboard())


async def handle_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages as potential reminders."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    # Ignore if user is in a conversation
    if context.user_data.get("in_conversation"):
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        return  # Silently ignore if user hasn't started

    text = update.message.text

    # Parse the text
    parsed = parse_reminder(text, user.timezone)

    # Only offer to create if confidence is reasonable and we have a date
    if parsed.confidence < 0.3 or parsed.due_at is None:
        return  # Don't respond to low-confidence parses

    # Store in context
    context.user_data["parsed_reminder"] = parsed
    context.user_data["user"] = user

    # Format confirmation
    message = "<b>💡 Create reminder?</b>\n\n"
    message += f"<b>Title:</b> {parsed.title}\n"

    from bugsbugger.utils.time_utils import from_utc
    due_local = from_utc(parsed.due_at, user.timezone)
    message += f"<b>Due:</b> {due_local.strftime('%b %d, %Y at %I:%M %p')}\n"

    if parsed.is_recurring and parsed.rrule:
        message += f"<b>Recurring:</b> ✓\n"

    if parsed.amount:
        curr = parsed.currency or 'USD'
        message += f"<b>Amount:</b> {curr} {parsed.amount:.2f}\n"

    await update.message.reply_html(message, reply_markup=parsed_reminder_keyboard())


async def escalation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /escalation <profile> command."""
    if not update.effective_user or not update.message:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    # If no args, show current
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            f"<b>Current profile:</b> {user.default_escalation_profile}\n\n"
            "<b>Available profiles:</b>\n\n"
            "• <code>standard</code> - Balanced nagging\n"
            "  Gentle → Moderate → Urgent → Critical → Overdue\n\n"
            "• <code>gentle</code> - Less aggressive\n"
            "  Longer intervals, fewer nags\n\n"
            "• <code>aggressive</code> - More intense\n"
            "  Starts earlier, shorter intervals\n\n"
            "To change: <code>/escalation gentle</code>"
        )
        return

    profile = context.args[0].lower()

    if profile not in ["standard", "gentle", "aggressive"]:
        await update.message.reply_text(
            "Invalid profile. Choose: standard, gentle, or aggressive"
        )
        return

    # Update settings
    await repo.update_user_settings(user.id, default_escalation_profile=profile)  # type: ignore

    await update.message.reply_html(
        f"✓ Escalation profile updated to <b>{profile}</b>\n\n"
        "New reminders will use this profile."
    )


async def snooze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /snooze <id> [duration] command."""
    if not update.effective_user or not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /snooze <reminder_id> [duration_in_minutes]\n\n"
            "Examples:\n"
            "  /snooze 5 60   (snooze for 1 hour)\n"
            "  /snooze 5 1440 (snooze for 1 day)\n"
            "  /snooze 5      (snooze for 1 hour by default)"
        )
        return

    try:
        reminder_id = int(context.args[0])
        duration_minutes = int(context.args[1]) if len(context.args) > 1 else 60
    except ValueError:
        await update.message.reply_text("Invalid reminder ID or duration. Must be numbers.")
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return

    reminder = await repo.get_reminder(reminder_id)

    if not reminder or reminder.user_id != user.id:
        await update.message.reply_text("Reminder not found.")
        return

    # Snooze the reminder
    from datetime import timedelta

    now = datetime.utcnow()
    snoozed_until = now + timedelta(minutes=duration_minutes)

    reminder.status = "snoozed"
    reminder.snoozed_until = snoozed_until
    reminder.next_nag_at = snoozed_until
    await repo.update_reminder(reminder)

    # Log the snooze
    await repo.log_snooze(reminder_id, duration_minutes)

    from bugsbugger.utils.time_utils import format_duration

    await update.message.reply_html(
        f"⏸ <b>Snoozed:</b> {reminder.title}\n\n"
        f"Will remind you again in {format_duration(duration_minutes)}."
    )
