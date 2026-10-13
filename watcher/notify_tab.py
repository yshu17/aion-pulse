"""SN-5: the notification settings — a compact block of the «Настройки» card (moved from its own tab on 13.10, user
decision); a thin screen over watcher.notify_settings (the rules live there)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from watcher.notify_settings import CORNERS, DURATIONS, SOURCES, STACK

SHORT = {"chat": "Чат", "status": "Игра не запущена", "schedule": "Расписание"}


class NotifyPanel(ttk.Frame):
    """Two rows: each source — «show» and «звук»; then place, duration, stack and «Не беспокоить». Writes the
    ``notify_*`` fields of ``cfg`` and calls ``on_change()`` after every change."""

    def __init__(self, master: tk.Misc, cfg, on_change: Callable[[], None]) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.cfg, self.on_change = cfg, on_change
        sources = ttk.Frame(self, style="Surface.TFrame")
        sources.pack(fill="x")
        self.show_vars: dict[str, tk.BooleanVar] = {}
        self.sound_vars: dict[str, tk.BooleanVar] = {}
        for index, (source, label) in enumerate(SOURCES):
            show = tk.BooleanVar(value=source not in cfg.notify_off)
            sound = tk.BooleanVar(value=source not in cfg.notify_mute)
            self.show_vars[source], self.sound_vars[source] = show, sound
            check = ttk.Checkbutton(sources, text=SHORT.get(source, label), variable=show,
                                    style="CardPlain.TCheckbutton", command=self.changed)
            check.pack(side="left", padx=(0 if index == 0 else 18, 0))
            ttk.Checkbutton(sources, text="звук", variable=sound, style="CardPlain.TCheckbutton",
                            command=self.changed).pack(side="left", padx=(6, 0))

        view = ttk.Frame(self, style="Surface.TFrame")
        view.pack(fill="x", pady=(6, 0))
        self.corner_var = tk.StringVar(value=CORNERS.get(cfg.notify_corner, CORNERS["bottom"]))
        self.duration_var = tk.StringVar(value=f"{cfg.notify_duration if cfg.notify_duration in DURATIONS else 8} с")
        self.stack_var = tk.StringVar(value=str(cfg.notify_stack if cfg.notify_stack in STACK else 3))
        for index, (label, var, values, width) in enumerate((
                ("Где", self.corner_var, list(CORNERS.values()), 13),
                ("Держать", self.duration_var, [f"{d} с" for d in DURATIONS], 5),
                ("Сразу", self.stack_var, [str(n) for n in STACK], 3))):
            ttk.Label(view, text=label, style="CardMuted.TLabel").pack(side="left", padx=(0 if index == 0 else 18, 8))
            box = ttk.Combobox(view, textvariable=var, values=values, state="readonly", width=width,
                               style="Card.TCombobox")
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda _e: self.changed())
        self.dnd_var = tk.BooleanVar(value=cfg.notify_dnd)
        ttk.Checkbutton(view, text="Не беспокоить", variable=self.dnd_var, style="CardPlain.TCheckbutton",
                        command=self.changed).pack(side="left", padx=(18, 0))

    def changed(self) -> None:
        cfg = self.cfg
        cfg.notify_off = [s for s, _label in SOURCES if not self.show_vars[s].get()]
        cfg.notify_mute = [s for s, _label in SOURCES if not self.sound_vars[s].get()]
        cfg.notify_dnd = bool(self.dnd_var.get())
        cfg.notify_corner = next((key for key, label in CORNERS.items() if label == self.corner_var.get()), "bottom")
        cfg.notify_duration = int(self.duration_var.get().split()[0])
        cfg.notify_stack = int(self.stack_var.get())
        self.on_change()
