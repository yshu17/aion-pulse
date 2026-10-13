"""SN-5: the «Уведомления» tab — a thin screen over watcher.notify_settings (the rules live there)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from watcher.notify_settings import CORNERS, DURATIONS, SOURCES, STACK


class NotifyTab(ttk.Frame):
    """Writes the ``notify_*`` fields of ``cfg`` and calls ``on_change()`` after every change; ``on_test()`` shows a
    sample toast."""

    def __init__(self, master: tk.Misc, cfg, on_change: Callable[[], None], on_test: Callable[[], None]) -> None:
        super().__init__(master, padding=(0, 12, 0, 0))
        self.cfg, self.on_change = cfg, on_change
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 12))
        card.pack(fill="x", anchor="n")
        ttk.Label(card, text="Что показывать", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(card, text="Звук", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w", padx=(24, 0))
        self.show_vars: dict[str, tk.BooleanVar] = {}
        self.sound_vars: dict[str, tk.BooleanVar] = {}
        for row, (source, label) in enumerate(SOURCES, start=1):
            show = tk.BooleanVar(value=source not in cfg.notify_off)
            sound = tk.BooleanVar(value=source not in cfg.notify_mute)
            self.show_vars[source], self.sound_vars[source] = show, sound
            ttk.Checkbutton(card, text=label, variable=show, style="CardPlain.TCheckbutton",
                            command=self.changed).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Checkbutton(card, variable=sound, style="CardPlain.TCheckbutton",
                            command=self.changed).grid(row=row, column=1, sticky="w", padx=(24, 0))

        view = ttk.Frame(self, style="Card.TFrame", padding=(16, 12))
        view.pack(fill="x", anchor="n", pady=(10, 0))
        ttk.Label(view, text="Карточки", style="Title.TLabel").grid(row=0, column=0, columnspan=4, sticky="w",
                                                                  pady=(0, 8))
        self.corner_var = tk.StringVar(value=CORNERS.get(cfg.notify_corner, CORNERS["bottom"]))
        self.duration_var = tk.StringVar(value=f"{cfg.notify_duration if cfg.notify_duration in DURATIONS else 8} с")
        self.stack_var = tk.StringVar(value=str(cfg.notify_stack if cfg.notify_stack in STACK else 3))
        for column, (label, var, values, width) in enumerate((
                ("Где", self.corner_var, list(CORNERS.values()), 14),
                ("Сколько держать", self.duration_var, [f"{d} с" for d in DURATIONS], 6),
                ("Сразу на экране", self.stack_var, [str(n) for n in STACK], 3))):
            ttk.Label(view, text=label, style="CardMuted.TLabel").grid(row=1, column=column, sticky="w",
                                                                      padx=(0 if column == 0 else 20, 0))
            box = ttk.Combobox(view, textvariable=var, values=values, state="readonly", width=width,
                               style="Card.TCombobox")
            box.grid(row=2, column=column, sticky="w", padx=(0 if column == 0 else 20, 0), pady=(4, 0))
            box.bind("<<ComboboxSelected>>", lambda _e: self.changed())
        self.dnd_var = tk.BooleanVar(value=cfg.notify_dnd)
        ttk.Checkbutton(view, text="Не беспокоить — копить, но не показывать", variable=self.dnd_var,
                        style="CardPlain.TCheckbutton", command=self.changed).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.test_button = ttk.Button(view, text="Проверить", style="Card.TButton", command=on_test)
        self.test_button.grid(row=3, column=3, sticky="e", padx=(20, 0), pady=(10, 0))

    def changed(self) -> None:
        cfg = self.cfg
        cfg.notify_off = [s for s, _label in SOURCES if not self.show_vars[s].get()]
        cfg.notify_mute = [s for s, _label in SOURCES if not self.sound_vars[s].get()]
        cfg.notify_dnd = bool(self.dnd_var.get())
        cfg.notify_corner = next((key for key, label in CORNERS.items() if label == self.corner_var.get()), "bottom")
        cfg.notify_duration = int(self.duration_var.get().split()[0])
        cfg.notify_stack = int(self.stack_var.get())
        self.on_change()
