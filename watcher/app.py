"""tkinter window: keywords, start/stop, list of matched messages."""

import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, ttk

from watcher import theme
from watcher.catalog import load_item_names, load_watch_items, resource_root
from watcher.config import load_config, save_config
from watcher.matcher import Matcher, highlight_segments
from watcher.notifier import Notifier
from watcher.parser import ChatMessage, parse_line
from watcher.specs import load_specs
from watcher.tailer import LogTailer
from watcher.tooltip import SpecTooltip

MAX_ROWS = 500
RETRY_MS = 2000
TOOLTIP_DELAY_MS = 300
HISTORY_CHOICES = {"нет": 0, "1 мин": 1, "2 мин": 2, "3 мин": 3}


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
        self.tailer: LogTailer | None = None
        self.running = False
        self._after_id: str | None = None
        self._rows = 0
        self._scan_history = False
        self._tooltip_after: str | None = None
        self._build_ui()
        self.tooltip = SpecTooltip(root)
        self._set_status("Остановлен")

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
        top.columnconfigure(1, weight=1)

        bar = ttk.Frame(root, padding=(16, 6, 16, 10))
        bar.pack(fill="x")
        self.start_btn = ttk.Button(bar, text="Start", style="Accent.TButton", command=self.toggle)
        self.start_btn.pack(side="left")
        ttk.Button(bar, text="Тест звука", command=self.notifier.play).pack(side="left", padx=8)
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

        body = ttk.Frame(root, padding=(16, 0, 16, 16))
        body.pack(fill="both", expand=True)
        self._build_items_panel(body)
        card = ttk.Frame(body, style="Card.TFrame", padding=2)
        card.pack(side="left", fill="both", expand=True)
        self.text = tk.Text(card, wrap="word", state="disabled")
        theme.style_text(self.text)
        scroll = ttk.Scrollbar(card, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        root.bind_all("<MouseWheel>", self._on_mouse_wheel, add="+")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

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
        for item in self.watch_items:
            var = tk.BooleanVar(value=item.id in checked)
            self.item_vars[item.id] = var
            icon = self._load_icon(item.id)
            box = ttk.Checkbutton(
                inner,
                text=f"  {item.name}",
                image=icon or "",
                compound="left",
                variable=var,
                style="Item.TCheckbutton",
                command=self._on_items_changed,
            )
            box.pack(fill="x", pady=1)
            box.bind("<Enter>", lambda _e, item_id=item.id: self._schedule_tooltip(item_id))
            box.bind("<Leave>", lambda _e: self._hide_tooltip())

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
            return None
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

    def _on_history_changed(self) -> None:
        self.cfg.history_min = HISTORY_CHOICES.get(self.history_var.get(), 0)
        save_config(self.config_path, self.cfg)

    def _checked_items(self) -> dict[str, str]:
        names = {item.id: item.name for item in self.watch_items}
        return {item_id: names[item_id] for item_id in self.cfg.watch_items if item_id in names}

    def _on_items_changed(self) -> None:
        self.cfg.watch_items = [item_id for item_id, var in self.item_vars.items() if var.get()]
        self.matcher.set_watch_items(self._checked_items())
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
        try:
            if self.tailer is None:
                tailer = LogTailer(str(path))
                tailer.start_at_end()
                self.tailer = tailer
                backlog = []
                if self._scan_history:
                    since = datetime.now() - timedelta(minutes=self.cfg.history_min)
                    backlog = tailer.read_backlog(since)
                    self._scan_history = False
                lines = backlog + tailer.read_new_lines()
            else:
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
            self._process(lines)
        except Exception as exc:
            self._set_status(f"Ошибка: {exc}")
        else:
            self._set_status(f"Слежу за {path}")
        self._schedule(self.cfg.poll_interval_ms)

    def _process(self, lines: list[str]) -> None:
        now = time.monotonic()
        matched = False
        for line in lines:
            msg = parse_line(line, self.item_names)
            if msg is None:
                continue
            hits = self.matcher.check(msg, now)
            if hits:
                self._add_row(msg, hits)
                matched = True
        if matched:
            self.notifier.play()

    def _add_row(self, msg: ChatMessage, hits: list[str]) -> None:
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        for chunk, is_hit in highlight_segments(msg.text, hits):
            parts += [chunk, ("hit",) if is_hit else ()]
        parts += ["\n", ()]
        self.text.configure(state="normal")
        self.text.insert("1.0", *parts)
        self._rows += 1
        if self._rows > MAX_ROWS:
            self.text.delete(f"{MAX_ROWS + 1}.0", "end")
            self._rows = MAX_ROWS
        self.text.configure(state="disabled")

    def _on_close(self) -> None:
        try:
            self._apply_keywords()
            self._apply_game_dir()
        finally:
            self.stop()
            self.root.destroy()
