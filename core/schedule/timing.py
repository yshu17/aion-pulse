"""Schedule time helpers: MSK server clock, local display, event ends, «через 40 мин», reminder keys.

Portable core. Event times in data/schedule.json are server time (MSK, UTC+3, no daylight saving); naive datetimes
here are MSK wall-clock times. `load_events(path)` reads the weekly events (a missing or broken file gives []).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.schedule.reminders import DAYS

MSK = timezone(timedelta(hours=3))
DAY_NAMES = {"mon": "Понедельник", "tue": "Вторник", "wed": "Среда", "thu": "Четверг", "fri": "Пятница",
             "sat": "Суббота", "sun": "Воскресенье"}
LEADS = {"5 мин": 5, "15 мин": 15, "30 мин": 30, "1 час": 60}  # SN-8: how early to remind (user choice 13.10)
DEFAULT_LEAD = 5


def load_events(path: Path) -> list[dict]:
    """The weekly events of data/schedule.json; a missing or broken file gives an empty schedule."""
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("events", []))
    except (OSError, ValueError, AttributeError):
        return []


def msk_now(now_utc: datetime | None = None) -> datetime:
    """Naive MSK wall-clock time, the clock the schedule is written in."""
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(MSK).replace(tzinfo=None)


def to_local(msk: datetime, tz: timezone | None = None) -> datetime:
    """An MSK wall-clock time in the computer's (or the given) time zone."""
    return msk.replace(tzinfo=MSK).astimezone(tz)


def end_of(event: dict, start: datetime) -> datetime:
    """The end of one occurrence; «24:00» and an end before the start roll over to the next day."""
    hour, minute = map(int, event["end"].split(":"))
    end = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hour, minutes=minute)
    return end if end > start else end + timedelta(days=1)


def until_text(start: datetime, end: datetime, now: datetime) -> str:
    """«идёт · ещё 25 мин», «через 40 мин», «через 3 ч 5 мин», «завтра» — all in MSK."""
    if start <= now < end:
        left = int((end - now).total_seconds() // 60)
        return f"идёт · ещё {_span(left)}"
    minutes = int((start - now).total_seconds() // 60)
    if minutes >= 24 * 60:
        return "через " + (f"{minutes // (24 * 60)} дн" if minutes >= 48 * 60 else "сутки")
    return f"через {_span(minutes)}"


def _span(minutes: int) -> str:
    minutes = max(minutes, 0)
    if minutes < 60:
        return f"{minutes} мин"
    hours, rest = divmod(minutes, 60)
    return f"{hours} ч {rest} мин" if rest else f"{hours} ч"


def zone_name(msk: datetime, tz: timezone | None = None) -> str:
    """«МСК» or «UTC+2» for the local zone at that moment (summer and winter time differ)."""
    offset = to_local(msk, tz).utcoffset() or timedelta(0)
    if offset == timedelta(hours=3):
        return "МСК"
    sign = "+" if offset >= timedelta(0) else "−"
    hours, rest = divmod(abs(int(offset.total_seconds())) // 60, 60)
    return f"UTC{sign}{hours}" + (f":{rest:02d}" if rest else "")


def bell_key(event: dict) -> str:
    """The saved id of a weekly event the user wants to be reminded of."""
    return f"{event['day']}|{event['start']}|{event['name']}"


def lead_label(minutes: int) -> str:
    return next((k for k, v in LEADS.items() if v == minutes), "5 мин")


def time_range(start: datetime, end: datetime, tz: timezone | None = None) -> str:
    """«20:00–21:00» in local time."""
    return f"{to_local(start, tz):%H:%M}–{to_local(end, tz):%H:%M}"


DAYS_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # the chips of the form, Monday first


def today_key(now: datetime) -> str:
    return DAYS[now.weekday()]
