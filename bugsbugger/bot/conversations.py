"""Conversation handlers for multi-step flows."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bugsbugger.bot.formatters import format_reminder
from bugsbugger.bot.keyboards import confirm_cancel_keyboard
from bugsbugger.db.models import Reminder
from bugsbugger.db.repository import Repository
from bugsbugger.engine.escalation import compute_next_nag_time

logger = logging.getLogger(__name__)

# Conversation states
TITLE, DATE, AMOUNT, CONFIRM = range(4)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the /add conversation."""
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Please /start the bot first.")
        return ConversationHandler.END

    # Store user in context
    context.user_data["user"] = user
    context.user_data["reminder_data"] = {}

    await update.message.reply_text(
        "<b>Add Reminder</b>\n\nWhat's the reminder title?\n\n"
        "Example: <i>Credit card payment</i>\n\n"
        "Send /cancel to abort.",
        parse_mode=ParseMode.HTML,
    )

    return TITLE


async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive reminder title."""
    if not update.message or not update.message.text:
        return TITLE

    title = update.message.text.strip()

    if not title:
        await update.message.reply_text("Please enter a title.")
        return TITLE

    context.user_data["reminder_data"]["title"] = title

    await update.message.reply_text(
        f"<b>Title:</b> {title}\n\n"
        "When is it due?\n\n"
        "Examples:\n"
        "• <i>tomorrow</i>\n"
        "• <i>March 15</i>\n"
        "• <i>in 3 days</i>\n"
        "• <i>2026-03-15 14:30</i>\n\n"
        "Send /cancel to abort.",
        parse_mode=ParseMode.HTML,
    )

    return DATE


async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive due date."""
    if not update.message or not update.message.text:
        return DATE

    date_text = update.message.text.strip().lower()
    user = context.user_data["user"]

    # Simple date parsing (will be enhanced in Phase 3 with parser)
    try:
        due_at = parse_simple_date(date_text, user.timezone)
    except ValueError as e:
        await update.message.reply_text(
            f"Couldn't parse that date: {e}\n\nPlease try again or /cancel."
        )
        return DATE

    context.user_data["reminder_data"]["due_at"] = due_at

    due_local = due_at.astimezone(ZoneInfo(user.timezone))
    await update.message.reply_text(
        f"<b>Due:</b> {due_local.strftime('%b %d, %Y at %I:%M %p')}\n\n"
        "Is there an amount? (optional)\n\n"
        "Examples:\n"
        "• <i>$500</i>\n"
        "• <i>1500.00</i>\n"
        "• <i>skip</i> (no amount)\n\n"
        "Send /cancel to abort.",
        parse_mode=ParseMode.HTML,
    )

    return AMOUNT


async def add_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive amount (optional)."""
    if not update.message or not update.message.text:
        return AMOUNT

    amount_text = update.message.text.strip().lower()

    # Parse amount
    amount = None
    currency = None

    if amount_text not in ["skip", "no", "none", ""]:
        try:
            # Remove currency symbols and parse
            amount_clean = amount_text.replace("$", "").replace(",", "").strip()
            amount = float(amount_clean)
            currency = "USD"  # Default currency
        except ValueError:
            await update.message.reply_text(
                "Invalid amount. Please enter a number or 'skip'."
            )
            return AMOUNT

    context.user_data["reminder_data"]["amount"] = amount
    context.user_data["reminder_data"]["currency"] = currency

    # Show confirmation
    await show_confirmation(update, context)

    return CONFIRM


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show confirmation message with reminder details."""
    if not update.message:
        return

    user = context.user_data["user"]
    data = context.user_data["reminder_data"]

    # Create a preview reminder
    reminder = Reminder(
        user_id=user.id,  # type: ignore
        title=data["title"],
        due_at=data["due_at"],
        amount=data.get("amount"),
        currency=data.get("currency"),
        status="active",
        escalation_profile=user.default_escalation_profile,
    )

    message = (
        "<b>Confirm Reminder</b>\n\n"
        + format_reminder(reminder, user, show_id=False)
        + "\n\nLooks good?"
    )

    await update.message.reply_html(
        message, reply_markup=confirm_cancel_keyboard("add")
    )


