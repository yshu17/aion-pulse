"""Bundled item data: id -> name catalog and the list of items the user can watch."""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path


def resource_root() -> Path:
    """Folder holding data/: inside the PyInstaller bundle when frozen, else the project."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def local_bestiary_dir() -> Path | None:
    """Folder with the NPC / Bestiary data, which is not part of the program: `bestiary/` next to the exe
    (or next to the build folder, or `local/bestiary/` in the project). None when it is not there, so the tab is simply not shown."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        candidates = [base / "bestiary", base.parent / "bestiary", base / "local" / "bestiary"]  # parent: onedir build
    else:
        candidates = [Path(__file__).resolve().parent.parent / "local" / "bestiary"]
    return next((folder for folder in candidates if (folder / "npcs.sqlite").is_file()), None)


CATEGORY_ORDER = [
    "Лата", "Кольчуга", "Кожа", "Ткань", "Оружие", "Щиты", "Крылья", "Украшения", "Головные уборы",
    "Изготовление", "Припасы", "Прочее",
]
# in the catalog (chat links, tooltips) but not in the «Что искать» list
UNLISTED_CATEGORIES = {"Изготовление", "Припасы", "Прочее"}
UNLISTED_GRADES = {"common", "rare", "junk"}  # white and green items
_ARMOR = {
    "Латная броня": "Лата",
    "Кольчужная броня": "Кольчуга",
    "Кожаная броня": "Кожа",
    "Тканая броня": "Ткань",
}
_WEAPONS = {"Меч", "Булава", "Кинжал", "Орб", "Гримуар", "Двуручный меч", "Копье", "Посох", "Лук"}


def category_for(item_type: str, name: str) -> str:
    """Group for the item list, from the site's «Тип» field (shields and wings have none)."""
    if item_type in _ARMOR:
        return _ARMOR[item_type]
    if item_type in _WEAPONS:
        return "Оружие"
    lowered = name.lower()
    if "щит" in lowered:
        return "Щиты"
    if "крыль" in lowered:
        return "Крылья"
    return "Прочее"


def is_listed(item: "WatchItem") -> bool:
    """Shown in the «Что искать» list: no white/green items, no materials, supplies or misc."""
    return item.category not in UNLISTED_CATEGORIES and item.grade not in UNLISTED_GRADES


@dataclass(frozen=True)
class WatchItem:
    id: str
    name: str
    level: int
    category: str = "Прочее"
    grade: str = ""
    icon: str = ""  # file name in data/icons (shared by items with the same picture)
    kind: str = ""  # finer type for the filter: weapon type («Меч»), accessory type («Кольца»)


def load_item_names(path: Path) -> dict[str, str]:
    """Read `id<TAB>name` lines. A missing file gives an empty catalog."""
    names: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                item_id, sep, name = line.rstrip("\n").partition("\t")
                if sep and item_id.isdigit():
                    names[item_id] = name.strip()
    except OSError:
        return {}
    return names


def load_link_names(data_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Map and quest names for chat links: (map id -> zone name, quest id -> name).

    data/map_names.tsv (official zone names, aidb.ru) and data/quest_names.tsv (kb.aionempire.com/quests), both
    `id<TAB>name`. Missing files give empty mappings: the parser then shows ids.
    """
    return load_item_names(data_dir / "map_names.tsv"), load_item_names(data_dir / "quest_names.tsv")


def load_watch_items(path: Path) -> list[WatchItem]:
    """Read watch_items.csv (id,name,level[,category,grade,icon,kind]). A missing file gives an empty list."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return [
                WatchItem(
                    id=row["id"],
                    name=row["name"],
                    level=int(row["level"]),
                    category=row.get("category") or "Прочее",
                    grade=row.get("grade") or "",
                    icon=row.get("icon") or "",
                    kind=row.get("kind") or "",
                )
                for row in csv.DictReader(f)
            ]
    except OSError:
        return []
