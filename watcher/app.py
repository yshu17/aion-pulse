"""tkinter window: keywords, start/stop, list of matched messages."""

import time
import tkinter as tk
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, ttk

from watcher import theme
from watcher.alerts import AlertTracker
from watcher.allchat import AllChatView
from watcher.catalog import WatchItem, is_listed, load_item_names, load_watch_items, resource_root
from watcher.config import load_config, save_config
from watcher.matcher import Matcher, highlight_segments
from watcher.alarm import NagAlarm
from watcher.feed import MatchFeed
from watcher.itemlist import ItemFilter, ItemList
from watcher.notifier import Notifier, system_sounds
from watcher.mapview import MapView, Place, load_zones
from watcher.parser import MAP_NAMES, ChatMessage, display_text, parse_line, places_in
from watcher.series import SeriesTracker
from watcher.specs import load_specs
from watcher.tailer import LogTailer
from watcher.tooltip import SpecTooltip

MAX_ROWS = 500
MAX_PLACES = 300  # place links remembered for the map's pins
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


def short_status(text: str) -> tuple[str, str]:
    """Compact status for the folder row and its label style."""
    if text.startswith("Слежу"):
        hint = text.split("  ·  ", 1)[1] if "  ·  " in text else ""
        return ("● Слежу" + (f"  ·  {hint}" if hint else ""), "Live.TLabel")
    if text.startswith("Chat.log не найден"):
        return "⚠ Chat.log не найден", "Warn.TLabel"
    if text.startswith("Ошибка"):
        return "⚠ " + (text if len(text) <= 40 else text[:39] + "…"), "Warn.TLabel"
    return "○ Не слежу", "Status.TLabel"


