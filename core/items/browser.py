"""State of the «Что искать» list without a window: sections, filters, search and the checked items.

    ItemBrowser(items, checked, collapsed, item_filter)
        .shown            {section: [WatchItem]} after the filter, sections in display order
        .visible          ids of the shown items, in display order
        .checked          set of watched item ids (kept apart from the filter: filtered-out items stay checked)
        .collapsed        list of folded sections
        .search(query) -> number of matches; .step(+1 / -1) -> id of the current match (None without matches)
        .set_all(value) / .set_group(section, value) / .toggle_item(id) / .group_checked(section)
        .toggle_grade(grade), .with_levels_type(low, high, kind), .type_choices(), .chip_state(grade, enabled)

    ItemFilter(grades, level_min, level_max, type).accepts(item): grades empty = all, 0 = any level,
    type is a section («Лата») or «Оружие: Меч». The two classes hold no widget, no timer and no file.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from core.chat.matcher import normalize
from core.items.catalog import CATEGORY_ORDER, WatchItem

PINNED_GROUP = "Рудра и Фланас"  # their gear is pulled out of its sections into this one, always on top
PINNED_RE = re.compile(r"рудр|фланас", re.IGNORECASE)
GRADE_ORDER = ["finality", "mythic", "epic", "unique", "legend", "rare", "common"]
GRADE_LABELS = {
    "finality": "Финал.", "mythic": "Миф.", "epic": "Эпич.", "unique": "Уник.", "legend": "Легенд.",
    "rare": "Редк.", "common": "Обыч.",
}
ALL_TYPES = "Все типы"
ANY_LEVEL = "любой"


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

    @property
    def active(self) -> bool:
        return bool(self.grades or self.level_min or self.level_max or self.type)


class ItemBrowser:
    def __init__(self, items: Iterable[WatchItem], checked: Iterable[str] = (), collapsed: Iterable[str] = (),
                 item_filter: ItemFilter | None = None) -> None:
        self.filter = item_filter or ItemFilter()
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
        self.grades = [g for g in GRADE_ORDER if any(item.grade == g for item in self.by_id.values())]
        self.levels = sorted({item.level for item in self.by_id.values()})
        self.shown: dict[str, list[WatchItem]] = {}
        self.visible: list[str] = []
        self.relayout()

    # --- list ---------------------------------------------------------------------------
    def relayout(self) -> None:
        """Recompute the shown sections and the visible ids after the filter changed."""
        self.shown = {}
        for category, items in self.groups.items():
            kept = [item for item in items if self.filter.accepts(item)]
            if kept:
                self.shown[category] = kept
        self.visible = [item.id for items in self.shown.values() for item in items]

    def checked_ids(self) -> list[str]:
        """Checked item ids in list order."""
        return [item_id for item_id in self.order if item_id in self.checked]

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

    # --- checking and folding -----------------------------------------------------------
    def set_all(self, value: bool) -> None:
        """Check or uncheck every shown item (filtered-out items keep their state)."""
        ids = set(self.visible)
        self.checked = self.checked | ids if value else self.checked - ids

    def set_group(self, category: str, value: bool) -> None:
        ids = {item.id for item in self.shown.get(category, [])}
        self.checked = self.checked | ids if value else self.checked - ids

    def toggle_item(self, item_id: str) -> None:
        self.checked ^= {item_id}

    def group_checked(self, category: str) -> bool:
        items = self.shown.get(category, [])
        return bool(items) and all(item.id in self.checked for item in items)

    def toggle_collapsed(self, category: str) -> None:
        if category in self.collapsed:
            self.collapsed.remove(category)
        else:
            self.collapsed.append(category)

    def expand_for(self, item_id: str) -> bool:
        """Unfold the section of an item; True when it was folded."""
        category = self.group_of[item_id]
        if category in self.collapsed:
            self.collapsed.remove(category)
            return True
        return False

    # --- search -------------------------------------------------------------------------
    def search(self, query: str) -> int:
        """Find shown items whose name holds every word of the query (a number also matches the level)."""
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
        return len(self.matches)

    def step(self, delta: int) -> str | None:
        """Move to the next (1) or previous (-1) match and return its id."""
        if not self.matches:
            return None
        self.match_index = (self.match_index + delta) % len(self.matches)
        return self.matches[self.match_index]

    def current_match(self) -> str | None:
        return self.matches[self.match_index] if self.matches else None

    # --- filter -------------------------------------------------------------------------
    def set_filter(self, item_filter: ItemFilter) -> None:
        self.filter = item_filter
        self.relayout()

    def chip_state(self, grade: str, enabled: bool = True) -> str:
        """«on» (the grade is shown), «off» or «disabled» (the item list is not used by the search mode)."""
        if not enabled:
            return "disabled"
        return "on" if not self.filter.grades or grade in self.filter.grades else "off"

    def toggle_grade(self, grade: str) -> ItemFilter:
        """The filter after a click on a grade chip (all grades shown = an empty set)."""
        shown = set(self.filter.grades or self.grades)
        shown ^= {grade}
        grades = set() if shown >= set(self.grades) else shown
        return ItemFilter(grades, self.filter.level_min, self.filter.level_max, self.filter.type)

    def with_levels_type(self, low: int, high: int, kind: str) -> ItemFilter:
        """The filter after the level or type boxes changed (a reversed range is swapped, «Все типы» = no type)."""
        if low and high and low > high:
            low, high = high, low
        return ItemFilter(set(self.filter.grades), low, high, "" if kind == ALL_TYPES else kind)
