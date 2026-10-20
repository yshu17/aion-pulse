"""SN-7: the user's own schedule changes, kept apart from data/schedule.json (the server's grid stays untouched).

Tk-free core (PAIR.md rule 17). File ``schedule_custom.json`` next to config.json::

    {"added": [{"day": "fri", "start": "19:30", "end": "20:30", "name": "Рейд"}], "removed": ["mon|02:00|Дер"]}

* ``Custom.load(path)`` / ``save()`` — a missing or broken file means no changes;
* ``merge(base)`` — the data events minus the removed ones, plus the added ones (kind «Свои»);
* ``add``, ``remove``, ``edit(old, new)`` — save at once; removing an own event drops it, removing a data event
  hides it by its key ``day|start|name`` (``event_key``);
* ``check(event)`` — "" when the event is valid, else what to fix (in Russian, for the form).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from core.schedule.reminders import DAYS

OWN_KIND = "Свои"
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def event_key(event: dict) -> str:
    return f"{event['day']}|{event['start']}|{event['name']}"


def check(event: dict) -> str:
    if event.get("day") not in DAYS:
        return "Выбери день недели."
    if not _TIME.match(event.get("start", "")) or not (_TIME.match(event.get("end", "")) or event.get("end") == "24:00"):
        return "Укажи время как ЧЧ:ММ, например 19:30."
    if not str(event.get("name", "")).strip():
        return "Укажи название события."
    return ""


class Custom:
    def __init__(self, path: Path | None, data: dict | None = None) -> None:
        self.path = path
        self.data = data or {"added": [], "removed": []}

    @classmethod
    def load(cls, path: Path) -> "Custom":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            added, removed = data.get("added", []), data.get("removed", [])
            if not (isinstance(added, list) and isinstance(removed, list)
                    and all(isinstance(e, dict) and not check(e) for e in added)
                    and all(isinstance(k, str) for k in removed)):
                raise ValueError("unexpected schedule_custom.json")
            added = list({event_key(e): e for e in added}.values())  # old duplicates collapse, the last one wins
            return cls(path, {"added": added, "removed": removed})
        except (OSError, ValueError, AttributeError):
            return cls(path)

    def save(self) -> None:
        if self.path is None:
            return
        tmp = Path(self.path).with_name(Path(self.path).name + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def merge(self, base: list[dict]) -> list[dict]:
        removed = set(self.data["removed"])
        added_keys = {event_key(event) for event in self.data["added"]}  # an own copy replaces the server event
        kept = [event for event in base if event_key(event) not in removed and event_key(event) not in added_keys]
        return kept + [{**event, "kind": OWN_KIND} for event in self.data["added"]]

    def add(self, event: dict) -> None:
        clean = {key: event[key] for key in ("day", "start", "end", "name")}
        clean.update({key: event[key] for key in ("group", "color") if event.get(key)})  # optional, set in the form
        clean["name"] = clean["name"].strip()
        key = event_key(clean)  # the same day, start and name: replace, never duplicate
        self.data["added"] = [e for e in self.data["added"] if event_key(e) != key] + [clean]
        self.save()

    def add_days(self, event: dict, days: list[str]) -> None:
        """One event on several weekdays («на все дни»): saved as one entry per day."""
        for day in days:
            self.add({**event, "day": day})

    def remove(self, event: dict) -> None:
        key = event_key(event)
        own = [e for e in self.data["added"] if event_key(e) == key]
        if own:
            self.data["added"] = [e for e in self.data["added"] if event_key(e) != key]
        elif key not in self.data["removed"]:
            self.data["removed"].append(key)
        self.save()

    def edit(self, old: dict, new: dict) -> None:
        self.remove(old)
        self.add(new)


DAY_BY_RU = {"пн": "mon", "вт": "tue", "ср": "wed", "чт": "thu", "пт": "fri", "сб": "sat", "вс": "sun"}
DAY_RU = {v: k for k, v in DAY_BY_RU.items()}
_LINE = re.compile(r"^\s*(пн|вт|ср|чт|пт|сб|вс)\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s+(.+?)\s*$", re.I)


def to_text(events: list[dict]) -> str:
    """Every event as a text line: «пн 20:00-21:00 Название», Monday first, times as in the data."""
    order = {d: i for i, d in enumerate(DAYS)}
    lines = [f"{DAY_RU[e['day']]} {e['start']}-{e['end']} {e['name']}"
             for e in sorted(events, key=lambda e: (order.get(e["day"], 9), e["start"]))]
    return "\n".join(lines)


def parse_text(text: str) -> tuple[list[dict], list[str]]:
    """Text lines back to events; returns (events, problems) — a bad line is reported, not dropped silently."""
    events, problems = [], []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = _LINE.match(line)
        if not match:
            problems.append(f"строка {number}: нужен вид «пн 20:00-21:00 Название»")
            continue
        event = {"day": DAY_BY_RU[match.group(1).lower()], "start": match.group(2), "end": match.group(3),
                 "name": match.group(4)}
        problem = check(event)
        if problem:
            problems.append(f"строка {number}: {problem}")
        else:
            events.append(event)
    return events, problems
