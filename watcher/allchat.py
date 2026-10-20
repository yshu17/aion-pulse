"""«Весь чат» tab: plain live view of the whole chat log, starting N minutes back."""

import re
import tkinter as tk
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from tkinter import ttk

from watcher import theme
from watcher.catalog import resource_root
from watcher.emptystate import EmptyState
from watcher.ui_icons import IconSet
from watcher.parser import ChatLine, parse_any_line
from watcher.tailer import LogTailer
from watcher.textview import ITEM_COLOR, BottomAnchor, CopyMenu, ItemLinker

POLL_MS = 500
RETRY_MS = 2000
MAX_ROWS = 2000
# Shown categories and their colours. Channel-less player lines are told apart by the name colour
# the game writes into [charname:Name;r g b] (Aion's default chat colours).
CATEGORY_COLORS = theme.CHAT_COLORS
_NAME_COLORS = {
    "1.0000 1.0000 1.0000": "Общий",
    "0.6275 1.0000 0.6275": "Личное",
    "0.0196 0.7843 0.8431": "Группа",
    "0.6118 0.9059 0.8627": "Легион",
}
_WHISPER_VERBS = {"шепчет", "шепчете"}
_NOTICE = re.compile(
    r"^(Получено|Получен[аы]?|Вы получили|Использовано|Невозможно|Нельзя|Недостаточно|Вы не можете|"
    r"Цель находится|Кто-то уже|Не удалось|Задание|Вы вошли|Вы покинули)"
    r"|получает: \[|присоединил|покинул[аи]? (группу|легион)|кинар",
)


def category(line: ChatLine) -> str | None:
    """Which «Весь чат» category a player line belongs to; None = not shown."""
    channel = line.channel or ""
    if channel.startswith("3."):
        return "Поиск группы"
    if channel.startswith("1."):
        return "Общий"
    if channel:
        return None  # trade and other numbered channels
    if line.verb in _WHISPER_VERBS:
        return "Личное"
    return _NAME_COLORS.get(line.color or "")


def is_notice(line: ChatLine) -> bool:
    """System «information» and «errors/notifications» (loot, kinah, can't-do-that…), not combat."""
    if line.is_player:
        return False
    if line.channel is not None:
        return not line.channel.startswith("?")  # [Event], [Ежедневно] …; unreadable ones are skipped
    return "??" not in line.text and bool(_NOTICE.search(line.text))


