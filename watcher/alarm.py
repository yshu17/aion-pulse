"""«Назойливый» alert mode: a looping sound and a blinking popup until the user reacts."""

import ctypes
import math
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from tkinter import ttk

from watcher import theme
from watcher.matcher import highlight_segments
from watcher.parser import ChatMessage, display_text
from watcher.window_icon import apply_app_icon

BEEP_REPEAT_MS = 1500
BLINK_MS = 500
MAX_SHOWN = 6  # messages the window shows without scrolling (UI/UX item 14)
DIM = theme.ALARM_DIM


class _FlashInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]


def taskbar_flasher(root: tk.Misc) -> Callable[[bool], None]:
    """Return flash(on): blink the app's taskbar button (Windows), or stop blinking."""

    def flash(on: bool) -> None:
        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            flags = 3 | 4 if on else 0  # FLASHW_ALL | FLASHW_TIMER, or FLASHW_STOP
            info = _FlashInfo(ctypes.sizeof(_FlashInfo), hwnd, flags, 0, 0)
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
        except (AttributeError, OSError):
            pass

    return flash


class NagAlarm:
    def __init__(
        self,
        root: tk.Misc,
        notifier,
        flash: Callable[[bool], None] | None = None,
        on_ack: Callable[[], None] | None = None,
        window_icons: tuple[tk.PhotoImage, ...] | None = None,
        icon_for: Callable[[list[str]], tk.PhotoImage | None] | None = None,
    ) -> None:
        self.root = root
        self.notifier = notifier
        self.flash = flash or taskbar_flasher(root)
        self.on_ack = on_ack  # the user reacted in the popup (hover, click or OK)
        self.window_icons = window_icons or ()
        self.window: tk.Toplevel | None = None
        self.text: tk.Text | None = None
        self.sounding = False
        self._native_loop = False
        self._beep_after: str | None = None
        self._blink_after: str | None = None
        self._blink_on = False
        self.icon_for = icon_for or (lambda _hits: None)  # small item picture for a message

    # --- public ---------------------------------------------------------------
    def trigger(self, entries: list[tuple[ChatMessage, list[str]]], popup: bool = True) -> None:
        """Ring until silence() / close(); with popup, also list the matches in a blinking window."""
        if popup:
            if self.window is None:
                self._open()
            for msg, hits in entries:
                self._add_row(msg, hits)
            self.window.deiconify()
            self.window.lift()
            self._fit()  # now the text has its width, so wrapped lines count right
        if not self.sounding:
            self._start()

    def silence(self) -> None:
        if not self.sounding:
            return
        self.sounding = False
        self.notifier.stop()
        self.flash(False)
        for timer in (self._beep_after, self._blink_after):
            if timer is not None:
                self.root.after_cancel(timer)
        self._beep_after = self._blink_after = None
        self._paint(False)

    def silence_on_click(self, _event) -> None:
        self.silence()
        self._acknowledged()

    def _on_hover(self) -> None:
        if self.sounding:
            self.silence()
            self._acknowledged()

    def _on_ok(self) -> None:
        self.close()
        self._acknowledged()

    def _acknowledged(self) -> None:
        if self.on_ack is not None:
            self.on_ack()

    def close(self) -> None:
        self.silence()
        if self.window is not None:
            self.window.destroy()
        self.window = self.text = None

    # --- internals ---------------------------------------------------------------
    def _start(self) -> None:
        self.sounding = True
        self._native_loop = self.notifier.start_loop()
        if not self._native_loop:
            self._repeat_beep()
        self.flash(True)
        self._blink()

    def _repeat_beep(self) -> None:
        self._beep_after = None
        if not self.sounding:
            return
        self.notifier.play()
        self._beep_after = self.root.after(BEEP_REPEAT_MS, self._repeat_beep)

    def _blink(self) -> None:
        self._blink_after = None
        if not self.sounding:
            return
        self._blink_on = not self._blink_on
        self._paint(self._blink_on)
        self._blink_after = self.root.after(BLINK_MS, self._blink)

    def _paint(self, bright: bool) -> None:
        if self.window is None:
            return
        self.window.configure(background=theme.ACCENT if bright else DIM)
        self._title.configure(foreground=theme.ACCENT if bright else theme.TEXT)

    def _open(self) -> None:
        win = tk.Toplevel(self.root, background=theme.ACCENT, padx=6, pady=6)
        win.title("Найдено в чате")
        apply_app_icon(win, self.window_icons)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self._on_ok)
        body = tk.Frame(win, background=theme.BG, padx=16, pady=14)
        body.pack(fill="both", expand=True)
        self._title = tk.Label(
            body,
            text="Найдено в чате!",
            background=theme.BG,
            foreground=theme.ACCENT,
            font=theme.font("alarm"),
            anchor="w",
        )
        self._title.pack(fill="x")
        tk.Label(
            body,
            text="Наведи на сообщение или нажми ОК, чтобы выключить сигнал",
            background=theme.BG,
            foreground=theme.MUTED,
            font=theme.font("caption"),
            anchor="w",
        ).pack(fill="x", pady=(2, 10))
        holder = tk.Frame(body, background=theme.BG)
        holder.pack(fill="both", expand=True)
        self.text = tk.Text(holder, wrap="word", height=1, width=70, state="disabled", cursor="hand2")
        theme.style_text(self.text)
        self._scroll = ttk.Scrollbar(holder, command=self.text.yview)
        self.text.configure(yscrollcommand=self._scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Enter>", lambda _e: self._on_hover())
        self.text.bind("<Configure>", lambda _e: self._fit())  # wrapped lines are known once the text has a width
        self.text.bind("<Button-1>", self.silence_on_click)
        ok = ttk.Button(body, text="ОК", style="Accent.TButton", command=self._on_ok, default="active")
        ok.pack(anchor="e", pady=(12, 0))
        # Enter / Esc = ОК once the window has the keyboard (it never takes it from the game by itself)
        for key in ("<Return>", "<KP_Enter>", "<Escape>"):
            win.bind(key, lambda _e: self._on_ok())
        win.update_idletasks()
        x = self.root.winfo_screenwidth() // 2 - win.winfo_reqwidth() // 2
        y = self.root.winfo_screenheight() // 3 - win.winfo_reqheight() // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        theme.dark_title_bar(win)
        self.window = win

    def _add_row(self, msg: ChatMessage, hits: list[str]) -> None:
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        for chunk, is_hit in highlight_segments(display_text(msg.text), hits):
            parts += [chunk, ("hit",) if is_hit else ()]
        parts += ["\n", ()]
        self.text.configure(state="normal")
        self.text.insert("1.0", *parts)
        icon = self.icon_for(hits)
        if icon is not None:
            self.text.image_create("1.0", image=icon, padx=4, align="center")
        self.text.configure(state="disabled")

    def _fit(self) -> None:
        """Height by content: 1 to MAX_SHOWN messages, more scroll (UI/UX item 14 — was a fixed 8 lines)."""
        if self.text is None:
            return
        messages = int(self.text.index("end-1c").split(".")[0]) - 1
        shown = min(messages, MAX_SHOWN)
        # Tk measures «height» in lines of the font plus the message spacing above and below (spacing1 + spacing3);
        # a wrapped continuation line takes only the font line plus spacing2: count the screen lines, convert
        wrapped = self.text.count("1.0", f"{shown + 1}.0", "displaylines") if self.text.winfo_width() > 1 else None
        rows = wrapped[0] if wrapped else shown
        line = tkfont.Font(font=self.text.cget("font")).metrics("linespace")
        unit = line + int(self.text.cget("spacing1")) + int(self.text.cget("spacing3"))
        pixels = shown * unit + (rows - shown) * (line + int(self.text.cget("spacing2")))
        height = max(1, math.ceil(pixels / unit))
        if int(self.text.cget("height")) != height:
            self.text.configure(height=height)
        if messages > MAX_SHOWN:
            self._scroll.pack(side="right", fill="y", before=self.text)
        else:
            self._scroll.pack_forget()
