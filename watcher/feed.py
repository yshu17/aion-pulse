"""Search tab feed: matched messages, newest at the bottom; nag alerts blink with an «принять» box."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from watcher import theme
from watcher.matcher import highlight_segments
from watcher.parser import ChatMessage

BLINK_ON = "#5a3610"
STATE_TEXT = {"accepted": "принято", "missed": "пропущено"}


class MatchFeed(ttk.Frame):
    def __init__(self, parent: tk.Misc, on_accept: Callable[[int], None], max_rows: int = 500) -> None:
        super().__init__(parent, style="Card.TFrame", padding=2)
        self.on_accept = on_accept
        self.max_rows = max_rows
        self.boxes: dict[int, ttk.Checkbutton] = {}
        self._vars: dict[int, tk.BooleanVar] = {}
        self._rows = 0
        self._blink_on = False
        self.text = tk.Text(self, wrap="word", state="disabled")
        theme.style_text(self.text)
        scroll = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("blink", background=theme.SURFACE)
        self.text.tag_raise("hit")

    def add(self, msg: ChatMessage, hits: list[str], alert_id: int | None = None) -> None:
        """Append a matched message. With alert_id the row blinks until mark() is called."""
        at_bottom = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        start = self.text.index("end-1c")
        if alert_id is not None:
            var = tk.BooleanVar(value=False)
            box = ttk.Checkbutton(
                self.text,
                text="принять",
                variable=var,
                style="Accept.TCheckbutton",
                command=lambda: self._accepted(alert_id),
                cursor="hand2",
            )
            self.boxes[alert_id] = box
            self._vars[alert_id] = var
            self.text.window_create("end-1c", window=box, padx=4)
            self.text.insert("end-1c", " ")
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        for chunk, is_hit in highlight_segments(msg.text, hits):
            parts += [chunk, ("hit",) if is_hit else ()]
        self.text.insert("end-1c", *parts, "\n", ())
        if alert_id is not None:
            # the range includes the newline, so the blinking stripe spans the full width
            self.text.tag_add(f"a{alert_id}", start, "end-1c")
            self.text.tag_add("blink", start, "end-1c")
        self._rows += 1
        self._trim()
        self.text.configure(state="disabled")
        if at_bottom:
            self.text.see("end")

    def mark(self, alert_id: int, state: str) -> None:
        """Stop blinking a row: state is "accepted" or "missed"."""
        tag = f"a{alert_id}"
        ranges = self.text.tag_ranges(tag)
        if ranges:
            self.text.tag_remove("blink", ranges[0], ranges[-1])
        box = self.boxes.get(alert_id)
        if box is not None:
            self._vars[alert_id].set(state == "accepted")
            style = "Accept.TCheckbutton" if state == "accepted" else "Missed.TCheckbutton"
            box.configure(text=STATE_TEXT[state], state="disabled", style=style, cursor="")

    def blink(self) -> None:
        self._blink_on = not self._blink_on
        self.text.tag_configure("blink", background=BLINK_ON if self._blink_on else theme.SURFACE)

    def _accepted(self, alert_id: int) -> None:
        if self._vars[alert_id].get():
            self.on_accept(alert_id)

    def _trim(self) -> None:
        while self._rows > self.max_rows:
            self.text.delete("1.0", "2.0")
            self._rows -= 1
        for alert_id in [i for i in self.boxes if not self.text.tag_ranges(f"a{i}")]:
            self.boxes.pop(alert_id).destroy()
            self._vars.pop(alert_id)
