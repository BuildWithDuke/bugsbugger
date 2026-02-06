# BugsBugger - Implementation Plan

## Context

You missed a credit card payment while travelling and calendar widgets weren't persistent enough to prevent it. BugsBugger is a Telegram bot that **nags you with escalating frequency** about upcoming bills, deadlines, and events until you mark them done. It won't shut up until you pay attention.

**Decided stack**: Python + Telegram Bot + SQLite, deployed on a cheap VPS.

---

## Project Structure

```
bugsbugger/
├── bugsbugger/
│   ├── __init__.py
│   ├── main.py              # Entry point: wire up DB, handlers, heartbeat
│   ├── config.py             # Settings from env vars
│   ├── db/
│   │   ├── models.py         # Dataclasses: User, Reminder, EscalationTier
│   │   ├── schema.sql        # DDL for all tables
│   │   ├── repository.py     # All SQL queries (aiosqlite)
│   │   └── migrations.py     # Sequential migration runner
│   ├── bot/
│   │   ├── handlers.py       # Command handlers (/start, /help, /list, /quick, etc.)
│   │   ├── conversations.py  # ConversationHandlers (/add, /edit, /settings flows)
│   │   ├── keyboards.py      # Inline keyboard builders
│   │   ├── callbacks.py      # Button press handlers (done, snooze, confirm)
│   │   └── formatters.py     # Message text builders
│   ├── engine/
│   │   ├── nag_engine.py     # Heartbeat loop - the core nagger
│   │   ├── escalation.py     # Tier definitions + next-nag-time computation
│   │   └── recurrence.py     # RRULE-based next-occurrence calculator
│   ├── parser/
│   │   ├── nlp.py            # Regex pipeline: text -> ParsedReminder
│   │   ├── patterns.py       # Compiled regex patterns
│   │   └── normalizer.py     # Date/time normalization
│   └── utils/
│       ├── time_utils.py     # Timezone, quiet hours, duration formatting
│       └── constants.py      # Default tiers, category list, limits
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

**Why this separation**: `engine/` has zero Telegram imports (pure logic, easy to test). `bot/` has zero SQL imports. `parser/` is isolated for a clean swap to Claude API later. `db/` can be swapped to Postgres by only touching that package.

---

## Data Model (SQLite)

### Tables

- **`users`** - telegram_id, timezone, quiet_start/end, default_escalation_profile
- **`categories`** - per-user categories (seeded: bills, subscriptions, birthdays, goals, business_leads)
- **`reminders`** - the core table:
  - `title`, `description`, `amount`, `currency`, `category_id`
  - `due_at` (UTC ISO 8601)
  - `is_recurring`, `rrule` (iCalendar RRULE string via python-dateutil)
  - `escalation_profile`, `custom_escalation` (JSON override)
  - `status` (active | snoozed | done | archived | skipped)
  - **`next_nag_at`** - precomputed, indexed. This is the key field - the heartbeat query is just `WHERE next_nag_at <= now AND status = 'active'`
  - `snoozed_until`, `last_nagged_at`, `nag_count`
- **`nag_history`** - audit trail: reminder_id, sent_at, telegram message_id, escalation_tier
- **`snooze_log`** - tracks snooze behavior
- **`escalation_profiles`** - user-customizable tier sets stored as JSON

### Key Design Decisions
- **Timestamps**: UTC everywhere, convert on display using user's timezone
- **Recurring "done"**: Updates reminder in-place (new due_at, reset nag_count) rather than creating new rows. History preserved in nag_history.
- **RRULE format**: Industry standard, python-dateutil handles all computation. Examples: `FREQ=MONTHLY;BYMONTHDAY=1` (rent), `FREQ=YEARLY;BYMONTH=6;BYMONTHDAY=10` (birthday).

---

## Nag Engine (the heart of the app)

### Architecture: Single Heartbeat + Precomputed `next_nag_at`

Instead of scheduling one job per reminder (fragile, lost on restart), a **single heartbeat runs every 60 seconds** via python-telegram-bot's built-in JobQueue and queries the DB for due nags.

```
JobQueue (every 60s) -> heartbeat() -> query DB for next_nag_at <= now -> send messages -> compute & store next next_nag_at
```

### Default Escalation Profile ("standard")

| Tier | Trigger | Nag Interval |
|------|---------|-------------|
| gentle | 3-7 days before due | Once/day |
| moderate | 1-3 days before | Twice/day |
| urgent | Due day | Every 2 hours |
| critical | Due within the hour | Every 30 min |
| overdue | Past due | Every 15 min |

Users can override per-reminder or change their default profile. Additional built-in profiles: "gentle" (less aggressive) and "aggressive" (starts earlier, shorter intervals).

### Snooze Flow
1. Set `status = 'snoozed'`, `snoozed_until = now + duration`, `next_nag_at = snoozed_until`
2. Heartbeat picks it back up when snooze expires, resumes normal escalation

### Done Flow
1. Set `status = 'done'`, reset `nag_count`
2. If recurring: compute next occurrence via RRULE, update `due_at` in-place, set `status = 'active'`, compute new `next_nag_at`
3. Edit the original Telegram message to show strikethrough + checkmark

### Quiet Hours
- Configurable per user (default 23:00-07:00 local)
- If a nag would fire during quiet hours, `next_nag_at` is pushed to the quiet period end

### Startup Recovery
On boot, find all reminders with `next_nag_at` in the past and set them to `now` so the next heartbeat catches up immediately.

---

## Telegram Bot Commands & UX

| Command | Description |
|---------|-------------|
| `/start` | Welcome, create user |
| `/add` | Guided flow: title -> date -> recurrence -> category -> amount -> confirm |
| `/quick <text>` | Natural language add: `/quick rent due 1st every month $1500` |
| Plain text | Also parsed as natural language, with confirm/edit/cancel buttons |
| `/list` | All active reminders (paginated) |
| `/upcoming` | Dashboard: next 7 days, grouped |
| `/done <id>` | Mark done by ID |
| `/snooze <id> [duration]` | Snooze by ID |
| `/edit <id>` | Edit flow |
| `/delete <id>` | Delete with confirmation |
| `/settings` | Timezone, quiet hours, default escalation |
| `/stats` | Nag count, completion rate |

### Nag Message Buttons
Each nag has inline buttons:
```
[ Done ]  [ Snooze 1h ]  [ Snooze 1d ]  [ Snooze... ]
```

### Confirmation Card (after NL parse)
Shows parsed reminder details with: `[ Confirm ]  [ Edit ]  [ Cancel ]`

---

## Natural Language Parser

Regex pipeline that extracts components in order:

1. **Amount**: `$1500`, `1,500.00`, `USD 200`
2. **Date**: `march 15`, `tomorrow`, `1st`, `in 3 days`
3. **Recurrence**: `every month`, `weekly`, `every 2 weeks`, `annually`
4. **Category**: keyword matching (rent -> bills, netflix -> subscriptions, birthday -> birthdays)
5. **Title**: whatever remains after extraction, cleaned up

Returns a `ParsedReminder` dataclass with a confidence score.

**Claude API upgrade path**: Same function signature in `parser/claude_parser.py`, toggled via `PARSER_BACKEND` env var. No other module changes.

---

## Dependencies

```
python-telegram-bot[job-queue]>=22.0
aiosqlite>=0.20.0
python-dateutil>=2.9.0
```

Dev: pytest, pytest-asyncio, ruff, mypy

---

## Deployment

- **Docker** (preferred): Single container, SQLite volume mount, `docker-compose up -d`
- **Fallback**: systemd service on bare VPS with a venv
- **Backups**: Daily cron copying the SQLite file
- **Health**: Log uptime on startup, structured JSON logging

---

## Phased Build Order

### Phase 1: Foundation
Bot starts, responds to commands, stores data in SQLite. No nagging yet.

1. `pyproject.toml` + project scaffolding
2. `config.py` - settings from env
3. `db/schema.sql` + `migrations.py` - create tables on first run
4. `db/models.py` - dataclasses
5. `db/repository.py` - CRUD for users and reminders
6. `main.py` - wire up Application, register handlers, init DB
7. `bot/handlers.py` - `/start`, `/help`
8. `bot/conversations.py` - `/add` guided flow
9. `bot/keyboards.py` + `bot/formatters.py` - basic UI

**Checkpoint**: `/start` the bot, `/add` a reminder, `/list` to see it, `/done` to complete it.

### Phase 2: Nag Engine
The bot actively bugs you.

1. `engine/escalation.py` - tier logic, `compute_next_nag_time()`
2. `engine/nag_engine.py` - heartbeat, startup recovery
3. Wire heartbeat into `main.py` via JobQueue
4. Nag keyboard (done/snooze buttons) + `bot/callbacks.py`
5. Snooze operations in repository
6. Quiet hours in `utils/time_utils.py`

**Checkpoint**: Add a reminder due in 5 minutes. Watch it escalate. Snooze it. Mark done. Test quiet hours. Test restart recovery.

### Phase 3: Natural Language + Recurrence
Add reminders naturally, recurring reminders roll forward.

1. `parser/patterns.py` - all regex
2. `parser/normalizer.py` + `parser/nlp.py` - the pipeline
3. `/quick` command + plain-text handler with confirmation flow
4. `engine/recurrence.py` - RRULE next-occurrence
5. Integrate recurrence into done flow
6. Parser tests (many edge cases)

**Checkpoint**: "rent due 1st every month $1500" parses correctly. Mark done, verify it rolls to next month.

### Phase 4: Polish
Full feature set, good UX.

1. Category management
2. `/upcoming` dashboard
3. `/edit` flow
4. `/settings` flow (timezone, quiet hours, escalation)
5. `/stats` command
6. Paginated `/list`
7. Edit old nag messages on done/snooze
8. Error handling + user-facing messages

### Phase 5: Deployment
1. Dockerfile + docker-compose.yml
2. Logging, health checks
3. SQLite backup cron
4. Rate limiting (safety valve)
5. Graceful shutdown
6. `.env.example`

---

## Verification

After each phase, test end-to-end by chatting with the bot on Telegram:
- **Phase 1**: Add, list, complete reminders via commands
- **Phase 2**: Set a reminder 5 min out, watch nags arrive, snooze, complete, verify quiet hours
- **Phase 3**: Send natural language like "credit card payment $500 due 15th every month", verify parsing and recurrence
- **Phase 4**: Test all commands, settings changes, dashboard accuracy
- **Phase 5**: `docker-compose up`, verify it runs, kill and restart, verify recovery

Run `pytest` after each phase. Key test areas: escalation timing, RRULE computation, parser edge cases, snooze/done state transitions.
