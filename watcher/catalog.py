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


@dataclass(frozen=True)
class WatchItem:
    id: str
    name: str
    level: int


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


def load_watch_items(path: Path) -> list[WatchItem]:
    """Read watch_items.csv (id,name,level). A missing file gives an empty list."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return [
                WatchItem(id=row["id"], name=row["name"], level=int(row["level"]))
                for row in csv.DictReader(f)
            ]
    except OSError:
        return []
