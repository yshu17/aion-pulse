"""Give every Abyss point and area name its map layer, from its height (dev tool, needs client_extract/).

The Abyss map has three pictures, one per altitude band. Points and area names without a layer were drawn on all
three. The height of each comes from the client: <npc_info> in client_world_ab1.xml (every placed NPC: x, y, z) and
the exported tables with x, y, z (service NPCs, area names, artifacts, gates, entrances). Bands, from the points the
client itself assigns a layer to: layer 1 is 1453-1696 high, layer 2 2244-2395, layer 3 2687-3104.

    python tools/assign_abyss_layers.py     updates data/maps/poi.json and data/maps/labels.tsv in place
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "client_extract" / "raw"
ABYSS = "400010000"
LAYER_TOPS = ((2000.0, 1), (2550.0, 2))  # below 2000: layer 1, below 2550: layer 2, above: layer 3


def layer_for(z: float) -> int:
    return next((layer for top, layer in LAYER_TOPS if z < top), 3)


def heights() -> dict[tuple[int, int], float]:
    """(round x, round y) -> z for every Abyss position the client export knows."""
    found: dict[tuple[int, int], float] = {}
    world = RAW / "Data" / "world" / "world" / "client_world_ab1.xml"
    if world.is_file():
        text = world.read_bytes().decode("utf-16")
        for x, y, z in re.findall(r"<npc_info>.*?<x>([\d.]+)</x>\s*<y>([\d.]+)</y>\s*<z>([\d.]+)</z>", text, re.S):
            found[(round(float(x)), round(float(y)))] = float(z)
    for table in RAW.glob("*.tsv"):
        with table.open(encoding="utf-8-sig") as stream:
            rows = csv.DictReader(stream, delimiter="\t")
            if not rows.fieldnames or not {"x", "y", "z"} <= set(rows.fieldnames):
                continue
            for row in rows:
                if row.get("zone", "ab1") not in ("ab1", "") and row.get("map_id", ABYSS) != ABYSS:
                    continue
                try:
                    found.setdefault((round(float(row["x"])), round(float(row["y"]))), float(row["z"]))
                except (TypeError, ValueError):
                    pass
    return found


def nearest_height(x: float, y: float, height: dict[tuple[int, int], float], radius: float = 120.0) -> float | None:
    """The height of the closest known position within `radius` (an NPC standing next to a known one)."""
    best = min(height.items(), key=lambda item: (item[0][0] - x) ** 2 + (item[0][1] - y) ** 2, default=None)
    if best is None or (best[0][0] - x) ** 2 + (best[0][1] - y) ** 2 > radius ** 2:
        return None
    return best[1]


def assign(points: list[dict], labels: list[str], height: dict[tuple[int, int], float]) -> tuple[int, int, list[str]]:
    """Set "layer" on Abyss points that have none; append a layer column to Abyss label lines. Returns counts."""
    done = 0
    for point in points:
        z = height.get((round(point["gx"]), round(point["gy"]))) or nearest_height(point["gx"], point["gy"], height)
        if point.get("layer") is None and z is not None:
            point["layer"] = layer_for(z)
            done += 1
    out, named = [], 0
    for line in labels:
        parts = line.split("\t")
        if not line.startswith("#") and len(parts) == 5 and parts[0] == ABYSS:
            z = height.get((round(float(parts[2])), round(float(parts[3]))))
            if z is not None:
                line = "\t".join([*parts, str(layer_for(z))])
                named += 1
        out.append(line)
    return done, named, out


def main() -> int:
    height = heights()
    poi_path, labels_path = ROOT / "data" / "maps" / "poi.json", ROOT / "data" / "maps" / "labels.tsv"
    data = json.loads(poi_path.read_text(encoding="utf-8"))
    done, named, lines = assign(data["zones"][ABYSS], labels_path.read_text(encoding="utf-8").splitlines(), height)
    poi_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    labels_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    left = sum(1 for p in data["zones"][ABYSS] if p.get("layer") is None)
    print(f"heights known: {len(height)}; points given a layer: {done}, still without: {left}; area names: {named}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
