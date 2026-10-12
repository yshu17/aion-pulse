"""Schedule reminders: which events start soon and were not announced yet. Pure logic, no Tk.

Times in `events` are server time (MSK, the same clock the watcher uses). `now` is a naive datetime in that clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # datetime.weekday() order


def starts_at(event: dict, day_start: datetime) -> datetime:
    """Start of the event in the week that begins at day_start (a Monday, 00:00)."""
    hour, minute = map(int, event["start"].split(":"))
    return day_start + timedelta(days=DAYS.index(event["day"]), hours=hour, minutes=minute)


def week_start(now: datetime) -> datetime:
    """Monday 00:00 of the week that contains now."""
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def reminder_key(event: dict, at: datetime) -> str:
    """Stable id of one occurrence: the same event in the same week is announced once."""
    return f"{event['day']}|{event['start']}|{event['name']}|{at.isoformat()}"


def due_reminders(events: list[dict], now: datetime, lead_min: int, sent: set[str]) -> list[tuple[str, dict, datetime]]:
    """Events that start within lead_min minutes from now (not in the past), not yet in sent.

    Returns (key, event, start) tuples, earliest first. The caller stores the keys it has shown into sent.
    """
    if lead_min < 0:
        raise ValueError("lead_min must be >= 0")
    base = week_start(now)
    window_end = now + timedelta(minutes=lead_min)
    found = []
    for event in events:
        # an event can start later this week or, for a week-boundary case, last week (it is still running now)
        for shift in (-7, 0, 7):
            at = starts_at(event, base + timedelta(days=shift))
            if now <= at <= window_end:
                key = reminder_key(event, at)
                if key not in sent:
                    found.append((key, event, at))
    return sorted(found, key=lambda item: item[2])
