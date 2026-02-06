"""Configuration management from environment variables."""

import os
from pathlib import Path
from typing import Literal

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars


class Config:
    """Application configuration loaded from environment variables."""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Database
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", "./data/bugsbugger.db"))

    # Parser
    PARSER_BACKEND: Literal["regex", "claude"] = os.getenv("PARSER_BACKEND", "regex")  # type: ignore
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Engine
    HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "60"))

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        if cls.PARSER_BACKEND == "claude" and not cls.CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY required when PARSER_BACKEND=claude")

        # Ensure database directory exists
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
