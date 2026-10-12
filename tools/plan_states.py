"""One vocabulary for task statuses and priorities, read by the generators and by the shared Task Card.

Statuses (decided by the user on 12.10.2026):
  planned   Запланировано   default for an open task
  research  Исследование    investigation before a decision (drafts start here)
  doing     В работе
  blocked   Заблокировано   waiting for something named in the task
  review    На проверке     work is finished, the user has not ticked it yet
  done      Выполнено       only by the checkbox: a ticked task is done, a done task is ticked
  deferred  Отложено
  cancelled Отменено        not done and not counted in progress

Legacy values from earlier data and browser ledgers: "todo" means "planned".
"""

from __future__ import annotations

STATES = [
    ("planned", "Запланировано", "#8c919c"),
    ("research", "Исследование", "#4aa3ff"),
    ("doing", "В работе", "#ff8c1a"),
    ("blocked", "Заблокировано", "#e5484d"),
    ("review", "На проверке", "#f5b544"),
    ("done", "Выполнено", "#5fd38d"),
    ("deferred", "Отложено", "#a58fd6"),
    ("cancelled", "Отменено", "#6b7080"),
]
STATE_KEYS = [key for key, _label, _color in STATES]
LABELS = {key: label for key, label, _color in STATES}
COLORS = {key: color for key, _label, color in STATES}

LEGACY_STATUS = {"todo": "planned"}
PRIORITIES = ["Critical", "High", "Medium", "Low"]  # order of the filter and of the cards
LEGACY_PRIORITY = {"P0": "Critical", "P1": "High", "P2": "Medium", "P3": "Low"}
NOT_SET = "Не определён"


def normalize_status(value: str | None) -> str:
    """Map a stored status to the vocabulary. Unknown or empty values become planned, never done."""
    value = LEGACY_STATUS.get(value or "", value or "")
    return value if value in LABELS else "planned"


def normalize_priority(value: str | None) -> str:
    """P0–P3 become Critical–Low. Empty stays empty: it is shown as NOT_SET and never guessed."""
    if not value:
        return ""
    return LEGACY_PRIORITY.get(value, value if value in PRIORITIES else "")


def priority_label(value: str | None) -> str:
    return value or NOT_SET


def native_status(value: str) -> str:
    """Value for the plans' own (older) status lists, which know only todo / doing / done."""
    if value == "doing":
        return "doing"
    if value == "done":
        return "done"
    return "todo"


def status_after_checkbox(current: str, checked: bool) -> str:
    """A ticked task is done. Unticking a done task sends it to review (the work is there, the acceptance is not)."""
    if checked:
        return "done"
    return "review" if normalize_status(current) == "done" else normalize_status(current)


def progress(statuses: list[str]) -> dict:
    """Counts from the statuses of unique tasks. Cancelled tasks leave the total; nothing is invented."""
    counted = [normalize_status(s) for s in statuses]
    total = [s for s in counted if s != "cancelled"]
    done = sum(1 for s in total if s == "done")
    return {
        "total": len(total),
        "done": done,
        "percent": round(100 * done / len(total)) if total else 0,
        "active": sum(1 for s in total if s in ("doing", "research", "review")),
        "blocked": sum(1 for s in total if s == "blocked"),
        "by_status": {key: sum(1 for s in counted if s == key) for key in STATE_KEYS},
    }
