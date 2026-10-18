"""Render the two review tabs with real local data for visual inspection."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from watcher import theme
from watcher.bestiary_view import BestiaryView
from watcher.catalog import local_bestiary_dir, resource_root
from watcher.mapview import MapView, load_zones
from watcher.parser import MAP_NAMES
from watcher.poi import PoiStore


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/bestiary-ui.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.title("Пульс 1.0.0 — просмотр Бестиария")
    root.geometry((sys.argv[3] if len(sys.argv) > 3 else "1396x1000") + "+20+20")
    theme.apply_dark_theme(root)
    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True)
    maps = resource_root() / "data" / "maps"
    bestiary = local_bestiary_dir()
    zones = load_zones(maps, MAP_NAMES)
    map_view = MapView(
        tabs, zones, poi=PoiStore.load(maps / "poi.json"), icons_dir=maps / "icons",
        bestiary_database=bestiary / "npcs.sqlite", bestiary_icons=bestiary / "icons",
    )
    tabs.add(map_view, text="Карта")
    view = BestiaryView(
        tabs, bestiary / "npcs.sqlite", bestiary / "icons",
        {map_id: zone.name for map_id, zone in zones.items()},
        on_map=lambda *args: None,
    )
    tabs.add(view, text="NPC / Бестиарий")
    if "map" in output.stem:
        tabs.select(map_view)
        map_view.activate()
        map_view.search_var.set(sys.argv[2] if len(sys.argv) > 2 else "страж")
        map_view._run_mob_search()
    else:
        tabs.select(view)
        view.activate()
        if "sold" in output.stem or "found" in output.stem:
            view.category.set("Монстры" if "found" in output.stem else "Торговцы")
        view.query.set(sys.argv[2] if len(sys.argv) > 2 else "страж")
        view._search(reset=True)
        if "stock" in output.stem:
            view.detail_tabs.select(view.stock_tab)
        elif "drops" in output.stem:
            view.detail_tabs.select(1)
    root.update()
    root.after(500, lambda: (root.update(), ImageGrab.grab(window=root.winfo_id()).save(output), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
