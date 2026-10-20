"""The «Что искать» item list: thousands of items in collapsible sections, with a search box.

Only the rows in view are drawn (on a Canvas), so the list stays fast with ~11 000 items.
Typing in the search box jumps to the first matching item; Enter advances and Shift+Enter goes back.
A match inside a folded section unfolds it.
Filters under the search box hide items by grade, level range and type; search, «Все» and the
section checkboxes only act on the items that are shown.
"""

import bisect
import re
import tkinter as tk
from dataclasses import dataclass, field
from collections.abc import Callable, Iterable
from tkinter import font as tkfont
from tkinter import ttk

from watcher import theme
from watcher.catalog import CATEGORY_ORDER, WatchItem
from watcher.catalog import resource_root
from watcher.ui_icons import IconSet
from watcher.hint import Hint
from core.chat.matcher import normalize

ROW_H = 62  # 56 px icon + gap
GROUP_H = 42
GROUP_GAP = 8
CHECK_X = 8
ICON_X = 46
NAME_X = 112
GROUP_CHECK_W = 96  # right part of a section header that toggles the whole section
SEARCH_DELAY_MS = 150
MATCH_BG = theme.MATCH_BG
HOVER_BG = theme.SURFACE_2
PINNED_GROUP = "Рудра и Фланас"  # their gear is pulled out of its sections into this one, always on top
PINNED_RE = re.compile(r"рудр|фланас", re.IGNORECASE)
GRADE_ORDER = ["finality", "mythic", "epic", "unique", "legend", "rare", "common"]
GRADE_LABELS = {
    "finality": "Финал.", "mythic": "Миф.", "epic": "Эпич.", "unique": "Уник.", "legend": "Легенд.",
    "rare": "Редк.", "common": "Обыч.",
}
ALL_TYPES = "Все типы"
LABEL_CHARS = 5  # ui:36: the width of the «Найти» / «Ур.» label column
ANY_LEVEL = "любой"


def _name_in_two_lines(name: str, width: int, font: tkfont.Font) -> str:
    """Keep long item names inside a fixed-height row without entering the level column."""
    width = max(1, width)
    remaining = " ".join(name.split())
    lines: list[str] = []
    for _ in range(2):
        if not remaining:
            break
        if font.measure(remaining) <= width:
            lines.append(remaining)
            remaining = ""
            break
        low, high = 0, len(remaining)
        while low < high:
            mid = (low + high + 1) // 2
            if font.measure(remaining[:mid]) <= width:
                low = mid
            else:
                high = mid - 1
        cut = max(1, low)
        space = remaining.rfind(" ", 0, cut + 1)
        if space >= cut // 2:
            cut = space
        lines.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining and lines:
        last = lines[-1]
        while last and font.measure(last + "…") > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return "\n".join(lines)


