"""SN-5: notification settings from config.json, applied to the notification center and the toast window.

Tk-free core (PAIR.md rule 17). ``apply(cfg, center, manager=None)`` reads the ``notify_*`` fields of ``Config``:

* ``notify_off`` — sources not shown at all, ``notify_mute`` — sources shown without sound (keys of ``SOURCES``);
* ``notify_dnd`` — «не беспокоить»: events are recorded, nothing pops up;
* ``notify_corner`` (``CORNERS``), ``notify_duration`` seconds (``DURATIONS``), ``notify_stack`` cards at once (1..3) —
  set on any object with ``corner``, ``duration`` and ``max_visible`` (the toast window); odd values fall back to defaults.
"""

from __future__ import annotations

SOURCES = (("chat", "Совпадения в чате"), ("status", "Игра не запущена"), ("schedule", "Напоминания расписания"))
CORNERS = {"bottom": "Справа снизу", "top": "Справа сверху"}
DURATIONS = (5, 8, 15)
STACK = (1, 2, 3)
DEFAULT_CORNER, DEFAULT_DURATION, DEFAULT_STACK = "bottom", 8, 3


def apply(cfg, center, manager=None) -> None:
    for source, _label in SOURCES:
        center.set_source(source, enabled=source not in cfg.notify_off, sound=source not in cfg.notify_mute)
    center.do_not_disturb = bool(cfg.notify_dnd)
    if manager is not None:
        manager.corner = cfg.notify_corner if cfg.notify_corner in CORNERS else DEFAULT_CORNER
        manager.duration = cfg.notify_duration if cfg.notify_duration in DURATIONS else DEFAULT_DURATION
        manager.max_visible = cfg.notify_stack if cfg.notify_stack in STACK else DEFAULT_STACK
