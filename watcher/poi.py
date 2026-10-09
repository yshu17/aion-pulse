"""Points of interest for the map tab (data/maps/poi.json, made by tools/build_poi.py).

Pure data, no Tk: loading, filtering by layer type, text search, the nearest point of a type with
the distance in metres (game units), and clustering of close points for drawing.
"""

import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from watcher.matcher import normalize


@dataclass(frozen=True)
class Poi:
    zone: str  # map id, e.g. "220070000"
    type: str  # layer type, e.g. "teleport"
    x: float  # map image pixels
    y: float
    gx: float  # game coordinates (1 unit ≈ 1 m)
    gy: float
    name: str


class PoiStore:
    def __init__(self, types: dict[str, dict], zones: dict[str, list[Poi]]) -> None:
        self.types = types  # type -> {"group", "name", "icon"?}, in filter-panel order
        self._zones = zones

    @classmethod
    def load(cls, path: Path) -> "PoiStore":
        """Missing or broken file gives an empty store (the map works without layers)."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            zones = {
                zone: [Poi(zone, p["t"], p["x"], p["y"], p["gx"], p["gy"], p.get("name", "")) for p in points]
                for zone, points in data.get("zones", {}).items()
            }
            return cls(dict(data.get("types", {})), zones)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return cls({}, {})

    def type_name(self, type_: str) -> str:
        return self.types.get(type_, {}).get("name", type_)

    def groups(self) -> dict[str, list[str]]:
        """group -> types, both in file order."""
        out: dict[str, list[str]] = {}
        for type_, info in self.types.items():
            out.setdefault(info.get("group", "other"), []).append(type_)
        return out

    def in_zone(self, zone: str, types: set[str]) -> list[Poi]:
        return [p for p in self._zones.get(zone, []) if p.type in types]

    def counts(self, zone: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self._zones.get(zone, []):
            out[p.type] = out.get(p.type, 0) + 1
        return out

    def search(self, zone: str, query: str, types: set[str]) -> list[Poi]:
        """Points of the shown layers whose name or type name holds every word of the query."""
        words = normalize(query).split()
        if not words:
            return []
        found = []
        for p in self.in_zone(zone, types):
            text = normalize(f"{p.name} {self.type_name(p.type)}")
            if all(w in text for w in words):
                found.append(p)
        return found

    def nearest(self, zone: str, gx: float, gy: float, type_: str) -> tuple[Poi, float] | None:
        """Closest point of a type and the distance in metres, None if the zone has none."""
        best = None
        for p in self.in_zone(zone, {type_}):
            metres = math.hypot(p.gx - gx, p.gy - gy)
            if best is None or metres < best[1]:
                best = (p, metres)
        return best


def cluster(
    points: Iterable[Poi], to_screen: Callable[[float, float], tuple[float, float]], radius_px: float
) -> list[tuple[float, float, list[Poi]]]:
    """Group points of the same type that fall into the same screen cell of radius_px.

    Returns (screen x, screen y, members); the position is the members' mean on screen.
    """
    cells: dict[tuple[str, int, int], list[tuple[float, float, Poi]]] = {}
    for p in points:
        sx, sy = to_screen(p.x, p.y)
        key = (p.type, math.floor(sx / radius_px), math.floor(sy / radius_px))
        cells.setdefault(key, []).append((sx, sy, p))
    out = []
    for members in cells.values():
        cx = sum(m[0] for m in members) / len(members)
        cy = sum(m[1] for m in members) / len(members)
        out.append((cx, cy, [m[2] for m in members]))
    return out
