"""tkinter window: keywords, start/stop, list of matched messages."""

import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, ttk

from watcher import theme
from watcher.alerts import AlertTracker
from watcher.allchat import AllChatView
from watcher.catalog import CATEGORY_ORDER, WatchItem, load_item_names, load_watch_items, resource_root
from watcher.config import load_config, save_config
from watcher.matcher import Matcher, highlight_segments
from watcher.alarm import NagAlarm
from watcher.feed import MatchFeed
from watcher.notifier import Notifier, system_sounds
from watcher.parser import ChatMessage, parse_line
from watcher.specs import load_specs
from watcher.tailer import LogTailer
from watcher.tooltip import SpecTooltip

MAX_ROWS = 500
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
        self.icons_dir = data_dir / "icons"
        self.specs = load_specs(data_dir / "item_specs.json")
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
        theme.apply_dark_theme(root)
        theme.dark_title_bar(root)

        header = ttk.Frame(root, padding=(16, 12, 16, 4))
        header.pack(fill="x")
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
        self.status_label.grid(row=0, column=2, sticky="w", padx=(0, 12))
        ttk.Button(top, text="Обзор…", command=self._pick_dir).grid(row=0, column=3, pady=4)

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
        self._build_items_panel(self.search_tab)
        column = ttk.Frame(self.search_tab)
        column.pack(side="left", fill="both", expand=True)
        self._build_counters(column)
        self.feed = MatchFeed(column, on_accept=self._on_feed_accept, max_rows=MAX_ROWS)
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
        )
        self.all_chat.configure(padding=(0, 12, 0, 0))
        self.tabs.add(self.all_chat, text="Весь чат")
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab_changed())

        root.bind_all("<MouseWheel>", self._on_mouse_wheel, add="+")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_counters(self, parent: ttk.Frame) -> None:
        self._counters_anchor = ttk.Frame(parent, height=1)
        self._counters_anchor.pack(fill="x")
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
        self.counters_bar.pack(fill="x", pady=(0, 10), after=self._counters_anchor)

    def _update_counters(self) -> None:
        self.found_var.set(f"Найдено: {self.tracker.found}")
        self.reacted_var.set(f"Отреагировал: {self.tracker.reacted}")
        self.missed_var.set(f"Пропущено: {self.tracker.missed}")

    def _reset_counters(self) -> None:
        self.tracker.reset()
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

    # --- alerts --------------------------------------------------------------------
    def _on_feed_accept(self, alert_id: int) -> None:
        if self.tracker.accept(alert_id):
            self.feed.mark(alert_id, "accepted")
        self._after_alert_change()

    def _on_popup_ack(self) -> None:
        for alert_id in self.tracker.accept_all():
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
        """Right-hand list: checkbox + icon + name for each watchable item."""
        panel = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10, 4, 10))
        panel.pack(side="right", fill="y", padx=(12, 0))
        head = ttk.Frame(panel, style="Card.TFrame")
        head.pack(fill="x", padx=(0, 8))
        self.items_title = ttk.Label(head, text="Что искать", style="Title.TLabel")
        self.items_title.pack(side="left")
        clear = ttk.Button(head, text="Снять", command=lambda: self._select_all_items(False))
        clear.pack(side="right")
        select_all = ttk.Button(head, text="Все", command=lambda: self._select_all_items(True))
        select_all.pack(side="right", padx=6)
        self.item_controls: list[ttk.Widget] = [clear, select_all]

        holder = ttk.Frame(panel, style="Card.TFrame")
        holder.pack(fill="both", expand=True, pady=(10, 0))
        canvas = tk.Canvas(
            holder, width=520, highlightthickness=0, borderwidth=0, background=theme.SURFACE
        )
        scroll = ttk.Scrollbar(holder, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, style="Card.TFrame")
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        self.items_holder = holder
        self.items_canvas = canvas

        checked = set(self.cfg.watch_items)
        self.item_vars: dict[str, tk.BooleanVar] = {}
        self._icons: dict[str, tk.PhotoImage] = {}
        self.groups: dict[str, list[str]] = {}
        for category in CATEGORY_ORDER:
            ids = [item.id for item in self.watch_items if item.category == category]
            if ids:
                self.groups[category] = ids
        self.group_vars: dict[str, tk.BooleanVar] = {}
        self.group_bodies: dict[str, ttk.Frame] = {}
        self._group_titles: dict[str, ttk.Label] = {}
        self._group_heads: dict[str, ttk.Frame] = {}
        by_id = {item.id: item for item in self.watch_items}
        for category, ids in self.groups.items():
            body = self._build_group(inner, category, len(ids))
            for item_id in ids:
                self._build_item_row(body, by_id[item_id], item_id in checked)
            self._sync_group(category)

    def _build_group(self, parent: ttk.Frame, category: str, count: int) -> ttk.Frame:
        """Section header (click to fold, checkbox for the whole group) and its body frame."""
        head = ttk.Frame(parent, style="Group.TFrame", padding=(6, 4))
        head.pack(fill="x", pady=(8, 2))
        title = ttk.Label(head, style="Group.TLabel", cursor="hand2")
        title.pack(side="left", fill="x", expand=True)
        title.bind("<Button-1>", lambda _e: self._toggle_collapsed(category))
        self._group_titles[category] = title
        var = tk.BooleanVar(value=False)
        self.group_vars[category] = var
        group_box = ttk.Checkbutton(
            head,
            text="все",
            variable=var,
            style="Group.TCheckbutton",
            command=lambda: self._on_group_toggled(category),
        )
        group_box.pack(side="right")
        self.item_controls.append(group_box)
        body = ttk.Frame(parent, style="Card.TFrame")
        self._group_heads[category] = head
        self.group_bodies[category] = body
        if category not in self.cfg.collapsed_groups:
            body.pack(fill="x", after=head)
        self._update_group_title(category, count)
        return body

    def _update_group_title(self, category: str, count: int | None = None) -> None:
        count = len(self.groups.get(category, [])) if count is None else count
        arrow = "▸" if category in self.cfg.collapsed_groups else "▾"
        self._group_titles[category].configure(text=f"{arrow}  {category}  ·  {count}")

    def _build_item_row(self, parent: ttk.Frame, item: WatchItem, is_checked: bool) -> None:
        var = tk.BooleanVar(value=is_checked)
        self.item_vars[item.id] = var
        icon = self._load_icon(item.id)
        dim = self._load_dim_icon(item.id)
        box = ttk.Checkbutton(
            parent,
            text=f"  {item.name}",
            image=(icon, "disabled", dim) if dim is not None else icon,
            compound="left",
            variable=var,
            style="Item.TCheckbutton",
            command=self._on_items_changed,
        )
        box.pack(fill="x", pady=1, padx=(8, 0))
        self.item_controls.append(box)
        box.bind("<Enter>", lambda _e, item_id=item.id: self._schedule_tooltip(item_id))
        box.bind("<Leave>", lambda _e: self._hide_tooltip())

    def _toggle_collapsed(self, category: str) -> None:
        body = self.group_bodies[category]
        if category in self.cfg.collapsed_groups:
            self.cfg.collapsed_groups.remove(category)
            body.pack(fill="x", after=self._group_heads[category])
        else:
            self.cfg.collapsed_groups.append(category)
            body.pack_forget()
        self._update_group_title(category)
        save_config(self.config_path, self.cfg)

    def _on_group_toggled(self, category: str) -> None:
        value = self.group_vars[category].get()
        for item_id in self.groups[category]:
            self.item_vars[item_id].set(value)
        self._on_items_changed()

    def _sync_group(self, category: str) -> None:
        ids = self.groups[category]
        self.group_vars[category].set(all(self.item_vars[i].get() for i in ids))

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        """Scroll the item list whenever the pointer is anywhere over it."""
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is not None and str(widget).startswith(str(self.items_holder)):
            steps = -event.delta // 120 or (-1 if event.delta > 0 else 1)
            self.items_canvas.yview_scroll(steps, "units")

    def _load_icon(self, item_id: str) -> tk.PhotoImage | None:
        path = self.icons_dir / f"{item_id}.png"
        try:
            icon = tk.PhotoImage(master=self.root, file=str(path))
        except tk.TclError:
            icon = theme.placeholder_icon(self.root)
        self._icons[item_id] = icon
        return icon

    def _load_dim_icon(self, item_id: str) -> tk.PhotoImage | None:
        """Greyed icon for the disabled list (data/icons/<id>_off.png); None if there is none."""
        try:
            dim = tk.PhotoImage(master=self.root, file=str(self.icons_dir / f"{item_id}_off.png"))
        except tk.TclError:
            return None
        self._icons[f"{item_id}_off"] = dim
        return dim

    def _schedule_tooltip(self, item_id: str) -> None:
        self._hide_tooltip()
        self._tooltip_after = self.root.after(TOOLTIP_DELAY_MS, self._show_tooltip, item_id)

    def _show_tooltip(self, item_id: str) -> None:
        self._tooltip_after = None
        spec = self.specs.get(item_id)
        if spec is None:
            return
        x, y = self.root.winfo_pointerxy()
        self.tooltip.show(spec, self._icons.get(item_id), x, y)

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
        names = {item.id: item.name for item in self.watch_items}
        return {item_id: names[item_id] for item_id in self.cfg.watch_items if item_id in names}

    def _on_items_changed(self) -> None:
        self.cfg.watch_items = [item_id for item_id, var in self.item_vars.items() if var.get()]
        self.matcher.set_watch_items(self._checked_items())
        for category in self.groups:
            self._sync_group(category)
        save_config(self.config_path, self.cfg)

    def _select_all_items(self, value: bool) -> None:
        for var in self.item_vars.values():
            var.set(value)
        self._on_items_changed()

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
                hits = self.matcher.check(msg, now)
                if hits:
                    self.feed.add(msg, hits)
        self.feed.add_note(f"— выше история за {self.cfg.history_min} мин, ниже новые сообщения —")

    def _process(self, lines: list[str]) -> None:
        now = time.monotonic()
        matched: list[tuple[ChatMessage, list[str]]] = []
        for line in lines:
            msg = parse_line(line, self.item_names)
            if msg is None:
                continue
            hits = self.matcher.check(msg, now)
            if hits:
                matched.append((msg, hits))
        if not matched:
            return
        nag = self.cfg.alert_mode == "nag"
        for msg, hits in matched:
            alert_id = self.tracker.add(msg, hits, now, nag=nag)
            self.feed.add(msg, hits, alert_id if nag else None)
            if nag:
                self.feed.set_countdown(self.tracker.remaining(now))
        if nag:
            self.alarm.trigger(matched, popup=self.cfg.nag_popup)
        else:
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
