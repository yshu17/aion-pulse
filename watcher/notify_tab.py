"""SN-5: the notification settings — a compact block of the «Настройки» card (moved from its own tab on 13.10, user
decision); a thin screen over core.notify.notify_settings (the rules live there)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from watcher import theme
from core.notify.notify_settings import CORNERS, DURATIONS, SOURCES, STACK

SHORT = {"chat": "Чат", "status": "Игра не запущена", "schedule": "Расписание"}


class NotifyPanel(ttk.Frame):
    """Two rows: each source — «show» and «звук»; then place, duration, stack and «Не беспокоить». Writes the
    ``notify_*`` fields of ``cfg`` and calls ``on_change()`` after every change."""

    def __init__(self, master: tk.Misc, cfg, on_change: Callable[[], None]) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.cfg, self.on_change = cfg, on_change
        # left group «О чём и со звуком или нет», right group «Как показывать карточку»
        what = ttk.Frame(self, style="Surface.TFrame")
        what.grid(row=0, column=0, sticky="nw")
        ttk.Label(what, text="О чём уведомлять", style="CardMuted.TLabel", font=theme.font("caption_strong")).grid(
            row=0, column=0, sticky="w")
        ttk.Label(what, text="Показать", style="CardMuted.TLabel").grid(row=0, column=1, padx=(14, 0))
        ttk.Label(what, text="Звук", style="CardMuted.TLabel").grid(row=0, column=2, padx=(14, 0))
        self.show_vars: dict[str, tk.BooleanVar] = {}
        self.sound_vars: dict[str, tk.BooleanVar] = {}
        for row, (source, label) in enumerate(SOURCES, start=1):
            show = tk.BooleanVar(value=source not in cfg.notify_off)
            sound = tk.BooleanVar(value=source not in cfg.notify_mute)
            self.show_vars[source], self.sound_vars[source] = show, sound
            ttk.Label(what, text=label, style="CardMuted.TLabel").grid(row=row, column=0, sticky="w")
            ttk.Checkbutton(what, variable=show, style="CardPlain.TCheckbutton", command=self.changed).grid(
                row=row, column=1, padx=(14, 0))
            ttk.Checkbutton(what, variable=sound, style="CardPlain.TCheckbutton", command=self.changed).grid(
                row=row, column=2, padx=(14, 0))

        how = ttk.Frame(self, style="Surface.TFrame")
        how.grid(row=0, column=1, sticky="nw", padx=(36, 0))
        ttk.Label(how, text="Как показывать", style="CardMuted.TLabel", font=theme.font("caption_strong")).grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.corner_var = tk.StringVar(value=CORNERS.get(cfg.notify_corner, CORNERS["bottom"]))
        self.duration_var = tk.StringVar(value=f"{cfg.notify_duration if cfg.notify_duration in DURATIONS else 8} с")
        self.stack_var = tk.StringVar(value=str(cfg.notify_stack if cfg.notify_stack in STACK else 3))
        for row, (label, var, values, width) in enumerate((
                ("Где на экране", self.corner_var, list(CORNERS.values()), 13),
                ("Сколько держать", self.duration_var, [f"{d} с" for d in DURATIONS], 5),
                ("Сколько сразу", self.stack_var, [str(n) for n in STACK], 3)), start=1):
            ttk.Label(how, text=label, style="CardMuted.TLabel").grid(row=row, column=0, sticky="w", pady=1)
            box = ttk.Combobox(how, textvariable=var, values=values, state="readonly", width=width,
                               style="Card.TCombobox")
            box.grid(row=row, column=1, padx=(10, 0), pady=1)
            box.bind("<<ComboboxSelected>>", lambda _e: self.changed())
        self.dnd_var = tk.BooleanVar(value=cfg.notify_dnd)
        ttk.Checkbutton(how, text="Не беспокоить (копить, не показывать)", variable=self.dnd_var,
                        style="CardPlain.TCheckbutton", command=self.changed).grid(row=4, column=0, columnspan=2,
                                                                                    sticky="w", pady=(4, 0))

    def changed(self) -> None:
        cfg = self.cfg
        cfg.notify_off = [s for s, _label in SOURCES if not self.show_vars[s].get()]
        cfg.notify_mute = [s for s, _label in SOURCES if not self.sound_vars[s].get()]
        cfg.notify_dnd = bool(self.dnd_var.get())
        cfg.notify_corner = next((key for key, label in CORNERS.items() if label == self.corner_var.get()), "bottom")
        cfg.notify_duration = int(self.duration_var.get().split()[0])
        cfg.notify_stack = int(self.stack_var.get())
        self.on_change()
