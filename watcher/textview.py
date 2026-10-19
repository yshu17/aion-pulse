"""Shared helpers for the chat text views: game-style item links and bottom-anchored rows."""

import re
import tkinter as tk
from collections.abc import Callable, Mapping

from watcher import theme
from watcher.matcher import highlight_segments, normalize
from watcher.parser import LINK_CLOSE, LINK_OPEN, split_place

ITEM_LINK = re.compile(r"\[([^\[\]]+)\]")
# item link | place / quest / «where» link (see parser.clean_text)
LINKS = re.compile(rf"\[([^\[\]]+)\]|{LINK_OPEN}([^{LINK_OPEN}{LINK_CLOSE}]+){LINK_CLOSE}")
SELECT_BG = theme.SELECT_BG  # mouse selection in the chat views
PLACE_COLOR = theme.PLACE  # place links, like the game's teal «Место»
HIGHLIGHT_NAMES = re.compile(r"рудр", re.IGNORECASE)  # item links worth spotting in the chat
ITEM_COLOR = theme.ACCENT  # «рыжий», like epic item links in the game


def text_height(text: tk.Text, start: str, end: str) -> int:
    """Pixel height of a text range (Text.count returns a tuple on older Pythons).

    «update» makes Tk lay out wrapped lines first: without it a message wrapping into several screen lines counted
    as one, and the bottom-anchored feed pushed its newest row below the edge (ui:32 recheck)."""
    value = text.count(start, end, "update", "ypixels")
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
        spare = max(0, height - content - 2 * int(str(self.text.cget("pady"))) - 4)
        if spare != getattr(self, "_spare", None):  # re-setting the same spacing still makes Tk re-lay out every line
            self._spare = spare
            self.text.tag_configure("spacer", spacing1=spare)


class ItemLinker:
    """Renders item links «[Name]» as «<Name>» in the grade colour and shows a spec tooltip on hover.

    Links to unknown items are left as plain text, except names with «Рудр» (shown orange).
    """

    def __init__(
        self,
        text: tk.Text,
        spec_items: Mapping[str, str] | None = None,
        on_enter: Callable[[str], None] | None = None,
        on_leave: Callable[[], None] | None = None,
        grades: Mapping[str, str] | None = None,
        on_place: Callable[[str, float, float, str], None] | None = None,
    ) -> None:
        self.text = text
        self.on_place = on_place  # click on a place link: (map id, game x, game y, label)
        self._places = 0
        self.grades = grades or {}  # item id -> grade (epic, legend, …) for the link colour
        self.spec_items = dict(spec_items or {})  # item name -> id, for items with a tooltip
        self.on_enter = on_enter
        self.on_leave = on_leave
        self._bound: set[str] = set()
        text.tag_configure("item", foreground=ITEM_COLOR)
        text.tag_configure("place", foreground=PLACE_COLOR)
        for grade, color in theme.GRADE_COLORS.items():
            text.tag_configure(f"grade_{grade}", foreground=color)
        if "hit" in text.tag_names():
            text.tag_raise("hit")

    def parts(self, message: str, hits: list[str] | None = None) -> list:
        """Insert-ready (chunk, tags, ...) for a message; hits are highlighted as matches."""
        hits = hits or []
        parts: list = []
        pos = 0
        for match in LINKS.finditer(message):
            if match.group(1) is None:  # place / quest / «where» link
                parts += self._plain(message[pos : match.start()], hits)
                shown, place = split_place(match.group(2))
                tags: tuple = ("place",)
                if place is not None and self.on_place is not None:
                    tags += (self._place_tag(place, shown),)
                parts += [f"<{shown}>", tags]
                pos = match.end()
                continue
            name = match.group(1)
            item_id = self.spec_items.get(name)
            if item_id is None and not HIGHLIGHT_NAMES.search(name):
                continue
            parts += self._plain(message[pos : match.start()], hits)
            tags: tuple = ("item",)
            if item_id is not None:
                grade = self.grades.get(item_id)
                if grade in theme.GRADE_COLORS:
                    tags += (f"grade_{grade}",)
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

    def _place_tag(self, place: tuple[str, float, float], shown: str) -> str:
        self._places += 1
        tag = f"pos_{self._places}"
        map_id, x, y = place
        self.text.tag_bind(tag, "<Button-1>", lambda _e: self.on_place(map_id, x, y, shown))
        self.text.tag_bind(tag, "<Enter>", lambda _e: self.text.configure(cursor="hand2"))
        self.text.tag_bind(tag, "<Leave>", lambda _e: self.text.configure(cursor=""))
        return tag

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


class CopyMenu:
    """Copy from a read-only chat Text: select with the mouse and Ctrl+C (any keyboard layout),
    or right-click: «Копировать», «Копировать сообщение» (the whole line), «Выделить всё»."""

    NOTE = "   Уже принято"  # feed suffix, not part of the message

    def __init__(self, text: tk.Text) -> None:
        self.text = text
        self._line = "end-1c"
        self.menu = tk.Menu(
            text, tearoff=False, background=theme.SURFACE_2, foreground=theme.TEXT,
            activebackground=theme.ACCENT, activeforeground=theme.ACCENT_TEXT, borderwidth=0,
            font=theme.font("caption"),
        )
        self.menu.add_command(label="Копировать", command=self.copy_selection)
        self.menu.add_command(label="Копировать сообщение", command=lambda: self.copy_line(self._line))
        self.menu.add_separator()
        self.menu.add_command(label="Выделить всё", command=self.select_all)
        text.configure(exportselection=True, selectbackground=SELECT_BG, inactiveselectbackground=SELECT_BG)
        text.tag_raise("sel")  # selection stays visible over coloured (alert, match) rows
        text.bind("<Button-1>", lambda _e: text.focus_set(), add="+")
        text.bind("<Button-3>", self._popup, add="+")
        text.bind("<Control-KeyPress>", self._on_ctrl_key, add="+")

    def selection(self) -> str:
        try:
            return self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def copy_selection(self) -> str:
        return self._to_clipboard(self.selection())

    def copy_line(self, index: str) -> str:
        line = self.text.get(f"{index} linestart", f"{index} lineend")
        return self._to_clipboard(line.replace(self.NOTE, "").strip())

    def select_all(self) -> None:
        self.text.tag_add("sel", "1.0", "end-1c")

    def _to_clipboard(self, value: str) -> str:
        if value:
            self.text.clipboard_clear()
            self.text.clipboard_append(value)
        return value

    def _on_ctrl_key(self, event: tk.Event) -> str | None:
        # keycode 67 is the C key whatever the layout (Ctrl+С on the Russian layout too)
        if event.keycode == 67 or event.keysym.lower() == "c":
            self.copy_selection()
            return "break"
        if event.keycode == 65 or event.keysym.lower() == "a":  # Ctrl+A / Ctrl+Ф
            self.select_all()
            return "break"
        return None

    def _popup(self, event: tk.Event) -> None:
        self._line = self.text.index(f"@{event.x},{event.y}")
        self.menu.entryconfigure("Копировать", state="normal" if self.selection() else "disabled")
        self.menu.tk_popup(event.x_root, event.y_root)
