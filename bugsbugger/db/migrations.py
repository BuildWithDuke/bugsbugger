"""Database migration runner."""

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


async def init_database(db_path: Path) -> None:
    """Initialize the database with the schema."""
    schema_path = Path(__file__).parent / "schema.sql"

    async with aiosqlite.connect(db_path) as db:
        # Read and execute schema
        with open(schema_path) as f:
            schema_sql = f.read()

        await db.executescript(schema_sql)
        await db.commit()

        logger.info(f"Database initialized at {db_path}")


async def run_migrations(db_path: Path) -> None:
    """Run any pending migrations.

    Currently just ensures the database is initialized.
    Future migrations can be added as versioned functions.
    """
    await init_database(db_path)
