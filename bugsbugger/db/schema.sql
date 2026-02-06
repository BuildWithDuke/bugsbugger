-- BugsBugger database schema

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    quiet_start TEXT NOT NULL DEFAULT '23:00',
    quiet_end TEXT NOT NULL DEFAULT '07:00',
    default_escalation_profile TEXT NOT NULL DEFAULT 'standard',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    amount REAL,
    currency TEXT,
    category_id INTEGER,
    due_at TEXT NOT NULL,  -- ISO 8601 UTC
    is_recurring INTEGER NOT NULL DEFAULT 0,
    rrule TEXT,  -- iCalendar RRULE format
    escalation_profile TEXT NOT NULL DEFAULT 'standard',
    custom_escalation TEXT,  -- JSON override
    status TEXT NOT NULL DEFAULT 'active',  -- active|snoozed|done|archived|skipped
    next_nag_at TEXT,  -- ISO 8601 UTC, precomputed
    snoozed_until TEXT,  -- ISO 8601 UTC
    last_nagged_at TEXT,  -- ISO 8601 UTC
    nag_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_next_nag_at ON reminders(next_nag_at);
CREATE INDEX IF NOT EXISTS idx_reminders_due_at ON reminders(due_at);
-- Critical index for the heartbeat query
CREATE INDEX IF NOT EXISTS idx_reminders_heartbeat ON reminders(next_nag_at, status)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS nag_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    telegram_message_id INTEGER NOT NULL,
    escalation_tier TEXT NOT NULL,
    nag_count INTEGER NOT NULL,
    FOREIGN KEY (reminder_id) REFERENCES reminders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nag_history_reminder_id ON nag_history(reminder_id);
CREATE INDEX IF NOT EXISTS idx_nag_history_sent_at ON nag_history(sent_at);

CREATE TABLE IF NOT EXISTS snooze_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id INTEGER NOT NULL,
    snoozed_at TEXT NOT NULL DEFAULT (datetime('now')),
    duration_minutes INTEGER NOT NULL,
    FOREIGN KEY (reminder_id) REFERENCES reminders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snooze_log_reminder_id ON snooze_log(reminder_id);

-- Migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
