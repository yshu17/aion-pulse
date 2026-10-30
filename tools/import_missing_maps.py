"""Bring the zones Codex extracted from the client (client_extract/missing_maps, tools/extract_missing_maps.py) into
the map of the programs, and build the NPC/monster index the map searches.

Zones taken: the client's own game maps («newmap») of playable zones, with their coordinate framing; the test zones,
the housing barrack, and the radar and area-radar pictures (no framing in the client: points would be guesses) are
left out and listed by `--report`. A zone with several pictures (floors of a dungeon, variants of a zone) gets them as
layers; the client gives no height bounds for its floors, so its points and area names are not tied to a floor.

Writes (re-running replaces what it wrote before, the 20 original zones stay as they are):
  data/maps/client/<picture>.jpg     the pictures
  data/maps/maps.json                the zones, with "kind": "instance" for dungeons
  data/maps/labels.tsv               area names (single-picture zones only)
  data/maps/spawns.json              {"names": {npc id: name}, "zones": {map id: [[npc id, game x, game y, game z]]}}:
                                     the NPC and monster points of every zone with a picture, from data/game
                                     (npc_points), from the client (missing_maps: spawns with an NPC id, world NPCs)
                                     and the named points of poi.json (id «poi:<name>»)
Dev tool. Usage: python tools/import_missing_maps.py [--report]
"""

from __future__ import annotations

import csv
import gzip
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "client_extract" / "missing_maps"
MAPS = ROOT / "data" / "maps"
GAME = ROOT / "data" / "game"
SKIP_ZONES = ("test_", "idtest_", "housing_")  # not part of the game
OPEN_ZONES = {"ldf4a", "ldf4b"}  # Sarpan and Tiamaranta: open zones, not instances
MARK = "# imported by tools/import_missing_maps.py"


def rows(name: str) -> list[dict[str, str]]:
    with open(SOURCE / name, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def chosen() -> dict[str, list[dict[str, str]]]:
    """map id -> its pictures (newmap, named, not a test zone), in the client's order."""
    zones: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows("maps.tsv"):
        if row["kind"] == "newmap" and row["name_ru"] and not row["zone"].startswith(SKIP_ZONES):
            zones[row["map_id"]].append(row)
    return dict(zones)


def report() -> None:
    picked = chosen()
    left = [r for r in rows("maps.tsv") if r["map_id"] not in picked]
    print("taken:", len(picked), "zones")
    for r in left:
        print("left out:", r["map_id"], r["zone"], r["kind"], r["name_ru"] or "(no name)")


def main() -> None:
    if "--report" in sys.argv:
        report()
        return
    picked = chosen()
    index_path = MAPS / "maps.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index = {k: v for k, v in index.items() if not v.get("imported")}
    for map_id, pictures in picked.items():
        files = []
        for p in pictures:
            target = f"client/{Path(p['file']).name}"
            shutil.copyfile(SOURCE / p["file"], MAPS / target)
            files.append(target)
        first = pictures[0]
        entry = {
            "file": files[0], "size": int(first["size"]),
            "x": [float(first["scale_x"]), float(first["offset_x"])], "y": [float(first["scale_y"]), float(first["offset_y"])],
            "side": "", "kind": "zone" if first["zone"] in OPEN_ZONES else "instance", "imported": True,
        }
        if len(files) > 1:
            entry["layers"] = [{"id": n + 1, "name": f"Этаж {n + 1}" if entry["kind"] == "instance" else f"Вариант {n + 1}", "file": f}
                               for n, f in enumerate(files)]
        index[map_id] = entry
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    # area names: only zones of one picture (a floor's names cannot be told apart)
    labels_path = MAPS / "labels.tsv"
    kept = []
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        if line == MARK:
            break
        kept.append(line)
    added = [MARK]
    for row in rows("labels.tsv"):
        if row["map_id"] in picked and len(picked[row["map_id"]]) == 1 and row["name_ru"] and row["display_level"] in ("main", "zoom"):
            added.append("\t".join([row["map_id"], row["display_level"], row["game_x"], row["game_y"], row["name_ru"]]))
    labels_path.write_text("\n".join(kept + added) + "\n", encoding="utf-8")

    # the NPC / monster index: every zone with a picture
    with_picture = set(index)
    names: dict[str, str] = {}
    with gzip.open(GAME / "npcs.json.gz", "rt", encoding="utf-8") as f:
        for record in json.load(f)["records"]:
            if record.get("name"):
                names[str(record["id"])] = record["name"]
    points: dict[str, set[tuple[str, float, float, float]]] = defaultdict(set)
    with gzip.open(GAME / "npc_points.json.gz", "rt", encoding="utf-8") as f:
        for map_id, npc, x, y, z, _zone in json.load(f)["rows"]:
            if map_id in with_picture and str(npc) in names:
                points[map_id].add((str(npc), round(x, 1), round(y, 1), round(z or 0)))
    for row in rows("mob_spawns.tsv") + rows("world_npcs.tsv"):
        npc = row["npc_id"]
        if row["map_id"] in picked and npc in names:
            points[row["map_id"]].add((npc, round(float(row["game_x"]), 1), round(float(row["game_y"]), 1), round(float(row["game_z"] or 0))))
    # the named points of the map layers (teleport statues, merchants, quest givers …): an id of their own per name
    poi = json.loads((MAPS / "poi.json").read_text(encoding="utf-8"))
    for map_id, zone_points in poi.get("zones", {}).items():
        for p in zone_points:
            if p.get("name") and map_id in with_picture:
                key = f"poi:{p['name']}"
                names[key] = p["name"]
                points[map_id].add((key, round(p["gx"], 1), round(p["gy"], 1), 0))
    used = {p[0] for zone in points.values() for p in zone}
    spawns = {"names": {npc: names[npc] for npc in sorted(used)},
              "zones": {map_id: sorted([list(p) for p in zone]) for map_id, zone in sorted(points.items())}}
    (MAPS / "spawns.json").write_text(json.dumps(spawns, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"zones: {len(picked)} imported ({len(index)} in all); points: {sum(len(z) for z in points.values())} "
          f"of {len(used)} NPCs in {len(points)} zones; area names: {len(added) - 1}")


if __name__ == "__main__":
    main()
