"""Callback query handlers for inline buttons."""

import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from bugsbugger.db.repository import Repository
from bugsbugger.utils.time_utils import format_duration

logger = logging.getLogger(__name__)


async def handle_done_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int
) -> None:
    """Handle 'Done' button press."""
    if not update.effective_user or not update.callback_query:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.callback_query.answer("Please /start the bot first.")
        return

    reminder = await repo.get_reminder(reminder_id)

    if not reminder or reminder.user_id != user.id:
        await update.callback_query.answer("Reminder not found.")
        return

    # Handle recurring reminders
    if reminder.is_recurring and reminder.rrule:
        from bugsbugger.engine.recurrence import get_next_occurrence
        from bugsbugger.engine.escalation import compute_next_nag_time

        try:
            # Get next occurrence
            next_due = get_next_occurrence(reminder.due_at, reminder.rrule)

            # Update reminder to next occurrence
            reminder.due_at = next_due
            reminder.nag_count = 0
            reminder.last_nagged_at = None
            reminder.status = "active"  # Keep active for next occurrence
            reminder.next_nag_at = compute_next_nag_time(reminder, user)

            await repo.update_reminder(reminder)

            # Edit message
            if update.callback_query.message:
                from bugsbugger.utils.time_utils import from_utc
                next_due_local = from_utc(next_due, user.timezone)
                await update.callback_query.message.edit_text(
                    f"✓ <b>Completed:</b> <s>{reminder.title}</s>\n\n"
                    f"🔁 Next occurrence: {next_due_local.strftime('%b %d, %Y')}",
                    parse_mode="HTML",
                )

            await update.callback_query.answer(f"✓ Done! Next: {next_due_local.strftime('%b %d')}")

        except Exception as e:
            logger.error(f"Error rolling forward recurring reminder: {e}")
            # Fall back to marking as done
            reminder.status = "done"
            reminder.nag_count = 0
            reminder.next_nag_at = None
            await repo.update_reminder(reminder)

            if update.callback_query.message:
                await update.callback_query.message.edit_text(
                    f"✓ <b>Completed:</b> <s>{reminder.title}</s>\n\n"
                    f"⚠️ Could not schedule next occurrence",
                    parse_mode="HTML",
                )
            await update.callback_query.answer("✓ Marked as done")

    else:
        # Non-recurring: mark as done
        reminder.status = "done"
        reminder.nag_count = 0
        reminder.next_nag_at = None
        await repo.update_reminder(reminder)

        # Edit the message to show completion
        if update.callback_query.message:
            await update.callback_query.message.edit_text(
                f"✓ <b>Completed:</b> <s>{reminder.title}</s>",
                parse_mode="HTML",
            )

        await update.callback_query.answer(f"✓ Marked {reminder.title} as done!")


async def handle_snooze_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int, minutes: int
) -> None:
    """Handle 'Snooze' button press."""
    if not update.effective_user or not update.callback_query:
        return

    repo: Repository = context.bot_data["repo"]
    user = await repo.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.callback_query.answer("Please /start the bot first.")
        return

    reminder = await repo.get_reminder(reminder_id)

    if not reminder or reminder.user_id != user.id:
        await update.callback_query.answer("Reminder not found.")
        return

    # Snooze the reminder
    now = datetime.utcnow()
    snoozed_until = now + timedelta(minutes=minutes)

    reminder.status = "snoozed"
    reminder.snoozed_until = snoozed_until
    reminder.next_nag_at = snoozed_until
    await repo.update_reminder(reminder)

    # Log the snooze
    await repo.log_snooze(reminder_id, minutes)

    # Edit the message
    if update.callback_query.message:
        await update.callback_query.message.edit_text(
            f"⏸ <b>Snoozed:</b> {reminder.title}\n\n"
            f"Will remind you again in {format_duration(minutes)}.",
            parse_mode="HTML",
        )

    await update.callback_query.answer(f"⏸ Snoozed for {format_duration(minutes)}")


async def handle_parsed_confirmation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle confirmation of parsed reminder."""
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    await query.answer()

    if query.data == "confirm:parsed":
        # Create the reminder
        repo: Repository = context.bot_data["repo"]
        user = context.user_data.get("user")
        parsed = context.user_data.get("parsed_reminder")

        if not user or not parsed:
            if query.message:
                await query.message.edit_text("Error: Session expired. Please try again.")
            return

        # Get category ID if category was detected
        category_id = None
        if parsed.category:
            category = await repo.get_category_by_name(user.id, parsed.category)  # type: ignore
            if category:
                category_id = category.id

        # Create reminder
        from bugsbugger.db.models import Reminder
        from bugsbugger.engine.escalation import compute_next_nag_time

        reminder = Reminder(
            user_id=user.id,  # type: ignore
            title=parsed.title,
            due_at=parsed.due_at,  # type: ignore
            amount=parsed.amount,
            currency=parsed.currency,
            category_id=category_id,
            is_recurring=parsed.is_recurring,
            rrule=parsed.rrule,
            status="active",
            escalation_profile=user.default_escalation_profile,
        )

        # Compute next nag time
        reminder.next_nag_at = compute_next_nag_time(reminder, user)

        created = await repo.create_reminder(reminder)

        if query.message:
            await query.message.edit_text(
                f"✓ <b>Reminder created!</b>\n\n"
                f"ID: {created.id}\n"
                f"Title: {created.title}\n\n"
                f"Use /list to see all your reminders.",
                parse_mode="HTML",
            )

    elif query.data == "cancel:parsed":
        if query.message:
            await query.message.edit_text("❌ Cancelled.")

    # Clear context
    context.user_data.pop("parsed_reminder", None)
    context.user_data.pop("user", None)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route callback queries to appropriate handlers."""
    if not update.callback_query:
        return

    query = update.callback_query
    data = query.data

    if not data:
        return

    # Parse callback data
    parts = data.split(":")

    if parts[0] == "done":
        reminder_id = int(parts[1])
        await handle_done_callback(update, context, reminder_id)

    elif parts[0] == "snooze":
        reminder_id = int(parts[1])
        minutes = int(parts[2])
        await handle_snooze_callback(update, context, reminder_id, minutes)

    elif parts[0] == "confirm" and parts[1] == "parsed":
        await handle_parsed_confirmation(update, context)

    elif parts[0] == "cancel":
        if parts[1] == "parsed":
            await handle_parsed_confirmation(update, context)
        else:
            # Generic cancel
            if query.message:
                await query.message.delete()
            await query.answer("Cancelled")

    else:
        await query.answer("Unknown action")
