"""Search tab feed: matched messages anchored to the bottom like the game chat.

Nag alerts are coloured stripes: blinking amber while waiting, green when accepted,
red when missed. Each has a countdown and a checkbox pinned to the right edge.
"""

import math
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from watcher import theme
from watcher.matcher import highlight_segments
from watcher.parser import ChatMessage

PENDING_BRIGHT = "#7a5410"
PENDING_DIM = "#3a2a0c"
ACCEPTED_BG = "#173a24"
MISSED_BG = "#3d1a1d"
STATE_BG = {"accepted": ACCEPTED_BG, "missed": MISSED_BG}
STATE_STYLE = {"accepted": "Accept.TCheckbutton", "missed": "Missed.TCheckbutton"}
HOLDER_WIDTH = 120  # space kept free at the right of an alert row for countdown + checkbox
RIGHT_MARGIN = 8
URGENT_SEC = 10


def text_height(text: tk.Text, start: str, end: str) -> int:
    """Pixel height of a text range (Text.count returns a tuple on older Pythons)."""
    value = text.count(start, end, "ypixels")
    if isinstance(value, tuple):
        value = value[0]
    return int(value or 0)


class MatchFeed(ttk.Frame):
    def __init__(self, parent: tk.Misc, on_accept: Callable[[int], None], max_rows: int = 500) -> None:
        super().__init__(parent, style="Card.TFrame", padding=2)
        self.on_accept = on_accept
        self.max_rows = max_rows
        self.boxes: dict[int, ttk.Checkbutton] = {}
        self.countdowns: dict[int, tk.Label] = {}
        self._holders: dict[int, tk.Frame] = {}
        self._vars: dict[int, tk.BooleanVar] = {}
        self._pending: set[int] = set()
        self._rows = 0
        self._blink_on = False
        self.text = tk.Text(self, wrap="word", state="disabled")
        theme.style_text(self.text)
        self._scroll = ttk.Scrollbar(self, command=self._yview)
        self.text.configure(yscrollcommand=self._on_text_scrolled)
        self._scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("alert", rmargin=HOLDER_WIDTH)
        self.text.tag_configure("blink", background=PENDING_DIM)
        self.text.tag_configure("accepted", background=ACCEPTED_BG)
        self.text.tag_configure("missed", background=MISSED_BG)
        self.text.tag_raise("hit")
        # line 1 stays empty: its top spacing pushes the rows down to the bottom edge
        self.text.configure(state="normal")
        self.text.insert("1.0", "\n", ("spacer",))
        self.text.configure(state="disabled")
        self.text.bind("<Configure>", lambda _e: self._relayout())

    # --- public -----------------------------------------------------------------------
    def add(self, msg: ChatMessage, hits: list[str], alert_id: int | None = None) -> None:
        """Append a matched message. With alert_id the row blinks until mark() is called."""
        at_bottom = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        start = self.text.index("end-1c")
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        for chunk, is_hit in highlight_segments(msg.text, hits):
            parts += [chunk, ("hit",) if is_hit else ()]
        self.text.insert("end-1c", *parts, "\n", ())
        if alert_id is not None:
            # the range includes the newline, so the stripe spans the full width
            for tag in (f"a{alert_id}", "alert", "blink"):
                self.text.tag_add(tag, start, "end-1c")
            self._make_holder(alert_id)
            self._pending.add(alert_id)
        self._rows += 1
        self._trim()
        self.text.configure(state="disabled")
        self._relayout()
        if at_bottom:
            self.text.see("end")
        self._place_holders()

    def set_countdown(self, remaining: dict[int, float]) -> None:
        """Seconds left before auto-accept, per pending alert."""
        for alert_id, seconds in remaining.items():
            label = self.countdowns.get(alert_id)
            if label is not None and alert_id in self._pending:
                left = max(0, math.ceil(seconds))
                color = theme.DANGER if left <= URGENT_SEC else "#ffd166"
                label.configure(text=f"{left} с", foreground=color)

    def mark(self, alert_id: int, state: str) -> None:
        """Finish an alert row: state is "accepted" (green) or "missed" (red)."""
        self._pending.discard(alert_id)
        ranges = self.text.tag_ranges(f"a{alert_id}")
        if ranges:
            self.text.tag_remove("blink", ranges[0], ranges[-1])
            self.text.tag_add(state, ranges[0], ranges[-1])
        box = self.boxes.get(alert_id)
        if box is None:
            return
        self._vars[alert_id].set(state == "accepted")
        box.configure(state="disabled", style=STATE_STYLE[state], cursor="")
        background = STATE_BG[state]
        self.countdowns[alert_id].configure(
            text="" if state == "accepted" else "пропущено",
            foreground="#ff8a8f",
            background=background,
        )
        self._holders[alert_id].configure(background=background)

    def blink(self) -> None:
        self._blink_on = not self._blink_on
        color = PENDING_BRIGHT if self._blink_on else PENDING_DIM
        self.text.tag_configure("blink", background=color)
        style = "PendHot.TCheckbutton" if self._blink_on else "Pend.TCheckbutton"
        for alert_id in self._pending:
            self.boxes[alert_id].configure(style=style)
            self._holders[alert_id].configure(background=color)
            self.countdowns[alert_id].configure(background=color)

    # --- internals ----------------------------------------------------------------------
    def _make_holder(self, alert_id: int) -> None:
        holder = tk.Frame(self.text, background=PENDING_DIM)
        label = tk.Label(
            holder,
            text="",
            background=PENDING_DIM,
            foreground="#ffd166",
            font=(theme.FONT_FAMILY, theme.FONT_SIZE - 1, "bold"),
        )
        label.pack(side="left", padx=(0, 6))
        var = tk.BooleanVar(value=False)
        box = ttk.Checkbutton(
            holder,
            text="",
            variable=var,
            style="Pend.TCheckbutton",
            command=lambda: self._accepted(alert_id),
            cursor="hand2",
        )
        box.pack(side="left")
        self.boxes[alert_id] = box
        self.countdowns[alert_id] = label
        self._holders[alert_id] = holder
        self._vars[alert_id] = var

    def _accepted(self, alert_id: int) -> None:
        if self._vars[alert_id].get():
            self.on_accept(alert_id)

    def _yview(self, *args) -> None:
        self.text.yview(*args)
        self._place_holders()

    def _on_text_scrolled(self, first: str, last: str) -> None:
        self._scroll.set(first, last)
        self._place_holders()

    def _place_holders(self) -> None:
        """Pin each countdown + checkbox to the right edge of its row's first line."""
        self.text.update_idletasks()
        right = self.text.winfo_width() - RIGHT_MARGIN
        # dlineinfo counts the text's inner padding, place() coordinates start inside it
        pady = int(str(self.text.cget("pady")))
        for alert_id, holder in self._holders.items():
            info = self.text.dlineinfo(f"a{alert_id}.first") if self.text.tag_ranges(f"a{alert_id}") else None
            if info is None:
                holder.place_forget()
                continue
            _x, y, _w, height, _base = info
            holder.place(x=right, y=y + height // 2 - pady, anchor="e")

    def _relayout(self) -> None:
        """Keep the rows pushed to the bottom and the checkboxes at the right edge."""
        height = self.text.winfo_height()
        content = text_height(self.text, "2.0", "end")
        spare = height - content - 2 * int(str(self.text.cget("pady"))) - 4
        self.text.tag_configure("spacer", spacing1=max(0, spare))
        self._place_holders()

    def _trim(self) -> None:
        while self._rows > self.max_rows:
            self.text.delete("2.0", "3.0")
            self._rows -= 1
        for alert_id in [i for i in self.boxes if not self.text.tag_ranges(f"a{i}")]:
            self._holders.pop(alert_id).destroy()
            self.boxes.pop(alert_id)
            self.countdowns.pop(alert_id)
            self._vars.pop(alert_id)
            self._pending.discard(alert_id)
