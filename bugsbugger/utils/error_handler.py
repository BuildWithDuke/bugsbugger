"""Global error handler for the bot."""

import logging
import traceback

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot."""
    # Log the error
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Get the traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Log full traceback
    logger.error(f"Traceback:\n{tb_string}")

    # Try to notify the user
    if isinstance(update, Update) and update.effective_message:
        try:
            error_message = (
                "😅 Oops! Something went wrong.\n\n"
                "The error has been logged. Please try again or use /help for assistance."
            )

            # Provide specific error messages for common issues
            error = context.error

            if "Unauthorized" in str(error):
                error_message = (
                    "❌ I don't have permission to send you messages.\n\n"
                    "Please /start the bot first."
                )
            elif "Bad Request" in str(error):
                error_message = (
                    "❌ Invalid request.\n\n"
                    "Please check your command syntax and try again. Use /help for examples."
                )
            elif "Timeout" in str(error):
                error_message = (
                    "⏱️ Request timed out.\n\n"
                    "Please try again in a moment."
                )
            elif "Network" in str(error):
                error_message = (
                    "🌐 Network error.\n\n"
                    "Please check your connection and try again."
                )

            await update.effective_message.reply_text(error_message)

        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
