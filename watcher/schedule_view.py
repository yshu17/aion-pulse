"""Pure schedule views. Event times and naive ``now`` use the watcher's MSK clock."""

from __future__ import annotations

from datetime import datetime, timedelta

from .reminders import DAYS, starts_at, week_start


def events_for_day(events: list[dict], day: str) -> list[dict]:
    """Events starting on ``day``, ordered by their start time."""
    return sorted((event for event in events if event["day"] == day), key=lambda event: event["start"])


def today_events(events: list[dict], now: datetime) -> list[dict]:
    """Events whose listed start day is today in MSK."""
    return events_for_day(events, DAYS[now.weekday()])


def _end_at(event: dict, start: datetime) -> datetime:
    hour, minute = map(int, event["end"].split(":"))
    end = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hour, minutes=minute)
    if end < start:
        end += timedelta(days=1)
    return end


def next_events(events: list[dict], now: datetime, limit: int) -> list[tuple[dict, datetime]]:
    """Next weekly occurrences, including events running at ``now``.

    Each tuple contains the original event and its actual start datetime. The
    end is exclusive; an event ending exactly at ``now`` is no longer running.
    """
    if limit <= 0 or not events:
        return []

    base = week_start(now)
    found: list[tuple[dict, datetime]] = []
    week_offset = -1  # previous Sunday's overnight event can still be running on Monday
    while len(found) < limit:
        monday = base + timedelta(weeks=week_offset)
        for event in events:
            start = starts_at(event, monday)
            if start >= now or start <= now < _end_at(event, start):
                found.append((event, start))
        week_offset += 1
    return sorted(found, key=lambda item: item[1])[:limit]
