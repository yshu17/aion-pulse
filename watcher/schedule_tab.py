"""The «Расписание» tab (SN-7): what runs now and next, and the events of any weekday.

Event times in data/schedule.json are server time (MSK, UTC+3, no daylight saving). The logic of «what is next»
works in MSK (watcher/schedule_view.py); the tab shows every time in the computer's local time, as the data file asks.
"""

from __future__ import annotations

import json
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import ttk

from watcher import theme
from watcher.reminders import DAYS
from watcher.schedule_view import events_for_day, next_events

MSK = timezone(timedelta(hours=3))
DAY_NAMES = {"mon": "Понедельник", "tue": "Вторник", "wed": "Среда", "thu": "Четверг", "fri": "Пятница",
             "sat": "Суббота", "sun": "Воскресенье"}
NEXT_LIMIT = 8
REFRESH_MS = 30_000


def load_events(path: Path) -> list[dict]:
    """The weekly events of data/schedule.json; a missing or broken file gives an empty schedule."""
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("events", []))
    except (OSError, ValueError, AttributeError):
        return []


def msk_now(now_utc: datetime | None = None) -> datetime:
    """Naive MSK wall-clock time, the clock the schedule is written in."""
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(MSK).replace(tzinfo=None)


def to_local(msk: datetime, tz: timezone | None = None) -> datetime:
    """An MSK wall-clock time in the computer's (or the given) time zone."""
    return msk.replace(tzinfo=MSK).astimezone(tz)


def end_of(event: dict, start: datetime) -> datetime:
    """The end of one occurrence; «24:00» and an end before the start roll over to the next day."""
    hour, minute = map(int, event["end"].split(":"))
    end = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hour, minutes=minute)
    return end if end > start else end + timedelta(days=1)


