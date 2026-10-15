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


def kind_of(event: dict) -> str:
    """SN-7: the event's kind for the filter («Арены» groups the arena brackets); without one, its own name."""
    return event.get("kind") or event["name"]


def kinds(events: list[dict]) -> list[str]:
    """Each kind once, in the order of the data."""
    return list(dict.fromkeys(kind_of(event) for event in events))


def visible(events: list[dict], hidden: set[str]) -> list[dict]:
    """The events whose kind is not hidden by the filter."""
    return [event for event in events if kind_of(event) not in hidden]


def map_for(event: dict, side: str) -> str | None:
    """SN-7 «На карте»: the zone map id of an event (field «maps»); of two zones, the one of the player's side —
    «dark» (Asmodians) prefers 220…, «light» (Elyos) 210…; None when the event has no place."""
    maps = event.get("maps") or []
    if not maps:
        return None
    prefix = "220" if side == "dark" else "210"
    return next((m for m in maps if m.startswith(prefix)), maps[0])


def _minutes(text: str) -> int:
    hour, minute = map(int, text.split(":"))
    return hour * 60 + minute


def day_blocks(events: list[dict]) -> list[tuple[dict, int, int, int]]:
    """Day strip: ``(event, start, end, lane)`` in minutes from midnight, sorted by start; an event that runs past
    midnight is cut at 1440; overlapping events go to the next free lane."""
    blocks: list[tuple[dict, int, int, int]] = []
    lane_ends: list[int] = []
    for event in sorted(events, key=lambda e: _minutes(e["start"])):
        start, end = _minutes(event["start"]), _minutes(event["end"])
        if end <= start:
            end = 1440
        lane = next((i for i, busy_until in enumerate(lane_ends) if busy_until <= start), len(lane_ends))
        if lane == len(lane_ends):
            lane_ends.append(end)
        else:
            lane_ends[lane] = end
        blocks.append((event, start, end, lane))
    return blocks


GROUPS = ("Дерадиконы", "PVP арена", "Арены Хаоса и Доблести", "Осады", "Прочее")  # menu order, as on the screenshot


def groups(events: list[dict]) -> list[str]:
    """The groups present in ``events``, in the menu order (Прочее goes last, «Свои» is the own events)."""
    present = {group_of(event) for event in events}
    known = [g for g in GROUPS if g in present]
    return known + sorted(present - set(GROUPS))  # the user's own groups after the known ones


def group_hidden(events: list[dict], hidden_groups: set[str]) -> list[dict]:
    """Events whose group is not hidden by the group filter."""
    return [event for event in events if group_of(event) not in hidden_groups]


def group_of(event: dict) -> str:
    """Section of the schedule for an event: its own «group» if the user set one, else by kind (or name)."""
    if event.get("group"):
        return event["group"]
    kind = kind_of(event)
    name = event["name"]
    if kind in ("Арены", "Арена"):
        return "Арены Хаоса и Доблести"
    if kind.startswith("PVP") or kind == "Potato":
        return "PVP арена"
    if "Осада" in name or "Осада" in kind:
        return "Осады"
    if name == "Дер" or "Дерадикон" in name:
        return "Дерадиконы"
    return "Прочее"


DAY_SHORT = {"mon": "ПН", "tue": "ВТ", "wed": "СР", "thu": "ЧТ", "fri": "ПТ", "sat": "СБ", "sun": "ВС"}


def day_label(day: str, now: datetime, today: datetime) -> str:
    """«Сегодня» for the current weekday, else «ВТ 13.10» — the date of that weekday in this week."""
    if day == DAY_SHORT_BY_INDEX[today.weekday()] and day == DAY_SHORT_BY_INDEX[now.weekday()]:
        return "Сегодня"
    monday = week_start(now)
    target = monday + timedelta(days=DAYS.index(day))
    return f"{DAY_SHORT[day]} {target:%d.%m}"


DAY_SHORT_BY_INDEX = dict(enumerate(DAYS))


def clock_pair(utc_now: datetime, local_tz) -> tuple[str, str]:
    """Server time (MSK, UTC+3) and this computer's time, both as HH:MM:SS."""
    from datetime import timezone as _tz
    msk = utc_now.astimezone(_tz(timedelta(hours=3)))
    local = utc_now.astimezone(local_tz)
    return f"{msk:%H:%M:%S}", f"{local:%H:%M:%S}"