async def add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation callback."""
    if not update.callback_query or not update.effective_user:
        return ConversationHandler.END

    query = update.callback_query

    # IMPORTANT: Answer the callback query first to stop the loading state
    await query.answer()

    try:
        if query.data == "confirm:add":
            # Create the reminder
            repo: Repository = context.bot_data["repo"]
            user = context.user_data.get("user")
            data = context.user_data.get("reminder_data")

            if not user or not data:
                if query.message:
                    await query.message.edit_text(
                        "Error: Session expired. Please use /add again."
                    )
                return ConversationHandler.END

            # Create reminder object
            reminder = Reminder(
                user_id=user.id,  # type: ignore
                title=data["title"],
                due_at=data["due_at"],
                amount=data.get("amount"),
                currency=data.get("currency"),
                status="active",
                escalation_profile=user.default_escalation_profile,
            )

            # Compute initial next_nag_at using escalation engine
            reminder.next_nag_at = compute_next_nag_time(reminder, user)

            created = await repo.create_reminder(reminder)

            if query.message:
                await query.message.edit_text(
                    f"✓ <b>Reminder created!</b>\n\n"
                    f"ID: {created.id}\n"
                    f"Title: {created.title}\n\n"
                    f"Use /list to see all your reminders.",
                    parse_mode=ParseMode.HTML,
                )

        elif query.data == "cancel:add":
            if query.message:
                await query.message.edit_text("❌ Cancelled. Use /add to try again.")

    except Exception as e:
        logger.error(f"Error in add_confirm: {e}")
        if query.message:
            await query.message.edit_text(
                f"Error creating reminder: {e}\n\nPlease try /add again."
            )

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the /add conversation."""
    if not update.message:
        return ConversationHandler.END

    await update.message.reply_text("Cancelled.")
    context.user_data.clear()

    return ConversationHandler.END


def parse_simple_date(text: str, timezone: str) -> datetime:
    """Simple date parser (enhanced version in Phase 3).

    Supports:
    - tomorrow
    - in X days/hours/minutes
    - ISO format (2026-03-15 or 2026-03-15 14:30)

    Returns:
        datetime in UTC timezone (always timezone-aware)
    """
    from bugsbugger.utils.time_utils import to_utc

    # Get current time in user's timezone
    now_local = datetime.now(ZoneInfo(timezone))

    if text == "tomorrow":
        dt_local = (now_local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return to_utc(dt_local, timezone)

    if text.startswith("in "):
        parts = text[3:].split()
        if len(parts) == 2:
            try:
                value = int(parts[0])
                unit = parts[1].lower()

                if unit in ["day", "days"]:
                    dt_local = now_local + timedelta(days=value)
                elif unit in ["hour", "hours"]:
                    dt_local = now_local + timedelta(hours=value)
                elif unit in ["minute", "minutes", "min", "mins"]:
                    dt_local = now_local + timedelta(minutes=value)
                else:
                    raise ValueError(f"Unknown time unit: {unit}")

                return to_utc(dt_local, timezone)
            except ValueError as e:
                raise ValueError(f"Invalid time value: {e}")

    # Try ISO format
    try:
        # Try with time
        if " " in text:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        else:
            dt = datetime.strptime(text, "%Y-%m-%d")
            dt = dt.replace(hour=9, minute=0)

        # Make timezone-aware in user's timezone, then convert to UTC
        dt_local = dt.replace(tzinfo=ZoneInfo(timezone))
        return to_utc(dt_local, timezone)
    except ValueError:
        pass

    raise ValueError(f"Couldn't understand date format: {text}")


# Build the conversation handler
def build_add_conversation_handler() -> ConversationHandler:
    """Build the /add conversation handler."""
    from telegram.ext import CallbackQueryHandler

    return ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount)],
            CONFIRM: [
                CallbackQueryHandler(add_confirm, pattern=r"^(confirm|cancel):add$")
            ],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
        per_message=False,  # Track per conversation, not per message
        conversation_timeout=300,  # 5 minute timeout
    )
