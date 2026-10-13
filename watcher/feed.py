"""Search tab feed: matched messages anchored to the bottom like the game chat.

Nag alerts are coloured stripes: blinking amber while waiting, green when accepted,
red when missed. Each has a countdown and a checkbox pinned to the right edge.
"""

import math
import tkinter as tk
from collections.abc import Callable, Mapping
from tkinter import ttk

from watcher import theme
from watcher.catalog import resource_root
from watcher.emptystate import EmptyState
from watcher.parser import ChatMessage
from watcher.textview import BottomAnchor, CopyMenu, ItemLinker
from watcher.ui_icons import IconSet

PENDING_BRIGHT = theme.PENDING_BRIGHT
PENDING_DIM = theme.PENDING_DIM
ACCEPTED_BG = theme.ACCEPTED_BG
MISSED_BG = theme.MISSED_BG
STATE_BG = {"accepted": ACCEPTED_BG, "missed": MISSED_BG}
STATE_STYLE = {"accepted": "Accept.TCheckbutton", "missed": "Missed.TCheckbutton"}
HOLDER_WIDTH = 120  # space kept free at the right of an alert row for countdown + checkbox
RIGHT_MARGIN = 8
URGENT_SEC = 10


class MatchFeed(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        on_accept: Callable[[int], None],
        max_rows: int = 500,
        spec_items: dict[str, str] | None = None,
        on_item_enter: Callable[[str], None] | None = None,
        on_item_leave: Callable[[], None] | None = None,
        grades: Mapping[str, str] | None = None,
        on_place: Callable[[str, float, float, str], None] | None = None,
        motion_enabled: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent, style="Card.TFrame", padding=6)
        self.on_accept = on_accept
        self.motion_enabled = motion_enabled or (lambda: True)
        self.max_rows = max_rows
        self.boxes: dict[int, ttk.Checkbutton] = {}
        self.countdowns: dict[int, tk.Label] = {}
        self._holders: dict[int, tk.Frame] = {}
        self._vars: dict[int, tk.BooleanVar] = {}
        self._pending: set[int] = set()
        self._rows = 0
        self._blink_on = False
        self._blink_color = PENDING_DIM
        self.ui_icons = IconSet(self, resource_root() / "data" / "ui" / "icons")
        self.banner = ttk.Frame(self, style="Surface.TFrame", padding=(10, 7))
        self.banner_button = ttk.Button(self.banner, style="Card.TButton")
        self.banner_button.pack(side="right", padx=(8, 0))
        self.banner_label = ttk.Label(self.banner, style="Warn.Chip.TLabel", anchor="w", width=1)
        self.banner_label.pack(side="left", fill="x", expand=True)
        self.banner.bind("<Configure>", self._fit_banner_text)
        self.banner.pack_forget()
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
        self.text.tag_configure("note", foreground=theme.MUTED, justify="center")
        self.text.tag_configure("quiet_note", foreground=theme.QUIET_NOTE)
        self.linker = ItemLinker(self.text, spec_items, on_item_enter, on_item_leave, grades=grades, on_place=on_place)
        self.anchor = BottomAnchor(self.text)  # rows start at line 2
        self.copy = CopyMenu(self.text)
        self.text.bind("<Configure>", lambda _e: self._relayout())
        self.empty = EmptyState(self.text, IconSet(self, resource_root() / "data" / "ui" / "icons"))

    @property
    def rows(self) -> int:
        return self._rows

    def show_empty(self, icon: str, title: str, hint: str = "", loading: bool = False) -> None:
        """What the feed will show, while it shows nothing yet (UI/UX item 12)."""
        if self._rows == 0:
            self.empty.show(icon, title, hint, loading)

    def show_banner(self, text: str, action: str, command: Callable[[], None]) -> None:
        """Show a compact actionable warning above the search feed."""
        self.banner_label.configure(text=text, image=self.ui_icons.get("warning", "caution", 16), compound="left")
        self.banner_button.configure(text=action, command=command)
        if not self.banner.winfo_manager():
            self.banner.pack(fill="x", side="top", pady=(0, 6), before=self.text)

    def _fit_banner_text(self, event: tk.Event) -> None:
        """Reserve the action button first and wrap warning text into the remaining width."""
        width = max(60, event.width - self.banner_button.winfo_reqwidth() - 42)
        if str(self.banner_label.cget("wraplength")) != str(width):
            self.banner_label.configure(wraplength=width)

    def hide_banner(self) -> None:
        if self.banner.winfo_manager():
            self.banner.pack_forget()

    # --- public -----------------------------------------------------------------------
    def add(self, msg: ChatMessage, hits: list[str], alert_id: int | None = None, quiet: bool = False,
            animate_new: bool = False) -> None:
        """Append a matched message. With alert_id the row blinks until mark() is called.

        quiet: a repeat of an already accepted series — a green row marked «уже принято», no alert.
        """
        self.empty.hide()
        at_bottom = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        start = self.text.index("end-1c")
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        parts += self.linker.parts(msg.text, hits)
        if quiet:
            parts += ["   Уже принято", ("quiet_note",)]
        self.text.insert("end-1c", *parts, "\n", ())
        # every row keeps a stripe-wide left margin; a row with a match colours it orange (UI/UX item 9)
        has_hit = any(isinstance(part, tuple) and "hit" in part for part in parts)
        self.text.tag_add("hitline" if has_hit else "row", start, "end-1c")
        if quiet:
            self.text.tag_add("accepted", start, "end-1c")
        if animate_new and alert_id is None and not quiet and self.motion_enabled():
            self._fade_new_row(start, "end-1c")
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

    def _fade_new_row(self, start: str, end: str) -> None:
        tag = f"fresh_{self._rows}_{id(self)}"
        self.text.tag_configure(tag, background=theme.ACCENT_SUBTLE)
        self.text.tag_add(tag, start, end)
        from watcher.motion import tween_color
        tween_color(self.text, lambda color: self.text.tag_configure(tag, background=color),
                    theme.ACCENT_SUBTLE, theme.SURFACE, 1200, steps=8,
                    done=lambda: self.text.tag_delete(tag))

    def add_note(self, note: str) -> None:
        """A muted centred separator line (e.g. between history and live messages)."""
        self.empty.hide()
        at_bottom = self.text.yview()[1] >= 0.999
        self.text.configure(state="normal")
        self.text.insert("end-1c", note + "\n", ("note",))
        self._rows += 1
        self._trim()
        self.text.configure(state="disabled")
        self._relayout()
        if at_bottom:
            self.text.see("end")

    def set_countdown(self, remaining: dict[int, float]) -> None:
        """Seconds left before auto-accept, per pending alert."""
        for alert_id, seconds in remaining.items():
            label = self.countdowns.get(alert_id)
            if label is not None and alert_id in self._pending:
                left = max(0, math.ceil(seconds))
                color = theme.COUNTDOWN_URGENT if left <= URGENT_SEC else theme.COUNTDOWN
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
            foreground=theme.MISSED_TEXT,
            background=background,
        )
        self._holders[alert_id].configure(background=background)

    def blink(self) -> None:
        self._blink_on = not self._blink_on
        color = PENDING_BRIGHT if self._blink_on else PENDING_DIM
        start = self._blink_color
        self._blink_color = color
        from watcher.motion import tween_color
        tween_color(self.text, lambda value: self.text.tag_configure("blink", background=value),
                    start, color, 450, enabled=self.motion_enabled(), steps=4)
        style = "PendHot.TCheckbutton" if self._blink_on else "Pend.TCheckbutton"
        for alert_id in self._pending:
            self.boxes[alert_id].configure(style=style)
            holder, countdown = self._holders[alert_id], self.countdowns[alert_id]
            tween_color(self.text, lambda value, w=holder: w.configure(background=value),
                        start, color, 450, enabled=self.motion_enabled(), steps=4)
            tween_color(self.text, lambda value, w=countdown: w.configure(background=value),
                        start, color, 450, enabled=self.motion_enabled(), steps=4)

    # --- internals ----------------------------------------------------------------------
    def _make_holder(self, alert_id: int) -> None:
        holder = tk.Frame(self.text, background=PENDING_DIM)
        label = tk.Label(
            holder,
            text="",
            background=PENDING_DIM,
            foreground=theme.COUNTDOWN,
            font=theme.font("caption_strong"),
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
        # dlineinfo counts the text's inner padding, place() coordinates start inside it
        padx = int(str(self.text.cget("padx")))
        pady = int(str(self.text.cget("pady")))
        right = self.text.winfo_width() - 2 * padx - RIGHT_MARGIN
        for alert_id, holder in self._holders.items():
            info = self.text.dlineinfo(f"a{alert_id}.first") if self.text.tag_ranges(f"a{alert_id}") else None
            if info is None:
                holder.place_forget()
                continue
            _x, y, _w, height, _base = info
            holder.place(x=right, y=y + height // 2 - pady, anchor="e")

    def _relayout(self) -> None:
        """Keep the rows pushed to the bottom and the checkboxes at the right edge."""
        self.anchor.update()
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
