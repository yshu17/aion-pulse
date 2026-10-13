"""The «Расписание» tab (SN-7): what runs now and next, and the events of any weekday.

Event times in data/schedule.json are server time (MSK, UTC+3, no daylight saving). The logic of «what is next»
works in MSK (watcher/schedule_view.py); the tab shows every time in the computer's local time, as the data file asks.
"""

from __future__ import annotations

import json
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import ttk

from watcher import theme
from watcher.catalog import resource_root
from watcher.hint import Hint
from watcher.ui_icons import IconSet
from watcher.reminders import DAYS
from watcher.schedule_custom import Custom, check
from watcher.schedule_view import (GROUPS, clock_pair, day_label, events_for_day, group_hidden, group_of, groups,
                                   kind_of, kinds, map_for, next_events)

MSK = timezone(timedelta(hours=3))
DAY_NAMES = {"mon": "Понедельник", "tue": "Вторник", "wed": "Среда", "thu": "Четверг", "fri": "Пятница",
             "sat": "Суббота", "sun": "Воскресенье"}
NEXT_LIMIT = 8
LEADS = {"5 мин": 5, "15 мин": 15, "30 мин": 30, "1 час": 60}  # SN-8: how early to remind (user choice 13.10)
DEFAULT_LEAD = 5
REFRESH_MS = 30_000
NOW_TICK_MS = 5_000  # the «now» line and the progress bars move this often; the lists rebuild every REFRESH_MS
# day strip: one colour per kind, in the order of the data (existing theme roles, no new colours)
KIND_COLORS = (theme.ACCENT, theme.PLACE, theme.NICK, theme.SUCCESS, theme.WARNING)  # no red: it reads as an error
LANE_H, AXIS_H = 18, 14


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


SCALE = 1.4  # user request 13.10: the schedule's text and icons 40 % larger than the common scale


def scaled_font(role: str) -> tuple[str, int, str]:
    """The common font of ``role`` with the schedule's size (SCALE), same family and weight."""
    family, size, weight = theme.font(role)
    return family, round(size * SCALE), weight


DAYS_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # the chips of the form, Monday first


def today_key(now: datetime) -> str:
    return DAYS[now.weekday()]


