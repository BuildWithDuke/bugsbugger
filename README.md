# BugsBugger 🐰

> A Telegram bot that **won't shut up** about your bills and deadlines until you pay attention.

Ever missed a payment because calendar notifications are too easy to dismiss? BugsBugger is different. It nags you with **escalating frequency** until you mark tasks as done. No more missed deadlines.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

### 🔥 Escalating Nags
Not just reminders - **persistent nagging** that gets more aggressive as deadlines approach:
- **7 days before:** Once per day (gentle)
- **3 days before:** Twice per day (moderate)
- **Due day:** Every 2 hours (urgent)
- **Past due:** Every 15 minutes (you can't ignore this)

### 🗣️ Natural Language
Just type what you need:
```
rent due 1st every month $1500
credit card payment $500 due 15th
call mom tomorrow
gym every monday
```

The bot parses it, confirms what it understood, and creates the reminder.

### 🔁 Smart Recurrence
Recurring reminders automatically roll forward when marked done:
- `every day` / `weekly` / `monthly` / `yearly`
- `every 2 weeks` / `every monday` / `every 1st`
- Powered by iCalendar RRULE for reliable scheduling

### 🌍 Timezone Aware
- Set your timezone once, all times display correctly
- Quiet hours respect your sleep schedule
- International currency support

### ⚡ Quick Actions
Every nag message has buttons:
- **✓ Done** - Mark complete (or roll to next occurrence)
- **Snooze 1h / 1d** - Postpone the nagging
- **Custom snooze** - Your choice

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- A Telegram account
- 5 minutes

### Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/BuildWithDuke/bugsbugger.git
   cd bugsbugger
   ```

2. **Set up environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -e .
   ```

3. **Get a bot token**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow prompts
   - Copy your bot token

4. **Configure**
   ```bash
   cp .env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN
   ```

5. **Run**
   ```bash
   python -m bugsbugger.main
   ```

6. **Start chatting**
   - Find your bot on Telegram
   - Send `/start`
   - Create your first reminder!

## 📱 Usage

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Initialize bot | - |
| `/add` | Guided reminder creation | Multi-step flow |
| `/quick <text>` | Natural language add | `/quick rent due 1st $1500` |
| `/list` | Show all reminders | - |
| `/upcoming` | Next 7 days dashboard | - |
| `/done <id>` | Mark complete | `/done 5` |
| `/snooze <id> [mins]` | Postpone reminder | `/snooze 5 60` |
| `/delete <id>` | Delete reminder | `/delete 5` |
| `/settings` | View settings | - |
| `/timezone <tz>` | Set timezone | `/timezone America/Toronto` |
| `/quiet <start> <end>` | Set quiet hours | `/quiet 23:00 07:00` |
| `/help` | Show help | - |

### Plain Text Parsing

Just send a message and BugsBugger will parse it:

```
rent due 1st every month $1500
```

The bot will show you what it understood and ask for confirmation.

**Supported patterns:**
- **Amounts:** `$1500`, `500 USD`, `1,200.50`
- **Dates:** `tomorrow`, `15th`, `March 15`, `in 2 weeks`, `next monday`
- **Recurrence:** `every day/week/month/year`, `every monday`, `every 1st`
- **Categories:** Auto-detected (rent→bills, netflix→subscriptions, etc.)

## 🏗️ Architecture

### The Nag Engine
Instead of scheduling individual jobs per reminder, BugsBugger uses a **single heartbeat** that runs every 60 seconds:

```
┌─────────────────┐
│  Heartbeat Job  │  Runs every 60s
│   (JobQueue)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Query: next_nag_at <= now          │  Indexed query
│         AND status = 'active'       │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  For each due reminder:             │
│  1. Send nag message                │
│  2. Increment nag_count             │
│  3. Compute next_nag_at             │
│  4. Update database                 │
└─────────────────────────────────────┘
```

**Key advantages:**
- ✅ Survives restarts (startup recovery)
- ✅ Scales to thousands of reminders
- ✅ No job scheduling complexity
- ✅ Easy to test and debug

### Project Structure

```
bugsbugger/
├── db/              # Database layer (SQLite)
│   ├── models.py    # Dataclasses
│   ├── schema.sql   # DDL
│   ├── repository.py # All SQL queries
│   └── migrations.py
├── bot/             # Telegram interface
│   ├── handlers.py     # Command handlers
│   ├── conversations.py # Multi-step flows
│   ├── keyboards.py    # Button layouts
│   ├── callbacks.py    # Button handlers
│   └── formatters.py   # Message formatting
├── engine/          # Core nagging logic
│   ├── nag_engine.py   # Heartbeat + startup recovery
│   ├── escalation.py   # Tier selection + next-nag computation
│   └── recurrence.py   # RRULE handling
├── parser/          # Natural language
│   ├── nlp.py          # Main parser pipeline
│   ├── patterns.py     # Regex patterns
│   └── normalizer.py   # Date/time normalization
└── utils/
    ├── time_utils.py   # Timezone, quiet hours
    └── constants.py    # Escalation profiles, defaults
```

**Design Principles:**
- `engine/` has zero Telegram imports (pure logic, easy to test)
- `bot/` has zero SQL imports (clean separation)
- `parser/` is isolated (can swap to Claude API)
- `db/` can swap to Postgres by only touching that package

## 🔧 Configuration

### Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_token_here
DATABASE_PATH=./data/bugsbugger.db
LOG_LEVEL=INFO
HEARTBEAT_INTERVAL=60
PARSER_BACKEND=regex  # or "claude"
```

### Escalation Profiles

Three built-in profiles:

**Standard** (default) - Balanced nagging
- Gentle (7 days before): Once/day
- Moderate (3 days): Twice/day
- Urgent (1 day): Every 2 hours
- Critical (1 hour): Every 30 min
- Overdue: Every 15 min

**Gentle** - Less aggressive
- Longer intervals
- Starts closer to due date

**Aggressive** - More intense
- Starts 2 weeks early
- Shorter intervals
- Nags every 10 min when overdue

Change with: `/escalation gentle|standard|aggressive`

## 🧪 Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Check coverage
pytest --cov=bugsbugger tests/

# Lint
ruff check .
ruff format .
```

## 🐳 Deployment

### Docker

```bash
docker-compose up -d
```

The `docker-compose.yml` includes:
- SQLite volume for persistence
- Automatic restart on crash
- Environment variable injection

### Systemd Service

For bare-metal deployment:

```bash
sudo cp bugsbugger.service /etc/systemd/system/
sudo systemctl enable bugsbugger
sudo systemctl start bugsbugger
```

### Backups

Daily SQLite backups:
```bash
# Add to crontab
0 3 * * * cp /path/to/bugsbugger.db /backups/bugsbugger-$(date +\%Y\%m\%d).db
```

## 🛣️ Roadmap

- [ ] Web dashboard for viewing reminders
- [ ] Email notifications as backup
- [ ] Shared reminders (families, teams)
- [ ] Attachment support (bills, receipts)
- [ ] Analytics dashboard (completion rates, snooze patterns)
- [ ] Claude API parser for better NLP
- [ ] Voice message reminders
- [ ] Integration with calendar apps

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- Built with [python-telegram-bot](https://python-telegram-bot.org/)
- Recurrence powered by [python-dateutil](https://dateutil.readthedocs.io/)
- Inspired by missing one too many credit card payments

## 📬 Contact

Built by [@BuildWithDuke](https://github.com/BuildWithDuke)

Found a bug? [Open an issue](https://github.com/BuildWithDuke/bugsbugger/issues)

---

**Warning:** This bot is designed to be annoying. That's the point. Don't say we didn't warn you. 🐰
