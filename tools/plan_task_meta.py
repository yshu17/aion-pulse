"""Shared add-time metadata for the interactive project plans."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[1]
META_PATH = ROOT / "docs" / "plan-task-meta.json"


def load_task_meta() -> dict:
    data = json.loads(META_PATH.read_text(encoding="utf-8"))
    if not isinstance(data.get("tasks"), dict):
        raise ValueError(f"Invalid task metadata in {META_PATH}")
    return data


def task_meta(data: dict, key: str) -> dict:
    """Return date and current-new state for a plan task key such as ``ui:42``."""
    info = data.get("tasks", {}).get(key, {})
    latest_day = data.get("tasks", {}).get(data.get("latest", ""), {}).get("added_at", "")[:10]
    added = info.get("added_at", "")
    return {
        "added_at": added,
        # added on the same day as the newest task: all of them are new, not only the very last one
        "is_latest": bool(latest_day) and added[:10] == latest_day,
    }


def register_new_tasks(keys: list[str]) -> bool:
    """Remember the existing catalogue, then date genuinely new IDs on later builds."""
    data = load_task_meta()
    current = set(keys)
    known = set(data.get("known_keys", []))
    if "known_keys" not in data:
        data["known_keys"] = sorted(current)
    else:
        new = current - known
        if not new:
            return False
        try:
            clock = datetime.now(ZoneInfo("Europe/Warsaw"))
        except ZoneInfoNotFoundError:
            # Windows Python often has no IANA tzdata; the project machine uses Europe/Warsaw.
            clock = datetime.now().astimezone()
        now = clock.strftime("%d.%m.%Y %H:%M")
        def order(key: str) -> tuple:
            plan, ident = key.split(":", 1)
            return (plan, tuple(int(n) for n in re.findall(r"\d+", ident)))
        for key in sorted(new, key=order):
            data.setdefault("tasks", {}).setdefault(key, {})["added_at"] = now
        data["latest"] = max(new, key=order)
        data["known_keys"] = sorted(known | current)
    META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


OLD_TASK_DATE = "08.10.2026"  # the date the user chose for tasks that have no recorded date (12.10.2026)


def remember_known(keys: list[str]) -> bool:
    """Add IDs to the known catalogue without dating them as new and without moving the NEW badge."""
    data = load_task_meta()
    known = set(data.get("known_keys", []))
    missing = set(keys) - known
    if not missing:
        return False
    data["known_keys"] = sorted(known | missing)
    META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def backfill_dates(dates: dict[str, tuple[str, str]]) -> bool:
    """Record a date for tasks that have none. dates maps key -> (date text, where it comes from).
    The old tasks get OLD_TASK_DATE (the user's decision); draft stages get their file's date."""
    data = load_task_meta()
    tasks = data.setdefault("tasks", {})
    touched = False
    for key, (date_text, origin_note) in dates.items():
        info = tasks.setdefault(key, {})
        if not info.get("added_at"):
            info["added_at"] = date_text
            info.setdefault("history", []).append({
                "at": "2026-10-12T00:00+02:00", "event": origin_note, "origin": "decision"})
            touched = True
    if touched:
        META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return touched


def register_source_changes(items: list[dict]) -> bool:
    """Date later source edits, without claiming a date for historical content."""
    data = load_task_meta()
    hashes = data.get("source_hashes", {})
    updated = "source_hashes" not in data
    for item in items:
        key = item["key"]
        source = {field: item.get(field) for field in ("title", "text", "status", "who", "priority",
                                                       "dependencies_text", "parent", "depends_on")}
        digest = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if key in hashes and hashes[key] != digest:
            try:
                clock = datetime.now(ZoneInfo("Europe/Warsaw"))
            except ZoneInfoNotFoundError:
                clock = datetime.now().astimezone()
            info = data.setdefault("tasks", {}).setdefault(key, {})
            info["changed_at"] = clock.strftime("%d.%m.%Y %H:%M")
            info.setdefault("history", []).append({"at": clock.isoformat(timespec="minutes"),
                                                    "event": "Изменено в исходном плане", "origin": "source"})
            updated = True
        if key not in hashes:
            updated = True
        hashes[key] = digest
    if updated:
        data["source_hashes"] = hashes
        META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    return False