def _fit(text: str, width: float, font: tkfont.Font) -> str:
    """The longest start of ``text`` (with «…» when cut) that fits ``width`` pixels; "" when not even «…» fits."""
    if font.measure(text) <= width:
        return text
    while text and font.measure(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…" if text else ""


class ScheduleTab(ttk.Frame):
    """Two cards: «Ближайшие» (running and next events) and «По дням» (a weekday picker and its events)."""

    def __init__(self, master: tk.Misc, events: list[dict], clock=msk_now, tz: timezone | None = None,
                 belled: set[str] | None = None, on_bell=None, lead_min: int = DEFAULT_LEAD, on_lead=None,
                 hidden: set[str] | None = None, on_filter=None, custom: Custom | None = None,
                 on_map=None, side=lambda: "dark", on_check=None, motion=lambda: True) -> None:
        super().__init__(master, padding=(0, 12, 0, 0))
        self.base = events  # data/schedule.json — never changed by the tab
        self.custom = custom or Custom(None)
        self.on_map, self.side = on_map, side
        self.icons = IconSet(self, resource_root() / "data" / "ui" / "icons")  # Phosphor, Codex icons-2
        self.motion = motion  # False with «Отключить анимации»: hover colours switch at once  # SN-7 «на карте»: open a zone; the player's side picks one of two  # SN-7: the user's own added / edited / removed events
        self.events = self.custom.merge(events)
        self.belled = belled if belled is not None else set()  # SN-8: events to remind of (shared with the app)
        self.on_bell = on_bell
        self.on_lead = on_lead
        self.clock = clock
        self.tz = tz
        self._after: str | None = None
        self._now_after: str | None = None
        self._progress: list[tuple[tk.Canvas, datetime, datetime]] = []  # running events: bar, start, end (MSK)
        # SN-7: «Виды» — hide kinds of events from both lists (reminders of belled events still come)
        self.on_filter = on_filter
        hidden = hidden or set()
        self.kind_vars = {group: tk.BooleanVar(value=group not in hidden) for group in groups(self.events)}  # groups
        bar = ttk.Frame(self)  # the bottom line: the time note and «Виды» (no extra height above the cards)
        self.kinds_menu = tk.Menu(self, tearoff=False, background=theme.SURFACE_2, foreground=theme.TEXT,
                                  activebackground=theme.SURFACE_3, activeforeground=theme.TEXT,
                                  selectcolor=theme.ACCENT)
        self._fill_kinds_menu()
        self.kinds_button = ttk.Button(bar, style="Card.TButton", command=self._show_kinds, compound="left",
                                       image=self.icons.get("funnel", "muted", 16))
        self.kinds_button.pack(side="right")
        ttk.Button(bar, text="Текстом", style="Card.TButton", command=lambda: TextEditor(self)).pack(
            side="right", padx=(0, 8))
        ttk.Button(bar, text="Добавить событие", style="Card.TButton", command=self.open_form, compound="left",
                   image=self.icons.get("plus", "muted", 16)).pack(side="right", padx=(0, 8))
        if on_check:  # SN-9: compare with the knowledge base article
            ttk.Button(bar, text="Проверить обновление", style="Ghost.TButton", command=on_check, compound="left",
                       image=self.icons.get("arrow-clockwise", "muted", 16)).pack(side="right", padx=(0, 4))
        self._label_kinds()
        # two clocks: the server (MSK) and this computer (user request 13.10)
        clocks = ttk.Frame(self)
        clocks.pack(fill="x", pady=(0, 6))
        ttk.Label(clocks, text="Сервер", style="CardMuted.TLabel").pack(side="left")
        self.server_clock = ttk.Label(clocks, text="", style="Title.TLabel", font=scaled_font("caption_strong"))
        self.server_clock.pack(side="left", padx=(8, 24))
        ttk.Label(clocks, text="Ты", style="CardMuted.TLabel").pack(side="left")
        self.local_clock = ttk.Label(clocks, text="", style="Title.TLabel", font=scaled_font("caption_strong"))
        self.local_clock.pack(side="left", padx=(8, 0))
        # the chosen day at a glance: hours 00–24, events as blocks by kind, a «now» line on today
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
        self.next_box.bind("<Configure>", lambda _e: self._trim_next())

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
        for group in groups(self.events):
            self.kind_vars.setdefault(group, tk.BooleanVar(value=True))
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
        self.kinds_button.configure(text=f" Группы: {count} скрыт{'о' if count > 1 else ''}" if count else " Группы: все")

    def _show_kinds(self) -> None:
        button = self.kinds_button
        self.kinds_menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    def refresh(self) -> None:
        """Rebuild both lists from the clock; called every REFRESH_MS while the tab exists."""
        now = self.clock()
        shown = group_hidden(self.events, self.hidden())
        self.note.configure(text="")  # the clocks at the top show both times; no note needed
        for box in (self.next_box, self.day_list):
            for child in box.winfo_children():
                child.destroy()
        self._progress = []
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
                      accent=theme.SUCCESS if running else theme.ACCENT, place=event,
                      date="" if event["day"] == today_key(now) else day_label(event["day"], now, now))
            if running:  # how far it has gone: a 3 px bar under the row
                bar = tk.Canvas(self.next_box, height=3, background=theme.SURFACE_3, highlightthickness=0,
                                borderwidth=0)
                bar.pack(fill="x", pady=(0, 2))
                bar.create_rectangle(0, 0, 0, 3, fill=theme.SUCCESS, outline="", tags="fill")
                bar.bind("<Configure>", lambda _e: self._move_progress(self.clock()))
                self._progress.append((bar, start, end))
        day = next((k for k, v in DAY_NAMES.items() if v == self.day_var.get()), DAYS[now.weekday()])
        today = DAYS[now.weekday()]
        day_events = events_for_day(shown, day)
        self.day_canvas.yview_moveto(0)
        if not day_events:
            self._row(self.day_list, "", "В этот день событий нет", "")
        monday = now.date() - timedelta(days=now.weekday())
        seen_groups: set[str] = set()
        for event in day_events:
            group = group_of(event)
            if group not in seen_groups:  # a section header before the first event of each group
                seen_groups.add(group)
                tk.Label(self.day_list, text=group, anchor="w", background=theme.SURFACE, foreground=theme.ACCENT,
                         font=scaled_font("caption_strong")).pack(fill="x", pady=(6, 0))
            hour, minute = map(int, event["start"].split(":"))
            start = datetime.combine(monday + timedelta(days=DAYS.index(day)), datetime.min.time()).replace(
                hour=hour, minute=minute)
            end = end_of(event, start)
            past = day == today and end <= now
            self._row(self.day_list, time_range(start, end, self.tz), event["name"], "", dim=past, bell=event,
                      date="" if day == today else day_label(day, now, now))
        self._show_clocks(now)
        self.after_idle(self._trim_next)
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(REFRESH_MS, self.refresh)
        if self._now_after is None:
            self._now_after = self.after(NOW_TICK_MS, self.tick_now)

    def tick_now(self) -> None:
        """The light tick: move the «now» line and the progress bars to the clock, nothing else is rebuilt."""
        self._now_after = None
        now = self.clock()
        self._show_clocks(now)
        self._move_progress(now)
        if self.winfo_exists():
            self._now_after = self.after(NOW_TICK_MS, self.tick_now)

    def _show_clocks(self, now: datetime) -> None:
        utc = now.replace(tzinfo=MSK).astimezone(timezone.utc) if self.clock is msk_now or now.tzinfo is None else now
        server, local = clock_pair(utc.replace(tzinfo=timezone.utc), self.tz or datetime.now().astimezone().tzinfo)
        self.server_clock.configure(text=server)
        self.local_clock.configure(text=local)

    def _move_progress(self, now: datetime) -> None:
        for bar, start, end in self._progress:
            if bar.winfo_exists():
                share = min(1.0, max(0.0, (now - start) / (end - start)))
                bar.coords("fill", 0, 0, bar.winfo_width() * share, 3)

    def _trim_next(self) -> None:
        """Only whole rows in «Ближайшие»: a row that does not fit the card's height is hidden, not cut in half."""
        box = self.next_box
        if not box.winfo_exists():
            return
        height = box.winfo_height()
        for row in box.winfo_children():
            if row.winfo_y() + row.winfo_reqheight() > height and height > 1:
                row.pack_forget()

    def _row(self, box: tk.Frame, when: str, name: str, badge: str, accent: str | None = None, dim: bool = False,
             bell: dict | None = None, place: dict | None = None, date: str = "") -> None:
        compact = box is self.day_list  # a weekday can have 11 events: they fit a 600 px window in the small font
        row = tk.Frame(box, background=theme.SURFACE)
        row.pack(fill="x", pady=0 if compact else 1)
        color = theme.MUTED if dim else theme.TEXT
        time_color = self._kind_color(bell or place) if (bell or place) else theme.MUTED
        if when:  # the time is a box with an outline in the colour of its kind's grade (user request 13.10)
            tk.Label(row, text=when, anchor="center", background=theme.SURFACE, foreground=time_color,
                     font=scaled_font("small"), highlightthickness=1, highlightbackground=time_color,
                     padx=4).pack(side="left", padx=(0, 6))
        # the toggle is packed first, so a long event name is cut, not the toggle
        if bell is not None:
            on = bell_key(bell) in self.belled
            toggle = tk.Label(row, image=self.icons.get("bell-fill" if on else "bell", "accent" if on else "muted", 16),
                              background=theme.SURFACE, cursor="hand2")
            toggle.pack(side="right", padx=(8, 4))
            Hint(toggle, "Напомню — нажми, чтобы отменить" if on else "Напомнить о событии")
            toggle.bind("<Button-1>", lambda _e, ev=bell: self.toggle_bell(ev))
        zone = map_for(place, self.side()) if place is not None and self.on_map else None
        if zone:
            link = tk.Label(row, text="на карте", background=theme.SURFACE, foreground=theme.PLACE,
                            font=scaled_font("small"), cursor="hand2", compound="left", padx=0,
                            image=self.icons.get("map-pin", "muted", 16))
            link.pack(side="right", padx=(8, 0))
            link.bind("<Button-1>", lambda _e, z=zone: self.on_map(z))
        if badge:
            tk.Label(row, text=badge, background=theme.SURFACE, foreground=accent or theme.MUTED,
                     font=scaled_font("small")).pack(side="right")
        if date:  # «Сегодня» / «ВТ 13.10» in the middle, between the name and the bell (user request 13.10)
            tk.Label(row, text=date, background=theme.SURFACE, foreground=theme.MUTED,
                     font=scaled_font("small")).pack(side="right", padx=(0, 10))
        label = tk.Label(row, text=name, anchor="w", background=theme.SURFACE, foreground=color,
                         font=theme.font("small" if compact else "body"))
        label.pack(side="left", fill="x", expand=True)
        if bell is not None:  # a day row: a click on the name or the pencil edits or removes the event (SN-7)
            label.configure(cursor="hand2")
            label.bind("<Button-1>", lambda _e, ev=bell: self.open_form(ev))
            pencil = tk.Label(row, image=self.icons.get("pencil-simple", "muted", 16), background=theme.SURFACE,
                              cursor="hand2")
            pencil.pack(side="right", padx=(4, 0))
            pencil.bind("<Button-1>", lambda _e, ev=bell: self.open_form(ev))
            Hint(pencil, "Изменить событие")
        row.bind("<Enter>", lambda _e, r=row: self._hover(r, theme.SURFACE_2))
        row.bind("<Leave>", lambda _e, r=row: None if self._pointer_in(r) else self._hover(r, theme.SURFACE))

    @staticmethod
    def _pointer_in(row: tk.Frame) -> bool:
        """<Leave> also fires when the mouse moves onto a label of the row: keep the light then."""
        try:
            under = row.winfo_containing(row.winfo_pointerx(), row.winfo_pointery())
        except (KeyError, tk.TclError):
            return False
        return under is not None and (under is row or under.master is row)

    def _kind_color(self, event: dict) -> str:
        """The colour of an event's kind, the same as its block on the day strip."""
        kinds_order = kinds(self.events)
        kind = kind_of(event)
        return KIND_COLORS[kinds_order.index(kind) % len(KIND_COLORS)] if kind in kinds_order else theme.MUTED

    def _hover(self, row: tk.Frame, color: str) -> None:
        """The row under the mouse takes a slightly lighter ground (theme.MOTION fast, 3 frames)."""
        from watcher.motion import tween_color

        def paint(value: str) -> None:
            for widget in (row, *row.winfo_children()):
                widget.configure(background=value)
        tween_color(row, paint, str(row.cget("background")), color, theme.MOTION["fast"],
                    enabled=bool(self.motion()), steps=3)

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
        if self._now_after:
            self.after_cancel(self._now_after)
            self._now_after = None
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
        self.day_chips: dict[str, tk.BooleanVar] = {d: tk.BooleanVar(value=(d == source["day"])) for d in DAYS_ORDER}
        self.start_var = tk.StringVar(value=source["start"])
        self.end_var = tk.StringVar(value=source["end"])
        self.name_var = tk.StringVar(value=source["name"])
        chips = ttk.Frame(self, style="Surface.TFrame")
        for d in DAYS_ORDER:  # the chips: one event on any days («на все дни»)
            ttk.Checkbutton(chips, text=DAY_NAMES[d][:2].upper(), variable=self.day_chips[d],
                            style="Toolbutton").pack(side="left", padx=(0, 3))
        fields = (("Дни", chips),
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
            self._trash = IconSet(self, resource_root() / "data" / "ui" / "icons").get("trash", "warning", 16)
            ttk.Button(buttons, text="Удалить", style="Card.TButton", command=self.delete, compound="left",
                       image=self._trash).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Отмена", style="Card.TButton", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton", command=self.save).pack(side="left")
        self.bind("<Return>", lambda _e: self.save())
        self.bind("<Escape>", lambda _e: self.destroy())
        fields[3][1].focus_set()

    def _value(self) -> dict:
        return {"day": "", "start": self.start_var.get().strip(), "end": self.end_var.get().strip(),
                "name": self.name_var.get().strip()}

    def _days(self) -> list[str]:
        return [d for d in DAYS_ORDER if self.day_chips[d].get()]

    def save(self) -> None:
        value = self._value()
        days = self._days()
        if not days:
            self.error.configure(text="Выбери хотя бы один день.")
            return
        problem = check({**value, "day": days[0]})
        if problem:
            self.error.configure(text=problem)
            return
        if self.event:
            self.tab.custom.edit(self.event, {**value, "day": days[0]})
            if len(days) > 1:
                self.tab.custom.add_days(value, days[1:])
        else:
            self.tab.custom.add_days(value, days)
        self.tab._changed_events()
        self.destroy()

    def delete(self) -> None:
        if self.event:
            self.tab.custom.remove(self.event)
            self.tab._changed_events()
        self.destroy()


