"""Make the schedule the user has set up the shared one: merge schedule_custom.json into data/schedule.json.

    python tools/export_schedule.py

The merged events (server grid + own events, removals, groups and colours) are written to data/schedule.json, which is
bundled into the exe, so every user gets this schedule. schedule_custom.json is moved to tmp/ and emptied, so the
events are not applied twice. Other fields of data/schedule.json (resets, commands, arena_daily) stay as they are.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.schedule.schedule_custom import Custom  # noqa: E402

DATA = ROOT / "data" / "schedule.json"
CUSTOM = ROOT / "schedule_custom.json"
BACKUP = ROOT / "tmp" / "schedule_custom_before_export.json"


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    custom = Custom.load(CUSTOM)
    merged = custom.merge(data["events"])
    for event in merged:  # every event needs a kind (the tests and the strip's colours use it)
        if event.get("kind") in (None, "Свои"):
            event["kind"] = event.get("group") or event["name"]
    before = len(data["events"])
    data["events"] = merged
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if CUSTOM.exists():
        BACKUP.parent.mkdir(exist_ok=True)
        shutil.copyfile(CUSTOM, BACKUP)
    Custom(CUSTOM).save()  # empty file: no own changes left to apply on top
    print(f"events: {before} -> {len(merged)}; custom backup: {BACKUP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
