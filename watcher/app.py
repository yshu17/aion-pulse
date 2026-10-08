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
REACT_CHOICES = {"выкл": 0, "15 с": 15, "30 с": 30, "60 с": 60, "2 мин": 120}
UI_TICK_MS = 500


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
            self.cfg.keywords, self.cfg.cooldown_sec, watch_items=self._checked_items()
        )
        self.notifier = Notifier(self.cfg.sound_path)
        self.tracker = AlertTracker(self.cfg.react_sec)
        self.tailer: LogTailer | None = None
        self.running = False
        self._after_id: str | None = None
        self._rows = 0
        self._scan_history = False
        self._tooltip_after: str | None = None
        self._build_ui()
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
        self.game_dir_var = tk.StringVar(value=self.cfg.game_dir)
        dir_entry = ttk.Entry(top, textvariable=self.game_dir_var)
        dir_entry.grid(row=0, column=1, sticky="ew", padx=(12, 6), pady=4)
        dir_entry.bind("<Return>", lambda _e: self._apply_game_dir())
        dir_entry.bind("<FocusOut>", lambda _e: self._apply_game_dir())
        ttk.Button(top, text="Обзор…", command=self._pick_dir).grid(row=0, column=2, pady=4)

        ttk.Label(top, text="Ключевые слова", style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        self.kw_var = tk.StringVar(value=", ".join(self.cfg.keywords))
        kw_entry = ttk.Entry(top, textvariable=self.kw_var)
        kw_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=4)
        kw_entry.bind("<Return>", lambda _e: self._apply_keywords())
        kw_entry.bind("<FocusOut>", lambda _e: self._apply_keywords())
        ttk.Label(top, text="Оповещение", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        alert = ttk.Frame(top)
        alert.grid(row=2, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=4)
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
            width=28,
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
        self.counters_var = tk.BooleanVar(value=self.cfg.show_counters)
        ttk.Checkbutton(
            alert,
            text="Счётчики",
            variable=self.counters_var,
            style="Plain.TCheckbutton",
            command=self._on_counters_toggled,
        ).pack(side="left", padx=(18, 0))
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
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side="left", padx=12)

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
            minutes=self.cfg.chat_minutes,
            show_system=self.cfg.chat_system,
            on_settings=self._on_chat_settings,
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
        if self.cfg.show_counters:
            self.counters_bar.pack(fill="x", pady=(0, 10), after=self._counters_anchor)

    def _update_counters(self) -> None:
        self.found_var.set(f"Найдено: {self.tracker.found}")
        self.reacted_var.set(f"Отреагировал: {self.tracker.reacted}")
        self.missed_var.set(f"Пропущено: {self.tracker.missed}")

    def _reset_counters(self) -> None:
        self.tracker.reset()
        self._update_counters()

    def _on_counters_toggled(self) -> None:
        self.cfg.show_counters = self.counters_var.get()
        if self.cfg.show_counters:
            self.counters_bar.pack(fill="x", pady=(0, 10), after=self._counters_anchor)
        else:
            self.counters_bar.pack_forget()
        save_config(self.config_path, self.cfg)

    def _on_react_selected(self) -> None:
        self.cfg.react_sec = REACT_CHOICES.get(self.react_var.get(), 30)
        self.tracker.react_sec = self.cfg.react_sec
        save_config(self.config_path, self.cfg)

    def _on_popup_toggled(self) -> None:
        self.cfg.nag_popup = self.popup_var.get()
        save_config(self.config_path, self.cfg)

    def _on_chat_settings(self, minutes: int, show_system: bool) -> None:
        self.cfg.chat_minutes = minutes
        self.cfg.chat_system = show_system
        save_config(self.config_path, self.cfg)

    def _on_tab_changed(self) -> None:
        if self.tabs.select() == str(self.all_chat):
            self.all_chat.activate()
        else:
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
        ttk.Label(head, text="Что искать", style="Title.TLabel").pack(side="left")
        ttk.Button(head, text="Снять", command=lambda: self._select_all_items(False)).pack(
            side="right"
        )
        ttk.Button(head, text="Все", command=lambda: self._select_all_items(True)).pack(
            side="right", padx=6
        )

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
        ttk.Checkbutton(
            head,
            text="все",
            variable=var,
            style="Group.TCheckbutton",
            command=lambda: self._on_group_toggled(category),
        ).pack(side="right")
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
        box = ttk.Checkbutton(
            parent,
            text=f"  {item.name}",
            image=icon or "",
            compound="left",
            variable=var,
            style="Item.TCheckbutton",
            command=self._on_items_changed,
        )
        box.pack(fill="x", pady=1, padx=(8, 0))
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
        live = text.startswith("Слежу")
        self.status_label.configure(style="Live.TLabel" if live else "Status.TLabel")

    def _pick_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.game_dir_var.get() or None)
        if chosen:
            self.game_dir_var.set(str(Path(chosen)))
            self._apply_game_dir()

    def _apply_game_dir(self) -> None:
        new_dir = self.game_dir_var.get().strip()
        if new_dir == self.cfg.game_dir:
            return
        self.cfg.game_dir = new_dir
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
            self._set_status(f"Слежу за {path}")
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
