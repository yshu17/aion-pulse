"""tkinter window: keywords, start/stop, list of matched messages."""

import json
import queue
import threading
import time
import webbrowser
import tkinter as tk
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, ttk

from watcher import theme
from watcher.bestiary_widgets import keep_pane_cursor, refresh_pointer_cursor
from watcher.mapview import RESIZE_SETTLE_MS
from watcher.snapshot import capture_widget
from watcher.win_sizing import install_sizing_hook
from watcher.alerts import AlertTracker
from watcher.allchat import AllChatView
from watcher.bestiary_view import BestiaryView
from watcher.catalog import WatchItem, is_listed, load_item_names, load_watch_items, local_bestiary_dir, resource_root
from watcher.config import OVERLAY_POPUP_ENABLED, read_config, save_config
from watcher.reminders import due_reminders, occurrences_between
from watcher.schedule_tab import (LEADS, ScheduleTab, bell_key, end_of, lead_label, load_events, msk_now, time_range,
                                  to_local)
from watcher.schedule_view import next_events
from watcher.errlog import log_exception
from watcher.matcher import Matcher, highlight_segments
from watcher.alarm import NagAlarm
from watcher.feed import MatchFeed
from watcher.gamecheck import game_running
from watcher.itemlist import ItemFilter, ItemList
from watcher.ui_icons import IconSet
from watcher.hint import Hint
from watcher.window_icon import load_app_icon
from watcher.notifier import Notifier, system_sounds
from watcher.alert_bridge import AlertBridge
from watcher.notify_center import Notification, NotificationAction, NotificationCenter
from watcher.notify_settings import apply as apply_notify_settings
from watcher.notify_tab import NotifyPanel
from watcher.schedule_custom import Custom
from watcher.schedule_update import ARTICLE, decide, http_fetch, known_fingerprint, site_fingerprint
from watcher.updater import API as RELEASE_API, latest_release, newer
from watcher.version import APP_NAME, VERSION, build_label
from watcher.toasts import ToastManager
from watcher.mapview import MapView, Place, load_zones
from watcher.poi import PoiStore
from watcher.parser import MAP_NAMES, ChatMessage, display_text, parse_line, places_in
from watcher.series import SeriesTracker
from watcher.recipes import load_recipes, with_recipe
from watcher.specs import load_specs
from watcher.tailer import LogTailer
from watcher.tooltip import SpecTooltip

MAX_ROWS = 500
MAX_PLACES = 300  # place links remembered for the map's pins
STAT_DOT = 8  # px, the coloured dot of a header statistic
RETRY_MS = 2000
TOOLTIP_DELAY_MS = 300
HISTORY_CHOICES = {"нет": 0, **{f"{m} мин": m for m in (5, 15, 30, 45, 60)}}
SYSTEM_BEEP = "Системный сигнал"
CUSTOM_SOUND = "Свой файл…"
ALERT_MODES = {"Стандартный": "standard", "Назойливый": "nag"}
REACT_CHOICES = {"15 с": 15, "30 с": 30, "60 с": 60, "2 мин": 120}
DEFAULT_REACT_SEC = 30
SEARCH_MODES = {
    "Слово ИЛИ предмет": "or",
    "Только слова": "words",
    "Только предметы": "items",
    "Слово И предмет": "and",
}
UI_TICK_MS = 500
GAME_CHECK_SEC = 5  # while watching: how often to look for the game process
GAME_OFF = "Игра не запущена — слежение остановлено"


REMIND_MS = 30_000  # SN-8: how often the schedule reminders are checked
REMIND_REPEAT_S = 180  # SN-8: an unanswered reminder comes back after this, until the event ends
MISSED_DAYS = 7  # SN-8: events missed while the program was closed are reported for at most a week back
STATUS_CHARS = 20  # the status chip keeps one width, so the keywords field does not jump; full text in its hint


def short_status(text: str) -> tuple[str, str]:
    """Compact status for the folder row and its label style."""
    if text.startswith("Слежу"):
        hint = text.split("  ·  ", 1)[1] if "  ·  " in text else ""
        return ("Слежу" + (f"  ·  {hint}" if hint else ""), "Live.Chip.TLabel")
    if text.startswith("Игра не запущена"):
        return "Игра не запущена", "Warn.Chip.TLabel"
    if text.startswith("Chat.log не найден"):
        return "Chat.log не найден", "Warn.Chip.TLabel"
    if text.startswith("Ошибка"):
        return (text if len(text) <= STATUS_CHARS else text[:STATUS_CHARS - 1] + "…"), "Error.Chip.TLabel"
    return "Не слежу", "Idle.Chip.TLabel"


def plural(n: int, one: str, few: str, many: str) -> str:
    """«1 слово», «3 слова», «5 слов» (Russian plural forms)."""
    last2, last = n % 100, n % 10
    word = one if last == 1 and last2 != 11 else few if 2 <= last <= 4 and not 12 <= last2 <= 14 else many
    return f"{n} {word}"