@dataclass
class ItemFilter:
    grades: set[str] = field(default_factory=set)  # shown grades; empty = all
    level_min: int = 0  # 0 = any
    level_max: int = 0  # 0 = any
    type: str = ""  # "" all, a category («Лата») or «Оружие: Меч»

    def accepts(self, item: WatchItem) -> bool:
        if self.grades and item.grade not in self.grades:
            return False
        if self.level_min and item.level < self.level_min:
            return False
        if self.level_max and item.level > self.level_max:
            return False
        if self.type:
            category, _sep, kind = self.type.partition(": ")
            if item.category != category or (kind and item.kind != kind):
                return False
        return True


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
        item_filter: ItemFilter | None = None,
        on_filter: Callable[[ItemFilter], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        self.ui_icons = IconSet(self, resource_root() / "data" / "ui" / "icons")
        self.icon_for = icon_for or (lambda _item: None)
        self.on_change = on_change or (lambda: None)
        self.on_collapse = on_collapse or (lambda _c: None)
        self.on_hover = on_hover or (lambda _i: None)
        self.on_leave = on_leave or (lambda: None)
        self.on_filter = on_filter or (lambda _f: None)
        self.filter = item_filter or ItemFilter()
        self.shown: dict[str, list[WatchItem]] = {}
        self.visible: list[str] = []
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
        self.font = tkfont.Font(font=theme.font("body"))
        self.bold = tkfont.Font(font=theme.font("body_strong"))
        self.small = tkfont.Font(font=theme.font("small"))

        search = ttk.Frame(self, style="Surface.TFrame")
        search.pack(fill="x", padx=(0, 8))
        # ui:36: «Найти» and «Ур.» share one label column; the grade chips start under the fields
        ttk.Label(search, text="Найти", style="CardMuted.TLabel", width=LABEL_CHARS).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search, textvariable=self.search_var, style="Card.TEntry")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.prev_btn = ttk.Button(search, image=self.ui_icons.get("arrow-up", "muted"), style="Card.TButton",
                                   command=lambda: self.step(-1), padding=(6, 5))
        self.next_btn = ttk.Button(search, image=self.ui_icons.get("arrow-down", "muted"), style="Card.TButton",
                                   command=lambda: self.step(1), padding=(6, 5))
        Hint(self.prev_btn, "Предыдущее совпадение")
        Hint(self.next_btn, "Следующее совпадение")
        self.count_label = ttk.Label(search, text="", style="CardMuted.TLabel", anchor="center")  # no empty reserve
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
        self._build_filters()

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
        """Check or uncheck every shown item (filtered-out items keep their state)."""
        ids = set(self.visible)
        self.checked = self.checked | ids if value else self.checked - ids
        self.render()
        self.on_change()

    def set_group(self, category: str, value: bool) -> None:
        ids = {item.id for item in self.shown.get(category, [])}
        self.checked = self.checked | ids if value else self.checked - ids
        self.render()
        self.on_change()

    def toggle_item(self, item_id: str) -> None:
        self.checked ^= {item_id}
        self.render()
        self.on_change()

    def group_checked(self, category: str) -> bool:
        items = self.shown.get(category, [])
        return bool(items) and all(item.id in self.checked for item in items)

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
        if hasattr(self, "grade_chips"):
            self._paint_chips()
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
                for item_id in self.visible
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

    def set_filter(self, item_filter: ItemFilter) -> None:
        self.filter = item_filter
        self._sync_filter_widgets()
        self._layout()
        if self.search_var.get().strip():
            self.search(self.search_var.get())
        self.on_filter(self.filter)

    def type_choices(self) -> list[str]:
        """«Все типы», then each section and, for weapons / accessories, each kind inside it."""
        choices = [ALL_TYPES]
        for category in CATEGORY_ORDER:
            items = [item for items in self.groups.values() for item in items if item.category == category]
            if not items:
                continue
            choices.append(category)
            for kind in sorted({item.kind for item in items if item.kind}):
                choices.append(f"{category}: {kind}")
        return choices

    # --- filters ----------------------------------------------------------------------
    def _build_filters(self) -> None:
        items = list(self.by_id.values())
        self.grades = [g for g in GRADE_ORDER if any(item.grade == g for item in items)]
        levels = sorted({item.level for item in items})
        bar = ttk.Frame(self, style="Surface.TFrame")
        bar.pack(fill="x", padx=(0, 8), pady=(6, 0))
        ttk.Label(bar, text="", style="CardMuted.TLabel", width=LABEL_CHARS).pack(side="left", padx=(0, 6))
        self.grade_chips: dict[str, tk.Label] = {}
        self._chip_hover: str | None = None
        for grade in self.grades:
            chip = tk.Label(
                bar, text=GRADE_LABELS.get(grade, grade), background=theme.SURFACE,
                font=self.small, padx=7, pady=2, cursor="hand2", borderwidth=0,
                highlightthickness=2, highlightcolor=theme.ACCENT, takefocus=1,
            )
            chip.pack(side="left", padx=(0, 4))
            chip.bind("<Button-1>", lambda _e, g=grade: self._toggle_grade(g))
            chip.bind("<space>", lambda _e, g=grade: self._toggle_grade(g))
            chip.bind("<Return>", lambda _e, g=grade: self._toggle_grade(g))
            chip.bind("<Enter>", lambda _e, g=grade: self._hover_chip(g))
            chip.bind("<Leave>", lambda _e: self._hover_chip(None))
            self.grade_chips[grade] = chip
        row = ttk.Frame(self, style="Surface.TFrame")
        row.pack(fill="x", padx=(0, 8), pady=(6, 0))
        ttk.Label(row, text="Ур.", style="CardMuted.TLabel", width=LABEL_CHARS).pack(side="left", padx=(0, 6))
        level_values = [ANY_LEVEL, *map(str, levels)]
        self.level_min_var = tk.StringVar()
        self.level_max_var = tk.StringVar()
        for var, pad in ((self.level_min_var, (0, 4)), (self.level_max_var, (4, 0))):
            box = ttk.Combobox(row, textvariable=var, values=level_values, state="readonly", width=6,
                               style="Card.TCombobox")
            box.pack(side="left", padx=pad)
            box.bind("<<ComboboxSelected>>", lambda _e: self._on_filter_widgets())
            if pad == (0, 4):
                ttk.Label(row, text="–", style="CardMuted.TLabel").pack(side="left")
        self.type_var = tk.StringVar()
        self.type_box = ttk.Combobox(row, textvariable=self.type_var, values=self.type_choices(),
                                     state="readonly", width=18, style="Card.TCombobox")
        self.type_box.pack(side="left", padx=(12, 0), fill="x", expand=True)
        self.type_box.bind("<<ComboboxSelected>>", lambda _e: self._on_filter_widgets())
        self.reset_btn = ttk.Button(row, image=self.ui_icons.get("x", "muted"), style="CardGhost.TButton",
                                    command=self._reset_filter, padding=(6, 5))
        Hint(self.reset_btn, "Сбросить фильтры")
        self._sync_filter_widgets()

    def _sync_filter_widgets(self) -> None:
        f = self.filter
        self._paint_chips()
        self.level_min_var.set(str(f.level_min) if f.level_min else ANY_LEVEL)
        self.level_max_var.set(str(f.level_max) if f.level_max else ANY_LEVEL)
        self.type_var.set(f.type or ALL_TYPES)
        active = bool(f.grades or f.level_min or f.level_max or f.type)
        if active and not self.reset_btn.winfo_manager():
            self.reset_btn.pack(side="left", padx=(4, 0))
        elif not active and self.reset_btn.winfo_manager():
            self.reset_btn.pack_forget()

    def chip_state(self, grade: str) -> str:
        """«on» (the grade is shown), «off» or «disabled» (the item list is not used by the search mode)."""
        if not self.enabled:
            return "disabled"
        return "on" if not self.filter.grades or grade in self.filter.grades else "off"

    def _paint_chips(self) -> None:
        """UI/UX item 13: on — quiet ground + grade colour + outline; off — outline and MUTED text, never «dead»."""
        for grade, chip in self.grade_chips.items():
            state = self.chip_state(grade)
            color = theme.GRADE_COLORS.get(grade, theme.TEXT)
            hover = self._chip_hover == grade and state != "disabled"
            if state == "on":
                ground, text, outline = theme.GRADE_SUBTLE.get(grade, theme.SURFACE_2), color, color
            elif state == "off":
                ground, text, outline = theme.SURFACE, theme.TEXT if hover else theme.MUTED, (
                    theme.TEXT if hover else theme.BORDER_CONTROL)
            else:
                ground, text, outline = theme.SURFACE, theme.DISABLED, theme.SURFACE_3
            chip.configure(background=ground, foreground=text, highlightbackground=outline,
                           highlightcolor=theme.ACCENT, takefocus=state != "disabled",
                           cursor="hand2" if state != "disabled" else "")

    def _hover_chip(self, grade: str | None) -> None:
        self._chip_hover = grade
        self._paint_chips()

    def _toggle_grade(self, grade: str) -> None:
        if not self.enabled:
            return
        shown = set(self.filter.grades or self.grades)
        shown ^= {grade}
        grades = set() if shown >= set(self.grades) else shown
        self.set_filter(ItemFilter(grades, self.filter.level_min, self.filter.level_max, self.filter.type))

    def _on_filter_widgets(self) -> None:
        def level(var: tk.StringVar) -> int:
            return int(var.get()) if var.get().isdigit() else 0

        low, high = level(self.level_min_var), level(self.level_max_var)
        if low and high and low > high:
            low, high = high, low
        kind = self.type_var.get()
        self.set_filter(ItemFilter(set(self.filter.grades), low, high, "" if kind == ALL_TYPES else kind))

    def _reset_filter(self) -> None:
        self.set_filter(ItemFilter())

    # --- layout and drawing -----------------------------------------------------------
    def _layout(self) -> None:
        self.shown = {}
        for category, items in self.groups.items():
            kept = [item for item in items if self.filter.accepts(item)]
            if kept:
                self.shown[category] = kept
        self.visible = [item.id for items in self.shown.values() for item in items]
        self._rows, self._tops = [], []
        y = 0
        for category, items in self.shown.items():
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
        mid = y + GROUP_H // 2
        items = self.shown.get(category, [])
        marked = sum(1 for item in items if item.id in self.checked)
        collapsed = category in self.collapsed
        canvas.create_image(
            14, mid, image=self.ui_icons.get("caret-right" if collapsed else "caret-down", "muted"),
            anchor="w", tags="row",
        )
        title_x = 34
        if category == PINNED_GROUP:
            canvas.create_image(34, mid, image=self.ui_icons.get("star", "accent"), anchor="w", tags="row")
            title_x += 20
        title = f"{category}  ·  {len(items)}"
        if marked:
            title += f"  ·  отмечено {marked}"
        canvas.create_text(title_x, mid, text=title, anchor="w", fill=theme.TEXT, font=self.bold, tags="row")
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
        name_width = max(1, width - NAME_X - 56)  # 14 px edge + level and safe gap
        canvas.create_text(
            NAME_X, mid, text=_name_in_two_lines(item.name, name_width, self.font),
            anchor="w", fill=color, font=self.font, width=name_width, tags="row",
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
