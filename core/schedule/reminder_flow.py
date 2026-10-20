"""Reminders of belled schedule events: what to announce now, and what was missed while the program was closed.

    planner = ReminderPlanner()
    for r in planner.due(belled_events, now, lead_min, tz):   # call every ~30 s; each occurrence comes once
        notify(r.title, r.text)                               # «Через 5 мин: …» / «Началось: …»
    missed = missed_events(belled_events, last_check, now)    # [(event, start)], at most MISSED_DAYS back
    title, text = missed_text(missed, tz)

Times are naive MSK wall-clock datetimes (core.schedule.timing); `tz` is the zone the text shows them in.
Portable core: no timer, no notification, no file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.schedule.reminders import due_reminders, occurrences_between
from core.schedule.schedule_view import next_events
from core.schedule.timing import bell_key, end_of, lead_label, time_range, to_local

MISSED_DAYS = 7  # events missed while the program was closed are reported for at most a week back
START_WINDOW_S = 120  # «Началось» is said within this many seconds after the start
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


@dataclass(frozen=True)
class Reminder:
    key: str
    title: str
    text: str
    event: dict
    start: datetime
    end: datetime


class ReminderPlanner:
    def __init__(self) -> None:
        self.reminded: set[str] = set()  # occurrences already announced this run

    def due(self, belled: list[dict], now: datetime, lead_min: int, tz: timezone | None = None) -> list[Reminder]:
        """A reminder `lead_min` minutes before each belled event and one when it starts; each occurrence once."""
        out = []
        for key, event, start in due_reminders(belled, now, lead_min, self.reminded):
            if (start - now).total_seconds() < 60:
                continue  # the start reminder below covers it
            self.reminded.add(key)
            out.append(self._make(key, f"Через {lead_label(lead_min)}: {event['name']}", event, start, tz))
        for event, start in next_events(belled, now, len(belled) + 1):
            key = bell_key(event) + "|start|" + start.isoformat()
            if 0 <= (now - start).total_seconds() < START_WINDOW_S and key not in self.reminded:
                self.reminded.add(key)
                out.append(self._make(key, f"Началось: {event['name']}", event, start, tz))
        return out

    @staticmethod
    def _make(key: str, title: str, event: dict, start: datetime, tz: timezone | None) -> Reminder:
        end = end_of(event, start)
        return Reminder(key, title, f"{time_range(start, end, tz)} · расписание сервера", event, start, end)


def missed_events(belled: list[dict], last: datetime | None, now: datetime,
                  max_days: int = MISSED_DAYS) -> list[tuple[dict, datetime]]:
    """Belled events that started between the last check and now (no further back than `max_days`)."""
    if last is None:
        return []
    last = max(last, now - timedelta(days=max_days))
    return [(e, at) for e, at in occurrences_between(belled, last, now) if (now - at).total_seconds() >= START_WINDOW_S]


def missed_text(missed: list[tuple[dict, datetime]], tz: timezone | None = None, shown: int = 5) -> tuple[str, str]:
    """(title, text) of the «missed while closed» notification: up to `shown` events with weekday and local time."""
    names = [f"{e['name']} ({WEEKDAYS[at.weekday()]} {to_local(at, tz):%H:%M})" for e, at in missed[:shown]]
    more = f" и ещё {len(missed) - shown}" if len(missed) > shown else ""
    return f"Пропущено, пока программа была закрыта: {len(missed)}", ", ".join(names) + more
