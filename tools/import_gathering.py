"""Bring the gathering points of aion-map.vercel.app (downloaded to downloads/aion_map_site) into the map.

The site keeps one file per zone (gathering/<zone>.json): a resource node with its Russian name, level, kind and its
spots in game coordinates («ingame_coords»: «[pos:Adamantium; 220040000 1225.0 492.9 0.0 0] …»). The site lists some
spots twice; they are kept once. Aether nodes are «Эфирокинез», the other kinds (ore, gems, plants, fish …) are
«Энергокинез». The Abyss comes as two files, its lower and upper layers (layers 1 and 3 of the zone).

Writes (re-running replaces them):
  data/maps/gathering.json     {"version": 1, "zones": {map id: [{"id", "name", "name_en", "kind": "aether"|"essence",
                               "type", "level", "icon", "layer": int|null, "points": [[game x, game y], …]}]}},
                               each zone's nodes by kind, then level
  data/maps/gathering/*.png    the node icons (40 px, from the site's /images/gathering)
Dev tool. Usage: python tools/import_gathering.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "downloads" / "aion_map_site"
MAPS = ROOT / "data" / "maps"
# the site's zone files: map id, Abyss layer
ZONES = {
    "poeta": ("210010000", None), "eltnen": ("210020000", None), "verteron": ("210030000", None),
    "heiron": ("210040000", None), "theobomos": ("210060000", None), "ishalgen": ("220010000", None),
    "morheim": ("220020000", None), "altgard": ("220030000", None), "beluslan": ("220040000", None),
    "brusthonin": ("220050000", None), "lower": ("400010000", 1), "upper": ("400010000", 3),
}
SPOT = re.compile(r"\[pos:[^;\]]*;\s*(\d+)\s+(-?[\d.]+)\s+(-?[\d.]+)")


def spots(text: str, map_id: str) -> list[list[float]]:
    """The game x, y of a node's spots in one zone, each once, in the site's order."""
    out: list[list[float]] = []
    seen: set[tuple[float, float]] = set()
    for zone, x, y in SPOT.findall(text or ""):
        key = (round(float(x)), round(float(y)))
        if zone != map_id or key in seen:
            continue
        seen.add(key)
        out.append([round(float(x), 1), round(float(y), 1)])
    return out


def node(raw: dict, map_id: str, layer: int | None) -> dict | None:
    points = spots(raw.get("ingame_coords", ""), map_id)
    if not points:
        return None
    return {
        "id": str(raw["id"]), "name": raw.get("ru_name") or raw["name"], "name_en": raw["name"],
        "kind": "aether" if raw["gathering_type"] == "Aether" else "essence", "type": raw["gathering_type"],
        "level": int(raw["gathering_lvl"]), "icon": raw["nameIcon"], "layer": layer, "points": points,
    }


def build(source: Path) -> dict:
    zones: dict[str, list[dict]] = {}
    for name, (map_id, layer) in ZONES.items():
        path = source / "gathering" / f"{name}.json"
        if not path.exists():
            continue
        nodes = [n for n in (node(r, map_id, layer) for r in json.loads(path.read_text(encoding="utf-8"))) if n]
        zones.setdefault(map_id, []).extend(nodes)
    for nodes in zones.values():
        nodes.sort(key=lambda n: (n["kind"] != "essence", n["level"], n["name"], n["layer"] or 0))
    return {"version": 1, "zones": zones}


def main() -> None:
    data = build(SOURCE)
    (MAPS / "gathering.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    icons = MAPS / "gathering"
    icons.mkdir(exist_ok=True)
    wanted = {n["icon"] for nodes in data["zones"].values() for n in nodes}
    missing = []
    for icon in sorted(wanted):
        src = SOURCE / "gathering_icons" / f"{icon}.png"
        if src.exists():
            shutil.copyfile(src, icons / f"{icon}.png")
        else:
            missing.append(icon)
    total = sum(len(n["points"]) for nodes in data["zones"].values() for n in nodes)
    nodes = sum(len(v) for v in data["zones"].values())
    print(f"{len(data['zones'])} zones, {nodes} nodes, {total} spots, {len(wanted) - len(missing)} icons")
    if missing:
        print("no icon:", ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
