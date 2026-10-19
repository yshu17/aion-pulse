"""NPC / Bestiary tab: global search, sourced details, drops and map locations."""

from __future__ import annotations

import math
import sqlite3
import tkinter as tk
import webbrowser
from types import SimpleNamespace
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from watcher import theme
from watcher.bestiary_store import BestiaryStore
from watcher.search_worker import SearchWorker
from watcher.bestiary_labels import plural, stat_text
from watcher.bestiary_widgets import (
    ProfileHeader, ScrollArea, bind_wheel_tree, keep_pane_cursor, refresh_pointer_cursor, wrap_badges,
)


PAGE_SIZE = 30
CATEGORY = {"Все группы": "", "Монстры": "monster", "NPC": "npc", "Торговцы": "merchant", "Служебные": "service"}
LOADING_DELAY_MS = 1000  # a faster search shows nothing
POLL_MS = 25
FIRST_CARDS = 8  # result cards drawn at once; the rest of the page follows in batches of this size
RARITY = {
    "junk": "Простой", "common": "Обычный", "rare": "Редкий",
    "legend": "Легендарный", "unique": "Уникальный", "epic": "Эпический",
    "mythic": "Мифический",
}


def _set_wrap(label: tk.Label, width: int) -> None:
    """Change the wrap width only when it differs: re-setting it made Tk lay the whole list out again."""
    if int(label.cget("wraplength")) != width:
        label.configure(wraplength=width)


