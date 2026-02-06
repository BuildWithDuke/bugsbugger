"""Statistics and analytics."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bugsbugger.db.repository import Repository


async def get_user_stats(repo: Repository, user_id: int) -> dict:
    """Get comprehensive user statistics.

    Returns:
        Dict with various statistics
    """
    stats = {}

    # Total reminders created
    all_reminders = await repo.get_reminders_by_user(user_id)
    stats['total_created'] = len(all_reminders)

    # Reminders by status
    active = [r for r in all_reminders if r.status == 'active']
    done = [r for r in all_reminders if r.status == 'done']
    snoozed = [r for r in all_reminders if r.status == 'snoozed']

    stats['active'] = len(active)
    stats['done'] = len(done)
    stats['snoozed'] = len(snoozed)

    # Completion rate
    if stats['total_created'] > 0:
        stats['completion_rate'] = (len(done) / stats['total_created']) * 100
    else:
        stats['completion_rate'] = 0.0

    # Total nags sent
    stats['total_nags'] = sum(r.nag_count for r in all_reminders)

    # Average nags per reminder
    if stats['total_created'] > 0:
        stats['avg_nags'] = stats['total_nags'] / stats['total_created']
    else:
        stats['avg_nags'] = 0.0

    # Most nagged reminder
    if all_reminders:
        most_nagged = max(all_reminders, key=lambda r: r.nag_count)
        stats['most_nagged'] = {
            'title': most_nagged.title,
            'count': most_nagged.nag_count
        }
    else:
        stats['most_nagged'] = None

    # Recurring vs one-time
    recurring = [r for r in all_reminders if r.is_recurring]
    stats['recurring'] = len(recurring)
    stats['one_time'] = len(all_reminders) - len(recurring)

    # Snooze statistics
    snooze_logs = []
    for reminder in all_reminders:
        logs = await repo.db.execute(
            "SELECT duration_minutes FROM snooze_log WHERE reminder_id = ?",
            (reminder.id,)
        )
        async with logs as cursor:
            rows = await cursor.fetchall()
            snooze_logs.extend([row[0] for row in rows])

    stats['total_snoozes'] = len(snooze_logs)
    if snooze_logs:
        stats['avg_snooze_minutes'] = sum(snooze_logs) / len(snooze_logs)
    else:
        stats['avg_snooze_minutes'] = 0.0

    # Overdue reminders
    now = datetime.now(ZoneInfo('UTC'))
    overdue = [r for r in active if r.due_at < now]
    stats['overdue'] = len(overdue)

    # Upcoming in next 7 days
    week_from_now = now + timedelta(days=7)
    upcoming = [r for r in active if now <= r.due_at <= week_from_now]
    stats['upcoming_week'] = len(upcoming)

    return stats


def format_stats_message(stats: dict) -> str:
    """Format statistics into a readable message."""
    lines = ["<b>📊 Your BugsBugger Statistics</b>\n"]

    # Overview
    lines.append("<b>📋 Overview</b>")
    lines.append(f"Total reminders created: {stats['total_created']}")
    lines.append(f"✓ Completed: {stats['done']}")
    lines.append(f"🔔 Active: {stats['active']}")
    lines.append(f"⏸ Snoozed: {stats['snoozed']}")
    lines.append(f"💥 Overdue: {stats['overdue']}")
    lines.append(f"📅 Upcoming (7 days): {stats['upcoming_week']}\n")

    # Performance
    lines.append("<b>🎯 Performance</b>")
    lines.append(f"Completion rate: {stats['completion_rate']:.1f}%")
    lines.append(f"Average nags per reminder: {stats['avg_nags']:.1f}\n")

    # Nagging stats
    lines.append("<b>🐰 Nagging Stats</b>")
    lines.append(f"Total nags sent: {stats['total_nags']}")
    if stats['most_nagged']:
        lines.append(
            f"Most nagged: <i>{stats['most_nagged']['title']}</i> "
            f"({stats['most_nagged']['count']} nags)"
        )
    lines.append("")

    # Snooze behavior
    if stats['total_snoozes'] > 0:
        lines.append("<b>⏸ Snooze Behavior</b>")
        lines.append(f"Total snoozes: {stats['total_snoozes']}")
        avg_hours = stats['avg_snooze_minutes'] / 60
        if avg_hours < 1:
            lines.append(f"Average snooze: {stats['avg_snooze_minutes']:.0f} minutes")
        else:
            lines.append(f"Average snooze: {avg_hours:.1f} hours")
        lines.append("")

    # Reminder types
    lines.append("<b>🔄 Reminder Types</b>")
    lines.append(f"🔁 Recurring: {stats['recurring']}")
    lines.append(f"1️⃣ One-time: {stats['one_time']}")

    return "\n".join(lines)
