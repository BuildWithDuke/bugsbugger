"""Nag engine - the heartbeat that sends nag messages."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot
from telegram.error import TelegramError

from bugsbugger.bot.formatters import format_nag_message
from bugsbugger.bot.keyboards import done_snooze_keyboard
from bugsbugger.db.repository import Repository
from bugsbugger.engine.escalation import compute_next_nag_time, get_current_tier

logger = logging.getLogger(__name__)


async def heartbeat(bot: Bot, repo: Repository) -> None:
    """Heartbeat job that checks for due nags and sends them.

    This runs every 60 seconds and:
    1. Queries for reminders where next_nag_at <= now
    2. Sends nag messages
    3. Updates reminder state and computes next nag time
    """
    now = datetime.now(ZoneInfo("UTC"))

    try:
        # Get all reminders due for nagging
        due_reminders = await repo.get_due_nags()

        if not due_reminders:
            return

        logger.info(f"Heartbeat: {len(due_reminders)} reminders due for nagging")

        for reminder in due_reminders:
            try:
                # Get user info
                user = await repo.get_user_by_id(reminder.user_id)
                if not user:
                    logger.warning(f"User not found for reminder {reminder.id}")
                    continue

                # Get current escalation tier
                tier, _ = get_current_tier(reminder, now)

                # Format and send nag message
                message = format_nag_message(reminder, user, tier.name)

                try:
                    sent_message = await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML",
                        reply_markup=done_snooze_keyboard(reminder.id),  # type: ignore
                    )

                    # Log the nag
                    await repo.log_nag(
                        reminder_id=reminder.id,  # type: ignore
                        telegram_message_id=sent_message.message_id,
                        escalation_tier=tier.name,
                        nag_count=reminder.nag_count + 1,
                    )

                    # Update reminder state
                    reminder.last_nagged_at = now
                    reminder.nag_count += 1
                    reminder.next_nag_at = compute_next_nag_time(reminder, user, now)

                    await repo.update_reminder(reminder)

                    logger.info(
                        f"Sent nag for reminder {reminder.id} ({tier.name} tier, "
                        f"count: {reminder.nag_count})"
                    )

                except TelegramError as e:
                    logger.error(f"Failed to send nag for reminder {reminder.id}: {e}")
                    # Don't update the reminder, will retry next heartbeat

            except Exception as e:
                logger.error(f"Error processing reminder {reminder.id}: {e}")
                continue

    except Exception as e:
        logger.error(f"Heartbeat error: {e}")


async def startup_recovery(repo: Repository) -> None:
    """Recovery on startup: catch up on missed nags.

    Finds all active reminders with next_nag_at in the past
    and sets them to now so the next heartbeat picks them up.
    """
    now = datetime.now(ZoneInfo("UTC"))

    try:
        # Get all overdue nags
        due_reminders = await repo.get_due_nags()

        if due_reminders:
            logger.info(
                f"Startup recovery: {len(due_reminders)} reminders have overdue nags"
            )

            for reminder in due_reminders:
                # Reset next_nag_at to now so heartbeat catches them
                reminder.next_nag_at = now
                await repo.update_reminder(reminder)

            logger.info("Startup recovery complete")

    except Exception as e:
        logger.error(f"Startup recovery error: {e}")