class TextEditor(tk.Toplevel):
    """The whole schedule as text, one event per line; «Сохранить» replaces the user's own changes with the text (the
    server's grid is not touched: a line that matches a data event is kept as a removal + an own copy)."""

    def __init__(self, tab: ScheduleTab) -> None:
        from watcher.schedule_custom import parse_text, to_text
        super().__init__(tab, background=theme.SURFACE, padx=16, pady=12)
        self.tab = tab
        self.title("Расписание текстом")
        self.transient(tab.winfo_toplevel())
        ttk.Label(self, text="Одна строка — одно событие: пн 20:00-21:00 Название", style="CardMuted.TLabel").pack(
            anchor="w")
        self.text = tk.Text(self, width=60, height=22, background=theme.SURFACE_2, foreground=theme.TEXT,
                            insertbackground=theme.TEXT, relief="flat", font=scaled_font("body"), wrap="none")
        self.text.pack(fill="both", expand=True, pady=(6, 6))
        self.text.insert("1.0", to_text(tab.events))
        self.error = ttk.Label(self, style="CardMuted.TLabel", foreground=theme.DANGER)
        self.error.pack(anchor="w")
        buttons = ttk.Frame(self, style="Surface.TFrame")
        buttons.pack(anchor="e", pady=(8, 0))
        ttk.Button(buttons, text="Отмена", style="Card.TButton", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton", command=self.save).pack(side="left")

    def save(self) -> None:
        from watcher.schedule_custom import parse_text
        events, problems = parse_text(self.text.get("1.0", "end"))
        if problems:
            self.error.configure(text="; ".join(problems[:3]))
            return
        custom = self.tab.custom
        from watcher.schedule_custom import event_key
        text_keys = {event_key(e) for e in events}
        base_keys = {event_key(e) for e in self.tab.base}
        # server events present in the text stay (no removal); those missing from it are removed; the rest are own
        custom.data["removed"] = sorted(base_keys - text_keys)
        custom.data["added"] = [e for e in events if event_key(e) not in base_keys]
        custom.save()
        self.tab._changed_events()
        self.destroy()
