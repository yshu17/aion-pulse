"""Filter panel of the «Карта» tab: layer groups with checkboxes, icons and point counts, presets.

The panel only keeps the set of shown layer types; MapView reads it and draws the points.
"""

import tkinter as tk
from collections.abc import Callable, Iterable
from pathlib import Path
from tkinter import ttk

from watcher import theme
from watcher.poi import PoiStore

GROUP_NAMES = {"npc": "Функциональные NPC", "landmark": "Ориентиры", "gather": "Сбор", "quest": "Задания"}
ICON_PX = 20


def presets(store: PoiStore) -> dict[str, set[str]]:
    groups = store.groups()
    npc, landmark = set(groups.get("npc", [])), set(groups.get("landmark", []))
    return {
        "Город": npc,
        "ПвП": {t for t in ("artifact", "portal", "direct_portal", "teleport") if t in store.types},
        "Сбор": set(groups.get("gather", [])),
        "Задания": set(groups.get("quest", [])) | ({"teleport"} & npc),
        "Всё": set(store.types),
        "Ничего": set(),
    }


def default_layers(store: PoiStore) -> set[str]:
    groups = store.groups()
    return set(groups.get("npc", [])) | set(groups.get("landmark", []))


def load_icon(path: Path, size: int, master: tk.Misc):
    """A ready-made icon scaled to size px (keeps its aspect ratio), None if the file is missing."""
    from PIL import Image, ImageTk

    try:
        with Image.open(path) as image:
            image = image.convert("RGBA")
            image.thumbnail((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(image, master=master)
    except OSError:
        return None


class LayerPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        store: PoiStore,
        icons_dir: Path,
        layers: Iterable[str],
        on_change: Callable[[set[str]], None],
    ) -> None:
        super().__init__(parent, style="Card.TFrame", padding=(12, 10, 6, 10))
        self.store = store
        self.icons_dir = icons_dir
        self.on_change = on_change
        self.layers: set[str] = {t for t in layers if t in store.types}
        self.vars: dict[str, tk.BooleanVar] = {}
        self.count_labels: dict[str, ttk.Label] = {}
        self._icons: dict[str, object] = {}

        ttk.Label(self, text="Слои", style="Title.TLabel").pack(anchor="w")
        chips = ttk.Frame(self, style="Surface.TFrame")
        chips.pack(fill="x", pady=(8, 6))
        self.chips: dict[str, tk.Label] = {}
        for index, name in enumerate(presets(store)):
            chip = tk.Label(chips, text=name, background=theme.SURFACE_2, foreground=theme.TEXT,
                            font=(theme.FONT_FAMILY, theme.FONT_SIZE - 2), padx=8, pady=3, cursor="hand2")
            chip.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 4), pady=(0, 4))
            chip.bind("<Button-1>", lambda _e, n=name: self.apply_preset(n))
            self.chips[name] = chip
        for column in range(3):
            chips.columnconfigure(column, weight=1)

        holder = ttk.Frame(self, style="Surface.TFrame")
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, width=290, highlightthickness=0, borderwidth=0, background=theme.SURFACE)
        scroll = ttk.Scrollbar(holder, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas, style="Surface.TFrame")
        window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        self._build_rows()

    def _build_rows(self) -> None:
        for group, types in self.store.groups().items():
            ttk.Label(self.inner, text=GROUP_NAMES.get(group, group), style="CardMuted.TLabel").pack(
                anchor="w", pady=(10, 2)
            )
            for type_ in types:
                row = ttk.Frame(self.inner, style="Surface.TFrame")
                row.pack(fill="x")
                var = tk.BooleanVar(value=type_ in self.layers)
                self.vars[type_] = var
                icon = load_icon(self.icons_dir / self.store.types[type_].get("icon", ""), ICON_PX, self)
                if icon is not None:
                    self._icons[type_] = icon
                box = ttk.Checkbutton(
                    row, text=f" {self.store.type_name(type_)}", variable=var, style="Item.TCheckbutton",
                    image=icon or "", compound="left", command=lambda t=type_: self._toggled(t),
                )
                box.pack(side="left")
                count = ttk.Label(row, text="", style="CardMuted.TLabel")
                count.pack(side="right", padx=(0, 6))
                self.count_labels[type_] = count

    def set_zone(self, zone: str | None) -> None:
        """Point counts of the shown zone next to each layer."""
        counts = self.store.counts(zone) if zone else {}
        for type_, label in self.count_labels.items():
            label.configure(text=str(counts.get(type_, 0)) if counts.get(type_) else "—")

    def apply_preset(self, name: str) -> None:
        self.set_layers(presets(self.store)[name])
        for chip_name, chip in self.chips.items():
            chip.configure(background="#3a2a12" if chip_name == name else theme.SURFACE_2,
                           foreground=theme.ACCENT if chip_name == name else theme.TEXT)

    def set_layers(self, layers: set[str]) -> None:
        self.layers = {t for t in layers if t in self.store.types}
        for type_, var in self.vars.items():
            var.set(type_ in self.layers)
        self.on_change(set(self.layers))

    def _toggled(self, type_: str) -> None:
        if self.vars[type_].get():
            self.layers.add(type_)
        else:
            self.layers.discard(type_)
        for chip in self.chips.values():
            chip.configure(background=theme.SURFACE_2, foreground=theme.TEXT)
        self.on_change(set(self.layers))
