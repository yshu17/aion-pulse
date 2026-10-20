"""Map zones: the zone index, the area names of each zone, points shown on the map and the filter groups of the menu.

Portable core. `load_zones(maps_dir, names)` reads data/maps/maps.json and labels.tsv (the path is a parameter) and
gives {map id: Zone}. A Zone converts game coordinates to image pixels: `to_image(x, y)`. `Place` is a pin from the chat.
`FILTER_GROUPS` maps a menu entry to the point types it switches; `SIDES` names the two races.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# whose NPCs the map shows where the two sides differ: fortress NPCs (the owner's stand) and quest givers
SIDES = {"dark": "Асмодиане", "light": "Элийцы"}
LABEL_LEVELS = ("main", "zoom")

# the «Метки» menu: group -> (title, point types). Every group can be switched off; there is no «all» entry
FILTER_GROUPS = {
    "buildings": ("Здания", ("fortress", "artifact", "portal", "raid_boss")),
    "dungeons": ("Подземелья", ("dungeon",)),
    "rifts": ("Пространственные разломы", ("direct_portal", "tunnel")),  # tunnel: the passes into the Silentera tunnel
    "merchants": ("Торговцы", ("merchant", "coin_merchant", "vendor")),
    "teleports": ("Телепорты", ("teleport",)),
    "services": ("Склад, стигмы, почта", ("warehouse", "stigma", "postbox", "bindstone")),
    "quests": ("Задания", ("quest_give", "quest_important", "quest_event")),
}
CAPITALS = {"110010000", "120010000"}  # Elysium, Pandaemonium
SHOWN_TYPES = ("teleport", "bindstone", "warehouse", "merchant", "coin_merchant", "vendor", "stigma", "postbox",
               "fortress", "artifact", "dungeon", "tunnel", "portal", "raid_boss", "direct_portal")
QUEST_TYPES = ("quest_give", "quest_important", "quest_event")  # NPCs with quests (the «Задания» entry of the menu)


@dataclass(frozen=True)
class Place:
    map_id: str
    x: float  # game coordinates
    y: float
    label: str
    note: str = ""  # «12:03 Nick: message» for pins from the chat


@dataclass(frozen=True)
class Zone:
    map_id: str
    name: str
    path: Path
    size: int
    kx: tuple[float, float]
    ky: tuple[float, float]
    labels: tuple[tuple[float, float, str, str], ...] = ()  # area names: (image x, image y, text, level)
    layers: tuple[tuple[int, str, Path], ...] = ()  # Abyss layer id, display name and map image
    label_layers: tuple[int | None, ...] = ()  # the Abyss layer of each label (same order), None: every layer
    side: str = ""  # "dark" (Asmodian), "light" (Elyos), "" a zone both sides share (maps.json, from the client)

    def to_image(self, x: float, y: float) -> tuple[float, float]:
        return self.kx[0] * y + self.kx[1], self.ky[0] * x + self.ky[1]


def load_zones(maps_dir: Path, names: dict[str, str]) -> dict[str, Zone]:
    """data/maps/maps.json -> {map id: Zone}. Missing or broken data gives {}."""
    try:
        index = json.loads((Path(maps_dir) / "maps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    labels = load_labels(Path(maps_dir) / "labels.tsv")
    label_layers = load_label_layers(Path(maps_dir) / "labels.tsv")
    zones = {}
    for map_id, info in index.items():
        path = Path(maps_dir) / info["file"]
        if path.is_file():
            kx, ky = tuple(info["x"]), tuple(info["y"])
            zones[map_id] = Zone(
                map_id, names.get(map_id, map_id), path, int(info["size"]), kx, ky,
                tuple((kx[0] * gy + kx[1], ky[0] * gx + ky[1], text, level)
                      for gx, gy, text, level in labels.get(map_id, [])),
                tuple((int(layer["id"]), layer.get("name", f"Слой {layer['id']}"), Path(maps_dir) / layer["file"])
                      for layer in info.get("layers", []) if (Path(maps_dir) / layer["file"]).is_file()),
                tuple(label_layers.get(map_id, [])),
                info.get("side", "") if info.get("side", "") in SIDES else "",
            )
    return zones


def load_labels(path: Path) -> dict[str, list[tuple[float, float, str, str]]]:
    """labels.tsv (tools/build_labels.py, the client's own area names) -> {map id: [(game x, game y, text,
    level), ...]}; level «main» is drawn on the whole map, «zoom» closer in; «|» in a name is a line break."""
    zones: dict[str, list] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        parts = line.split("\t")
        if line.startswith("#") or len(parts) not in (5, 6) or parts[1] not in LABEL_LEVELS:
            continue
        try:
            zones.setdefault(parts[0], []).append((float(parts[2]), float(parts[3]), parts[4].replace("|", "\n"),
                                                   parts[1]))
        except ValueError:
            continue
    return zones


def load_label_layers(path: Path) -> dict[str, list[int | None]]:
    """The optional 6th column of labels.tsv (tools/assign_abyss_layers.py): the Abyss layer of each label, in the
    same order as load_labels gives them; None where a label has no layer."""
    zones: dict[str, list[int | None]] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        parts = line.split("	")
        if line.startswith("#") or len(parts) not in (5, 6) or parts[1] not in LABEL_LEVELS:
            continue
        try:
            float(parts[2]), float(parts[3])
        except ValueError:
            continue
        zones.setdefault(parts[0], []).append(int(parts[5]) if len(parts) == 6 and parts[5].isdigit() else None)
    return zones
