"""Right-hand card of the «Карта» tab: the selected point and the nearest useful points («Рядом»)."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from core.text import metres_text  # noqa: F401  (kept importable from here)
from watcher import theme

EMPTY = "Кликни по значку на карте или найди точку поиском — здесь появится карточка и что рядом"
NEARBY_TYPES = ["teleport", "bindstone", "warehouse", "merchant", "stigma", "artifact"]


class PointCard(ttk.Frame):
    def __init__(self, parent: tk.Misc, get_icon: Callable[[str], object]) -> None:
        super().__init__(parent, style="Card.TFrame", padding=(14, 12))
        self.get_icon = get_icon
        self.kind = ttk.Label(self, text="", style="CardMuted.TLabel")
        self.kind.pack(anchor="w")
        self.title = ttk.Label(self, text=EMPTY, style="CardMuted.TLabel", wraplength=230)
        self.title.pack(anchor="w", pady=(2, 0))
        self.coords = ttk.Label(self, text="", style="CardMuted.TLabel")
        self.coords.pack(anchor="w", pady=(2, 0))
        self.note = ttk.Label(self, text="", style="CardMuted.TLabel", wraplength=230, justify="left")
        self.note.pack(anchor="w", pady=(6, 0))
        self.near_title = ttk.Label(self, text="", style="Title.TLabel")
        self.near_title.pack(anchor="w", pady=(14, 4))
        self.near = ttk.Frame(self, style="Surface.TFrame")
        self.near.pack(fill="x")
        self.rows: list[tuple[str, str, float]] = []  # (type, name, metres) — for tests

    def show(
        self,
        kind: str,
        title: str,
        gx: float,
        gy: float,
        note: str,
        nearby: list[tuple[str, str, str, float, Callable[[], None]]],
    ) -> None:
        """nearby: (type, type name, point name, metres, on_click)."""
        self.kind.configure(text=kind)
        self.title.configure(text=title or kind, style="Title.TLabel")
        self.coords.configure(text=f"x {gx:.0f} · y {gy:.0f}")
        self.note.configure(text=note)
        self.near_title.configure(text="Рядом" if nearby else "")
        for child in self.near.winfo_children():
            child.destroy()
        self.rows = []
        for type_, type_name, name, metres, on_click in nearby:
            row = tk.Frame(self.near, background=theme.SURFACE, cursor="hand2")
            row.pack(fill="x", pady=2)
            icon = self.get_icon(type_)
            label = tk.Label(row, image=icon or "", text=f"  {name or type_name}", compound="left",
                             anchor="w", background=theme.SURFACE, foreground=theme.TEXT,
                             font=theme.font("caption"))
            label.pack(side="left", fill="x", expand=True)
            dist = tk.Label(row, text=metres_text(metres), background=theme.SURFACE, foreground=theme.MUTED,
                            font=theme.font("small"))
            dist.pack(side="right")
            for widget in (row, label, dist):
                widget.bind("<Button-1>", lambda _e, f=on_click: f())
                widget.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
                widget.bind("<Leave>", lambda _e, r=row: self._hover(r, False))
            self.rows.append((type_, name, metres))

    def clear(self) -> None:
        self.kind.configure(text="")
        self.title.configure(text=EMPTY, style="CardMuted.TLabel")
        self.coords.configure(text="")
        self.note.configure(text="")
        self.near_title.configure(text="")
        for child in self.near.winfo_children():
            child.destroy()
        self.rows = []

    @staticmethod
    def _hover(row: tk.Frame, on: bool) -> None:
        color = theme.SURFACE_2 if on else theme.SURFACE
        row.configure(background=color)
        for child in row.winfo_children():
            child.configure(background=color)
