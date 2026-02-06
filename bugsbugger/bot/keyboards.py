"""Inline keyboard builders."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def done_snooze_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Keyboard for nag messages: Done, Snooze options."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✓ Done", callback_data=f"done:{reminder_id}"),
                InlineKeyboardButton("Snooze 1h", callback_data=f"snooze:{reminder_id}:60"),
            ],
            [
                InlineKeyboardButton("Snooze 1d", callback_data=f"snooze:{reminder_id}:1440"),
                InlineKeyboardButton("Snooze...", callback_data=f"snooze_custom:{reminder_id}"),
            ],
        ]
    )


def confirm_cancel_keyboard(action: str) -> InlineKeyboardMarkup:
    """Keyboard for confirmations: Confirm, Cancel."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✓ Confirm", callback_data=f"confirm:{action}"),
                InlineKeyboardButton("✗ Cancel", callback_data=f"cancel:{action}"),
            ]
        ]
    )


def reminder_actions_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Keyboard for reminder detail view: Done, Edit, Delete."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✓ Done", callback_data=f"done:{reminder_id}"),
                InlineKeyboardButton("✎ Edit", callback_data=f"edit:{reminder_id}"),
            ],
            [
                InlineKeyboardButton("Snooze", callback_data=f"snooze_custom:{reminder_id}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete_confirm:{reminder_id}"),
            ],
        ]
    )


def parsed_reminder_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for parsed reminder confirmation: Confirm, Edit, Cancel."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✓ Confirm", callback_data="confirm:parsed"),
                InlineKeyboardButton("✎ Edit", callback_data="edit:parsed"),
            ],
            [
                InlineKeyboardButton("✗ Cancel", callback_data="cancel:parsed"),
            ],
        ]
    )
