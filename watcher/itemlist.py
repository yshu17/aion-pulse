"""The «Что искать» item list: thousands of items in collapsible sections, with a search box.

Only the rows in view are drawn (on a Canvas), so the list stays fast with ~11 000 items.
Typing in the search box jumps to the first matching item; Enter / ▼ go to the next match,
Shift+Enter / ▲ to the previous one. A match inside a folded section unfolds it.
"""

import bisect
import re
import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import font as tkfont
from tkinter import ttk

from watcher import theme
from watcher.catalog import CATEGORY_ORDER, WatchItem
from watcher.matcher import normalize

ROW_H = 62  # 56 px icon + gap
GROUP_H = 42
GROUP_GAP = 8
CHECK_X = 8
ICON_X = 46
NAME_X = 112
GROUP_CHECK_W = 96  # right part of a section header that toggles the whole section
SEARCH_DELAY_MS = 150
MATCH_BG = "#3a2a12"
HOVER_BG = theme.SURFACE_2
PINNED_GROUP = "Рудра"  # Rudra gear is pulled out of its sections into this one, always on top
PINNED_RE = re.compile(r"рудр", re.IGNORECASE)


class ItemList(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        items: Iterable[WatchItem],
        checked: Iterable[str] = (),
        collapsed: Iterable[str] = (),
        icon_for: Callable[[WatchItem], tk.PhotoImage | None] | None = None,
        on_change: Callable[[], None] | None = None,
        on_collapse: Callable[[list[str]], None] | None = None,
        on_hover: Callable[[str], None] | None = None,
        on_leave: Callable[[], None] | None = None,
        width: int = 520,
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        self.icon_for = icon_for or (lambda _item: None)
        self.on_change = on_change or (lambda: None)
        self.on_collapse = on_collapse or (lambda _c: None)
        self.on_hover = on_hover or (lambda _i: None)
        self.on_leave = on_leave or (lambda: None)
        self.enabled = True
        self.groups: dict[str, list[WatchItem]] = {}
        self.group_of: dict[str, str] = {}
        for item in items:
            group = PINNED_GROUP if PINNED_RE.search(item.name) else item.category
            self.groups.setdefault(group, []).append(item)
            self.group_of[item.id] = group
        order = {name: i for i, name in enumerate([PINNED_GROUP, *CATEGORY_ORDER])}
        self.groups = dict(sorted(self.groups.items(), key=lambda kv: order.get(kv[0], len(order))))
        self.by_id = {item.id: item for items_ in self.groups.values() for item in items_}
        self.order = [item.id for items_ in self.groups.values() for item in items_]
        self._norm = {item.id: normalize(item.name) for item in self.by_id.values()}
        self.checked: set[str] = {i for i in checked if i in self.by_id}
        self.collapsed: list[str] = [c for c in collapsed if c in self.groups]
        self.matches: list[str] = []
        self.match_index = -1
        self._rows: list[tuple[str, str]] = []  # ("group", category) | ("item", id)
        self._tops: list[int] = []
        self._height = 0
        self._hover: tuple[str, str] | None = None
        self._search_after: str | None = None
        self.font = tkfont.Font(family=theme.FONT_FAMILY, size=theme.FONT_SIZE)
        self.bold = tkfont.Font(family=theme.FONT_FAMILY, size=theme.FONT_SIZE, weight="bold")
        self.small = tkfont.Font(family=theme.FONT_FAMILY, size=theme.FONT_SIZE - 2)

        search = ttk.Frame(self, style="Surface.TFrame")
        search.pack(fill="x", padx=(0, 8))
        ttk.Label(search, text="Найти", style="CardMuted.TLabel").pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search, textvariable=self.search_var, style="Card.TEntry")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.prev_btn = ttk.Button(search, text="▲", width=3, style="Card.TButton", command=lambda: self.step(-1))
        self.next_btn = ttk.Button(search, text="▼", width=3, style="Card.TButton", command=lambda: self.step(1))
        self.count_label = ttk.Label(search, text="", style="CardMuted.TLabel", width=8, anchor="center")
        self.count_label.pack(side="left", padx=(6, 0))
        self.prev_btn.pack(side="left", padx=(4, 0))
        self.next_btn.pack(side="left", padx=(4, 0))
        entry = self.search_entry
        entry.bind("<KeyRelease>", self._on_search_key)
        entry.bind("<Return>", lambda _e: self.step(1))
        entry.bind("<Shift-Return>", lambda _e: self.step(-1))
        entry.bind("<Down>", lambda _e: self.step(1))
        entry.bind("<Up>", lambda _e: self.step(-1))
        entry.bind("<Escape>", lambda _e: self.clear_search())

        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas = tk.Canvas(body, width=width, highlightthickness=0, borderwidth=0, background=theme.SURFACE)
        self._scroll = ttk.Scrollbar(body, command=self._yview)
        self.canvas.configure(yscrollcommand=self._scroll.set)
        self._scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.render())
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._set_hover(None))
        self._layout()

    # --- public -----------------------------------------------------------------------
    def checked_ids(self) -> list[str]:
        """Checked item ids in list order."""
        return [item_id for item_id in self.order if item_id in self.checked]

    def set_all(self, value: bool) -> None:
        self.checked = set(self.order) if value else set()
        self.render()
        self.on_change()

    def set_group(self, category: str, value: bool) -> None:
        ids = {item.id for item in self.groups[category]}
        self.checked = self.checked | ids if value else self.checked - ids
        self.render()
        self.on_change()

    def toggle_item(self, item_id: str) -> None:
        self.checked ^= {item_id}
        self.render()
        self.on_change()

    def group_checked(self, category: str) -> bool:
        return all(item.id in self.checked for item in self.groups[category])

    def toggle_collapsed(self, category: str) -> None:
        if category in self.collapsed:
            self.collapsed.remove(category)
        else:
            self.collapsed.append(category)
        self._layout()
        self.on_collapse(list(self.collapsed))

    def set_enabled(self, enabled: bool) -> None:
        """Disabled: checkboxes do nothing and the rows are dimmed (search and folding still work)."""
        self.enabled = enabled
        self.render()

    def scroll(self, steps: int) -> None:
        self.canvas.yview_scroll(steps, "units")
        self.render()

    def search(self, query: str) -> int:
        """Find items whose name holds every word of the query (a number also matches the level).

        Jumps to the first match and returns how many there are.
        """
        words = normalize(query).split()
        if not words:
            self.matches = []
        else:
            self.matches = [
                item_id
                for item_id in self.order
                if all(w in self._norm[item_id] or w == str(self.by_id[item_id].level) for w in words)
            ]
        self.match_index = 0 if self.matches else -1
        if self.matches:
            self._goto(self.matches[0])
        else:
            self.render()
        self._update_count(bool(words))
        return len(self.matches)

    def step(self, delta: int) -> str:
        """Go to the next (1) or previous (-1) match. Returns "break" for key bindings."""
        if self._search_after is not None:  # Enter right after typing: search first
            self._run_search()
        if self.matches:
            self.match_index = (self.match_index + delta) % len(self.matches)
            self._goto(self.matches[self.match_index])
            self._update_count(True)
        return "break"

    def clear_search(self) -> None:
        self.search_var.set("")
        self.search("")

    def current_match(self) -> str | None:
        return self.matches[self.match_index] if self.matches else None

    def row_top(self, item_id: str) -> int | None:
        """Canvas y of an item row, None while its section is folded."""
        try:
            return self._tops[self._rows.index(("item", item_id))]
        except ValueError:
            return None

    # --- layout and drawing -----------------------------------------------------------
    def _layout(self) -> None:
        self._rows, self._tops = [], []
        y = 0
        for category, items in self.groups.items():
            y += GROUP_GAP
            self._rows.append(("group", category))
            self._tops.append(y)
            y += GROUP_H
            if category not in self.collapsed:
                for item in items:
                    self._rows.append(("item", item.id))
                    self._tops.append(y)
                    y += ROW_H
        self._height = y + GROUP_GAP
        self.canvas.configure(scrollregion=(0, 0, 1, self._height), yscrollincrement=ROW_H // 2)
        self.render()

    def render(self) -> None:
        canvas = self.canvas
        canvas.delete("row")
        width = canvas.winfo_width() if canvas.winfo_width() > 1 else int(canvas.cget("width"))
        top = int(canvas.canvasy(0))
        bottom = top + max(canvas.winfo_height(), 1)
        first = max(0, bisect.bisect_right(self._tops, top) - 1)
        for index in range(first, len(self._rows)):
            y = self._tops[index]
            if y > bottom:
                break
            kind, key = self._rows[index]
            if kind == "group":
                self._draw_group(key, y, width)
            else:
                self._draw_item(self.by_id[key], y, width)

    def _draw_group(self, category: str, y: int, width: int) -> None:
        canvas = self.canvas
        _round_rect(canvas, 2, y, width - 4, y + GROUP_H, theme.RADIUS, fill=theme.SURFACE_2, tags="row")
        arrow = "▸" if category in self.collapsed else "▾"
        items = self.groups[category]
        marked = sum(1 for item in items if item.id in self.checked)
        star = "★ " if category == PINNED_GROUP else ""
        title = f"{arrow}  {star}{category}  ·  {len(items)}"
        if marked:
            title += f"  ·  ✓ {marked}"
        mid = y + GROUP_H // 2
        canvas.create_text(14, mid, text=title, anchor="w", fill=theme.TEXT, font=self.bold, tags="row")
        check = self._check_image(self.group_checked(category))
        x = width - GROUP_CHECK_W + 8
        canvas.create_image(x, mid, image=check, anchor="w", tags="row")
        color = theme.ACCENT if self.group_checked(category) and self.enabled else theme.MUTED
        canvas.create_text(x + 38, mid, text="все", anchor="w", fill=color, font=self.font, tags="row")

    def _draw_item(self, item: WatchItem, y: int, width: int) -> None:
        canvas = self.canvas
        mid = y + ROW_H // 2
        if item.id == self.current_match():
            canvas.create_rectangle(
                2, y + 1, width - 4, y + ROW_H - 1, fill=MATCH_BG, outline=theme.ACCENT, tags="row"
            )
        elif self._hover == ("item", item.id):
            canvas.create_rectangle(2, y + 1, width - 4, y + ROW_H - 1, fill=HOVER_BG, outline="", tags="row")
        canvas.create_image(CHECK_X, mid, image=self._check_image(item.id in self.checked), anchor="w", tags="row")
        icon = self.icon_for(item)
        if icon is not None:
            canvas.create_image(ICON_X, mid, image=icon, anchor="w", tags="row")
            if not self.enabled:
                canvas.create_rectangle(
                    ICON_X, mid - 28, ICON_X + 56, mid + 28,
                    fill=theme.SURFACE, outline="", stipple="gray50", tags="row",
                )
        color = theme.GRADE_COLORS.get(item.grade, theme.TEXT) if self.enabled else theme.DISABLED
        canvas.create_text(
            NAME_X, mid, text=item.name, anchor="w", fill=color, font=self.font,
            width=max(60, width - NAME_X - 56), tags="row",
        )
        canvas.create_text(
            width - 14, mid, text=str(item.level), anchor="e", fill=theme.MUTED, font=self.small, tags="row"
        )

    def _check_image(self, on: bool) -> tk.PhotoImage | str:
        key = ("on" if on else "off") + ("" if self.enabled else "_dim")
        return theme.CHECKS.get(key, "")

    # --- events -----------------------------------------------------------------------
    def _row_at(self, y: int) -> tuple[str, str] | None:
        cy = int(self.canvas.canvasy(y))
        index = bisect.bisect_right(self._tops, cy) - 1
        if index < 0:
            return None
        kind, key = self._rows[index]
        height = GROUP_H if kind == "group" else ROW_H
        return (kind, key) if cy < self._tops[index] + height else None

    def _on_click(self, event: tk.Event) -> None:
        row = self._row_at(event.y)
        if row is None:
            return
        kind, key = row
        if kind == "group":
            if event.x >= self.canvas.winfo_width() - GROUP_CHECK_W:
                if self.enabled:
                    self.set_group(key, not self.group_checked(key))
            else:
                self.toggle_collapsed(key)
        elif self.enabled:
            self.toggle_item(key)

    def _on_motion(self, event: tk.Event) -> None:
        self._set_hover(self._row_at(event.y))

    def _set_hover(self, row: tuple[str, str] | None) -> None:
        if row == self._hover:
            return
        self._hover = row
        self.canvas.configure(cursor="hand2" if row is not None else "")
        self.render()
        if row is not None and row[0] == "item":
            self.on_hover(row[1])
        else:
            self.on_leave()

    def _yview(self, *args) -> None:
        self.canvas.yview(*args)
        self.render()

    def _on_search_key(self, event: tk.Event) -> None:
        if event.keysym in ("Return", "Up", "Down", "Escape", "Shift_L", "Shift_R"):
            return
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(SEARCH_DELAY_MS, self._run_search)

    def _run_search(self) -> None:
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = None
        self.search(self.search_var.get())

    def _goto(self, item_id: str) -> None:
        """Unfold the item's section and scroll so the item sits in the upper third of the view."""
        category = self.group_of[item_id]
        if category in self.collapsed:
            self.collapsed.remove(category)
            self._layout()
            self.on_collapse(list(self.collapsed))
        top = self.row_top(item_id) or 0
        view = max(self.canvas.winfo_height(), ROW_H)
        target = max(0, top - view // 3)
        self.canvas.yview_moveto(target / max(self._height, 1))
        self.render()

    def _update_count(self, searching: bool) -> None:
        if not searching:
            text = ""
        elif not self.matches:
            text = "нет"
        else:
            text = f"{self.match_index + 1} / {len(self.matches)}"
        self.count_label.configure(text=text)


def _round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, **options) -> int:
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **options)