class BestiaryView(ttk.Frame):
    """Thin Tk adapter over BestiaryStore.

    on_map(map_id, game_x, game_y, label) navigates to the existing map tab.
    The view owns only selection/filter state and never writes source data.
    """

    def __init__(
        self, parent: tk.Misc, database: Path, icons_dir: Path,
        map_names: dict[str, str],
        on_map: Callable[[str, float, float, str, list[dict], list[dict]], None],
        on_item_enter: Callable[[dict, object], None] | None = None,
        on_item_leave: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        # item preview, the same tooltip as in «Поиск»: (item {item_id, name, rarity}, its icon) and hide
        self.on_item_enter = on_item_enter or (lambda item, icon: None)
        self.on_item_leave = on_item_leave or (lambda: None)
        self._hover_row: str | None = None
        self.database = Path(database)
        self.icons_dir = Path(icons_dir)
        self.map_names = map_names
        self.on_map = on_map
        self.store: BestiaryStore | None = None
        self._ready = False
        self._after: str | None = None
        self._offset = 0
        self._total = 0
        self._selected_id = ""
        self._detail: dict | None = None
        self._icons: dict[tuple[str, int], object] = {}
        self._map_targets: dict[str, tuple[str, float, float, str]] = {}
        self._zone_ids: dict[str, str] = {"Все локации": ""}
        self._split_after: str | None = None
        self._build()

    def _build(self) -> None:
        style = ttk.Style(self)
        style.configure(
            "Bestiary.Treeview", background=theme.SURFACE, fieldbackground=theme.SURFACE,
            foreground=theme.TEXT, borderwidth=0, rowheight=30, font=theme.font("control"),
        )
        style.map(
            "Bestiary.Treeview",
            background=[("selected", theme.SELECT_BG)],
            foreground=[("selected", theme.TEXT)],
        )
        style.configure("BestiaryItems.Treeview", background=theme.SURFACE, fieldbackground=theme.SURFACE,
                        foreground=theme.TEXT, rowheight=44, font=theme.font("control"), indent=0)
        style.map("BestiaryItems.Treeview", background=[("selected", theme.SELECT_BG)], foreground=[("selected", theme.TEXT)])
        style.layout("BestiaryItems.Treeview.Item", [("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Treeitem.image", {"side": "left", "sticky": ""}), ("Treeitem.text", {"side": "left", "sticky": ""})]})])
        style.configure(
            "Bestiary.Treeview.Heading", background=theme.SURFACE_2,
            foreground=theme.TEXT, font=theme.font("control_strong"),
        )
        self.split = tk.PanedWindow(
            self, orient="horizontal", sashwidth=10, sashcursor="sb_h_double_arrow",
            background=theme.BG, borderwidth=0, opaqueresize=False,
        )
        self.split.pack(fill="both", expand=True)
        left = ttk.Frame(self.split, style="Card.TFrame", padding=12)
        right = ttk.Frame(self.split, style="Card.TFrame", padding=12)
        self.split.add(left, stretch="always", minsize=430)  # the five group chips and the level row need this
        self.split.add(right, stretch="always", minsize=480)
        keep_pane_cursor(self.split, left, right)
        self.bind("<Configure>", self._schedule_initial_split, add="+")

        ttk.Label(left, text="Бестиарий", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        self.coverage_note = ttk.Label(left, text="", style="Muted.TLabel")
        self.coverage_note.pack(anchor="w", pady=(0, 8))
        filters = ttk.Frame(left)
        filters.pack(fill="x", pady=(0, 7))
        filters.columnconfigure(0, weight=1)
        self.query = tk.StringVar()
        self.search = ttk.Entry(filters, textvariable=self.query, style="Card.TEntry")
        self.search.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        self.search.insert(0, "")
        self.search.bind("<KeyRelease>", self._schedule_search)
        self.search.bind("<Return>", lambda _e: self._search(reset=True))
        self.search.bind("<Escape>", lambda _e: (self.query.set(""), self._search(reset=True)))
        self.category = tk.StringVar(value="Все группы")
        self.race = tk.StringVar(value="Все расы")
        self.rank = tk.StringVar(value="Все ранги")
        self.zone = tk.StringVar(value="Все локации")
        self.region = tk.StringVar(value="Все районы")
        self.min_level = tk.StringVar()
        self.max_level = tk.StringVar()
        chips = tk.Frame(left, bg=theme.SURFACE)
        chips.pack(fill="x", pady=(0, 7))
        self.category_chips: dict[str, tk.Button] = {}
        for value, title in (("Все группы", "ВСЕ"), ("Монстры", "МОНСТР"), ("NPC", "NPC"), ("Торговцы", "ТОРГОВЦЫ"), ("Служебные", "СЛУЖЕБНЫЕ")):
            button = tk.Button(chips, text=title, bd=1, relief="solid", cursor="hand2",
                               font=theme.font("micro"), padx=10, pady=4,
                               command=lambda choice=value: self._choose_category(choice))
            button.pack(side="left", padx=(0, 6))
            self.category_chips[value] = button
        self._update_category_chips()
        choices = (
            (self.category, list(CATEGORY), 14),
            (self.race, ["Все расы"], 18),
            (self.rank, ["Все ранги"], 16),
            (self.zone, ["Все локации"], 23),
        )
        self.filter_boxes = []
        for column, (variable, values, width) in enumerate(choices):
            box = ttk.Combobox(filters, textvariable=variable, values=values, state="readonly", width=width)
            box.grid(row=1 + column // 2, column=column % 2, sticky="ew", padx=(8 if column % 2 else 0, 0), pady=3)
            box.bind("<<ComboboxSelected>>", lambda _e: self._search(reset=True))
            filters.columnconfigure(column % 2, weight=1)
            self.filter_boxes.append(box)
        self.filter_boxes[3].bind("<<ComboboxSelected>>", self._zone_changed)
        self.region_box = ttk.Combobox(filters, textvariable=self.region, values=["Все районы"], state="readonly", width=16)
        self.region_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=3)
        self.region_box.bind("<<ComboboxSelected>>", lambda _e: self._search(reset=True))
        levels = ttk.Frame(filters)
        levels.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Label(levels, text="Уровень").pack(side="left", padx=(0, 8))
        validate_level = (self.register(lambda value: not value or (value.isdigit() and len(value) <= 3)), "%P")
        for variable, title in ((self.min_level, "от"), (self.max_level, "до")):
            ttk.Label(levels, text=title).pack(side="left", padx=(4, 4))
            entry = ttk.Entry(levels, textvariable=variable, width=4, validate="key", validatecommand=validate_level)
            entry.pack(side="left")
            entry.bind("<KeyRelease>", self._schedule_search)
        ttk.Button(levels, text="Сброс", command=self._reset_filters, width=6).pack(side="right")
        paging = ttk.Frame(left)
        paging.pack(fill="x", pady=(7, 7))
        self.page_label = ttk.Label(paging, text="", style="Muted.TLabel")
        self.page_label.pack(side="left")
        self.next = ttk.Button(paging, text="→", width=3, command=lambda: self._page(1))
        self.next.pack(side="right")
        self.previous = ttk.Button(paging, text="←", width=3, command=lambda: self._page(-1))
        self.previous.pack(side="right", padx=(0, 4))

        result_body = ttk.Frame(left)
        result_body.pack(fill="both", expand=True)
        self.results = tk.Canvas(result_body, bg=theme.SURFACE, highlightthickness=0, borderwidth=0)
        self.results.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(result_body, orient="vertical", command=self.results.yview)
        scroll.pack(side="right", fill="y")
        self.results.configure(yscrollcommand=scroll.set)
        self.result_frame = tk.Frame(self.results, bg=theme.SURFACE)
        self._results_window = self.results.create_window((0, 0), window=self.result_frame, anchor="nw")
        self.result_frame.bind("<Configure>", lambda _e: self.results.configure(scrollregion=self.results.bbox("all")))
        self.results.bind("<Configure>", lambda e: self.results.itemconfigure(self._results_window, width=e.width))
        self.results.bind("<MouseWheel>", lambda e: self.results.yview_scroll(-int(e.delta / 120), "units"))
        self._result_rows: dict[str, tk.Frame] = {}
        self._cards: list[SimpleNamespace] = []  # reused result cards
        self._worker = SearchWorker(self.database)  # searches run off the UI thread
        self._seq = 0  # number of the newest search request
        self._polling = False
        self._loading_after: str | None = None
        self._loading = tk.Label(self, text="Загрузка…", bg=theme.SURFACE, fg=theme.MUTED, font=theme.font("body"),
                                 cursor="watch")  # covers the list only when a search takes over a second
        self._stale: set[str] = set()  # detail lists not filled yet for the selected NPC (filled when shown)

        self.profile_header = ProfileHeader(right, self.icons_dir)
        self.profile_header.pack(fill="x", pady=(0, 4))
        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(0, 8))
        self.copy_button = ttk.Button(actions, text="Копировать ссылку", command=self._copy_link)
        self.copy_button.pack(side="left")
        self.header_map_button = ttk.Button(actions, text="⌖  На карте", command=self._show_first_on_map)
        self.header_map_button.pack(side="left", padx=(8, 0))
        self.kb_button = ttk.Button(actions, text="Открыть KB", command=self._open_kb)
        self.kb_button.pack(side="left", padx=(8, 0))
        self.copy_button.configure(state="disabled")
        self.header_map_button.configure(state="disabled")
        self.kb_button.configure(state="disabled")
        self.source_note = ttk.Label(right, text="", style="Muted.TLabel", wraplength=350)
        self.source_note.pack(anchor="w", fill="x", pady=(0, 8))

        self.detail_tabs = ttk.Notebook(right)
        self.detail_tabs.pack(fill="both", expand=True)
        self.detail_tabs.bind("<<NotebookTabChanged>>", self._fill_visible)
        overview = ttk.Frame(self.detail_tabs)
        self.detail_tabs.add(overview, text="Обзор")
        self.overview_scroll = ScrollArea(overview)
        self.overview_scroll.pack(fill="both", expand=True)
        self.info_panel = tk.Frame(self.overview_scroll.content, bg=theme.SURFACE)
        self.info_panel.pack(fill="x")
        self.summary_panel = ttk.Frame(self.overview_scroll.content)
        self.summary_panel.pack(fill="both", expand=True, pady=(8, 0))

        drops_tab = self.drops_tab = ttk.Frame(self.detail_tabs)
        self.detail_tabs.add(drops_tab, text="Добыча")
        drop_search = ttk.Frame(drops_tab, padding=(0, 7))
        drop_search.pack(fill="x")
        ttk.Label(drop_search, text="Найти предмет").pack(side="left", padx=(0, 8))
        self.drop_query = tk.StringVar()
        ttk.Entry(drop_search, textvariable=self.drop_query).pack(side="left", fill="x", expand=True)
        self.drop_query.trace_add("write", lambda *_: self._list_changed("drops"))
        drop_body = ttk.Frame(drops_tab)
        drop_body.pack(fill="both", expand=True)
        self.drops = ttk.Treeview(
            drop_body, columns=("name", "rarity"), show="tree headings", style="BestiaryItems.Treeview", height=6,
        )
        self.drops.heading("#0", text="")
        self.drops.column("#0", width=52, minwidth=52, stretch=False)
        self.drops.heading("name", text="Предмет")
        self.drops.column("name", width=210, stretch=True)
        self.drops.heading("rarity", text="Редкость")
        self.drops.column("rarity", width=100, stretch=False)
        self.drops.pack(side="left", fill="both", expand=True)
        drop_scroll = ttk.Scrollbar(drop_body, command=self.drops.yview)
        drop_scroll.pack(side="right", fill="y")
        self.drops.configure(yscrollcommand=drop_scroll.set)
        for rarity, color in theme.GRADE_COLORS.items():
            self.drops.tag_configure(rarity, foreground=color)
        self.drops.bind("<Motion>", lambda e: self._hover_list(self.drops, e))
        self.drops.bind("<Leave>", lambda _e: self._leave_list())
        self.drops.bind("<Double-1>", self._open_item)
        self.drops.bind("<Return>", self._open_item)
        self.drop_count = ttk.Label(drops_tab, text="", style="Muted.TLabel", wraplength=450)
        self.drop_count.pack(side="bottom", anchor="w", pady=(6, 0), before=drop_body)

        places_tab = self.places_tab = ttk.Frame(self.detail_tabs)
        self.detail_tabs.add(places_tab, text="Локации")
        places_body = ttk.Frame(places_tab)
        places_body.pack(fill="both", expand=True)
        self.places = ttk.Treeview(
            places_body, columns=("place", "count"), show="tree headings", style="Bestiary.Treeview", height=6,
        )
        self.places.heading("#0", text="")
        self.places.column("#0", width=18, minwidth=18, stretch=False)
        self.places.heading("place", text="Зона / точка")
        self.places.column("place", width=260, stretch=True)
        self.places.heading("count", text="Точек")
        self.places.column("count", width=56, stretch=False)
        self.places.pack(side="left", fill="both", expand=True)
        places_scroll = ttk.Scrollbar(places_body, command=self.places.yview)
        places_scroll.pack(side="right", fill="y")
        self.places.configure(yscrollcommand=places_scroll.set)
        self.places.bind("<<TreeviewSelect>>", lambda _e: self._update_map_button())
        self.places.bind("<Double-1>", self._show_on_map)
        self.places.bind("<Return>", self._show_on_map)
        footer = ttk.Frame(places_tab)
        footer.pack(fill="x", pady=(8, 0))
        self.map_button = ttk.Button(footer, text="Показать на карте", command=self._show_on_map)
        self.map_button.pack(side="right")
        self.map_button.configure(state="disabled")
        ttk.Label(
            places_tab, text="Области приблизительны; точки взяты из файлов клиента.",
            style="Muted.TLabel", wraplength=330,
        ).pack(anchor="w", pady=(6, 0))

        stock = self.stock_tab = ttk.Frame(self.detail_tabs, padding=(0, 7))
        self.detail_tabs.add(stock, text="Товары", state="hidden")
        self.stock_query = tk.StringVar()
        stock_search = ttk.Frame(stock)
        stock_search.pack(fill="x", pady=(0, 7))
        ttk.Label(stock_search, text="Найти товар").pack(side="left", padx=(0, 8))
        ttk.Entry(stock_search, textvariable=self.stock_query).pack(side="left", fill="x", expand=True)
        self.stock_query.trace_add("write", lambda *_: self._list_changed("stock"))
        stock_body = ttk.Frame(stock)
        stock_body.pack(fill="both", expand=True)
        self.stock = ttk.Treeview(stock_body, columns=("name", "group", "mode"), show="tree headings", style="BestiaryItems.Treeview")
        self.stock.column("#0", width=52, minwidth=52, stretch=False)
        for column, title, width in (("name", "Предмет", 220), ("group", "Раздел", 130), ("mode", "Способ", 100)):
            self.stock.heading(column, text=title)
            self.stock.column(column, width=width, minwidth=70, stretch=column == "name")
        self.stock.pack(side="left", fill="both", expand=True)
        stock_scroll = ttk.Scrollbar(stock_body, command=self.stock.yview)
        stock_scroll.pack(side="right", fill="y")
        self.stock.configure(yscrollcommand=stock_scroll.set)
        for rarity, color in theme.GRADE_COLORS.items():
            self.stock.tag_configure(rarity, foreground=color)
        self.stock.bind("<Motion>", lambda e: self._hover_list(self.stock, e))
        self.stock.bind("<Leave>", lambda _e: self._leave_list())
        self.stock.bind("<Double-1>", self._open_stock_item)
        self.stock.bind("<Return>", self._open_stock_item)
        self.stock_note = ttk.Label(stock, text="", style="Muted.TLabel", wraplength=500)
        self.stock_note.pack(side="bottom", anchor="w", pady=(7, 0), before=stock_body)

    def _schedule_initial_split(self, _event: tk.Event) -> None:
        if getattr(self, "_split_set", False):
            return
        if self._split_after:
            self.after_cancel(self._split_after)
        self._split_after = self.after(180, self._set_initial_split)

    def _set_initial_split(self) -> None:
        self._split_after = None
        if self.split.winfo_width() < 650:
            return
        self._split_set = True
        self.split.sash_place(0, max(430, round(self.split.winfo_width() * 0.33)), 0)

    def activate(self) -> None:
        if self._ready:
            return
        self._ready = True
        try:
            self.store = BestiaryStore(self.database)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.page_label.configure(text="База недоступна")
            self._write_overview(
                "Не удалось открыть данные бестиария.\n\n"
                f"{exc}\n\nДля локальной сборки запустите tools/build_bestiary_index.py."
            )
            return
        self.filter_boxes[1].configure(values=["Все расы", *self.store.races()])
        total, profiles, levels = self.store.coverage()
        self.coverage_note.configure(text=f"Подробные профили: {profiles:,} / {total:,}".replace(",", " "))
        self.filter_boxes[2].configure(values=["Все ранги", *self.store.ranks()])
        self._zone_ids = {"Все локации": ""}
        for map_id, name in self.store.zones():
            self._zone_ids[name if name not in self._zone_ids else f"{name} ({map_id})"] = map_id
        self.filter_boxes[3].configure(values=list(self._zone_ids))
        self.region_box.configure(values=["Все районы", *self.store.regions()])
        self._search(reset=True)

    def _schedule_search(self, event: tk.Event) -> None:
        if event.keysym in ("Up", "Down", "Left", "Right", "Return"):
            return
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(220, lambda: self._search(reset=True))

    def _search(self, reset: bool = False) -> None:
        if self._after:
            self.after_cancel(self._after)
            self._after = None
        if not self.store:
            return
        self._update_category_chips()
        if reset:
            self._offset = 0
        low = int(self.min_level.get()) if self.min_level.get().isdigit() else None
        high = int(self.max_level.get()) if self.max_level.get().isdigit() else None
        if low is not None and high is not None and low > high:
            self.page_label.configure(text="Уровень «от» больше «до»")
            return
        self._seq += 1
        self._worker.submit(
            self._seq, self.query.get(), CATEGORY[self.category.get()],
            "" if self.race.get() == "Все расы" else self.race.get(),
            "" if self.rank.get() == "Все ранги" else self.rank.get(),
            self._zone_ids.get(self.zone.get(), ""), self._offset, PAGE_SIZE,
            min_level=low, max_level=high, region="" if self.region.get() == "Все районы" else self.region.get(),
        )
        if self._loading_after is None:  # the indicator appears only when a search is really slow
            self._loading_after = self.after(LOADING_DELAY_MS, self._show_loading)
        if not self._polling:
            self._polling = True
            self.after(POLL_MS, self._poll_search)

    def _poll_search(self) -> None:
        """Pick up the newest finished search; answers to requests that were already replaced are dropped."""
        if not self.winfo_exists():
            return
        result = self._worker.latest()
        if result is not None and result.seq == self._seq:
            self._polling = False
            self._hide_loading()
            self._apply_results(result)
            return
        self.after(POLL_MS, self._poll_search)

    def _show_loading(self) -> None:
        self._loading_after = None
        self._loading.place(in_=self.results, relx=0, rely=0, relwidth=1, relheight=1)
        self._loading.lift()

    def _hide_loading(self) -> None:
        if self._loading_after is not None:
            self.after_cancel(self._loading_after)
            self._loading_after = None
        if self._loading.winfo_ismapped():
            self._loading.place_forget()
            refresh_pointer_cursor(self)

    def wait_for_search(self, timeout: float = 5.0) -> None:
        """Run the event loop until the last requested search is shown (tests, scripts)."""
        import time
        end = time.monotonic() + timeout
        while self._polling and time.monotonic() < end:
            self.update()
            time.sleep(0.005)

    def _apply_results(self, result) -> None:
        rows, self._total = result.rows, result.total
        if result.error:
            self.page_label.configure(text="Поиск не удался")
            self._clear_detail()
            return
        self._render_results(rows)
        first = self._offset + 1 if rows else 0
        last = self._offset + len(rows)
        self.page_label.configure(text=f"{first}–{last} из {self._total} NPC" if rows else "Ничего не найдено")
        self.previous.configure(state="normal" if self._offset else "disabled")
        self.next.configure(state="normal" if last < self._total else "disabled")
        if rows:
            self._select_npc(rows[0]["id"])
            self.results.yview_moveto(0)
        else:
            self._clear_detail()

    def _zone_changed(self, _event=None) -> None:
        self.region.set("Все районы")
        if self.store:
            self.region_box.configure(values=["Все районы", *self.store.regions(self._zone_ids.get(self.zone.get(), ""))])
        self._search(reset=True)

    def _reset_filters(self) -> None:
        self.category.set("Все группы")
        self.race.set("Все расы")
        self.rank.set("Все ранги")
        self.zone.set("Все локации")
        self.min_level.set("")
        self.max_level.set("")
        self._zone_changed()

    def _choose_category(self, value: str) -> None:
        self.category.set(value)
        self._search(reset=True)

    def _update_category_chips(self) -> None:
        for value, button in self.category_chips.items():
            active = self.category.get() == value
            button.configure(bg=theme.ACCENT_SUBTLE if active else theme.SURFACE_2,
                             fg=theme.ACCENT if active else theme.TEXT,
                             activebackground=theme.ACCENT_SUBTLE,
                             highlightbackground=theme.ACCENT if active else theme.BORDER)

    def _make_card(self) -> SimpleNamespace:
        """One result card; cards are reused between searches (creating and destroying ~40 widgets per card made
        every search and page switch take half a second)."""
        card = SimpleNamespace(npc_id="")
        card.outer = tk.Frame(self.result_frame, padx=1, pady=1, cursor="hand2")
        card.inner = tk.Frame(card.outer, padx=8, pady=7)
        card.inner.pack(fill="x")
        card.picture = tk.Label(card.inner, width=50, height=50)
        card.picture.pack(side="left", padx=(0, 9))
        card.info = tk.Frame(card.inner)
        card.info.pack(side="left", fill="x", expand=True)
        card.name = tk.Label(card.info, fg=theme.TEXT, font=theme.font("control_strong"), anchor="w", justify="left")
        card.name.pack(fill="x")
        card.info.bind("<Configure>", lambda e, label=card.name: _set_wrap(label, max(100, e.width)))
        card.summary = tk.Label(card.info, fg=theme.MUTED, font=theme.font("small"), anchor="w")
        card.summary.pack(fill="x", pady=(2, 2))
        card.hit = tk.Label(card.info, fg=theme.ACCENT, font=theme.font("small"), anchor="w")
        card.chips = tk.Frame(card.info)
        card.chips.pack(fill="x")
        card.chip_labels = [
            tk.Label(card.chips, bg=theme.SURFACE_2, fg=color, font=theme.font("micro"), padx=5, pady=1)
            for color in (theme.PLACE, theme.DANGER, theme.MUTED)
        ]
        card.arrange = wrap_badges(card.chips)
        for widget in (card.outer, card.inner, card.picture, card.info, card.chips, card.name, card.summary,
                       card.hit, *card.chip_labels):
            widget.bind("<Button-1>", lambda _e, c=card: self._select_npc(c.npc_id))
        bind_wheel_tree(card.outer, self.results)
        return card

    def _render_results(self, rows: list[dict]) -> None:
        """The first cards at once, the rest in small batches, so typing and clicking never wait for a full page."""
        self._render_generation = getattr(self, "_render_generation", 0) + 1
        self._result_rows.clear()
        for card in self._cards[FIRST_CARDS:]:
            card.npc_id = ""
            card.outer.pack_forget()
        self._fill_cards(rows, 0, self._render_generation)

    def _fill_cards(self, rows: list[dict], start: int, generation: int) -> None:
        if generation != self._render_generation or not self.winfo_exists():
            return
        end = min(len(rows), start + FIRST_CARDS)
        while len(self._cards) < end:
            self._cards.append(self._make_card())
        for card, row in zip(self._cards[start:end], rows[start:end]):
            npc_id = card.npc_id = str(row["id"])
            asset = "ui/monster.png" if row["kind"] == "Монстр" else row["icon_asset"]
            card.picture.configure(image=self._load_icon(asset, 48) or "")
            card.name.configure(text=row["name"])
            summary = f"Уровень {row['level']}" if row["level"] else "Уровень не указан"
            zone = row["zone_names"].split(", ", 1)[0]
            card.summary.configure(text=summary + (f"  ·  {zone}" if zone else ""))
            hit = f"Продаёт: {row['sold']}" if row.get("sold") else f"Добыча: {row['dropped']}" if row.get("dropped") else ""
            card.hit.configure(text=hit)
            if hit and not card.hit.winfo_manager():
                card.hit.pack(fill="x", pady=(0, 2), before=card.chips)
            elif not hit and card.hit.winfo_manager():
                card.hit.pack_forget()
            for label, text in zip(card.chip_labels, (row["kind"], row.get("faction") or row["race"], row["rank"])):
                label.configure(text=str(text or "").upper())
            card.arrange()
            selected = npc_id == self._selected_id
            card.outer.configure(bg=theme.ACCENT if selected else theme.BORDER)
            self._set_card_bg(card.inner, theme.ACCENT_SUBTLE if selected else theme.SURFACE)
            if not card.outer.winfo_manager():
                card.outer.pack(fill="x", pady=(0, 5))
            self._result_rows[npc_id] = card.outer
        if end < len(rows):
            self.after(15, lambda: self._fill_cards(rows, end, generation))
        else:
            if start == 0:
                for card in self._cards[end:]:
                    card.npc_id = ""
                    card.outer.pack_forget()
            self.after_idle(lambda: refresh_pointer_cursor(self))  # the card under the pointer may be another one now

    def _select_npc(self, npc_id: str) -> None:
        if not self.store:
            return
        for row_id in {self._selected_id, npc_id}:  # restyle only the card losing and the card getting the selection
            frame = self._result_rows.get(row_id)
            if frame is None:
                continue
            active = row_id == npc_id
            frame.configure(bg=theme.ACCENT if active else theme.BORDER)
            self._set_card_bg(frame.winfo_children()[0], theme.ACCENT_SUBTLE if active else theme.SURFACE)
        if npc_id == self._selected_id:
            return
        self._select_result(npc_id)

    def _set_card_bg(self, widget: tk.Misc, color: str) -> None:
        try:
            widget.configure(bg=color)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            if not isinstance(child, tk.Label) or child.cget("bg") != theme.SURFACE_2:
                self._set_card_bg(child, color)

    def _page(self, direction: int) -> None:
        self._offset = max(0, self._offset + direction * PAGE_SIZE)
        self._search()

    def open_npc(self, npc_id: str) -> None:
        """Select an NPC from another tab or a pasted pulse://npc/<id> link."""
        self.activate()
        self.query.set(f"pulse://npc/{npc_id}")
        self.category.set("Все группы")
        self.race.set("Все расы")
        self.rank.set("Все ранги")
        self.zone.set("Все локации")
        self.region.set("Все районы")
        self.min_level.set("")
        self.max_level.set("")
        self._search(reset=True)

    def _select_result(self, npc_id: str) -> None:
        if not self.store:
            return
        if npc_id == self._selected_id:
            return
        detail = self.store.detail(npc_id)
        if detail is None:
            return
        self._selected_id = npc_id
        self._detail = detail
        self._stale = {"drops", "places", "stock"}  # long lists are filled when their tab is opened
        self.profile_header.show(detail)
        self.drop_query.set("")
        self.stock_query.set("")
        term = self.query.get().strip().casefold()
        if term and any(term in str(i.get("name", "")).casefold() for i in detail.get("drops") or []):
            self.drop_query.set(term)  # a mob found by a dropped item: show that item in the drop list
        if term and any(term in str(i.get("name", "")).casefold() for i in detail.get("stock") or []):
            self.stock_query.set(term)  # a merchant found by an item: show that item in the goods list
        self.copy_button.configure(state="normal")
        self.kb_button.configure(state="normal" if detail.get("kb_url") else "disabled")
        self.source_note.configure(
            text="Данные KB + файлы клиента" if detail.get("kb_status") == "loaded"
            else "Данные клиента; подробный профиль KB не загружен"
        )
        self.detail_tabs.tab(
            self.stock_tab,
            state="normal" if detail.get("role") == "merchant" or detail.get("kind") == "Торговец" else "hidden",
        )
        self._fill_overview(detail)
        self._fill_summary(detail)
        self.detail_tabs.select(self.stock_tab if detail.get("stock") else 0)
        self._fill_visible()
        self.overview_scroll.refresh()

    def _list_changed(self, name: str) -> None:
        self._stale.add(name)
        self._fill_visible()

    def _fill_visible(self, _event=None) -> None:
        """Fill the open tab's list if the selected NPC changed or its filter did since it was last filled."""
        if not self._detail:
            return
        current = self.detail_tabs.select()
        for name, tab, fill in (("drops", self.drops_tab, self._fill_drops), ("places", self.places_tab, self._fill_places),
                                ("stock", self.stock_tab, self._fill_stock)):
            if name in self._stale and current == str(tab):
                self._stale.discard(name)
                fill(self._detail)

    def _clear_detail(self) -> None:
        self._selected_id = ""
        self._detail = None
        self.profile_header.show(None)
        self.source_note.configure(text="")
        self.detail_tabs.tab(self.stock_tab, state="hidden")
        self.copy_button.configure(state="disabled")
        self.kb_button.configure(state="disabled")
        self.header_map_button.configure(state="disabled")
        self._write_overview("")
        self.drops.delete(*self.drops.get_children())
        self.drop_count.configure(text="")
        self.stock.delete(*self.stock.get_children())
        self.stock_note.configure(text="")
        self.places.delete(*self.places.get_children())
        self._map_targets.clear()
        self.map_button.configure(state="disabled")
        for child in self.summary_panel.winfo_children():
            child.destroy()

    def _fill_summary(self, detail: dict) -> None:
        for child in self.summary_panel.winfo_children():
            child.destroy()
        drops = detail.get("drops") or []
        points = detail.get("points") or []
        self.header_map_button.configure(state="normal" if any(str(p.get("map_id")) in self.map_names for p in points) else "disabled")
        sections = (
            ("Добыча", drops[:5], "В профиле KB нет списка добычи." if detail.get("kb_status") == "loaded"
             else "Сведения о добыче пока не загружены."),
            ("Локации", [], "Точки появления в файлах клиента не найдены."),
        )
        for heading, entries, empty in sections:
            block = tk.Frame(self.summary_panel, bg=theme.SURFACE_2, padx=12, pady=9)
            block.pack(fill="x", pady=(0, 8))
            tk.Label(block, text=heading, bg=theme.SURFACE_2, fg=theme.TEXT,
                     font=theme.font("control_strong"), anchor="w").pack(fill="x", pady=(0, 5))
            if heading == "Добыча":
                if not entries:
                    tk.Label(block, text=empty, bg=theme.SURFACE_2, fg=theme.MUTED,
                             anchor="w", font=theme.font("small")).pack(fill="x")
                for item in entries:
                    row = tk.Frame(block, bg=theme.SURFACE_2)
                    row.pack(fill="x", pady=2)
                    asset = f"items/{Path(item.get('icon') or '').name}"
                    icon = self._load_icon(asset, 32)
                    row.columnconfigure(1, weight=1)
                    icon_box = tk.Frame(row, bg=theme.SURFACE_2, width=36, height=36)
                    icon_box.grid(row=0, column=0, padx=(0, 12), pady=3)
                    icon_box.pack_propagate(False)
                    tk.Label(icon_box, image=icon or "", text="" if icon else "—", bg=theme.SURFACE_2,
                             fg=theme.MUTED).pack(fill="both", expand=True)
                    name = tk.Label(row, text=item.get("name") or item.get("item_id") or "Предмет",
                                    bg=theme.SURFACE_2, fg=theme.GRADE_COLORS.get(item.get("rarity"), theme.TEXT),
                                    anchor="w", cursor="hand2", justify="left")
                    name.grid(row=0, column=1, sticky="ew")
                    name.bind("<Configure>", lambda e, label=name: label.configure(wraplength=max(120, e.width - 10)))
                    if item.get("item_id"):
                        name.bind("<Button-1>", lambda _e, value=item["item_id"]: webbrowser.open(f"https://kb.aionempire.com/items/{value}"))
                    preview = ({"item_id": str(item.get("item_id") or ""), "name": item.get("name") or "",
                                "rarity": item.get("rarity") or ""}, self._load_icon(asset, 40))
                    for widget in (name, icon_box, *icon_box.winfo_children()):
                        widget.bind("<Enter>", lambda _e, p=preview: self.on_item_enter(*p), add="+")
                        widget.bind("<Leave>", lambda _e: self.on_item_leave(), add="+")
                if len(drops) > len(entries):
                    ttk.Button(block, text=f"Показать все {len(drops)} предметов →",
                               command=lambda: self.detail_tabs.select(1)).pack(anchor="e")
            else:
                counts: dict[str, int] = defaultdict(int)
                for point in points:
                    counts[str(point.get("map_id") or "")] += 1
                if not counts:
                    locations = [loc.get("name") or loc.get("slug") for loc in detail.get("kb_locations") or []]
                    location_text = "По базе KB: " + ", ".join(filter(None, locations)) if locations else empty
                    tk.Label(block, text=location_text, bg=theme.SURFACE_2, fg=theme.MUTED, wraplength=400, justify="left",
                             anchor="w", font=theme.font("small")).pack(fill="x")
                if counts and detail.get("points_from"):
                    tk.Label(block, text=f"Места взяты у одноимённой записи «{detail['points_from']}».", bg=theme.SURFACE_2,
                             fg=theme.MUTED, wraplength=400, justify="left", anchor="w",
                             font=theme.font("small")).pack(fill="x")
                for map_id, count in sorted(counts.items(), key=lambda pair: self.map_names.get(pair[0], pair[0])):
                    row = tk.Frame(block, bg=theme.SURFACE_2)
                    row.pack(fill="x", pady=3)
                    tk.Label(row, text=f"⌖  {self.map_names.get(map_id, map_id)}  ·  {plural(count, "точка", "точки", "точек")}",
                             bg=theme.SURFACE_2, fg=theme.TEXT, anchor="w").pack(side="left", fill="x", expand=True)
                    if map_id in self.map_names:
                        ttk.Button(row, text="На карте", command=lambda value=map_id: self._show_zone_on_map(value)).pack(side="right")

    def _show_first_on_map(self) -> None:
        points = (self._detail or {}).get("points") or []
        for point in points:
            if str(point.get("map_id")) in self.map_names:
                self._show_zone_on_map(str(point["map_id"]))
                return

    def _show_zone_on_map(self, map_id: str) -> None:
        if not self._detail:
            return
        points = [p for p in self._detail.get("points") or [] if str(p.get("map_id")) == map_id]
        if not points:
            return
        selected = points[0]
        areas = [area for area in (self.store.areas(self._selected_id) if self.store else [])
                 if area["map_id"] == map_id]
        self.on_map(map_id, float(selected["gx"]), float(selected["gy"]), self._detail["name"], points, areas)

    def _overview_widgets(self) -> SimpleNamespace:
        """Overview labels are created once and reused for every NPC (rebuilding them cost most of a click)."""
        if getattr(self, "_overview", None) is None:
            panel = self.info_panel
            ov = self._overview = SimpleNamespace(cells=[])
            ov.intro = tk.Label(panel, bg=theme.SURFACE, fg=theme.TEXT, justify="left", anchor="w", wraplength=450,
                                font=theme.font("body"), padx=12, pady=10)
            ov.intro.bind("<Configure>", lambda e: ov.intro.configure(wraplength=max(200, e.width - 24)))
            ov.note = tk.Label(panel, text="Подробные характеристики пока не загружены.", bg=theme.SURFACE,
                               fg=theme.MUTED, wraplength=400, justify="left")
            ov.message = tk.Label(panel, bg=theme.SURFACE, fg=theme.TEXT, wraplength=450, justify="left")
        return self._overview

    def _stat_cell(self, index: int) -> SimpleNamespace:
        ov = self._overview_widgets()
        while len(ov.cells) <= index:
            cell = SimpleNamespace(frame=tk.Frame(self.info_panel, bg=theme.SURFACE_2, padx=12, pady=9))
            cell.name = tk.Label(cell.frame, bg=theme.SURFACE_2, fg=theme.MUTED, font=theme.font("micro"), anchor="w")
            cell.name.pack(fill="x")
            cell.value = tk.Label(cell.frame, bg=theme.SURFACE_2, fg=theme.TEXT, font=theme.font("control_strong"),
                                  anchor="w", justify="left")
            cell.value.pack(fill="x", pady=(3, 0))
            cell.frame.bind("<Configure>", lambda e, target=cell.value: target.configure(wraplength=max(80, e.width - 24)))
            ov.cells.append(cell)
        return ov.cells[index]

    def _fill_overview(self, detail: dict) -> None:
        ov = self._overview_widgets()
        ov.message.grid_remove()
        stats = detail.get("stats") or {}
        rows = [("Уровень", detail.get("level") or "Не указан"),
                ("Ранг", detail.get("rank") or "Не указан"),
                *stats.items(), ("Принадлежность", detail.get("faction") or "Другие"),
                ("Вид", detail.get("race") or "Не указан")]
        self.info_panel.columnconfigure(0, weight=1, uniform="stats")
        self.info_panel.columnconfigure(1, weight=1, uniform="stats")
        description = "\n".join(value for value in (detail.get("title"), detail.get("description")) if value)
        if detail.get("stock"):
            groups = list(dict.fromkeys(item.get("group", "") for item in detail["stock"]))
            description += "\nТорговые разделы: " + ", ".join(filter(None, groups))
        first_row = 0
        if description.strip():
            ov.intro.configure(text=description.strip())
            ov.intro.grid(row=0, column=0, columnspan=2, sticky="ew")
            first_row = 1
        else:
            ov.intro.grid_remove()
        for index, (name, value) in enumerate(rows):
            cell = self._stat_cell(index)
            cell.name.configure(text=str(name).upper())
            cell.value.configure(text=stat_text(value))
            cell.frame.grid(row=first_row + index // 2, column=index % 2, sticky="nsew", padx=1, pady=1)
        for cell in ov.cells[len(rows):]:
            cell.frame.grid_remove()
        if stats:
            ov.note.grid_remove()
        else:
            ov.note.grid(row=first_row + len(rows) // 2 + 1, column=0, columnspan=2, sticky="w", pady=8)

    def _write_overview(self, text: str) -> None:
        ov = self._overview_widgets()
        for widget in (ov.intro, ov.note, *(cell.frame for cell in ov.cells)):
            widget.grid_remove()
        if text:
            ov.message.configure(text=text)
            ov.message.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=12)
        else:
            ov.message.grid_remove()

    def _fill_drops(self, detail: dict) -> None:
        self.drops.delete(*self.drops.get_children())
        for index, item in enumerate(detail.get("drops") or []):
            if self.drop_query.get().strip().casefold() not in str(item.get("name") or "").casefold():
                continue
            asset = f"items/{Path(item.get('icon') or '').name}"
            icon = self._load_icon(asset, 32)
            rarity = str(item.get("rarity") or "")
            self.drops.insert(
                "", "end", iid=f"d{index}", image=icon or "", tags=(rarity,),
                values=(item.get("name") or item.get("item_id") or "Без названия", RARITY.get(rarity, rarity)),
            )
        total = len(detail.get("drops") or [])
        self.drop_count.configure(text=f"Показано {len(self.drops.get_children())} из {total}. Шансы выпадения не указаны."
                                  if total else "В профиле нет списка добычи." if detail.get("kb_status") == "loaded"
                                  else "Сведения о добыче пока не загружены.")

    def _fill_stock(self, detail: dict) -> None:
        self.stock.delete(*self.stock.get_children())
        term = self.stock_query.get().strip().casefold()
        items = detail.get("stock") or []
        for index, item in enumerate(items):
            if term not in (item.get("name", "") + " " + item.get("group", "")).casefold():
                continue
            icon = self._load_icon(item.get("icon_asset", ""), 32)
            self.stock.insert("", "end", iid=f"s{index}", image=icon or "", tags=(item.get("rarity", ""),),
                              values=(item.get("name", ""), item.get("group", ""), item.get("trade_mode", "")))
        self.stock_note.configure(text=f"Показано {len(self.stock.get_children())} из {len(items)}. Ассортимент из клиента; на сервере возможны отличия."
                                  if items else "Для этого NPC список товаров в клиенте не найден.")

    def _list_item(self, row: str) -> tuple[dict, object] | None:
        """The item behind a drop («d<n>») or goods («s<n>») row, with the icon the row shows."""
        if not row or not self._detail:
            return None
        items = self._detail.get("drops" if row[0] == "d" else "stock") or []
        try:
            item = items[int(row[1:])]
        except (IndexError, ValueError):
            return None
        if row[0] == "d":
            icon = self._load_icon(f"items/{Path(item.get('icon') or '').name}", 40)
        else:
            icon = self._load_icon(item.get("icon_asset", ""), 40)
        return {"item_id": str(item.get("item_id") or ""), "name": item.get("name") or "",
                "rarity": item.get("rarity") or ""}, icon

    def _hover_list(self, tree: ttk.Treeview, event: tk.Event) -> None:
        row = tree.identify_row(event.y)
        if row == self._hover_row:
            return
        self._hover_row = row
        found = self._list_item(row)
        if found is None:
            self.on_item_leave()
        else:
            self.on_item_enter(*found)

    def _leave_list(self) -> None:
        self._hover_row = None
        self.on_item_leave()

    def _open_stock_item(self, _event=None) -> None:
        selected = self.stock.selection()
        if selected and self._detail:
            item = self._detail["stock"][int(selected[0][1:])]
            webbrowser.open(f"https://kb.aionempire.com/items/{item['item_id']}")

    def _fill_places(self, detail: dict) -> None:
        self.places.delete(*self.places.get_children())
        self._map_targets.clear()
        self.map_button.configure(state="disabled")
        points_by_zone: dict[str, list[dict]] = defaultdict(list)
        for point in detail.get("points") or []:
            points_by_zone[str(point.get("map_id") or "")].append(point)
        areas_by_zone: dict[str, list[dict]] = defaultdict(list)
        if self.store:
            for area in self.store.areas(detail["id"]):
                areas_by_zone[area["map_id"]].append(area)
        for map_id, points in sorted(points_by_zone.items(), key=lambda item: self.map_names.get(item[0], item[0])):
            zone_name = self.map_names.get(map_id, map_id)
            parent = self.places.insert("", "end", values=(zone_name, len(points)), open=True)
            if points and map_id in self.map_names:
                point = points[0]
                self._map_targets[parent] = (
                    map_id, float(point["gx"]), float(point["gy"]), detail["name"],
                )
            for area in areas_by_zone[map_id]:
                clean_names = [name for name in area["names"] if "\ufffd" not in name]
                name = ", ".join(clean_names[:2]) if clean_names else "Область появления"
                area_row = self.places.insert(
                    parent, "end", values=(f"≈ {name}", area["point_count"])
                )
                if points and map_id in self.map_names:
                    cx, cy = area["center"]
                    closest = min(
                        points, key=lambda point: math.hypot(float(point["x"]) - cx, float(point["y"]) - cy)
                    )
                    self._map_targets[area_row] = (
                        map_id, float(closest["gx"]), float(closest["gy"]), detail["name"],
                    )
            for index, point in enumerate(points, 1):
                row = self.places.insert(
                    parent, "end", values=(f"Точка {index}  ·  {float(point['x']):.0f}, {float(point['y']):.0f}", "")
                )
                if map_id in self.map_names:
                    self._map_targets[row] = (
                        map_id, float(point["gx"]), float(point["gy"]), detail["name"],
                    )
        # KB coordinates use a different system; show the named locations without
        # offering a misleading jump to the game's map.
        for location in detail.get("kb_locations") or []:
            self.places.insert(
                "", "end", values=(f"KB: {location.get('name') or location.get('slug') or 'Зона'}",
                                    location.get("count", len(location.get("points") or []))),
            )

    def _update_map_button(self) -> None:
        selected = self.places.selection()
        self.map_button.configure(state="normal" if selected and selected[0] in self._map_targets else "disabled")

    def _show_on_map(self, _event: tk.Event | None = None) -> None:
        selected = self.places.selection()
        if selected and (target := self._map_targets.get(selected[0])):
            map_id = target[0]
            points = [
                point for point in (self._detail or {}).get("points") or []
                if str(point.get("map_id")) == map_id
            ]
            areas = [
                area for area in (self.store.areas(self._selected_id) if self.store else [])
                if area["map_id"] == map_id
            ]
            self.on_map(*target, points, areas)

    def _copy_link(self) -> None:
        if not self._selected_id:
            return
        self.clipboard_clear()
        self.clipboard_append(f"pulse://npc/{self._selected_id}")
        self.update_idletasks()
        self.source_note.configure(text=f"Ссылка pulse://npc/{self._selected_id} скопирована. Вставьте её в поиск.")

    def _open_kb(self) -> None:
        if self._detail and self._detail.get("kb_url"):
            webbrowser.open(self._detail["kb_url"])

    def _open_item(self, _event: tk.Event | None = None) -> None:
        selected = self.drops.selection()
        if not selected or not self._detail:
            return
        try:
            item = self._detail["drops"][int(selected[0][1:])]
        except (IndexError, ValueError):
            return
        if item.get("item_id"):
            webbrowser.open(f"https://kb.aionempire.com/items/{item['item_id']}")

    def _load_icon(self, asset: str, size: int):
        if not asset:
            return None
        key = (asset, size)
        if key in self._icons:
            return self._icons[key]
        path = self.icons_dir / asset
        if not path.is_file():
            return None
        try:
            from PIL import Image, ImageTk
            with Image.open(path) as raw:
                image = raw.convert("RGBA")
                if asset.startswith(("items/", "client/")) and image.size == (64, 64):
                    # Game item tiles are 40px tiles in a padded 64px texture: always cut the padding off
                    # (a uniform-strip test misses tiles with dark frames and left them small).
                    image = image.crop((0, 0, 40, 40))
                from PIL import ImageOps
                image = ImageOps.contain(image, (size, size), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image, master=self)
        except (OSError, ValueError):
            return None
        self._icons[key] = photo
        return photo

    def destroy(self) -> None:
        if self._after:
            self.after_cancel(self._after)
        if self._split_after:
            self.after_cancel(self._split_after)
        self._polling = False
        self._worker.close()
        if self.store:
            self.store.close()
            self.store = None
        super().destroy()
