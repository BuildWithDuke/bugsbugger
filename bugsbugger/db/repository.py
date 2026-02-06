"""Database repository - all SQL queries."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

import aiosqlite

from bugsbugger.db.models import Category, NagHistory, Reminder, SnoozeLog, User
from bugsbugger.utils.constants import DEFAULT_CATEGORIES

logger = logging.getLogger(__name__)


class Repository:
    """Database access layer."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        logger.info(f"Connected to database at {self.db_path}")

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            logger.info("Database connection closed")

    @property
    def db(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if self._db is None:
            raise RuntimeError("Database not connected")
        return self._db

    # User operations

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        async with self.db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return User(
                    id=row["id"],
                    telegram_id=row["telegram_id"],
                    timezone=row["timezone"],
                    quiet_start=row["quiet_start"],
                    quiet_end=row["quiet_end"],
                    default_escalation_profile=row["default_escalation_profile"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            return None

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by database ID."""
        async with self.db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return User(
                    id=row["id"],
                    telegram_id=row["telegram_id"],
                    timezone=row["timezone"],
                    quiet_start=row["quiet_start"],
                    quiet_end=row["quiet_end"],
                    default_escalation_profile=row["default_escalation_profile"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            return None

    async def create_user(self, telegram_id: int) -> User:
        """Create a new user with default settings."""
        async with self.db.execute(
            """
            INSERT INTO users (telegram_id)
            VALUES (?)
            RETURNING *
            """,
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            await self.db.commit()

            user = User(
                id=row["id"],
                telegram_id=row["telegram_id"],
                timezone=row["timezone"],
                quiet_start=row["quiet_start"],
                quiet_end=row["quiet_end"],
                default_escalation_profile=row["default_escalation_profile"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

            # Seed default categories
            for category_name in DEFAULT_CATEGORIES:
                await self.create_category(user.id, category_name)  # type: ignore

            logger.info(f"Created user {telegram_id}")
            return user

    async def update_user_settings(
        self,
        user_id: int,
        timezone: str | None = None,
        quiet_start: str | None = None,
        quiet_end: str | None = None,
        default_escalation_profile: str | None = None,
    ) -> None:
        """Update user settings."""
        updates = []
        params = []

        if timezone is not None:
            updates.append("timezone = ?")
            params.append(timezone)
        if quiet_start is not None:
            updates.append("quiet_start = ?")
            params.append(quiet_start)
        if quiet_end is not None:
            updates.append("quiet_end = ?")
            params.append(quiet_end)
        if default_escalation_profile is not None:
            updates.append("default_escalation_profile = ?")
            params.append(default_escalation_profile)

        if updates:
            params.append(user_id)
            await self.db.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
            )
            await self.db.commit()

    # Category operations

    async def get_categories(self, user_id: int) -> List[Category]:
        """Get all categories for a user."""
        async with self.db.execute(
            "SELECT * FROM categories WHERE user_id = ? ORDER BY name",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                Category(id=row["id"], user_id=row["user_id"], name=row["name"])
                for row in rows
            ]

    async def get_category_by_name(self, user_id: int, name: str) -> Category | None:
        """Get a category by name."""
        async with self.db.execute(
            "SELECT * FROM categories WHERE user_id = ? AND name = ?",
            (user_id, name),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Category(id=row["id"], user_id=row["user_id"], name=row["name"])
            return None

    async def create_category(self, user_id: int, name: str) -> Category:
        """Create a new category."""
        async with self.db.execute(
            "INSERT INTO categories (user_id, name) VALUES (?, ?) RETURNING *",
            (user_id, name),
        ) as cursor:
            row = await cursor.fetchone()
            await self.db.commit()
            return Category(id=row["id"], user_id=row["user_id"], name=row["name"])

    # Reminder operations

    async def create_reminder(self, reminder: Reminder) -> Reminder:
        """Create a new reminder."""
        async with self.db.execute(
            """
            INSERT INTO reminders (
                user_id, title, description, amount, currency, category_id,
                due_at, is_recurring, rrule, escalation_profile, custom_escalation,
                status, next_nag_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                reminder.user_id,
                reminder.title,
                reminder.description,
                reminder.amount,
                reminder.currency,
                reminder.category_id,
                reminder.due_at.isoformat(),
                1 if reminder.is_recurring else 0,
                reminder.rrule,
                reminder.escalation_profile,
                reminder.custom_escalation,
                reminder.status,
                reminder.next_nag_at.isoformat() if reminder.next_nag_at else None,
            ),
        ) as cursor:
            row = await cursor.fetchone()
            await self.db.commit()
            return self._row_to_reminder(row)

    async def get_reminder(self, reminder_id: int) -> Reminder | None:
        """Get a reminder by ID."""
        async with self.db.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_reminder(row)
            return None

    async def get_reminders_by_user(
        self, user_id: int, status: str | None = None
    ) -> List[Reminder]:
        """Get all reminders for a user, optionally filtered by status."""
        if status:
            query = "SELECT * FROM reminders WHERE user_id = ? AND status = ? ORDER BY due_at"
            params = (user_id, status)
        else:
            query = "SELECT * FROM reminders WHERE user_id = ? ORDER BY due_at"
            params = (user_id,)

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_reminder(row) for row in rows]

    async def get_due_nags(self) -> List[Reminder]:
        """Get all reminders that are due for nagging (heartbeat query)."""
        now = datetime.utcnow().isoformat()
        async with self.db.execute(
            """
            SELECT * FROM reminders
            WHERE status = 'active'
            AND next_nag_at IS NOT NULL
            AND next_nag_at <= ?
            ORDER BY next_nag_at
            """,
            (now,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_reminder(row) for row in rows]

    async def update_reminder(self, reminder: Reminder) -> None:
        """Update a reminder."""
        await self.db.execute(
            """
            UPDATE reminders SET
                title = ?,
                description = ?,
                amount = ?,
                currency = ?,
                category_id = ?,
                due_at = ?,
                is_recurring = ?,
                rrule = ?,
                escalation_profile = ?,
                custom_escalation = ?,
                status = ?,
                next_nag_at = ?,
                snoozed_until = ?,
                last_nagged_at = ?,
                nag_count = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                reminder.title,
                reminder.description,
                reminder.amount,
                reminder.currency,
                reminder.category_id,
                reminder.due_at.isoformat(),
                1 if reminder.is_recurring else 0,
                reminder.rrule,
                reminder.escalation_profile,
                reminder.custom_escalation,
                reminder.status,
                reminder.next_nag_at.isoformat() if reminder.next_nag_at else None,
                reminder.snoozed_until.isoformat() if reminder.snoozed_until else None,
                reminder.last_nagged_at.isoformat() if reminder.last_nagged_at else None,
                reminder.nag_count,
                reminder.id,
            ),
        )
        await self.db.commit()

    async def delete_reminder(self, reminder_id: int) -> None:
        """Delete a reminder."""
        await self.db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await self.db.commit()

    # Nag history operations

    async def log_nag(
        self,
        reminder_id: int,
        telegram_message_id: int,
        escalation_tier: str,
        nag_count: int,
    ) -> None:
        """Log a sent nag to history."""
        await self.db.execute(
            """
            INSERT INTO nag_history (reminder_id, telegram_message_id, escalation_tier, nag_count)
            VALUES (?, ?, ?, ?)
            """,
            (reminder_id, telegram_message_id, escalation_tier, nag_count),
        )
        await self.db.commit()

    async def get_nag_history(self, reminder_id: int) -> List[NagHistory]:
        """Get nag history for a reminder."""
        async with self.db.execute(
            "SELECT * FROM nag_history WHERE reminder_id = ? ORDER BY sent_at DESC",
            (reminder_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                NagHistory(
                    id=row["id"],
                    reminder_id=row["reminder_id"],
                    sent_at=datetime.fromisoformat(row["sent_at"]),
                    telegram_message_id=row["telegram_message_id"],
                    escalation_tier=row["escalation_tier"],
                    nag_count=row["nag_count"],
                )
                for row in rows
            ]

    # Snooze log operations

    async def log_snooze(self, reminder_id: int, duration_minutes: int) -> None:
        """Log a snooze action."""
        await self.db.execute(
            "INSERT INTO snooze_log (reminder_id, duration_minutes) VALUES (?, ?)",
            (reminder_id, duration_minutes),
        )
        await self.db.commit()

    # Helper methods

    def _row_to_reminder(self, row: aiosqlite.Row) -> Reminder:
        """Convert a database row to a Reminder object."""
        return Reminder(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            amount=row["amount"],
            currency=row["currency"],
            category_id=row["category_id"],
            due_at=datetime.fromisoformat(row["due_at"]),
            is_recurring=bool(row["is_recurring"]),
            rrule=row["rrule"],
            escalation_profile=row["escalation_profile"],
            custom_escalation=row["custom_escalation"],
            status=row["status"],  # type: ignore
            next_nag_at=datetime.fromisoformat(row["next_nag_at"])
            if row["next_nag_at"]
            else None,
            snoozed_until=datetime.fromisoformat(row["snoozed_until"])
            if row["snoozed_until"]
            else None,
            last_nagged_at=datetime.fromisoformat(row["last_nagged_at"])
            if row["last_nagged_at"]
            else None,
            nag_count=row["nag_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
