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
from watcher.schedule_custom import Custom, check
from watcher.schedule_view import events_for_day, kinds, map_for, next_events, visible

MSK = timezone(timedelta(hours=3))
DAY_NAMES = {"mon": "Понедельник", "tue": "Вторник", "wed": "Среда", "thu": "Четверг", "fri": "Пятница",
             "sat": "Суббота", "sun": "Воскресенье"}
NEXT_LIMIT = 8
LEADS = {"5 мин": 5, "15 мин": 15, "30 мин": 30, "1 час": 60}  # SN-8: how early to remind (user choice 13.10)
DEFAULT_LEAD = 5
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


def bell_key(event: dict) -> str:
    """The saved id of a weekly event the user wants to be reminded of."""
    return f"{event['day']}|{event['start']}|{event['name']}"


def lead_label(minutes: int) -> str:
    return next((k for k, v in LEADS.items() if v == minutes), "5 мин")


def time_range(start: datetime, end: datetime, tz: timezone | None = None) -> str:
    """«20:00–21:00» in local time."""
    return f"{to_local(start, tz):%H:%M}–{to_local(end, tz):%H:%M}"


class ScheduleTab(ttk.Frame):
    """Two cards: «Ближайшие» (running and next events) and «По дням» (a weekday picker and its events)."""

    def __init__(self, master: tk.Misc, events: list[dict], clock=msk_now, tz: timezone | None = None,
                 belled: set[str] | None = None, on_bell=None, lead_min: int = DEFAULT_LEAD, on_lead=None,
                 hidden: set[str] | None = None, on_filter=None, custom: Custom | None = None,
                 on_map=None, side=lambda: "dark") -> None:
        super().__init__(master, padding=(0, 12, 0, 0))
        self.base = events  # data/schedule.json — never changed by the tab
        self.custom = custom or Custom(None)
        self.on_map, self.side = on_map, side  # SN-7 «на карте»: open a zone; the player's side picks one of two  # SN-7: the user's own added / edited / removed events
        self.events = self.custom.merge(events)
        self.belled = belled if belled is not None else set()  # SN-8: events to remind of (shared with the app)
        self.on_bell = on_bell
        self.on_lead = on_lead
        self.clock = clock
        self.tz = tz
        self._after: str | None = None
        # SN-7: «Виды» — hide kinds of events from both lists (reminders of belled events still come)
        self.on_filter = on_filter
        hidden = hidden or set()
        self.kind_vars = {kind: tk.BooleanVar(value=kind not in hidden) for kind in kinds(events)}
        bar = ttk.Frame(self)  # the bottom line: the time note and «Виды» (no extra height above the cards)
        self.kinds_menu = tk.Menu(self, tearoff=False, background=theme.SURFACE_2, foreground=theme.TEXT,
                                  activebackground=theme.SURFACE_3, activeforeground=theme.TEXT,
                                  selectcolor=theme.ACCENT)
        self._fill_kinds_menu()
        self.kinds_button = ttk.Button(bar, style="Card.TButton", command=self._show_kinds)
        self.kinds_button.pack(side="right")
        ttk.Button(bar, text="Добавить событие", style="Card.TButton", command=self.open_form).pack(
            side="right", padx=(0, 8))
        self._label_kinds()
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="cards")
        body.columnconfigure(1, weight=2, uniform="cards")
        body.rowconfigure(0, weight=1)

        nearest = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        nearest.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        near_head = ttk.Frame(nearest, style="Surface.TFrame")
        near_head.pack(fill="x")
        ttk.Label(near_head, text="Ближайшие", style="Title.TLabel").pack(side="left")
        self.lead_var = tk.StringVar(value=lead_label(lead_min))
        self.lead_box = ttk.Combobox(near_head, textvariable=self.lead_var, values=list(LEADS), state="readonly",
                                     width=7, style="Card.TCombobox")
        self.lead_box.pack(side="right")
        self.lead_box.bind("<<ComboboxSelected>>", lambda _e: self._on_lead())
        ttk.Label(near_head, text="Напоминать за", style="CardMuted.TLabel").pack(side="right", padx=(0, 8))
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

        self.note = ttk.Label(bar, style="Muted.TLabel")
        self.note.pack(side="left", anchor="w")
        bar.pack(side="bottom", fill="x", pady=(8, 0), before=body)  # reserved first: never pushed off
        self.refresh()

    def _fill_kinds_menu(self) -> None:
        self.kinds_menu.delete(0, "end")
        for kind, var in self.kind_vars.items():
            self.kinds_menu.add_checkbutton(label=kind, variable=var, command=self.filter_changed)

    def _changed_events(self) -> None:
        """After the user's own change: merge again, offer a new kind in «Виды», redraw."""
        self.events = self.custom.merge(self.base)
        for kind in kinds(self.events):
            self.kind_vars.setdefault(kind, tk.BooleanVar(value=True))
        self._fill_kinds_menu()
        self.refresh()

    def open_form(self, event: dict | None = None) -> "EventForm":
        """SN-7: the add form, or with an event — edit it or remove it."""
        return EventForm(self, event)

    def hidden(self) -> set[str]:
        return {kind for kind, var in self.kind_vars.items() if not var.get()}

    def filter_changed(self) -> None:
        self._label_kinds()
        if self.on_filter:
            self.on_filter(self.hidden())
        self.refresh()

    def _label_kinds(self) -> None:
        count = len(self.hidden())
        self.kinds_button.configure(text=f"Виды: {count} скрыт{'о' if count > 1 else ''} ▾" if count else "Виды: все ▾")

    def _show_kinds(self) -> None:
        button = self.kinds_button
        self.kinds_menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    def refresh(self) -> None:
        """Rebuild both lists from the clock; called every REFRESH_MS while the tab exists."""
        now = self.clock()
        shown = visible(self.events, self.hidden())
        self.note.configure(text=f"Время — твоё локальное ({zone_name(now, self.tz)}), сервер живёт по МСК.")
        for box in (self.next_box, self.day_list):
            for child in box.winfo_children():
                child.destroy()
        upcoming = next_events(shown, now, NEXT_LIMIT)
        if not upcoming:
            self._row(self.next_box, "", "Расписание пусто", "")
        for event, start in upcoming:
            end = end_of(event, start)
            running = start <= now < end
            badge = until_text(start, end, now)
            if bell_key(event) in self.belled:
                badge = "напомню · " + badge
            self._row(self.next_box, time_range(start, end, self.tz), event["name"], badge,
                      accent=theme.SUCCESS if running else theme.ACCENT, place=event)
        day = next((k for k, v in DAY_NAMES.items() if v == self.day_var.get()), DAYS[now.weekday()])
        today = DAYS[now.weekday()]
        day_events = events_for_day(shown, day)
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
            self._row(self.day_list, time_range(start, end, self.tz), event["name"], "", dim=past, bell=event)
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(REFRESH_MS, self.refresh)

    def _row(self, box: tk.Frame, when: str, name: str, badge: str, accent: str | None = None, dim: bool = False,
             bell: dict | None = None, place: dict | None = None) -> None:
        compact = box is self.day_list  # a weekday can have 11 events: they fit a 600 px window in the small font
        row = tk.Frame(box, background=theme.SURFACE)
        row.pack(fill="x", pady=0 if compact else 1)
        color = theme.MUTED if dim else theme.TEXT
        # the toggle is packed first, so a long event name is cut, not the toggle
        if bell is not None:
            on = bell_key(bell) in self.belled
            toggle = tk.Label(row, text="напомню" if on else "напомнить", background=theme.SURFACE,
                              foreground=theme.ACCENT if on else theme.MUTED, font=theme.font("small"), cursor="hand2")
            toggle.pack(side="right", padx=(8, 4))
            toggle.bind("<Button-1>", lambda _e, ev=bell: self.toggle_bell(ev))
        zone = map_for(place, self.side()) if place is not None and self.on_map else None
        if zone:
            link = tk.Label(row, text="на карте", background=theme.SURFACE, foreground=theme.PLACE,
                            font=theme.font("small"), cursor="hand2")
            link.pack(side="right", padx=(8, 0))
            link.bind("<Button-1>", lambda _e, z=zone: self.on_map(z))
        tk.Label(row, text=when, width=11, anchor="w", background=theme.SURFACE, foreground=theme.MUTED,
                 font=theme.font("mono")).pack(side="left")
        label = tk.Label(row, text=name, anchor="w", background=theme.SURFACE, foreground=color,
                         font=theme.font("small" if compact else "body"))
        label.pack(side="left", fill="x", expand=True)
        if bell is not None:  # a day row: a click on the name edits or removes the event (SN-7)
            label.configure(cursor="hand2")
            label.bind("<Button-1>", lambda _e, ev=bell: self.open_form(ev))
        if badge:
            tk.Label(row, text=badge, background=theme.SURFACE, foreground=accent or theme.MUTED,
                     font=theme.font("small")).pack(side="right")

    def toggle_bell(self, event: dict) -> None:
        """SN-8: switch the reminder of one weekly event on or off and tell the app (it saves the choice)."""
        key = bell_key(event)
        on = key not in self.belled
        (self.belled.add if on else self.belled.discard)(key)
        if self.on_bell:
            self.on_bell(key, on)
        self.refresh()

    def lead_minutes(self) -> int:
        return LEADS.get(self.lead_var.get(), DEFAULT_LEAD)

    def _on_lead(self) -> None:
        if self.on_lead:
            self.on_lead(self.lead_minutes())

    def scroll(self, steps: int) -> None:
        """Wheel over the weekday list: scroll only when the list is taller than its card."""
        if self.day_list.winfo_reqheight() > self.day_canvas.winfo_height():
            self.day_canvas.yview_scroll(steps, "units")

    def destroy(self) -> None:
        if self._after:
            self.after_cancel(self._after)
            self._after = None
        super().destroy()