def split_keywords(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


class App:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.cfg = load_config(config_path)
        data_dir = resource_root() / "data"
        self.item_names = load_item_names(data_dir / "item_names.tsv")
        self.watch_items = load_watch_items(data_dir / "watch_items.csv")
        self.item_by_id = {item.id: item for item in self.watch_items}
        self.icons_dir = data_dir / "icons"
        self.specs = load_specs(data_dir / "item_specs.json.gz")
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
        self.series = SeriesTracker()
        self.zones = load_zones(data_dir / "maps", MAP_NAMES)
        self.places: deque[Place] = deque(maxlen=MAX_PLACES)  # place links seen in «Поиск группы»
        self.tailer: LogTailer | None = None
        self.running = False
        self._after_id: str | None = None
        self._rows = 0
        self._scan_history = False
        self._tooltip_after: str | None = None
        self._build_ui()
        self._apply_search_mode_state()
        self.tooltip = SpecTooltip(root)
        self.alarm = NagAlarm(root, self.notifier, on_ack=self._on_popup_ack)
        self._set_status("Остановлен")
        self._update_counters()
        self._ui_after = root.after(UI_TICK_MS, self._ui_tick)

    def _build_ui(self) -> None:
        root = self.root
        root.title("Aion Chat Watcher")
        root.geometry("1400x860")
        root.minsize(1000, 600)
        theme.apply_dark_theme(root, resource_root() / "data" / "ui")
        theme.dark_title_bar(root)

        header = ttk.Frame(root, padding=(16, 12, 16, 4))
        header.pack(fill="x")
        self.header = header
        ttk.Label(header, text="Aion Chat Watcher", style="AppTitle.TLabel").pack(side="left")
        ttk.Label(header, text="  ·  Поиск группы", style="Muted.TLabel").pack(side="left", pady=(6, 0))

        top = ttk.Frame(root, padding=(16, 8))
        top.pack(fill="x")
        ttk.Label(top, text="Папка игры", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.game_dir_var = tk.StringVar(value=str(self.cfg.chat_log_path()))
        dir_entry = ttk.Entry(top, textvariable=self.game_dir_var)
        dir_entry.grid(row=0, column=1, sticky="ew", padx=(12, 12), pady=4)
        dir_entry.bind("<Return>", lambda _e: self._apply_game_dir())
        dir_entry.bind("<FocusOut>", lambda _e: self._apply_game_dir())
        self.status_short_var = tk.StringVar()
        self.status_label = ttk.Label(top, textvariable=self.status_short_var, style="Status.TLabel")
        self.browse_btn = ttk.Button(top, text="Обзор…", command=self._pick_dir)
        self.browse_btn.grid(row=0, column=2, pady=4, padx=(0, 12))
        self.status_label.grid(row=0, column=3, sticky="w")

        ttk.Label(top, text="Ключевые слова", style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        self.kw_var = tk.StringVar(value=", ".join(self.cfg.keywords))
        kw_entry = ttk.Entry(top, textvariable=self.kw_var)
        self.kw_entry = kw_entry
        kw_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(12, 12), pady=4)
        self.search_mode_var = tk.StringVar(
            value=next((k for k, v in SEARCH_MODES.items() if v == self.cfg.search_mode), "Слово ИЛИ предмет")
        )
        search_mode = ttk.Combobox(
            top, textvariable=self.search_mode_var, values=list(SEARCH_MODES), state="readonly", width=18
        )
        search_mode.grid(row=1, column=3, sticky="ew", pady=4)
        search_mode.bind("<<ComboboxSelected>>", lambda _e: self._on_search_mode_selected())
        kw_entry.bind("<Return>", lambda _e: self._apply_keywords())
        kw_entry.bind("<FocusOut>", lambda _e: self._apply_keywords())
        ttk.Label(top, text="Оповещение", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        alert = ttk.Frame(top)
        alert.grid(row=2, column=1, columnspan=3, sticky="w", padx=(12, 0), pady=4)
        self.mode_var = tk.StringVar(
            value=next((k for k, v in ALERT_MODES.items() if v == self.cfg.alert_mode), "Стандартный")
        )
        mode = ttk.Combobox(
            alert, textvariable=self.mode_var, values=list(ALERT_MODES), state="readonly", width=12
        )
        mode.pack(side="left")
        mode.bind("<<ComboboxSelected>>", lambda _e: self._on_mode_selected())
        ttk.Label(alert, text="Звук", style="Muted.TLabel").pack(side="left", padx=(18, 8))
        self.sound_choices = self._sound_choices()
        self.sound_var = tk.StringVar(value=self._sound_label(self.cfg.sound_path))
        self.sound_box = ttk.Combobox(
            alert,
            textvariable=self.sound_var,
            values=[*self.sound_choices, CUSTOM_SOUND],
            state="readonly",
            width=22,
        )
        self.sound_box.pack(side="left")
        self.sound_box.bind("<<ComboboxSelected>>", lambda _e: self._on_sound_selected())
        ttk.Button(alert, text="▶", width=3, command=self.notifier.play).pack(side="left", padx=8)
        ttk.Label(alert, text="Реакция", style="Muted.TLabel").pack(side="left", padx=(18, 8))
        self.react_var = tk.StringVar(
            value=next((k for k, v in REACT_CHOICES.items() if v == self.cfg.react_sec), "30 с")
        )
        react = ttk.Combobox(
            alert, textvariable=self.react_var, values=list(REACT_CHOICES), state="readonly", width=7
        )
        react.pack(side="left")
        react.bind("<<ComboboxSelected>>", lambda _e: self._on_react_selected())
        self.popup_var = tk.BooleanVar(value=self.cfg.nag_popup)
        ttk.Checkbutton(
            alert,
            text="Окно поверх игры",
            variable=self.popup_var,
            style="Plain.TCheckbutton",
            command=self._on_popup_toggled,
        ).pack(side="left", padx=(18, 0))
        ttk.Label(alert, text="Громкость", style="Muted.TLabel").pack(side="left", padx=(18, 8))
        self.volume_var = tk.IntVar(value=self.notifier.volume)
        ttk.Scale(
            alert,
            from_=0,
            to=100,
            orient="horizontal",
            length=120,
            variable=self.volume_var,
            command=lambda _v: self._on_volume_changed(save=False),
        ).pack(side="left")
        alert.winfo_children()[-1].bind("<ButtonRelease-1>", lambda _e: self._on_volume_changed())
        self.volume_label = ttk.Label(alert, text=f"{self.notifier.volume}%", style="Muted.TLabel", width=5)
        self.volume_label.pack(side="left", padx=(8, 0))
        top.columnconfigure(1, weight=1)

        bar = ttk.Frame(root, padding=(16, 6, 16, 10))
        bar.pack(fill="x")
        self.start_btn = ttk.Button(bar, text="Start", style="Accent.TButton", command=self.toggle)
        self.start_btn.pack(side="left")
        ttk.Label(bar, text="История", style="Muted.TLabel").pack(side="left", padx=(16, 6))
        minutes_to_choice = {m: c for c, m in HISTORY_CHOICES.items()}
        self.history_var = tk.StringVar(value=minutes_to_choice.get(self.cfg.history_min, "нет"))
        history = ttk.Combobox(
            bar,
            textvariable=self.history_var,
            values=list(HISTORY_CHOICES),
            state="readonly",
            width=7,
        )
        history.pack(side="left")
        history.bind("<<ComboboxSelected>>", lambda _e: self._on_history_changed())
        ttk.Label(bar, text="поиск при Start и «Весь чат»", style="Muted.TLabel").pack(side="left", padx=10)
        self.status_var = tk.StringVar()  # full status text; the folder row shows a short form

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.search_tab = ttk.Frame(self.tabs, padding=(0, 12, 0, 0))
        self.tabs.add(self.search_tab, text="Поиск")
        # feed | item list, split by a draggable divider
        self.split = tk.PanedWindow(
            self.search_tab,
            orient="horizontal",
            sashwidth=12,
            sashcursor="sb_h_double_arrow",
            opaqueresize=True,
            background=theme.BG,
            borderwidth=0,
        )
        self.split.pack(fill="both", expand=True)
        column = ttk.Frame(self.split)
        self.split.add(column, stretch="always")
        self._build_items_panel(self.split)
        self.split.add(self.items_panel, stretch="never")
        self.split.bind("<ButtonRelease-1>", lambda _e: self._on_split_moved(), add="+")
        root.after_idle(self._init_split)
        self._build_counters(header)
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
        )
        self.all_chat.configure(padding=(0, 12, 0, 0))
        self.tabs.add(self.all_chat, text="Весь чат")
        self.map_view = MapView(self.tabs, self.zones, get_places=lambda: list(self.places))
        self.map_view.configure(padding=(0, 12, 0, 0))
        self.tabs.add(self.map_view, text="Карта")
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab_changed())

        root.bind_all("<MouseWheel>", self._on_mouse_wheel, add="+")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_counters(self, parent: ttk.Frame) -> None:
        """Found / reacted / missed, in the header so they are visible on every tab."""
        self.counters_bar = ttk.Frame(parent)
        self.found_var = tk.StringVar()
        self.reacted_var = tk.StringVar()
        self.missed_var = tk.StringVar()
        for var, style in (
            (self.found_var, "Found.Counter.TLabel"),
            (self.reacted_var, "Reacted.Counter.TLabel"),
            (self.missed_var, "Missed.Counter.TLabel"),
        ):
            ttk.Label(self.counters_bar, textvariable=var, style=style).pack(side="left", padx=(0, 8))
        ttk.Button(self.counters_bar, text="Сбросить", command=self._reset_counters).pack(side="left")
        self.counters_bar.pack(side="right")

    def _update_counters(self) -> None:
        self.found_var.set(f"Найдено: {self.tracker.found}")
        self.reacted_var.set(f"Отреагировал: {self.tracker.reacted}")
        self.missed_var.set(f"Пропущено: {self.tracker.missed}")

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

    # --- alerts --------------------------------------------------------------------
    def _on_feed_accept(self, alert_id: int) -> None:
        self._accept(alert_id)
        self._after_alert_change()

    def _accept(self, alert_id: int) -> None:
        """Accept an alert and every other waiting alert of the same series (same player and match)."""
        for accepted in (alert_id, *sorted(self.series.accept(alert_id))):
            if self.tracker.accept(accepted):
                self.feed.mark(accepted, "accepted")

    def _on_popup_ack(self) -> None:
        for alert_id in self.tracker.accept_all():
            self.series.accept(alert_id)
            self.feed.mark(alert_id, "accepted")
        self._after_alert_change()

    def _after_alert_change(self) -> None:
        if not self.tracker.pending_ids:
            self.alarm.close()
        self._update_counters()

    def _ui_tick(self, now: float | None = None) -> None:
        """Blink pending rows and move overdue ones to «missed»."""
        self._ui_after = None
        current = time.monotonic() if now is None else now
        expired = self.tracker.expire(current)
        for alert_id in expired:
            self.feed.mark(alert_id, "missed")
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
        head.pack(fill="x", padx=(0, 8), pady=(0, 10))
        self.items_title = ttk.Label(head, text="Что искать", style="Title.TLabel")
        self.items_title.pack(side="left")
        clear = ttk.Button(head, text="Снять", style="Card.TButton", command=lambda: self._select_all_items(False))
        clear.pack(side="right")
        select_all = ttk.Button(head, text="Все", style="Card.TButton", command=lambda: self._select_all_items(True))
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
        self.root.minsize(2 * min_width + 12 + 32, 600)
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
        """Scroll the item list whenever the pointer is anywhere over it."""
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is not None and str(widget).startswith(str(self.items_holder)):
            steps = -event.delta // 120 or (-1 if event.delta > 0 else 1)
            self.item_list.scroll(steps * 2)

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

    def _select_all_items(self, value: bool) -> None:
        self.item_list.set_all(value)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        short, style = short_status(text)
        self.status_short_var.set(short)
        self.status_label.configure(style=style)

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

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        self._apply_keywords()
        self.running = True
        self.tailer = None
        self._scan_history = self.cfg.history_min > 0
        self.start_btn.configure(text="Stop", style="Danger.TButton")
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

    def _schedule(self, delay_ms: int) -> None:
        self._after_id = self.root.after(delay_ms, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
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
            self._set_status(f"Ошибка: {exc}")
        else:
            hint = self._search_hint()
            self._set_status(f"Слежу за {path}" + (f"  ·  {hint}" if hint else ""))
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

    def _remember_places(self, msg: ChatMessage) -> None:
        note = f"{msg.time[11:16]}  {msg.nick}: {display_text(msg.text)}"
        for label, (map_id, x, y) in places_in(msg.text):
            self.places.append(Place(map_id, x, y, label, note))

    def _open_place(self, map_id: str, x: float, y: float, label: str) -> None:
        """Click on a place link: the zone map centred on it, with the other places from the chat."""
        self._hide_tooltip()
        self.tabs.select(self.map_view)
        self.map_view.show(Place(map_id, x, y, label))

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
                self.feed.add(msg, hits)
                loud.append((msg, hits))
            elif self.series.is_silent(msg, hits, now):
                # a repeat of a series the user already accepted: show it, no alarm
                self.tracker.add(msg, hits, now, nag=False)
                self.series.record(msg, hits, now)
                self.feed.add(msg, hits, quiet=True)
            else:
                alert_id = self.tracker.add(msg, hits, now, nag=True)
                self.series.record(msg, hits, now, alert_id)
                self.feed.add(msg, hits, alert_id)
                self.feed.set_countdown(self.tracker.remaining(now))
                loud.append((msg, hits))
        if loud and nag:
            self.alarm.trigger(loud, popup=self.cfg.nag_popup)
        elif loud:
            self.notifier.play()
        self._update_counters()

    def _on_close(self) -> None:
        try:
            self._apply_keywords()
            self._apply_game_dir()
        finally:
            self.stop()
            self.alarm.close()
            self.all_chat.deactivate()
            if self._ui_after is not None:
                self.root.after_cancel(self._ui_after)
            self.root.destroy()
