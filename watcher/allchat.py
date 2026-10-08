"""«Весь чат» tab: plain live view of the whole chat log, starting N minutes back."""

import tkinter as tk
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from tkinter import ttk

from watcher import theme
from watcher.parser import ChatLine, parse_any_line
from watcher.tailer import LogTailer

POLL_MS = 500
RETRY_MS = 2000
MAX_ROWS = 2000
PERIODS = {"5 мин": 5, "10 мин": 10, "15 мин": 15, "20 мин": 20, "30 мин": 30, "45 мин": 45, "60 мин": 60}
CHANNEL_COLORS = [
    ("3.", "#ffb45e"),  # «Поиск группы»
    ("2.", "#7fd48a"),  # «Торговля»
    ("1.", "#9cc4ff"),
    ("Группа", "#6fc7ff"),
    ("Легион", "#c39bff"),
]
WHISPER = "#ff8fd0"


def channel_color(line: ChatLine) -> str:
    if line.channel is None:
        return WHISPER if line.is_player else theme.MUTED
    for prefix, color in CHANNEL_COLORS:
        if line.channel.startswith(prefix):
            return color
    return theme.MUTED


class AllChatView(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        get_path: Callable[[], str],
        names: Mapping[str, str],
        minutes: int,
        show_system: bool,
        on_settings: Callable[..., None],
    ) -> None:
        super().__init__(parent)
        self.get_path = get_path
        self.names = names
        self.on_settings = on_settings
        self.tailer: LogTailer | None = None
        self.paused = False
        self.active = False
        self._after_id: str | None = None
        self._held: list[str] = []
        self._rows = 0
        self._build(minutes, show_system)

    # --- UI -----------------------------------------------------------------------
    def _build(self, minutes: int, show_system: bool) -> None:
        bar = ttk.Frame(self, padding=(0, 0, 0, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="Показать за", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        label = next((k for k, v in PERIODS.items() if v == minutes), "15 мин")
        self.minutes_var = tk.StringVar(value=label)
        period = ttk.Combobox(
            bar, textvariable=self.minutes_var, values=list(PERIODS), state="readonly", width=7
        )
        period.pack(side="left")
        period.bind("<<ComboboxSelected>>", lambda _e: self._on_settings_changed())
        self.system_var = tk.BooleanVar(value=show_system)
        ttk.Checkbutton(
            bar,
            text="Системные сообщения",
            variable=self.system_var,
            style="Plain.TCheckbutton",
            command=self._on_settings_changed,
        ).pack(side="left", padx=16)
        self.pause_btn = ttk.Button(bar, text="Пауза", command=self.toggle_pause)
        self.pause_btn.pack(side="left")
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").pack(side="left", padx=12)

        card = ttk.Frame(self, style="Card.TFrame", padding=2)
        card.pack(fill="both", expand=True)
        self.text = tk.Text(card, wrap="word", state="disabled")
        theme.style_text(self.text)
        scroll = ttk.Scrollbar(card, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self._color_tags: dict[str, str] = {}

    def _tag_for(self, color: str) -> str:
        tag = self._color_tags.get(color)
        if tag is None:
            tag = f"ch{len(self._color_tags)}"
            self.text.tag_configure(tag, foreground=color)
            self._color_tags[color] = tag
        return tag

    # --- lifecycle ------------------------------------------------------------------
    def activate(self) -> None:
        """Start (or restart) the view: load the chosen period, then follow the log."""
        self.deactivate()
        self.active = True
        self._clear()
        self._held = []
        self._open(with_history=True)

    def deactivate(self) -> None:
        self.active = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.tailer = None

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_btn.configure(text="Продолжить" if self.paused else "Пауза")
        if not self.paused and self._held:
            held, self._held = self._held, []
            self._show(held)

    def _on_settings_changed(self) -> None:
        minutes = PERIODS.get(self.minutes_var.get(), 15)
        self.on_settings(minutes=minutes, show_system=self.system_var.get())
        if self.active:
            self.activate()

    # --- reading ----------------------------------------------------------------------
    def _open(self, with_history: bool) -> None:
        path = self.get_path()
        try:
            tailer = LogTailer(path)
            tailer.start_at_end()
            lines = []
            if with_history:
                since = datetime.now() - timedelta(minutes=PERIODS.get(self.minutes_var.get(), 15))
                lines = tailer.read_backlog(since)
        except FileNotFoundError:
            self.status_var.set(f"Chat.log не найден: {path}")
            self._schedule(RETRY_MS, retry=True)
            return
        except OSError as exc:
            self.status_var.set(f"Ошибка чтения: {exc}")
            self._schedule(RETRY_MS, retry=True)
            return
        self.tailer = tailer
        self.status_var.set("")
        self._show(lines)
        if with_history:
            self.text.after_idle(lambda: self.text.yview_moveto(1.0))  # open at the newest line
        self._schedule(POLL_MS)

    def _schedule(self, delay_ms: int, retry: bool = False) -> None:
        if self.active:
            callback = (lambda: self._open(with_history=False)) if retry else self._poll
            self._after_id = self.after(delay_ms, callback)

    def _poll(self) -> None:
        self._after_id = None
        if not self.active or self.tailer is None:
            return
        try:
            lines = self.tailer.read_new_lines()
        except FileNotFoundError:
            self.tailer = None
            self._schedule(RETRY_MS, retry=True)
            return
        except OSError as exc:
            self.status_var.set(f"Ошибка чтения: {exc}")
            lines = []
        if self.paused:
            self._held.extend(lines)
        else:
            self._show(lines)
        self._schedule(POLL_MS)

    # --- rendering --------------------------------------------------------------------
    def _clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._rows = 0

    def _show(self, raw_lines: list[str]) -> None:
        show_system = self.system_var.get()
        parsed = [parse_any_line(raw, self.names) for raw in raw_lines]
        rows = [p for p in parsed if p is not None and (p.is_player or show_system)]
        if not rows:
            return
        at_bottom = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        for line in rows:
            parts: list = [f"{line.time[11:]}  ", ("meta",)]
            if line.channel:
                parts += [f"[{line.channel}] ", (self._tag_for(channel_color(line)),)]
            if line.nick:
                parts += [f"{line.nick}: ", ("nick",)]
                parts += [line.text, ()]
            else:
                parts += [line.text, (self._tag_for(theme.MUTED),)]
            parts += ["\n", ()]
            self.text.insert("end", *parts)
        self._rows += len(rows)
        if self._rows > MAX_ROWS:
            self.text.delete("1.0", f"{self._rows - MAX_ROWS + 1}.0")
            self._rows = MAX_ROWS
        self.text.configure(state="disabled")
        if at_bottom:
            self.text.see("end")
