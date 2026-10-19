"""Put the client's NPC positions of Elysium, the sacred arenas and the temples into the Bestiary data.

The client's world XML (client_world_<zone>.txt.xml) places every NPC of a zone. Elysium alone has 390 of them
(guards, citizens, decorations); the map shows only the ones a player deals with, so for Elysium only NPCs with a
function are added: merchants, coin merchants, gatekeepers, warehouse keepers, the stigma master, the post box,
brokers and the Kibelisk. The arenas and temples are small and get all their NPCs. (The first version of this
step was written by Codex in codex/mob-search; the Elysium selection is the addition.)

    python tools/add_zone_npc_points.py        updates local/bestiary/npcs.json.gz (a copy is kept next to it)
    then: python tools/build_bestiary_index.py

Needs client_extract/ and local/bestiary/. Idempotent: a point already there (same place) is updated, not repeated.
"""

from __future__ import annotations

import csv
import gzip
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_poi import FUNCTIONS  # noqa: E402

# zone code: (map id, name, only NPCs with a function)
ZONES = {
    "lc1": ("110010000", "Элизиум", True),
    "lc2": ("110020000", "Храм Кайсинеля", False),
    "arena_l_lobby": ("110070000", "Священная арена Кайсинеля", False),
    "dc2": ("120020000", "Храм Маркутана", False),
    "arena_d_lobby": ("120080000", "Священная арена Маркутана", False),
}


def has_function(function_type: str) -> bool:
    """The NPC does something for the player: the types the map draws (tools/build_poi.py FUNCTIONS)."""
    return bool(function_type) and (function_type in FUNCTIONS or function_type.casefold() == "teleport"
                                    or function_type.casefold() in {k.casefold() for k in FUNCTIONS})


def world_npcs(extract: Path, code: str) -> list[tuple[str, float, float, float]]:
    stem = extract / "raw" / "Data" / "world" / "world" / f"client_world_{code}"
    path = stem.with_suffix(".txt.xml") if stem.with_suffix(".txt.xml").is_file() else stem.with_suffix(".xml")
    data = path.read_bytes()
    text = data.decode("utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    found = []
    for npc in ET.fromstring(text).findall("./npc_infos/npc_info"):
        npc_id, pos = npc.findtext("nameid", "").strip(), npc.find("pos")
        if not npc_id or pos is None:
            continue
        try:
            found.append((npc_id, *(float(pos.findtext(axis, "")) for axis in ("x", "y", "z"))))
        except ValueError:
            continue
    return found


def add_points(catalog: dict, maps: dict, extract: Path, function_of: dict[str, str]) -> Counter:
    records = {str(row["id"]): row for row in catalog["records"]}
    counts: Counter = Counter()
    for code, (map_id, name, functional_only) in ZONES.items():
        catalog["zones"][map_id] = name
        info = maps[map_id]
        for npc_id, gx, gy, gz in world_npcs(extract, code):
            if functional_only and not has_function(function_of.get(npc_id, "")):
                counts[(code, "skipped: no function")] += 1
                continue
            ix, iy = info["x"][0] * gy + info["x"][1], info["y"][0] * gx + info["y"][1]
            if not (0 <= ix <= info["size"] and 0 <= iy <= info["size"]):
                counts[(code, "outside the map")] += 1
                continue
            record = records.get(npc_id)
            if record is None:
                counts[(code, "unknown id")] += 1
                continue
            point = {"map_id": map_id, "x": round(ix, 2), "y": round(iy, 2), "gx": round(gx, 2), "gy": round(gy, 2),
                     "gz": round(gz, 2), "source": "client_world"}
            points = record.setdefault("points", [])
            same = next((p for p in points if p.get("map_id") == map_id and abs(p.get("gx", -1e9) - gx) < 0.1
                         and abs(p.get("gy", -1e9) - gy) < 0.1), None)
            if same is not None:
                same.update(point)
            else:
                points.append(point)
                counts[(code, "added")] += 1
    return counts


def main() -> int:
    extract, local = ROOT / "client_extract", ROOT / "local" / "bestiary"
    maps = json.loads((ROOT / "data" / "maps" / "maps.json").read_text(encoding="utf-8"))
    with (extract / "client_npcs.tsv").open(encoding="utf-8-sig", newline="") as stream:
        function_of = {r["npc_id"]: r["function_type"] for r in csv.DictReader(stream, delimiter="\t")}
    source = local / "npcs.json.gz"
    backup = local / "npcs.before-zone-points.json.gz"
    if not backup.exists():
        shutil.copyfile(source, backup)
    with gzip.open(source, "rt", encoding="utf-8") as stream:
        catalog = json.load(stream)
    counts = add_points(catalog, maps, extract, function_of)
    with gzip.open(source, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(catalog, stream, ensure_ascii=False, separators=(",", ":"))
    for (code, what), number in sorted(counts.items()):
        print(f"{code:14s} {what:22s} {number}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