def split_keywords(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


class App:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.error_log = config_path.with_name("errors.log")
        self._last_error = ""
        self.cfg, self._config_notice = read_config(config_path)
        self.ui_icons = IconSet(root, resource_root() / "data" / "ui" / "icons")
        data_dir = resource_root() / "data"
        self.item_names = load_item_names(data_dir / "item_names.tsv")
        self.watch_items = load_watch_items(data_dir / "watch_items.csv")
        self.item_by_id = {item.id: item for item in self.watch_items}
        self.icons_dir = data_dir / "icons"
        self.specs = load_specs(data_dir / "item_specs.json.gz")
        self.recipes = load_recipes(data_dir / "recipes.json.gz")  # empty until the recipe data is added
        self.matcher = Matcher(
            self.cfg.keywords,
            self.cfg.cooldown_sec,
            watch_items=self._checked_items(),
            mode=self.cfg.search_mode,
        )
        self.notifier = Notifier(self.cfg.sound_path, volume=self.cfg.sound_volume)
        if self.cfg.react_sec not in REACT_CHOICES.values():
            self.cfg.react_sec = DEFAULT_REACT_SEC  # e.g. the removed «выкл» (0) from an older config
        self.tracker = AlertTracker(self.cfg.react_sec)
        self._toasted_alerts: set[int] = set()  # SN-4: alerts already shown in a toast
        self.series = SeriesTracker()
        self.zones = load_zones(data_dir / "maps", MAP_NAMES)
        self.places: deque[Place] = deque(maxlen=MAX_PLACES)  # place links seen in «Поиск группы»
        self.tailer: LogTailer | None = None
        self.running = False
        self._after_id: str | None = None
        self._rows = 0
        self._scan_history = False
        self._last_game_check = 0.0
        self._tooltip_after: str | None = None
        self._build_ui()
        self._apply_search_mode_state()
        self.tooltip = SpecTooltip(root)
        self.alarm = NagAlarm(
            root,
            self.notifier,
            on_ack=self._on_popup_ack,
            window_icons=self._window_icons,
            icon_for=self._popup_icon,
        )
        self.alarm.reduce_motion = self.cfg.reduce_motion
        self.tooltip.reduce_motion = self.cfg.reduce_motion
        self.notifications = NotificationCenter(sound=lambda _event: self.notifier.play())
        self.alert_bridge = AlertBridge(self.notifications)  # SN-4: chat alerts and «game off» as toasts
        self.toasts = ToastManager(
            root, self.notifications, on_open=self._open_notification,
            on_action=self._on_toast_action,
            reduce_motion=lambda: self.cfg.reduce_motion,
        )
        apply_notify_settings(self.cfg, self.notifications, self.toasts)
        self.toasts.start()
        self._set_status(self._config_notice or "Остановлен")
        self._update_counters()
        self._feed_empty_state()
        self._ui_after = root.after(UI_TICK_MS, self._ui_tick)

    def _build_ui(self) -> None:
        root = self.root
        root.title(f"{APP_NAME} {VERSION}{build_label()}")
        root.geometry("1400x860")
        root.minsize(1000, 600)
        theme.apply_dark_theme(root, resource_root() / "data" / "ui")
        self._window_icons = load_app_icon(root, resource_root() / "data" / "ui")
        theme.dark_title_bar(root)

        header = ttk.Frame(root, padding=(16, 10, 16, 2))  # ui:41: less empty space above and between the rows
        header.pack(fill="x")
        self.header = header
        ttk.Label(header, text=APP_NAME, style="AppTitle.TLabel").pack(side="left")
        ttk.Label(header, text="  ·  Поиск группы", style="Muted.TLabel").pack(side="left", pady=(6, 0))

        # UI/UX plan item 3: one always visible control row (Start, status, what to look for) and the settings that
        # change rarely (game folder, alerts, history) in a card that folds away; open on the first run, remembered.
        control = ttk.Frame(root, padding=(16, 4, 16, 8))
        control.pack(fill="x")
        self.control_bar = control
        self.start_btn = ttk.Button(control, text="Start", style="Accent.TButton", command=self.toggle, width=7)
        self.start_btn.pack(side="left")
        self.status_short_var = tk.StringVar()
        self.status_label = ttk.Label(control, textvariable=self.status_short_var, style="Idle.Chip.TLabel", compound="left",
                                      width=STATUS_CHARS, anchor="center")  # ui:38: icon and text centred as one group
        self.status_hint = Hint(self.status_label, "")
        self._status_pulse_after: str | None = None
        self._status_pulse_generation = 0
        self.status_label.pack(side="left", padx=(12, 0))
        ttk.Label(control, text="Ключевые слова", style="Muted.TLabel").pack(side="left", padx=(16, 8))
        self.kw_var = tk.StringVar(value=", ".join(self.cfg.keywords))
        kw_entry = ttk.Entry(control, textvariable=self.kw_var)
        self.kw_entry = kw_entry
        self.search_mode_var = tk.StringVar(
            value=next((k for k, v in SEARCH_MODES.items() if v == self.cfg.search_mode), "Слово ИЛИ предмет")
        )
        search_mode = ttk.Combobox(
            control, textvariable=self.search_mode_var, values=list(SEARCH_MODES), state="readonly", width=18
        )
        search_mode.bind("<<ComboboxSelected>>", lambda _e: self._on_search_mode_selected())
        kw_entry.bind("<Return>", lambda _e: self._apply_keywords())
        kw_entry.bind("<FocusOut>", lambda _e: self._apply_keywords())
        self.settings_btn = ttk.Button(control, text="Настройки", command=self._toggle_settings, compound="right", width=0)
        # ui:41 / UI-DEF-1: the right-hand controls are packed before the entry, so a narrow window shrinks the
        # keyword entry instead of cutting «Настройки» off the edge
        self.settings_btn.pack(side="right", padx=(8, 0))
        search_mode.pack(side="right", padx=(8, 0))
        kw_entry.configure(width=10)
        kw_entry.pack(side="left", fill="x", expand=True)

        settings = ttk.Frame(root, style="Card.TFrame", padding=(16, 4))
        self.settings_card = settings
        ttk.Label(settings, text="Папка игры", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        self.game_dir_var = tk.StringVar(value=str(self.cfg.chat_log_path()))
        dir_entry = ttk.Entry(settings, textvariable=self.game_dir_var, style="Card.TEntry")
        dir_entry.grid(row=0, column=1, sticky="ew", padx=(12, 12), pady=4)
        dir_entry.bind("<Return>", lambda _e: self._apply_game_dir())
        dir_entry.bind("<FocusOut>", lambda _e: self._apply_game_dir())
        self.browse_btn = ttk.Button(settings, text="Обзор…", style="Card.TButton", command=self._pick_dir)
        self.browse_btn.grid(row=0, column=2, pady=4, sticky="w")
        Hint(self.browse_btn, "Выбрать папку игры или Chat.log")
        ttk.Label(settings, text="Оповещение", style="CardMuted.TLabel").grid(row=1, column=0, sticky="nw", pady=(10, 0))
        # one grid (ui:37): the mode, sound, play and test; under them the volume (under «Звук») and the reaction;
        # then the popup setting. The columns line up instead of two independent rows, and 1000 px fits
        alert = ttk.Frame(settings, style="Surface.TFrame")
        alert.grid(row=1, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=4)
        alert_row = alert_row2 = alert
        self.mode_var = tk.StringVar(
            value=next((k for k, v in ALERT_MODES.items() if v == self.cfg.alert_mode), "Стандартный")
        )
        mode = ttk.Combobox(
            alert_row, textvariable=self.mode_var, values=list(ALERT_MODES), state="readonly", width=12, style="Card.TCombobox"
        )
        mode.grid(row=0, column=0, sticky="w")
        mode.bind("<<ComboboxSelected>>", lambda _e: self._on_mode_selected())
        ttk.Label(alert_row, text="Звук", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w", padx=(18, 8))
        self.sound_choices = self._sound_choices()
        self.sound_var = tk.StringVar(value=self._sound_label(self.cfg.sound_path))
        self.sound_box = ttk.Combobox(
            alert_row,
            textvariable=self.sound_var,
            values=[*self.sound_choices, CUSTOM_SOUND],
            state="readonly",
            width=22,
            style="Card.TCombobox",
        )
        self.sound_box.grid(row=0, column=2, sticky="ew")
        self.sound_box.bind("<<ComboboxSelected>>", lambda _e: self._on_sound_selected())
        play_button = ttk.Button(
            alert_row, image=self.ui_icons.get("play", "accent", 16), style="Card.TButton",
            command=self.notifier.play, padding=(6, 5),
        )
        play_button.grid(row=0, column=3, padx=8)
        Hint(play_button, "Прослушать звук")
        preview = ttk.Button(alert_row, text="Тест уведомления", style="Card.TButton", command=self._preview_notification)
        preview.grid(row=0, column=4, sticky="w", padx=(0, 8))
        Hint(preview, "Показать пробное уведомление в углу экрана")
        react_cell = ttk.Frame(alert, style="Surface.TFrame")  # «Реакция» sits after the volume, so 1000 px fits
        react_cell.grid(row=1, column=4, sticky="w", pady=(6, 0))
        ttk.Label(react_cell, text="Реакция", style="CardMuted.TLabel").pack(side="left", padx=(0, 8))
        self.react_var = tk.StringVar(
            value=next((k for k, v in REACT_CHOICES.items() if v == self.cfg.react_sec), "30 с")
        )
        react = ttk.Combobox(
            react_cell, textvariable=self.react_var, values=list(REACT_CHOICES), state="readonly", width=7, style="Card.TCombobox"
        )
        react.pack(side="left")
        react.bind("<<ComboboxSelected>>", lambda _e: self._on_react_selected())
        self.popup_var = tk.BooleanVar(value=self.cfg.nag_popup)
        # ui:40: temporarily unavailable, shown disabled so the user sees why it does nothing; the label greys out too
        # (the card style has no disabled colour — found by the visual check of 13.10)
        ttk.Style(self.root).map("Off.CardPlain.TCheckbutton", foreground=[("disabled", theme.DISABLED), ("selected", theme.ACCENT)],
                                 background=[("active", theme.SURFACE)])
        self.popup_check = ttk.Checkbutton(
            alert_row2,
            text="Окно поверх игры (пока недоступно)",
            variable=self.popup_var,
            style="Off.CardPlain.TCheckbutton",
            command=self._on_popup_toggled,
            state="normal" if OVERLAY_POPUP_ENABLED else "disabled",
        )
        self.popup_check.grid(row=2, column=1, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Label(alert_row2, text="Громкость", style="CardMuted.TLabel").grid(row=1, column=1, sticky="w", padx=(18, 8),
                                                                         pady=(6, 0))
        self.volume_var = tk.IntVar(value=self.notifier.volume)
        volume = ttk.Scale(
            alert_row2,
            from_=0,
            to=100,
            orient="horizontal",
            length=120,
            variable=self.volume_var,
            command=lambda _v: self._on_volume_changed(save=False),
        )
        volume.grid(row=1, column=2, sticky="ew", pady=(6, 0))
        volume.bind("<ButtonRelease-1>", lambda _e: self._on_volume_changed())
        self.volume_label = ttk.Label(alert_row2, text=f"{self.notifier.volume}%", style="Caption.TLabel", width=5)
        self.volume_label.grid(row=1, column=3, pady=(6, 0))
        ttk.Label(settings, text="История", style="CardMuted.TLabel").grid(row=2, column=0, sticky="w")
        history_row = ttk.Frame(settings, style="Surface.TFrame")
        history_row.grid(row=2, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=4)
        minutes_to_choice = {m: c for c, m in HISTORY_CHOICES.items()}
        self.history_var = tk.StringVar(value=minutes_to_choice.get(self.cfg.history_min, "нет"))
        history = ttk.Combobox(
            history_row,
            textvariable=self.history_var,
            values=list(HISTORY_CHOICES),
            state="readonly",
            width=7,
        )
        history.pack(side="left")
        history.bind("<<ComboboxSelected>>", lambda _e: self._on_history_changed())
        ttk.Label(history_row, text="поиск при Start и «Весь чат»", style="CardMuted.TLabel").pack(side="left", padx=10)
        self.reduce_motion_var = tk.BooleanVar(value=self.cfg.reduce_motion)
        ttk.Checkbutton(
            settings, text="Отключить анимации", variable=self.reduce_motion_var,
            style="CardPlain.TCheckbutton", command=self._on_reduce_motion,
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(4, 2))
        # SN-5: notification settings — a block of this card (user decision 13.10: not a tab of their own)
        ttk.Label(settings, text="Уведомления", style="CardMuted.TLabel").grid(row=4, column=0, sticky="nw",
                                                                           pady=(8, 0))
        self.notify_panel = NotifyPanel(settings, self.cfg, on_change=self._on_notify_settings)
        self.notify_panel.grid(row=4, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(6, 2))
        settings.columnconfigure(1, weight=1)
        self._show_settings(self.cfg.settings_open)
        self.status_var = tk.StringVar()  # full status text; the folder row shows a short form

        self.tabs = ttk.Notebook(root)
        # While the window is dragged its content is taken out of the layout (every page keeps its state); it comes
        # back once the size settles. Tk re-lays out every page on each size step: 150-300 ms per step, 2-3 fps.
        self._frozen_tabs: dict | None = None
        self._thaw_after: str | None = None
        # Windows tells when an edge drag starts and ends; elsewhere the size changes themselves are watched
        self._sizing_hook = install_sizing_hook(root, self._freeze_window, self.settle_layout)
        root.bind("<Configure>", self._on_root_resize, add="+")
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.search_tab = ttk.Frame(self.tabs, padding=(0, 12, 0, 0))
        self.tabs.add(self.search_tab, text="Поиск")
        # feed | item list, split by a draggable divider
        self.split = tk.PanedWindow(
            self.search_tab,
            orient="horizontal",
            sashwidth=12,
            sashcursor="sb_h_double_arrow",
            opaqueresize=False,  # a rubber band while dragging, one layout on release
            background=theme.BG,
            borderwidth=0,
        )
        self.split.pack(fill="both", expand=True)
        column = ttk.Frame(self.split)
        self.split.add(column, stretch="always")
        self._build_items_panel(self.split)
        self.split.add(self.items_panel, stretch="never")
        keep_pane_cursor(self.split, column, self.items_panel)
        self.split.bind("<ButtonRelease-1>", lambda _e: self._on_split_moved(), add="+")
        root.after_idle(self._init_split)
        self._build_counters(header)
        self._header_gradient = theme.install_header_gradient(header)  # ui:31: quiet title-row gradient
        spec_items = {item.name: item.id for item in self.watch_items if item.id in self.specs}
        grades = {item.id: item.grade for item in self.watch_items}
        self.feed = MatchFeed(
            column,
            on_accept=self._on_feed_accept,
            max_rows=MAX_ROWS,
            spec_items=spec_items,
            grades=grades,
            on_item_enter=self._schedule_tooltip,
            on_item_leave=self._hide_tooltip,
            on_place=self._open_place,
            motion_enabled=lambda: not self.cfg.reduce_motion,
        )
        self.feed.pack(fill="both", expand=True)
        self.text = self.feed.text

        self.all_chat = AllChatView(
            self.tabs,
            get_path=lambda: str(self.cfg.chat_log_path()),
            names=self.item_names,
            get_minutes=lambda: self.cfg.history_min,
            show_system=self.cfg.chat_system,
            on_settings=self._on_chat_settings,
            toolbar_parent=root,
            spec_items=spec_items,
            grades=grades,
            on_item_enter=self._schedule_tooltip,
            on_item_leave=self._hide_tooltip,
            on_place=self._open_place,
            motion_enabled=lambda: not self.cfg.reduce_motion,
        )
        self.all_chat.configure(padding=(0, 12, 0, 0))
        self.tabs.add(self.all_chat, text="Весь чат")
        maps_dir = resource_root() / "data" / "maps"
        bestiary_dir = local_bestiary_dir()  # NPC data is loaded from outside the program; no data, no tab
        self.map_view = MapView(
            self.tabs,
            self.zones,
            get_places=lambda: list(self.places),
            poi=PoiStore.load(maps_dir / "poi.json"),
            icons_dir=maps_dir / "icons",
            show_quests=self.cfg.map_quests,
            on_show_quests=self._on_map_quests,
            map_theme=self.cfg.map_theme,
            on_theme=self._on_map_theme,
            side=self.cfg.map_side,
            on_side=self._on_map_side,
            bestiary_database=bestiary_dir / "npcs.sqlite" if bestiary_dir else None,
            bestiary_icons=bestiary_dir / "icons" if bestiary_dir else None,
        )
        self.map_view.motion_enabled = lambda: not self.cfg.reduce_motion
        self.map_view.configure(padding=(0, 12, 0, 0))
        self.tabs.add(self.map_view, text="Карта")
        self.bestiary_view = None
        if bestiary_dir:
            self.bestiary_view = BestiaryView(
                self.tabs,
                bestiary_dir / "npcs.sqlite",
                bestiary_dir / "icons",
                {map_id: zone.name for map_id, zone in self.zones.items()},
                on_map=self._open_bestiary_point,
            )
            self.bestiary_view.configure(padding=(0, 12, 0, 0))
            self.tabs.add(self.bestiary_view, text="NPC / Бестиарий")
        # SN-7: the server schedule — what runs now and next, and the events of any weekday
        self.schedule_tab = ScheduleTab(
            self.tabs, load_events(resource_root() / "data" / "schedule.json"),
            belled=set(self.cfg.remind_events), on_bell=self._on_bell,
            lead_min=self.cfg.remind_min if self.cfg.remind_min in LEADS.values() else 5, on_lead=self._on_lead,
            hidden=set(self.cfg.schedule_hidden), on_filter=self._on_schedule_filter,
            custom=Custom.load(self.config_path.with_name("schedule_custom.json")),  # SN-7: the user's own events
            on_map=self._open_zone, side=lambda: self.cfg.map_side, on_check=lambda: self.check_schedule_update(True),
            motion=lambda: not self.cfg.reduce_motion,
        )
        # SN-9: the grid of data/schedule.json was typed from this picture version of the knowledge base article
        try:
            self.schedule_known = known_fingerprint(
                json.loads((resource_root() / "data" / "schedule.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            self.schedule_known = ""
        self._update_results: queue.Queue = queue.Queue()
        self._update_note: tuple[int, str] | None = None  # the «обновилось» toast and its site version
        if self.cfg.schedule_check:
            self.root.after(5000, lambda: self.check_schedule_update(False))
        self._release_results: queue.Queue = queue.Queue()
        self._release_note: tuple[int, str, str] | None = None  # toast id, tag, release page
        if self.cfg.update_check:
            self.root.after(8000, self.check_release)
        self._msk_clock = msk_now  # tests replace it
        self._reminded: set[str] = set()  # occurrences already announced this run (no repeats)
        self._reminder_ids: dict[int, datetime] = {}  # notification id -> end of its event: repeats stop there
        self.root.after_idle(self._report_missed_reminders)
        self._remind_after = self.root.after(REMIND_MS, self._check_reminders)
        self.tabs.add(self.schedule_tab, text="Расписание")
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab_changed())

        root.bind_all("<MouseWheel>", self._on_mouse_wheel, add="+")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_counters(self, parent: ttk.Frame) -> None:
        """Found / reacted / missed, in the header so they are visible on every tab."""
        self.counters_bar = ttk.Frame(parent)
        self.found_var = tk.StringVar()
        self.reacted_var = tk.StringVar()
        self.missed_var = tk.StringVar()
        # UI/UX item 10: statistics, not buttons — a dot, a large number and a caption; only «Сбросить» is pressed
        for var, name, caption in (
            (self.found_var, "Found", "найдено"),
            (self.reacted_var, "Reacted", "отреагировал"),
            (self.missed_var, "Missed", "пропущено"),
        ):
            stat = ttk.Frame(self.counters_bar)
            dot = tk.Canvas(stat, width=STAT_DOT, height=STAT_DOT, background=theme.BG, highlightthickness=0)
            color = theme.STAT_COLORS[name]
            dot.create_oval(0, 0, STAT_DOT - 1, STAT_DOT - 1, fill=color, outline=color)
            dot.pack(side="left", padx=(0, 6))
            ttk.Label(stat, textvariable=var, style=f"{name}.Stat.TLabel").pack(side="left")
            ttk.Label(stat, text=caption, style="Stat.TLabel").pack(side="left", padx=(4, 0), pady=(3, 0))
            stat.pack(side="left", padx=(0, 16))
        self.reset_btn = ttk.Button(
            self.counters_bar,
            text="Сбросить",
            image=(self.ui_icons.get("x", "muted", 16), "active", self.ui_icons.get("x", "text", 16)),
            compound="left",
            style="Ghost.TButton",
            command=self._reset_counters,
        )
        self.reset_btn.pack(side="left")
        Hint(self.reset_btn, "Обнулить счётчики")
        self.counters_bar.pack(side="right")

    def _update_counters(self) -> None:
        self.found_var.set(str(self.tracker.found))
        self.reacted_var.set(str(self.tracker.reacted))
        self.missed_var.set(str(self.tracker.missed))

    def _reset_counters(self) -> None:
        self.tracker.reset()
        self.series.reset()
        self._update_counters()

    def _on_search_mode_selected(self) -> None:
        self.cfg.search_mode = SEARCH_MODES.get(self.search_mode_var.get(), "or")
        self.matcher.set_mode(self.cfg.search_mode)
        self._apply_search_mode_state()
        save_config(self.config_path, self.cfg)

    def _apply_search_mode_state(self) -> None:
        """Grey out what the search mode ignores: items for «Только слова», keywords for «Только предметы»."""
        mode = self.cfg.search_mode
        items_off = mode == "words"
        for widget in self.item_controls:
            widget.state(["disabled"] if items_off else ["!disabled"])
        self.item_list.set_enabled(not items_off)
        self.items_title.configure(text="Что искать  ·  не используется" if items_off else "Что искать")
        self.kw_entry.state(["disabled"] if mode == "items" else ["!disabled"])
        if hasattr(self, "feed"):
            self._feed_empty_state()

    def _feed_empty_state(self) -> None:
        """The empty feed says what will appear there and what is being looked for (UI/UX item 12)."""
        if self.feed.rows:
            return
        words, items = len(self.cfg.keywords), len(self.cfg.watch_items)
        missing = self._search_hint()
        hint = (f"Сейчас {missing}" if missing else
                f"Ищу: {plural(words, 'слово', 'слова', 'слов')}, {plural(items, 'предмет', 'предмета', 'предметов')}")
        if self.running:
            self.feed.show_empty("magnifying-glass", "Слежу — совпадений пока нет", hint)
        else:
            self.feed.show_empty("magnifying-glass", "Нажми Start — здесь появятся совпадения", hint)

    def _search_hint(self) -> str:
        """What the chosen search mode is missing, e.g. «нет ключевых слов»."""
        mode = self.cfg.search_mode
        no_words = not self.cfg.keywords and mode in ("words", "and", "or")
        no_items = not self.cfg.watch_items and mode in ("items", "and", "or")
        if mode == "or" and not (no_words and no_items):
            return ""
        missing = [text for flag, text in ((no_words, "нет ключевых слов"), (no_items, "не отмечены предметы")) if flag]
        return ", ".join(missing)

    def _on_react_selected(self) -> None:
        self.cfg.react_sec = REACT_CHOICES.get(self.react_var.get(), DEFAULT_REACT_SEC)
        self.tracker.react_sec = self.cfg.react_sec
        save_config(self.config_path, self.cfg)

    def _on_popup_toggled(self) -> None:
        self.cfg.nag_popup = self.popup_var.get()
        save_config(self.config_path, self.cfg)

    def _on_chat_settings(self, show_system: bool) -> None:
        self.cfg.chat_system = show_system
        save_config(self.config_path, self.cfg)

    def _on_volume_changed(self, save: bool = True) -> None:
        self.notifier.set_volume(self.volume_var.get())
        self.volume_label.configure(text=f"{self.notifier.volume}%")
        if save:
            self.cfg.sound_volume = self.notifier.volume
            save_config(self.config_path, self.cfg)

    def _on_tab_changed(self) -> None:
        self.root.after_idle(lambda: refresh_pointer_cursor(self.root))  # the page under the pointer changed
        if self.tabs.select() == str(self.all_chat):
            # the tab's own controls sit in the free space of the tab row, right side
            self.all_chat.toolbar.place(in_=self.tabs, relx=1.0, x=-2, y=2, anchor="ne")
            self.all_chat.toolbar.lift()
            self.all_chat.activate()
        else:
            self.all_chat.toolbar.place_forget()
            self.all_chat.deactivate()
        if self.tabs.select() == str(self.map_view):
            self.map_view.activate()
        if self.bestiary_view and self.tabs.select() == str(self.bestiary_view):
            self.bestiary_view.activate()

    def _on_root_resize(self, event: tk.Event) -> None:
        """Without the Windows hook: two size changes in quick succession mean a drag; the content returns after a pause."""
        if event.widget is not self.root or self._sizing_hook:
            return
        if self._frozen_tabs is None and self._thaw_after is None:
            # a single size change (showing the window, a programmatic resize) is not a drag: just watch for the next
            self._thaw_after = self.root.after(RESIZE_SETTLE_MS, self._thaw_tabs)
            return
        self._freeze_window()
        if self._thaw_after is not None:
            self.root.after_cancel(self._thaw_after)
        self._thaw_after = self.root.after(RESIZE_SETTLE_MS, self._thaw_tabs)

    def _freeze_window(self) -> None:
        """Take the whole window content (header and pages, every page keeps its state) out of the layout and show one
        still picture of it: nothing is laid out or drawn while the edge moves."""
        if self._frozen_tabs is not None:
            return
        picture = capture_widget(self.root)
        self._frozen_tabs = [(widget, widget.pack_info()) for widget in self.root.pack_slaves()]
        for widget, _info in self._frozen_tabs:
            widget.pack_forget()
        self._veil = tk.Frame(self.root, background=theme.BG)
        self._veil.pack_propagate(False)
        self._veil.pack(fill="both", expand=True)
        self._veil_photo = None
        if picture is not None:
            from PIL import ImageTk
            self._veil_photo = ImageTk.PhotoImage(picture, master=self.root)
            tk.Label(self._veil, image=self._veil_photo, background=theme.BG, borderwidth=0).place(x=0, y=0)

    def settle_layout(self) -> None:
        """Bring the tab pages back at once (tests and anything that reads the layout right after a resize)."""
        if getattr(self, "_thaw_after", None) is not None:  # not set yet while the window is still being built
            self.root.after_cancel(self._thaw_after)
        self._thaw_tabs()

    def _thaw_tabs(self) -> None:
        self._thaw_after = None
        if getattr(self, "_frozen_tabs", None) is None:
            return
        self._veil.destroy()
        for widget, info in self._frozen_tabs:  # in the original order, so nothing moves
            widget.pack(**info)
        self._frozen_tabs = None
        self.root.after_idle(lambda: refresh_pointer_cursor(self.root))

    # --- alerts --------------------------------------------------------------------
    def _on_feed_accept(self, alert_id: int) -> None:
        self._accept(alert_id)
        self._after_alert_change()

    def _accept(self, alert_id: int) -> None:
        """Accept an alert and every other waiting alert of the same series (same player and match)."""
        done = []
        for accepted in (alert_id, *sorted(self.series.accept(alert_id))):
            if self.tracker.accept(accepted):
                self.feed.mark(accepted, "accepted")
                done.append(accepted)
        self.alert_bridge.alerts_done(done)

    def _on_toast_action(self, event: Notification, action: str) -> None:
        """SN-4: «Принять» on a chat toast accepts its alerts; «Проверить снова» restarts watching; other actions open
        the source tab."""
        if action == "site":
            webbrowser.open(ARTICLE)
        elif action == "release" and self._release_note and (event.repeat_key or event.id) == self._release_note[0]:
            webbrowser.open(self._release_note[2])
        elif action == "accept" and self._release_note and (event.repeat_key or event.id) == self._release_note[0]:
            self.cfg.update_seen = self._release_note[1]  # this release is known: no toast at the next start
            save_config(self.config_path, self.cfg)
            self._release_note = None
        elif action == "accept" and self._update_note and (event.repeat_key or event.id) == self._update_note[0]:
            self.cfg.schedule_seen = self._update_note[1]  # SN-9: this site version is known, no toast at start
            save_config(self.config_path, self.cfg)
            self._update_note = None
        elif action == "accept":
            alerts = self.alert_bridge.toast_accepted(event)
            for alert_id in alerts:
                self._accept(alert_id)
            if alerts:
                self._after_alert_change()
        elif action == "retry":
            self.start()
        else:
            self._open_notification(event)

    def _on_popup_ack(self) -> None:
        accepted = self.tracker.accept_all()
        for alert_id in accepted:
            self.series.accept(alert_id)
            self.feed.mark(alert_id, "accepted")
        self.alert_bridge.alerts_done(accepted)
        self._after_alert_change()

    def _after_alert_change(self) -> None:
        if not self.tracker.pending_ids:
            self.alarm.close()
        self._update_counters()

    def _ui_tick(self, now: float | None = None) -> None:
        """Blink pending rows and move overdue ones to «missed»."""
        self._ui_after = None
        while hasattr(self, "_update_results") and not self._update_results.empty():
            self._on_update_result(*self._update_results.get_nowait())
        while hasattr(self, "_release_results") and not self._release_results.empty():
            self._on_release_result(self._release_results.get_nowait())
        current = time.monotonic() if now is None else now
        expired = self.tracker.expire(current)
        for alert_id in expired:
            self.feed.mark(alert_id, "missed")
        self.alert_bridge.alerts_done(expired)
        if expired:
            self._after_alert_change()
        if self.tracker.pending_ids:
            self.feed.set_countdown(self.tracker.remaining(current))
            self.feed.blink()
        if now is None:
            self._ui_after = self.root.after(UI_TICK_MS, self._ui_tick)

    def _build_items_panel(self, parent: ttk.Frame) -> None:
        """Right-hand list: checkbox + icon + name for each watchable item, with a search box."""
        panel = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10, 4, 10))
        self.items_panel = panel
        head = ttk.Frame(panel, style="Surface.TFrame")
        head.pack(fill="x", padx=(0, 8), pady=(0, 8))
        self.items_title = ttk.Label(head, text="Что искать", style="Title.TLabel")
        self.items_title.pack(side="left")
        clear = ttk.Button(head, text="Снять", style="Card.TButton", command=lambda: self._select_all_items(False),
                           width=0)  # ui:36: natural width instead of the theme's 11 characters
        clear.pack(side="right")
        select_all = ttk.Button(head, text="Все", style="Card.TButton", command=lambda: self._select_all_items(True),
                                width=0)
        select_all.pack(side="right", padx=6)
        self.item_controls: list[ttk.Widget] = [clear, select_all]
        self._icons: dict[str, tk.PhotoImage] = {}
        self.item_list = ItemList(
            panel,
            [item for item in self.watch_items if is_listed(item)],
            checked=self.cfg.watch_items,
            collapsed=self.cfg.collapsed_groups,
            icon_for=self._icon_for,
            on_change=self._on_items_changed,
            on_collapse=self._on_collapse,
            on_hover=self._schedule_tooltip,
            on_leave=self._hide_tooltip,
            item_filter=ItemFilter(
                set(self.cfg.filter_grades),
                self.cfg.filter_level_min,
                self.cfg.filter_level_max,
                self.cfg.filter_type,
            ),
            on_filter=self._on_filter,
        )
        self.item_list.pack(fill="both", expand=True)
        self.items_holder = self.item_list

    def _on_filter(self, item_filter: ItemFilter) -> None:
        self.cfg.filter_grades = sorted(item_filter.grades)
        self.cfg.filter_level_min = item_filter.level_min
        self.cfg.filter_level_max = item_filter.level_max
        self.cfg.filter_type = item_filter.type
        save_config(self.config_path, self.cfg)

    def _init_split(self) -> None:
        """Both sides are at least as wide as the item list's natural width; restore the saved width."""
        self.root.update_idletasks()
        min_width = self.items_panel.winfo_reqwidth()
        self.split.paneconfigure(self.items_panel, minsize=min_width)
        self.split.paneconfigure(self.split.panes()[0], minsize=min_width)
        # ui:28: at 125/150 % the control row and the map bar outgrow two list widths, and 600 px of height cut the
        # bottom of the panels — the minimum follows the widest row and the display scale (within the screen)
        scale = max(1.0, float(self.root.tk.call("tk", "scaling")) / (96 / 72))
        width = max(2 * min_width + 12 + 32, self.control_bar.winfo_reqwidth(), self.map_view.bar.winfo_reqwidth() + 48)
        height = max(600, min(round(600 * scale), self.root.winfo_screenheight() - 80))
        self.root.minsize(min(width, self.root.winfo_screenwidth()), height)
        if self.cfg.items_width:
            self.set_items_width(self.cfg.items_width)

    def set_items_width(self, width: int) -> None:
        """Move the divider so the item list is `width` px wide (clamped by the minimum sizes)."""
        self.root.update_idletasks()
        total = self.split.winfo_width()
        sash = self.split.cget("sashwidth")
        self.split.sash_place(0, max(0, total - width - int(sash)), 0)
        self.root.update_idletasks()

    def _on_split_moved(self) -> None:
        width = self.items_panel.winfo_width()
        if width > 1 and width != self.cfg.items_width:
            self.cfg.items_width = width
            save_config(self.config_path, self.cfg)

    def _on_collapse(self, collapsed: list[str]) -> None:
        self.cfg.collapsed_groups = collapsed
        save_config(self.config_path, self.cfg)

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        """Scroll the item list (or the schedule's weekday list) whenever the pointer is anywhere over it."""
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        steps = -event.delta // 120 or (-1 if event.delta > 0 else 1)
        if str(widget).startswith(str(self.items_holder)):
            self.item_list.scroll(steps * 2)
        elif str(widget).startswith(str(self.schedule_tab.day_canvas)):
            self.schedule_tab.scroll(steps)

    def _icon_for(self, item: WatchItem) -> tk.PhotoImage:
        """Icon from data/icons (shared by items with the same picture); a placeholder if missing."""
        key = Path(item.icon).stem if item.icon else item.id
        icon = self._icons.get(key)
        if icon is None:
            try:
                icon = theme.load_png(self.root, self.icons_dir / f"{key}.png")
            except tk.TclError:
                icon = self._icons.get("") or theme.placeholder_icon(self.root)
                self._icons[""] = icon
            self._icons[key] = icon
        return icon

    def _popup_icon(self, hits: list[str]) -> tk.PhotoImage | None:
        """The picture of the first watched item among the hits, at half size (28 px) for the alarm window."""
        names = {item.name.lower(): item for item in self.item_by_id.values()}
        item = next((names[h.lower()] for h in hits if h.lower() in names), None)
        if item is None:
            return None
        key = f"half:{item.id}"
        if key not in self._icons:
            self._icons[key] = self._icon_for(item).subsample(2)
        return self._icons[key]

    def _schedule_tooltip(self, item_id: str) -> None:
        self._hide_tooltip()
        self._tooltip_after = self.root.after(TOOLTIP_DELAY_MS, self._show_tooltip, item_id)

    def _show_tooltip(self, item_id: str) -> None:
        self._tooltip_after = None
        spec = self.specs.get(item_id)
        if spec is None:
            return
        x, y = self.root.winfo_pointerxy()
        item = self.item_by_id.get(item_id)
        if len(self.recipes):
            spec = with_recipe(spec, self.recipes.for_item(spec.get("name", ""), item_id))
        self.tooltip.show(spec, self._icon_for(item) if item else None, x, y)

    def _hide_tooltip(self) -> None:
        if self._tooltip_after is not None:
            self.root.after_cancel(self._tooltip_after)
            self._tooltip_after = None
        self.tooltip.hide()

    def _sound_choices(self) -> dict[str, str]:
        """Display name -> WAV path ("" = system beep). The configured custom file is kept."""
        choices = {SYSTEM_BEEP: ""}
        for path in system_sounds():
            choices[path.stem] = str(path)
        if self.cfg.sound_path and self.cfg.sound_path not in choices.values():
            choices[Path(self.cfg.sound_path).stem] = self.cfg.sound_path
        return choices

    def _sound_label(self, sound_path: str) -> str:
        return next((name for name, path in self.sound_choices.items() if path == sound_path), SYSTEM_BEEP)

    def _on_sound_selected(self) -> None:
        choice = self.sound_var.get()
        if choice == CUSTOM_SOUND:
            path = filedialog.askopenfilename(
                title="Звук оповещения", filetypes=[("WAV", "*.wav"), ("Все файлы", "*.*")]
            )
            if path:
                self._set_custom_sound(str(Path(path)))
            else:
                self.sound_var.set(self._sound_label(self.cfg.sound_path))
            return
        self._apply_sound(self.sound_choices.get(choice, ""))
        self.notifier.play()

    def _set_custom_sound(self, path: str) -> None:
        self.sound_choices[Path(path).stem] = path
        self.sound_box.configure(values=[*self.sound_choices, CUSTOM_SOUND])
        self.sound_var.set(Path(path).stem)
        self._apply_sound(path)

    def _apply_sound(self, path: str) -> None:
        self.cfg.sound_path = path
        self.notifier.sound_path = path
        save_config(self.config_path, self.cfg)

    def _on_mode_selected(self) -> None:
        self.cfg.alert_mode = ALERT_MODES.get(self.mode_var.get(), "standard")
        save_config(self.config_path, self.cfg)

    def _on_history_changed(self) -> None:
        self.cfg.history_min = HISTORY_CHOICES.get(self.history_var.get(), 0)
        save_config(self.config_path, self.cfg)
        self.all_chat.reload()

    def _checked_items(self) -> dict[str, str]:
        return {i: self.item_by_id[i].name for i in self.cfg.watch_items if i in self.item_by_id}

    def _on_items_changed(self) -> None:
        self.cfg.watch_items = self.item_list.checked_ids()
        self.matcher.set_watch_items(self._checked_items())
        save_config(self.config_path, self.cfg)
        self._feed_empty_state()

    def _select_all_items(self, value: bool) -> None:
        self.item_list.set_all(value)

    def _set_status(self, text: str) -> None:
        unchanged = self.status_var.get() == text
        if not unchanged:
            self._stop_status_pulse()
        self.status_var.set(text)
        short, style = short_status(text)
        self.status_short_var.set(short)
        # the chip's icon repeats its colour: green check, yellow warning, red warning, grey circle
        icon = {"Live.Chip.TLabel": ("check-circle", "success"), "Warn.Chip.TLabel": ("warning", "caution"),
                "Error.Chip.TLabel": ("warning", "warning")}.get(style, ("circle", "muted"))
        image = self.ui_icons.get(*icon, 16)
        self.status_label.configure(style=style, image=image)
        self.status_hint.text = text  # the full status (path, error) on hover
        if hasattr(self, "feed"):
            if text == GAME_OFF:
                self.feed.show_banner("Игра не запущена. После запуска Aion нажми «Проверить снова».",
                                      "Проверить снова", self.start)
            elif text.startswith("Chat.log не найден"):
                self.feed.show_banner("Не найден Chat.log. Проверь папку игры или выбери файл вручную.",
                                      "Обзор…", self._pick_dir)
            elif text.startswith("Ошибка чтения"):
                self.feed.show_banner("Не удалось прочитать Chat.log. Проверь путь и доступ к файлу.",
                                      "Обзор…", self._pick_dir)
            elif text.startswith("Ошибка:"):
                self.feed.show_banner("Сбой слежения. Проверь Chat.log и настройки программы.",
                                      "Обзор…", self._pick_dir)
            else:
                self.feed.hide_banner()
        if not unchanged and hasattr(self, "alert_bridge"):
            self.alert_bridge.game_running(text != GAME_OFF)
        if style == "Live.Chip.TLabel" and not self.cfg.reduce_motion and not unchanged:
            self._pulse_status(theme.SUCCESS, theme.SUCCESS_PULSE)

    def _pulse_status(self, start: str, end: str) -> None:
        from watcher.motion import tween_color
        generation = self._status_pulse_generation

        def paint(color: str) -> None:
            if generation == self._status_pulse_generation and self.status_short_var.get().startswith("Слежу"):
                self.status_label.configure(foreground=color)

        def cycle(color_a: str, color_b: str) -> None:
            if generation != self._status_pulse_generation or self.cfg.reduce_motion or not self.status_short_var.get().startswith("Слежу"):
                return
            tween_color(
                self.status_label, paint,
                color_a, color_b, 1000, enabled=True, steps=12,  # ~83 ms a frame: no visible steps (ui:21)
                done=lambda: schedule(color_b, color_a),
            )

        def schedule(a: str, b: str) -> None:
            if generation != self._status_pulse_generation or self.cfg.reduce_motion or not self.status_short_var.get().startswith("Слежу"):
                return
            self._status_pulse_after = self.root.after(1, lambda: cycle(a, b))

        cycle(start, end)

    def _stop_status_pulse(self) -> None:
        self._status_pulse_generation += 1
        if self._status_pulse_after is not None:
            try:
                self.root.after_cancel(self._status_pulse_after)
            except tk.TclError:
                pass
            self._status_pulse_after = None
        try:
            self.status_label.configure(foreground="")
        except tk.TclError:
            pass

    def _on_reduce_motion(self) -> None:
        self.cfg.reduce_motion = self.reduce_motion_var.get()
        self.alarm.reduce_motion = self.cfg.reduce_motion
        self.tooltip.reduce_motion = self.cfg.reduce_motion
        save_config(self.config_path, self.cfg)
        self._stop_status_pulse()
        if not self.cfg.reduce_motion and self.status_short_var.get().startswith("Слежу"):
            self._pulse_status(theme.SUCCESS, theme.SUCCESS_PULSE)

    def _pick_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.cfg.game_dir or None)
        if chosen:
            self.game_dir_var.set(str(Path(chosen)))
            self._apply_game_dir()

    def _apply_game_dir(self) -> None:
        """Accept a game folder or a full path to Chat.log; show the resulting Chat.log path."""
        text = self.game_dir_var.get().strip().strip('"')
        game_dir, chat_log = self.cfg.game_dir, self.cfg.chat_log
        if text:
            path = Path(text)
            if path.name.lower() == "chat.log":
                if path.parent.name.lower() == "classic":
                    game_dir, chat_log = str(path.parent.parent), ""
                else:
                    chat_log = str(path)
            else:
                game_dir, chat_log = str(path), ""
        self.game_dir_var.set(str(Path(game_dir) / "classic" / "Chat.log") if not chat_log else chat_log)
        if (game_dir, chat_log) == (self.cfg.game_dir, self.cfg.chat_log):
            return
        self.cfg.game_dir, self.cfg.chat_log = game_dir, chat_log
        save_config(self.config_path, self.cfg)
        if self.running:
            self.stop()
            self.start()

    def _apply_keywords(self) -> None:
        keywords = split_keywords(self.kw_var.get())
        if keywords == self.cfg.keywords:
            return
        self.cfg.keywords = keywords
        self.matcher.set_keywords(keywords)
        save_config(self.config_path, self.cfg)
        self._feed_empty_state()

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        self._apply_keywords()
        if self._game_closed():
            return
        self.running = True
        self.tailer = None
        self._scan_history = self.cfg.history_min > 0
        self.start_btn.configure(text="Stop", style="Danger.TButton")
        if self._scan_history:
            self.feed.show_empty("hourglass-medium", f"Читаю историю за {self.cfg.history_min} мин…", loading=True)
            self.root.update_idletasks()  # paint «reading» before the (blocking) read
        self._tick()

    def stop(self) -> None:
        self.running = False
        self.series.reset()
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.tailer = None
        self.start_btn.configure(text="Start", style="Accent.TButton")
        self._set_status("Остановлен")
        self._feed_empty_state()

    def _game_closed(self) -> bool:
        """Game check (config «game_check»): no aion.bin process -> stop watching and say so.

        An unreadable process list counts as «running», so a failed check never stops the watching.
        """
        self._last_game_check = time.monotonic()
        if not self.cfg.game_check or game_running() is not False:
            return False
        if self.running:
            self.stop()
        self._set_status(GAME_OFF)
        self.feed.add_note(f"— {datetime.now():%H:%M} {GAME_OFF}: запусти игру и нажми Start —")
        return True

    def _schedule(self, delay_ms: int) -> None:
        self._after_id = self.root.after(delay_ms, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
            return
        if time.monotonic() - self._last_game_check >= GAME_CHECK_SEC and self._game_closed():
            return
        path = self.cfg.chat_log_path()
        history: list[str] | None = None
        try:
            if self.tailer is None:
                tailer = LogTailer(str(path))
                tailer.start_at_end()
                self.tailer = tailer
                if self._scan_history:
                    since = datetime.now() - timedelta(minutes=self.cfg.history_min)
                    history = tailer.read_backlog(since)
                    self._scan_history = False
            lines = self.tailer.read_new_lines()
        except FileNotFoundError:
            self.tailer = None
            self._set_status(f"Chat.log не найден: {path}")
            self._schedule(RETRY_MS)
            return
        except OSError as exc:
            self._set_status(f"Ошибка чтения: {exc}")
            self._schedule(self.cfg.poll_interval_ms)
            return
        try:
            if history is not None:
                self._show_history(history)
            self._process(lines)
        except Exception as exc:
            # the status line shows one line; errors.log keeps the traceback, once per distinct error
            self._last_error = log_exception(self.error_log, "_tick", self._last_error)
            self._set_status(f"Ошибка: {exc}")
        else:
            self._last_error = ""
            hint = self._search_hint()
            self._set_status(f"Слежу за {path}" + (f"  ·  {hint}" if hint else ""))
            self._feed_empty_state()
        self._schedule(self.cfg.poll_interval_ms)

    def _show_history(self, lines: list[str]) -> None:
        """Matches from before Start: listed in the feed, but no sound, no alert, not counted."""
        now = time.monotonic()
        for line in lines:
            msg = parse_line(line, self.item_names)
            if msg is not None:
                self._remember_places(msg)
                hits = self.matcher.check(msg, now)
                if hits:
                    self.feed.add(msg, hits)
        self.feed.add_note(f"— выше история за {self.cfg.history_min} мин, ниже новые сообщения —")

    def _on_map_quests(self, on: bool) -> None:
        self.cfg.map_quests = on
        save_config(self.config_path, self.cfg)

    def _show_settings(self, open_: bool) -> None:
        """The «Настройки» card under the control row; the button names the action and shows the state."""
        self.settle_layout()  # the window content must be in place before the card is packed after the control row
        if open_:
            self.settings_card.pack(fill="x", padx=16, pady=(0, 6), after=self.control_bar)
        else:
            self.settings_card.pack_forget()
        self.settings_btn.configure(
            text="Настройки",
            image=self.ui_icons.get("caret-up" if open_ else "caret-down", "muted", 16),
        )

    def _toggle_settings(self) -> None:
        self.settle_layout()
        self.cfg.settings_open = not self.cfg.settings_open
        self._fold_settings(self.cfg.settings_open)
        save_config(self.config_path, self.cfg)

    def _fold_settings(self, open_: bool) -> None:
        """Grow or shrink the «Настройки» card over theme.MOTION base (ease-out); a click in the middle reverses from
        the current height; ends natural-height when open, unpacked when closed; instant with reduce_motion."""
        from watcher.motion import animate
        card = self.settings_card
        running = getattr(self, "_fold", None)
        if running is not None:
            running.cancel()
        shown = bool(card.winfo_manager())
        current = card.winfo_height() if shown else 0
        if open_ and not shown:
            card.pack_propagate(False)
            card.configure(height=1)
            self._show_settings(True)
        self.settings_btn.configure(image=self.ui_icons.get("caret-up" if open_ else "caret-down", "muted", 16))
        card.update_idletasks()
        card.pack_propagate(False)
        target = card.winfo_reqheight() if open_ else 0
        if open_:  # the natural height: measure with propagation for a moment
            card.pack_propagate(True)
            card.update_idletasks()
            target = card.winfo_reqheight()
            card.pack_propagate(False)
            card.configure(height=max(1, current))

        def finish() -> None:
            self._fold = None
            if open_:
                card.pack_propagate(True)
            else:
                self._show_settings(False)
                card.pack_propagate(True)

        self._fold = animate(card, current, target, theme.MOTION["base"],
                             lambda h: card.configure(height=max(1, int(h))),
                             enabled=not self.cfg.reduce_motion, done=finish)

    def _on_map_theme(self, theme: str) -> None:
        self.cfg.map_theme = theme
        save_config(self.config_path, self.cfg)

    def _on_map_side(self, side: str) -> None:
        self.cfg.map_side = side
        save_config(self.config_path, self.cfg)

    def _remember_places(self, msg: ChatMessage) -> None:
        note = f"{msg.time[11:16]}  {msg.nick}: {display_text(msg.text)}"
        for label, (map_id, x, y) in places_in(msg.text):
            self.places.append(Place(map_id, x, y, label, note))

    def _open_place(self, map_id: str, x: float, y: float, label: str) -> None:
        """Click on a place link: the zone map centred on it, with the other places from the chat."""
        self._hide_tooltip()
        self.tabs.select(self.map_view)
        self.map_view.show(Place(map_id, x, y, label))

    def _open_bestiary_point(
        self, map_id: str, x: float, y: float, label: str,
        points: list[dict], areas: list[dict],
    ) -> None:
        """Open a client spawn point selected in the Bestiary."""
        self.tabs.select(self.map_view)
        self.map_view.show(
            Place(map_id, x, y, label, "Точка появления из файлов клиента; серверная расстановка не подтверждена"),
            others=[
                Place(map_id, float(point["gx"]), float(point["gy"]), label, "Другая точка появления")
                for point in points
                if (float(point["gx"]), float(point["gy"])) != (x, y)
            ],
            source_label="Точка появления",
            spawn_areas=[area["polygon"] for area in areas],
        )
        self.map_view.search_var.set(label)
        self.map_view._run_mob_search(preserve_map=True)

    def _process(self, lines: list[str]) -> None:
        now = time.monotonic()
        matched: list[tuple[ChatMessage, list[str]]] = []
        for line in lines:
            msg = parse_line(line, self.item_names)
            if msg is None:
                continue
            self._remember_places(msg)
            hits = self.matcher.check(msg, now)
            if hits:
                matched.append((msg, hits))
        if not matched:
            return
        nag = self.cfg.alert_mode == "nag"
        loud: list[tuple[ChatMessage, list[str]]] = []
        for msg, hits in matched:
            if not nag:
                self.tracker.add(msg, hits, now, nag=False)
                self.feed.add(msg, hits, animate_new=True)
                loud.append((msg, hits))
            elif self.series.is_silent(msg, hits, now):
                # a repeat of a series the user already accepted: show it, no alarm
                self.tracker.add(msg, hits, now, nag=False)
                self.series.record(msg, hits, now)
                self.feed.add(msg, hits, quiet=True, animate_new=True)
            else:
                alert_id = self.tracker.add(msg, hits, now, nag=True)
                self.series.record(msg, hits, now, alert_id)
                self.feed.add(msg, hits, alert_id, animate_new=True)
                self.feed.set_countdown(self.tracker.remaining(now))
                loud.append((msg, hits))
        if loud:
            # SN-4: one toast per batch; standard mode beeps through the center (its per-source sound rule),
            # nag mode keeps the alarm's looping sound and the toast offers «Принять»
            waiting = [alert_id for alert_id in self.tracker.pending_ids if alert_id not in self._toasted_alerts]
            self._toasted_alerts.update(waiting)
            self.alert_bridge.chat_match(waiting, [(msg.nick, msg.text, hits) for msg, hits in loud], nag=nag)
        if loud and nag:
            self.alarm.trigger(loud, popup=self.cfg.nag_popup and OVERLAY_POPUP_ENABLED)
        self._update_counters()

    def _on_bell(self, key: str, on: bool) -> None:
        events = set(self.cfg.remind_events)
        (events.add if on else events.discard)(key)
        self.cfg.remind_events = sorted(events)
        save_config(self.config_path, self.cfg)

    def check_schedule_update(self, manual: bool) -> None:
        """SN-9: ask the site in a background thread (short timeout); the UI tick shows the answer."""
        def work() -> None:
            try:
                self._update_results.put(("ok", site_fingerprint(http_fetch), manual))
            except Exception as error:  # network, site layout: report on a manual check only
                self._update_results.put(("err", str(error), manual))
        threading.Thread(target=work, daemon=True).start()

    def check_release(self) -> None:
        """Ask GitHub for the latest release in the background; a private repo or no network gives no answer."""
        def work() -> None:
            try:
                body, _headers = http_fetch(RELEASE_API, "GET")
                self._release_results.put(latest_release(body))
            except Exception:
                self._release_results.put(None)
        threading.Thread(target=work, daemon=True).start()

    def _on_release_result(self, found: tuple[str, str] | None) -> None:
        if found is None or not newer(found[0], VERSION) or found[0] == self.cfg.update_seen:
            return
        note = self.notifications.notify(
            "app", "event", f"Доступна новая версия {found[0]}",
            "Открой страницу релиза и скачай новый Pulse.exe. Программа сама ничего не скачивает.",
            [NotificationAction("release", "Открыть релиз"), NotificationAction("accept", "Понятно")])
        if note is not None:
            self._release_note = (note.id, found[0], found[1])

    def _on_update_result(self, status: str, value: str, manual: bool) -> None:
        if status == "err":
            if manual:
                self.notifications.notify("schedule", "warning", "Не удалось проверить расписание", value[:120])
            return
        verdict = decide(self.schedule_known, value, self.cfg.schedule_seen, manual)
        if verdict == "same":
            self.notifications.notify("schedule", "event", "Расписание актуально",
                                      "Картинка в базе знаний та же, по которой составлена сетка программы.")
        elif verdict == "changed":
            note = self.notifications.notify(
                "schedule", "event", "Расписание на сайте обновилось",
                "Картинка в базе знаний новая — сверь сетку; data/schedule.json правится вручную.",
                [NotificationAction("site", "Открыть статью"), NotificationAction("accept", "Понятно")])
            if note is not None:
                self._update_note = (note.id, value)

    def _open_zone(self, map_id: str) -> None:
        """SN-7 «на карте»: the zone of a schedule event on the «Карта» tab."""
        self.tabs.select(self.map_view)
        self.map_view.open_zone(map_id)

    def _on_schedule_filter(self, hidden: set[str]) -> None:
        self.cfg.schedule_hidden = sorted(hidden)
        save_config(self.config_path, self.cfg)

    def _on_lead(self, minutes: int) -> None:
        self.cfg.remind_min = minutes
        save_config(self.config_path, self.cfg)

    def _check_reminders(self) -> None:
        """SN-8: a toast N minutes before a belled event and one when it starts; each occurrence once."""
        try:
            now = self._msk_clock()
            belled = [e for e in self.schedule_tab.events if bell_key(e) in self.schedule_tab.belled]
            lead = self.schedule_tab.lead_minutes()
            for event_id, end in list(self._reminder_ids.items()):
                if now >= end:  # the event is over: its reminder stops repeating
                    self.notifications.acknowledge(event_id)
                    del self._reminder_ids[event_id]
            for key, event, start in due_reminders(belled, now, lead, self._reminded):
                if (start - now).total_seconds() < 60:
                    continue  # the start toast below covers it
                self._reminded.add(key)
                self._remind(f"Через {lead_label(lead)}: {event['name']}", event, start)
            for event, start in next_events(belled, now, len(belled) + 1):
                key = bell_key(event) + "|start|" + start.isoformat()
                if 0 <= (now - start).total_seconds() < 120 and key not in self._reminded:
                    self._reminded.add(key)
                    self._remind(f"Началось: {event['name']}", event, start)
            self.cfg.remind_last_check = now.isoformat(timespec="seconds")
        finally:
            self._remind_after = self.root.after(REMIND_MS, self._check_reminders)

    def _remind(self, title: str, event: dict, start: datetime) -> None:
        """One reminder toast: «Понятно» stops it, «Через 5 мин» snoozes it, silence repeats it until the event ends."""
        end = end_of(event, start)
        note = self.notifications.notify(
            "schedule", "event", title, f"{time_range(start, end, self.schedule_tab.tz)} · расписание сервера",
            [NotificationAction("accept", "Понятно"), NotificationAction("snooze", "Через 5 мин")],
            repeat_after=REMIND_REPEAT_S,
        )
        if note is not None:
            self._reminder_ids[note.id] = end

    def _report_missed_reminders(self) -> None:
        """SN-8: belled events that started while the program was closed — one toast, at most a week back."""
        now = self._msk_clock()
        try:
            last = datetime.fromisoformat(self.cfg.remind_last_check)
        except ValueError:
            last = None
        self.cfg.remind_last_check = now.isoformat(timespec="seconds")
        save_config(self.config_path, self.cfg)
        if last is None:
            return
        last = max(last, now - timedelta(days=MISSED_DAYS))
        belled = [e for e in self.schedule_tab.events if bell_key(e) in self.schedule_tab.belled]
        missed = [(e, at) for e, at in occurrences_between(belled, last, now) if (now - at).total_seconds() >= 120]
        if not missed:
            return
        days = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        names = [f"{e['name']} ({days[at.weekday()]} {to_local(at, self.schedule_tab.tz):%H:%M})" for e, at in missed[:5]]
        more = f" и ещё {len(missed) - 5}" if len(missed) > 5 else ""
        self.notifications.notify("schedule", "event", f"Пропущено, пока программа была закрыта: {len(missed)}",
                                  ", ".join(names) + more)

    def _on_notify_settings(self) -> None:
        apply_notify_settings(self.cfg, self.notifications, self.toasts)
        save_config(self.config_path, self.cfg)

    def _preview_notification(self) -> None:
        self.notifications.notify(
            "preview", "chat", "Уведомления работают",
            "Наведите мышь, чтобы задержать карточку. Нажмите на неё, чтобы открыть «Поиск».",
            [NotificationAction("accept", "Принять"), NotificationAction("snooze", "Через 5 мин")],
        )

    def _open_notification(self, event: Notification) -> None:
        # Only an explicit user click brings the application to the foreground.
        tab_name = {"schedule": "Расписание", "map": "Карта"}.get(event.source, "Поиск")
        for tab in self.tabs.tabs():
            if self.tabs.tab(tab, "text") == tab_name:
                self.tabs.select(tab)
                break
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self) -> None:
        try:
            self._apply_keywords()
            self._apply_game_dir()
        finally:
            self.stop()
            self.toasts.close()
            self.cfg.remind_last_check = self._msk_clock().isoformat(timespec="seconds")  # SN-8: «missed while closed» starts here
            save_config(self.config_path, self.cfg)
            try:
                self.root.after_cancel(self._remind_after)
            except (tk.TclError, ValueError):
                pass
            self.alarm.close()
            self.all_chat.deactivate()
            if self._ui_after is not None:
                self.root.after_cancel(self._ui_after)
            self.root.destroy()
