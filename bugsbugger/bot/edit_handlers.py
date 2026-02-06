"""Edit conversation handlers for reminders."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bugsbugger.bot.conversations import parse_simple_date
from bugsbugger.db.repository import Repository
from bugsbugger.engine.escalation import compute_next_nag_time

logger = logging.getLogger(__name__)

# Conversation states
EDIT_TITLE, EDIT_DATE, EDIT_AMOUNT, EDIT_RECURRENCE = range(4)


async def edit_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Route edit button callbacks to appropriate handlers."""
    if not update.callback_query:
        return None

    query = update.callback_query
    data = query.data

    if not data or not data.startswith("edit_"):
        return None

    await query.answer()

    parts = data.split(":")
    action = parts[0]
    reminder_id = int(parts[1])

    # Store reminder_id in context
    context.user_data["editing_reminder_id"] = reminder_id

    repo: Repository = context.bot_data["repo"]
    reminder = await repo.get_reminder(reminder_id)

    if not reminder:
        await query.message.edit_text("❌ Reminder not found.")
        return ConversationHandler.END

    # Route to appropriate handler
    if action == "edit_title":
        await query.message.edit_text(
            f"<b>Edit Title</b>\n\n"
            f"Current: <i>{reminder.title}</i>\n\n"
            f"Send me the new title, or /cancel to abort.",
            parse_mode="HTML"
        )
        return EDIT_TITLE

    elif action == "edit_date":
        from bugsbugger.utils.time_utils import from_utc
        user = await repo.get_user_by_id(reminder.user_id)
        if user:
            due_local = from_utc(reminder.due_at, user.timezone)
            current_date = due_local.strftime('%b %d, %Y at %I:%M %p')
        else:
            current_date = reminder.due_at.isoformat()

        await query.message.edit_text(
            f"<b>Edit Due Date</b>\n\n"
            f"Current: <i>{current_date}</i>\n\n"
            f"Send me the new date (e.g., 'tomorrow', '15th', 'in 3 days'), or /cancel.",
            parse_mode="HTML"
        )
        return EDIT_DATE

    elif action == "edit_amount":
        current = f"${reminder.amount:.2f}" if reminder.amount else "None"
        await query.message.edit_text(
            f"<b>Edit Amount</b>\n\n"
            f"Current: <i>{current}</i>\n\n"
            f"Send me the new amount (e.g., '$500', '1200.50', or 'none'), or /cancel.",
            parse_mode="HTML"
        )
        return EDIT_AMOUNT

    elif action == "edit_recur":
        recur_text = reminder.rrule if reminder.is_recurring else "Not recurring"
        await query.message.edit_text(
            f"<b>Edit Recurrence</b>\n\n"
            f"Current: <i>{recur_text}</i>\n\n"
            f"Send me the recurrence pattern (e.g., 'every month', 'every monday', or 'none'), or /cancel.",
            parse_mode="HTML"
        )
        return EDIT_RECURRENCE

    return None


async def handle_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new title input."""
    if not update.message or not update.message.text:
        return EDIT_TITLE

    new_title = update.message.text.strip()

    if not new_title:
        await update.message.reply_text("Title cannot be empty. Please try again or /cancel.")
        return EDIT_TITLE

    reminder_id = context.user_data.get("editing_reminder_id")
    if not reminder_id:
        await update.message.reply_text("❌ Session expired. Please try /edit again.")
        return ConversationHandler.END

    repo: Repository = context.bot_data["repo"]
    reminder = await repo.get_reminder(reminder_id)

    if not reminder:
        await update.message.reply_text("❌ Reminder not found.")
        return ConversationHandler.END

    # Update
    reminder.title = new_title
    await repo.update_reminder(reminder)

    await update.message.reply_html(
        f"✓ <b>Updated title:</b>\n<i>{new_title}</i>"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def handle_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new date input."""
    if not update.message or not update.message.text:
        return EDIT_DATE

    date_text = update.message.text.strip()
    reminder_id = context.user_data.get("editing_reminder_id")

    if not reminder_id:
        await update.message.reply_text("❌ Session expired. Please try /edit again.")
        return ConversationHandler.END

    repo: Repository = context.bot_data["repo"]
    reminder = await repo.get_reminder(reminder_id)

    if not reminder:
        await update.message.reply_text("❌ Reminder not found.")
        return ConversationHandler.END

    user = await repo.get_user_by_id(reminder.user_id)
    if not user:
        await update.message.reply_text("❌ User not found.")
        return ConversationHandler.END

    # Parse new date
    try:
        new_due_at = parse_simple_date(date_text, user.timezone)

        # Update reminder
        reminder.due_at = new_due_at
        reminder.next_nag_at = compute_next_nag_time(reminder, user)
        await repo.update_reminder(reminder)

        from bugsbugger.utils.time_utils import from_utc
        due_local = from_utc(new_due_at, user.timezone)

        await update.message.reply_html(
            f"✓ <b>Updated due date:</b>\n<i>{due_local.strftime('%b %d, %Y at %I:%M %p')}</i>"
        )

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError as e:
        await update.message.reply_text(f"❌ Couldn't parse date: {e}\n\nPlease try again or /cancel.")
        return EDIT_DATE