def until_text(start: datetime, end: datetime, now: datetime) -> str:
    """«идёт · ещё 25 мин», «через 40 мин», «через 3 ч 5 мин», «завтра» — all in MSK."""
    if start <= now < end:
        left = int((end - now).total_seconds() // 60)
        return f"идёт · ещё {_span(left)}"
    minutes = int((start - now).total_seconds() // 60)
    if minutes >= 24 * 60:
        return "через " + (f"{minutes // (24 * 60)} дн" if minutes >= 48 * 60 else "сутки")
    return f"через {_span(minutes)}"


def _span(minutes: int) -> str:
    minutes = max(minutes, 0)
    if minutes < 60:
        return f"{minutes} мин"
    hours, rest = divmod(minutes, 60)
    return f"{hours} ч {rest} мин" if rest else f"{hours} ч"


def zone_name(msk: datetime, tz: timezone | None = None) -> str:
    """«МСК» or «UTC+2» for the local zone at that moment (summer and winter time differ)."""
    offset = to_local(msk, tz).utcoffset() or timedelta(0)
    if offset == timedelta(hours=3):
        return "МСК"
    sign = "+" if offset >= timedelta(0) else "−"
    hours, rest = divmod(abs(int(offset.total_seconds())) // 60, 60)
    return f"UTC{sign}{hours}" + (f":{rest:02d}" if rest else "")


def time_range(start: datetime, end: datetime, tz: timezone | None = None) -> str:
    """«20:00–21:00» in local time."""
    return f"{to_local(start, tz):%H:%M}–{to_local(end, tz):%H:%M}"


class ScheduleTab(ttk.Frame):
    """Two cards: «Ближайшие» (running and next events) and «По дням» (a weekday picker and its events)."""

    def __init__(self, master: tk.Misc, events: list[dict], clock=msk_now, tz: timezone | None = None) -> None:
        super().__init__(master, padding=(0, 12, 0, 0))
        self.events = events
        self.clock = clock
        self.tz = tz
        self._after: str | None = None
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="cards")
        body.columnconfigure(1, weight=2, uniform="cards")
        body.rowconfigure(0, weight=1)

        nearest = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        nearest.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(nearest, text="Ближайшие", style="Title.TLabel").pack(anchor="w")
        self.next_box = tk.Frame(nearest, background=theme.SURFACE)
        self.next_box.pack(fill="both", expand=True, pady=(8, 0))

        by_day = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        by_day.grid(row=0, column=1, sticky="nsew")
        head = ttk.Frame(by_day, style="Surface.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="По дням", style="Title.TLabel").pack(side="left")
        self.day_var = tk.StringVar(value=DAY_NAMES[DAYS[self.clock().weekday()]])
        self.day_box = ttk.Combobox(head, textvariable=self.day_var, values=list(DAY_NAMES.values()),
                                    state="readonly", width=13, style="Card.TCombobox")
        self.day_box.pack(side="right")
        self.day_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        # a weekend day has 12 events: the list scrolls with the wheel when the window is low (the app routes the wheel)
        self.day_canvas = tk.Canvas(by_day, background=theme.SURFACE, highlightthickness=0, borderwidth=0)
        self.day_canvas.pack(fill="both", expand=True, pady=(8, 0))
        self.day_list = tk.Frame(self.day_canvas, background=theme.SURFACE)
        window = self.day_canvas.create_window(0, 0, window=self.day_list, anchor="nw")
        self.day_list.bind("<Configure>", lambda _e: self.day_canvas.configure(scrollregion=self.day_canvas.bbox("all")))
        self.day_canvas.bind("<Configure>", lambda e: self.day_canvas.itemconfigure(window, width=e.width))

        self.note = ttk.Label(self, style="Muted.TLabel")
        self.note.pack(side="bottom", anchor="w", pady=(8, 0), before=body)  # reserved first: never pushed off
        self.refresh()

    def refresh(self) -> None:
        """Rebuild both lists from the clock; called every REFRESH_MS while the tab exists."""
        now = self.clock()
        self.note.configure(text=f"Время — твоё локальное ({zone_name(now, self.tz)}); сервер живёт по МСК. "
                                 "Источник: база знаний Aion Empire.")
        for box in (self.next_box, self.day_list):
            for child in box.winfo_children():
                child.destroy()
        upcoming = next_events(self.events, now, NEXT_LIMIT)
        if not upcoming:
            self._row(self.next_box, "", "Расписание пусто", "")
        for event, start in upcoming:
            end = end_of(event, start)
            running = start <= now < end
            self._row(self.next_box, time_range(start, end, self.tz), event["name"], until_text(start, end, now),
                      accent=theme.SUCCESS if running else theme.ACCENT)
        day = next((k for k, v in DAY_NAMES.items() if v == self.day_var.get()), DAYS[now.weekday()])
        today = DAYS[now.weekday()]
        day_events = events_for_day(self.events, day)
        self.day_canvas.yview_moveto(0)
        if not day_events:
            self._row(self.day_list, "", "В этот день событий нет", "")
        monday = now.date() - timedelta(days=now.weekday())
        for event in day_events:
            hour, minute = map(int, event["start"].split(":"))
            start = datetime.combine(monday + timedelta(days=DAYS.index(day)), datetime.min.time()).replace(
                hour=hour, minute=minute)
            end = end_of(event, start)
            past = day == today and end <= now
            self._row(self.day_list, time_range(start, end, self.tz), event["name"], "", dim=past)
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(REFRESH_MS, self.refresh)

    def _row(self, box: tk.Frame, when: str, name: str, badge: str, accent: str | None = None, dim: bool = False) -> None:
        compact = box is self.day_list  # a weekday can have 11 events: they fit a 600 px window in the small font
        row = tk.Frame(box, background=theme.SURFACE)
        row.pack(fill="x", pady=0 if compact else 1)
        color = theme.MUTED if dim else theme.TEXT
        tk.Label(row, text=when, width=11, anchor="w", background=theme.SURFACE, foreground=theme.MUTED,
                 font=theme.font("mono")).pack(side="left")
        tk.Label(row, text=name, anchor="w", background=theme.SURFACE, foreground=color,
                 font=theme.font("small" if compact else "body")).pack(side="left", fill="x", expand=True)
        if badge:
            tk.Label(row, text=badge, background=theme.SURFACE, foreground=accent or theme.MUTED,
                     font=theme.font("small")).pack(side="right")

    def scroll(self, steps: int) -> None:
        """Wheel over the weekday list: scroll only when the list is taller than its card."""
        if self.day_list.winfo_reqheight() > self.day_canvas.winfo_height():
            self.day_canvas.yview_scroll(steps, "units")

    def destroy(self) -> None:
        if self._after:
            self.after_cancel(self._after)
            self._after = None
        super().destroy()
