"""A tab that is announced but not built yet: its name, what it will do, and a «в разработке» mark."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from watcher import theme
from watcher.ui_icons import IconSet

# (tab label, page title, what the tab will do); labels stay short: nine tabs must fit a 1000 px window
COMING_SOON = [
    ("Крафт", "Крафт", "Рецепты: из чего создаётся предмет, профессия и уровень мастерства, где взять ингредиенты."),
    ("Броня", "Калькулятор брони", "Подбор комплекта брони и сравнение характеристик предметов."),
    ("Стигмы", "Калькулятор стигм", "Сборка стигм персонажа: дерево стигм, слоты и итоговые умения."),
    ("Гайды", "Гайды", "Полезные гайды по игре: классы, подземелья, боссы и события сервера."),
]


class ComingSoonTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, label: str, title: str, description: str, icons_dir: Path) -> None:
        super().__init__(parent, style="Card.TFrame", padding=24)
        self.label, self.title = label, title
        box = tk.Frame(self, background=theme.SURFACE)
        box.place(relx=0.5, rely=0.42, anchor="center")
        self._icon = IconSet(self, icons_dir).get("hourglass-medium", "muted", 32)
        tk.Label(box, image=self._icon or "", background=theme.SURFACE).pack()
        tk.Label(box, text=title, background=theme.SURFACE, foreground=theme.TEXT,
                 font=theme.font("title")).pack(pady=(theme.SPACE[2], 0))
        tk.Label(box, text="В разработке · появится в одном из следующих обновлений", background=theme.SURFACE,
                 foreground=theme.ACCENT, font=theme.font("small")).pack(pady=(theme.SPACE[1], 0))
        self.description = tk.Label(box, text=description, background=theme.SURFACE, foreground=theme.MUTED,
                                    font=theme.font("caption"), wraplength=520, justify="center")
        self.description.pack(pady=(theme.SPACE[2], 0))