async def handle_edit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new amount input."""
    if not update.message or not update.message.text:
        return EDIT_AMOUNT

    amount_text = update.message.text.strip().lower()
    reminder_id = context.user_data.get("editing_reminder_id")

    if not reminder_id:
        await update.message.reply_text("❌ Session expired. Please try /edit again.")
        return ConversationHandler.END

    repo: Repository = context.bot_data["repo"]
    reminder = await repo.get_reminder(reminder_id)

    if not reminder:
        await update.message.reply_text("❌ Reminder not found.")
        return ConversationHandler.END

    # Parse amount
    if amount_text in ["none", "no", "remove", "delete"]:
        reminder.amount = None
        reminder.currency = None
        await repo.update_reminder(reminder)
        await update.message.reply_text("✓ Removed amount")
    else:
        try:
            # Remove currency symbols
            amount_clean = amount_text.replace("$", "").replace(",", "").strip()
            amount = float(amount_clean)

            reminder.amount = amount
            reminder.currency = reminder.currency or "USD"
            await repo.update_reminder(reminder)

            await update.message.reply_html(
                f"✓ <b>Updated amount:</b> ${amount:.2f}"
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number or 'none'.\n\nTry again or /cancel.")
            return EDIT_AMOUNT

    context.user_data.clear()
    return ConversationHandler.END


async def handle_edit_recurrence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new recurrence input."""
    if not update.message or not update.message.text:
        return EDIT_RECURRENCE

    recur_text = update.message.text.strip().lower()
    reminder_id = context.user_data.get("editing_reminder_id")

    if not reminder_id:
        await update.message.reply_text("❌ Session expired. Please try /edit again.")
        return ConversationHandler.END

    repo: Repository = context.bot_data["repo"]
    reminder = await repo.get_reminder(reminder_id)

    if not reminder:
        await update.message.reply_text("❌ Reminder not found.")
        return ConversationHandler.END

    # Parse recurrence
    if recur_text in ["none", "no", "remove", "delete", "one-time"]:
        reminder.is_recurring = False
        reminder.rrule = None
        await repo.update_reminder(reminder)
        await update.message.reply_text("✓ Removed recurrence (now one-time)")
    else:
        from bugsbugger.engine.recurrence import build_rrule_from_text

        rrule = build_rrule_from_text(recur_text)
        if rrule:
            reminder.is_recurring = True
            reminder.rrule = rrule
            await repo.update_reminder(reminder)
            await update.message.reply_html(f"✓ <b>Updated recurrence:</b> {rrule}")
        else:
            await update.message.reply_text(
                "❌ Couldn't understand recurrence pattern.\n\n"
                "Try: 'every day', 'every month', 'every monday', etc.\n\n"
                "Or /cancel to abort."
            )
            return EDIT_RECURRENCE

    context.user_data.clear()
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel editing."""
    if update.message:
        await update.message.reply_text("❌ Edit cancelled.")
    context.user_data.clear()
    return ConversationHandler.END