class EventForm(tk.Toplevel):
    """Add or edit one weekly event; times are server time (MSK), like the data file."""

    def __init__(self, tab: ScheduleTab, event: dict | None) -> None:
        super().__init__(tab, background=theme.SURFACE, padx=16, pady=12)
        self.tab, self.event = tab, event
        self.title("Изменить событие" if event else "Новое событие")
        self.transient(tab.winfo_toplevel())
        self.resizable(False, False)
        source = event or {"day": DAYS[tab.clock().weekday()], "start": "", "end": "", "name": ""}
        self.day_var = tk.StringVar(value=DAY_NAMES.get(source["day"], DAY_NAMES["mon"]))
        self.start_var = tk.StringVar(value=source["start"])
        self.end_var = tk.StringVar(value=source["end"])
        self.name_var = tk.StringVar(value=source["name"])
        fields = (("День", ttk.Combobox(self, textvariable=self.day_var, values=list(DAY_NAMES.values()),
                                        state="readonly", width=14, style="Card.TCombobox")),
                  ("Начало (МСК)", ttk.Entry(self, textvariable=self.start_var, width=8, style="Card.TEntry")),
                  ("Конец (МСК)", ttk.Entry(self, textvariable=self.end_var, width=8, style="Card.TEntry")),
                  ("Название", ttk.Entry(self, textvariable=self.name_var, width=28, style="Card.TEntry")))
        for row, (label, widget) in enumerate(fields):
            ttk.Label(self, text=label, style="CardMuted.TLabel").grid(row=row, column=0, sticky="w", pady=3)
            widget.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=3)
        self.error = ttk.Label(self, style="CardMuted.TLabel", foreground=theme.DANGER)
        self.error.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        buttons = ttk.Frame(self, style="Surface.TFrame")
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        if event:
            ttk.Button(buttons, text="Удалить", style="Card.TButton", command=self.delete).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Отмена", style="Card.TButton", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton", command=self.save).pack(side="left")
        self.bind("<Return>", lambda _e: self.save())
        self.bind("<Escape>", lambda _e: self.destroy())
        fields[3][1].focus_set()

    def _value(self) -> dict:
        day = next((k for k, v in DAY_NAMES.items() if v == self.day_var.get()), "")
        return {"day": day, "start": self.start_var.get().strip(), "end": self.end_var.get().strip(),
                "name": self.name_var.get().strip()}

    def save(self) -> None:
        value = self._value()
        problem = check(value)
        if problem:
            self.error.configure(text=problem)
            return
        if self.event:
            self.tab.custom.edit(self.event, value)
        else:
            self.tab.custom.add(value)
        self.tab._changed_events()
        self.destroy()

    def delete(self) -> None:
        if self.event:
            self.tab.custom.remove(self.event)
            self.tab._changed_events()
        self.destroy()
