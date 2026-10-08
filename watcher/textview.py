"""Shared helpers for the chat text views: game-style item links and bottom-anchored rows."""

import re
import tkinter as tk
from collections.abc import Callable, Mapping

from watcher import theme
from watcher.matcher import highlight_segments, normalize

ITEM_LINK = re.compile(r"\[([^\[\]]+)\]")
HIGHLIGHT_NAMES = re.compile(r"рудр", re.IGNORECASE)  # item links worth spotting in the chat
ITEM_COLOR = theme.ACCENT  # «рыжий», like epic item links in the game


def text_height(text: tk.Text, start: str, end: str) -> int:
    """Pixel height of a text range (Text.count returns a tuple on older Pythons)."""
    value = text.count(start, end, "ypixels")
    if isinstance(value, tuple):
        value = value[0]
    return int(value or 0)


class BottomAnchor:
    """Keeps a Text's rows pushed to the bottom edge, like the game chat.

    Line 1 stays an empty spacer whose top spacing fills the free height, so real rows start at
    line 2 (delete old rows from "2.0").
    """

    def __init__(self, text: tk.Text) -> None:
        self.text = text
        state = str(text.cget("state"))
        text.configure(state="normal")
        text.insert("1.0", "\n", ("spacer",))
        text.configure(state=state)

    def update(self) -> None:
        height = self.text.winfo_height()
        content = text_height(self.text, "2.0", "end")
        spare = height - content - 2 * int(str(self.text.cget("pady"))) - 4
        self.text.tag_configure("spacer", spacing1=max(0, spare))


class ItemLinker:
    """Renders item links «[Name]» as orange «<Name>» and shows a spec tooltip on hover."""

    def __init__(
        self,
        text: tk.Text,
        spec_items: Mapping[str, str] | None = None,
        on_enter: Callable[[str], None] | None = None,
        on_leave: Callable[[], None] | None = None,
    ) -> None:
        self.text = text
        self.spec_items = dict(spec_items or {})  # item name -> id, for items with a tooltip
        self.on_enter = on_enter
        self.on_leave = on_leave
        self._bound: set[str] = set()
        text.tag_configure("item", foreground=ITEM_COLOR)
        if "hit" in text.tag_names():
            text.tag_raise("hit", "item")

    def parts(self, message: str, hits: list[str] | None = None) -> list:
        """Insert-ready (chunk, tags, ...) for a message; hits are highlighted as matches."""
        hits = hits or []
        parts: list = []
        pos = 0
        for match in ITEM_LINK.finditer(message):
            name = match.group(1)
            item_id = self.spec_items.get(name)
            if item_id is None and not HIGHLIGHT_NAMES.search(name):
                continue
            parts += self._plain(message[pos : match.start()], hits)
            tags: tuple = ("item",)
            if item_id is not None:
                tags += (self._tag(item_id),)
            if any(normalize(h) in normalize(name) for h in hits if h.strip()):
                tags += ("hit",)
            parts += [f"<{name}>", tags]
            pos = match.end()
        parts += self._plain(message[pos:], hits)
        return parts

    @staticmethod
    def _plain(chunk: str, hits: list[str]) -> list:
        if not hits:
            return [chunk, ()]
        out: list = []
        for piece, is_hit in highlight_segments(chunk, hits):
            out += [piece, ("hit",) if is_hit else ()]
        return out or ["", ()]

    def _tag(self, item_id: str) -> str:
        tag = f"item_{item_id}"
        if tag not in self._bound:
            self._bound.add(tag)
            self.text.tag_bind(tag, "<Enter>", lambda _e: self.enter(item_id))
            self.text.tag_bind(tag, "<Leave>", lambda _e: self.leave())
        return tag

    def enter(self, item_id: str) -> None:
        self.text.configure(cursor="hand2")
        if self.on_enter is not None:
            self.on_enter(item_id)

    def leave(self) -> None:
        self.text.configure(cursor="")
        if self.on_leave is not None:
            self.on_leave()