class AllChatView(ttk.Frame):
    ITEM_COLOR = ITEM_COLOR
    def __init__(
        self,
        parent: tk.Misc,
        get_path: Callable[[], str],
        names: Mapping[str, str],
        get_minutes: Callable[[], int],
        show_system: bool,
        on_settings: Callable[..., None],
        toolbar_parent: tk.Misc | None = None,
        spec_items: Mapping[str, str] | None = None,
        on_item_enter: Callable[[str], None] | None = None,
        on_item_leave: Callable[[], None] | None = None,
        grades: Mapping[str, str] | None = None,
        on_place: Callable[[str, float, float, str], None] | None = None,
        motion_enabled: Callable[[], bool] | None = None,
        map_names: Mapping[str, str] | None = None,
        quest_names: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.get_path = get_path
        self.get_minutes = get_minutes  # history period, shared with the search tab («История»)
        self.names = names
        self.map_names, self.quest_names = map_names or {}, quest_names or {}  # zone and quest links
        self.on_settings = on_settings
        self.motion_enabled = motion_enabled or (lambda: True)
        self._links = (spec_items, on_item_enter, on_item_leave, grades, on_place)
        self.tailer: LogTailer | None = None
        self.paused = False
        self.active = False
        self._after_id: str | None = None
        self._held: list[str] = []
        self._rows = 0
        self._build(show_system, toolbar_parent)

    # --- UI -----------------------------------------------------------------------
    def _build(self, show_system: bool, toolbar_parent: tk.Misc | None) -> None:
        """Toolbar (system checkbox, pause, status) goes into toolbar_parent if given, else on top."""
        bar = ttk.Frame(toolbar_parent if toolbar_parent is not None else self)
        if toolbar_parent is None:
            bar.pack(fill="x", pady=(0, 8))
        self.toolbar = bar
        self.system_var = tk.BooleanVar(value=show_system)
        ttk.Checkbutton(
            bar,
            text="Информация и уведомления",
            variable=self.system_var,
            style="Plain.TCheckbutton",
            command=self._on_settings_changed,
        ).pack(side="left", padx=(0, 16))
        self.pause_btn = ttk.Button(bar, text="Пауза", command=self.toggle_pause)
        self.pause_btn.pack(side="left")
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").pack(side="left", padx=12)

        card = ttk.Frame(self, style="Card.TFrame", padding=6)
        card.pack(fill="both", expand=True)
        self.text = tk.Text(card, wrap="word", state="disabled")
        theme.style_text(self.text)
        scroll = ttk.Scrollbar(card, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self._color_tags: dict[str, str] = {}
        self.linker = ItemLinker(self.text, *self._links)
        self.anchor = BottomAnchor(self.text)
        self.copy = CopyMenu(self.text)
        self.text.bind("<Configure>", lambda _e: self.anchor.update())
        self.empty = EmptyState(self.text, IconSet(self, resource_root() / "data" / "ui" / "icons"))

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
        self.empty.show("hourglass-medium", "Читаю чат…", loading=True)
        self.update_idletasks()  # paint «reading» before the (blocking) read
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
            self._show(held, live=True)

    def _on_settings_changed(self) -> None:
        self.on_settings(show_system=self.system_var.get())
        self.reload()

    def reload(self) -> None:
        """Re-read the history period (e.g. after «История» changed) if the view is open."""
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
                minutes = self.get_minutes()
                if minutes > 0:
                    lines = tailer.read_backlog(datetime.now() - timedelta(minutes=minutes))
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
        self._show(lines, live=False)
        if self._rows == 0:
            minutes = self.get_minutes() if with_history else 0
            self.empty.show("chat-circle-dots", "Пока тихо",
                            "Здесь появятся новые сообщения чата" + (f"; за последние {minutes} мин их не было"
                                                                       if minutes else ""))
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
            self._show(lines, live=True)
        self._schedule(POLL_MS)

    # --- rendering --------------------------------------------------------------------
    def _clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("2.0", "end-1c")  # "end" would also eat the spacer line
        self.text.configure(state="disabled")
        self._rows = 0
        self.anchor.update()

    def _show(self, raw_lines: list[str], live: bool = False) -> None:
        show_system = self.system_var.get()
        rows = []
        for raw in raw_lines:
            line = parse_any_line(raw, self.names, maps=self.map_names, quests=self.quest_names)
            if line is None:
                continue
            if line.is_player:
                kind = category(line)
                if kind is not None:
                    rows.append((line, kind))
            elif show_system and is_notice(line):
                rows.append((line, None))
        if not rows:
            return
        self.empty.hide()
        at_bottom = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        fresh_ranges: list[tuple[str, str]] = []
        for line, kind in rows:
            start = self.text.index("end-1c")
            parts: list = [f"{line.time[11:]}  ", ("meta",)]
            if kind is not None:
                label = line.channel if kind == "Поиск группы" and "?" not in (line.channel or "?") else kind
                parts += [f"[{label}] ", (self._tag_for(CATEGORY_COLORS[kind]),)]
            elif line.channel:
                parts += [f"[{line.channel}] ", (self._tag_for(theme.MUTED),)]
            if line.nick:
                parts += [f"{line.nick}: ", ("nick",)]
                parts += self.linker.parts(line.text)
            else:
                parts += [line.text, (self._tag_for(theme.MUTED),)]
            parts += ["\n", ()]
            self.text.insert("end", *parts)
            fresh_ranges.append((start, self.text.index("end-1c")))
        self._rows += len(rows)
        if self._rows > MAX_ROWS:
            self.text.delete("2.0", f"{self._rows - MAX_ROWS + 2}.0")
            self._rows = MAX_ROWS
        if live and self.motion_enabled():
            from watcher.motion import tween_color
            for index, (start, end) in enumerate(fresh_ranges[-10:]):
                tag = f"fresh_{self._rows}_{index}_{id(self)}"
                self.text.tag_configure(tag, background=theme.ACCENT_SUBTLE)
                self.text.tag_add(tag, start, end)
                tween_color(self.text, lambda color, t=tag: self.text.tag_configure(t, background=color),
                            theme.ACCENT_SUBTLE, theme.SURFACE, 1200, steps=8,
                            done=lambda t=tag: self.text.tag_delete(t))
        self.text.configure(state="disabled")
        self.anchor.update()
        if at_bottom:
            self.text.see("end")
