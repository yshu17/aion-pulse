"""tkinter window: keywords, start/stop, list of matched messages."""

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from watcher.config import load_config, save_config
from watcher.matcher import Matcher, highlight_segments
from watcher.notifier import Notifier
from watcher.parser import ChatMessage, parse_line
from watcher.tailer import LogTailer

MAX_ROWS = 500
RETRY_MS = 2000


def split_keywords(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


class App:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.cfg = load_config(config_path)
        self.matcher = Matcher(self.cfg.keywords, self.cfg.cooldown_sec)
        self.notifier = Notifier(self.cfg.sound_path)
        self.tailer: LogTailer | None = None
        self.running = False
        self._after_id: str | None = None
        self._rows = 0
        self._build_ui()
        self._set_status("Остановлен")

    def _build_ui(self) -> None:
        root = self.root
        root.title("Aion Chat Watcher")
        root.geometry("760x480")

        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Папка игры:").grid(row=0, column=0, sticky="w")
        self.game_dir_var = tk.StringVar(value=self.cfg.game_dir)
        dir_entry = ttk.Entry(top, textvariable=self.game_dir_var)
        dir_entry.grid(row=0, column=1, sticky="ew", padx=4)
        dir_entry.bind("<Return>", lambda _e: self._apply_game_dir())
        dir_entry.bind("<FocusOut>", lambda _e: self._apply_game_dir())
        ttk.Button(top, text="…", width=3, command=self._pick_dir).grid(row=0, column=2)

        ttk.Label(top, text="Ключевые слова:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.kw_var = tk.StringVar(value=", ".join(self.cfg.keywords))
        kw_entry = ttk.Entry(top, textvariable=self.kw_var)
        kw_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=4, pady=(6, 0))
        kw_entry.bind("<Return>", lambda _e: self._apply_keywords())
        kw_entry.bind("<FocusOut>", lambda _e: self._apply_keywords())
        top.columnconfigure(1, weight=1)

        bar = ttk.Frame(root, padding=(8, 0))
        bar.pack(fill="x")
        self.start_btn = ttk.Button(bar, text="Start", command=self.toggle)
        self.start_btn.pack(side="left")
        ttk.Button(bar, text="Тест звука", command=self.notifier.play).pack(side="left", padx=6)
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=10)

        frame = ttk.Frame(root, padding=8)
        frame.pack(fill="both", expand=True)
        self.text = tk.Text(frame, wrap="word", state="disabled", font=("Segoe UI", 10))
        scroll = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("meta", foreground="#888888")
        self.text.tag_configure("nick", font=("Segoe UI", 10, "bold"))
        self.text.tag_configure("hit", background="#ffe066", foreground="#000000")

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

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
        self.start_btn.configure(text="Stop")
        self._tick()

    def stop(self) -> None:
        self.running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.tailer = None
        self.start_btn.configure(text="Start")
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
        self._set_status(f"Слежу за {path}")
        self._process(lines)
        self._schedule(self.cfg.poll_interval_ms)

    def _process(self, lines: list[str]) -> None:
        now = time.monotonic()
        matched = False
        for line in lines:
            msg = parse_line(line)
            if msg is None:
                continue
            if self.matcher.check(msg, now):
                self._add_row(msg)
                matched = True
        if matched:
            self.notifier.play()

    def _add_row(self, msg: ChatMessage) -> None:
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        for chunk, is_hit in highlight_segments(msg.text, self.matcher.keywords):
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
        self._apply_keywords()
        self._apply_game_dir()
        self.stop()
        self.root.destroy()
