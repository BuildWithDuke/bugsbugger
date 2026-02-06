"""Main entry point for BugsBugger bot."""

import logging
import sys
from pathlib import Path

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bugsbugger.bot.callbacks import callback_router
from bugsbugger.bot.conversations import build_add_conversation_handler
from bugsbugger.bot.handlers import (
    category_command,
    delete_command,
    done_command,
    edit_command,
    escalation_command,
    handle_plain_text,
    help_command,
    list_command,
    quiet_command,
    quick_command,
    settings_command,
    snooze_command,
    start_command,
    stats_command,
    timezone_command,
    upcoming_command,
)
from bugsbugger.config import Config
from bugsbugger.db.migrations import run_migrations
from bugsbugger.db.repository import Repository
from bugsbugger.engine.nag_engine import heartbeat, startup_recovery
from bugsbugger.utils.error_handler import error_handler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, Config.LOG_LEVEL),
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


async def heartbeat_job(context: "ContextTypes.DEFAULT_TYPE") -> None:
    """Job callback for the heartbeat."""
    repo: Repository = context.bot_data["repo"]
    await heartbeat(context.bot, repo)


async def post_init(application: Application) -> None:
    """Initialize bot resources after application is created."""
    # Initialize database
    await run_migrations(Config.DATABASE_PATH)

    # Create repository and store in bot_data
    repo = Repository(Config.DATABASE_PATH)
    await repo.connect()
    application.bot_data["repo"] = repo

    # Run startup recovery
    await startup_recovery(repo)

    # Start the heartbeat job
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            heartbeat_job,
            interval=Config.HEARTBEAT_INTERVAL,
            first=10,  # Start after 10 seconds
            name="heartbeat",
        )
        logger.info(f"Heartbeat job scheduled (interval: {Config.HEARTBEAT_INTERVAL}s)")

    logger.info("BugsBugger initialized successfully")


async def post_shutdown(application: Application) -> None:
    """Cleanup resources on shutdown."""
    repo: Repository = application.bot_data.get("repo")
    if repo:
        await repo.close()

    logger.info("BugsBugger shut down")


def main() -> None:
    """Start the bot."""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Create application
    application = (
        Application.builder()
        .token(Config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register handlers

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("upcoming", upcoming_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("snooze", snooze_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("category", category_command))

    # Settings commands
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("timezone", timezone_command))
    application.add_handler(CommandHandler("quiet", quiet_command))
    application.add_handler(CommandHandler("escalation", escalation_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Natural language parsing
    application.add_handler(CommandHandler("quick", quick_command))

    # Conversation handlers
    application.add_handler(build_add_conversation_handler())

    # Edit conversation handler
    from bugsbugger.bot.edit_handlers import (
        EDIT_TITLE, EDIT_DATE, EDIT_AMOUNT, EDIT_RECURRENCE,
        handle_edit_title, handle_edit_date, handle_edit_amount,
        handle_edit_recurrence, edit_cancel
    )
    from telegram.ext import ConversationHandler

    edit_conv_handler = ConversationHandler(
        entry_points=[],  # Entry is via callback, not command
        states={
            EDIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_title)],
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_date)],
            EDIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_amount)],
            EDIT_RECURRENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_recurrence)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
        per_message=False,
    )
    application.add_handler(edit_conv_handler)

    # Callback queries (buttons)
    application.add_handler(CallbackQueryHandler(callback_router))

    # Plain text handler (must be last)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_text)
    )

    # Error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Starting BugsBugger bot...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
