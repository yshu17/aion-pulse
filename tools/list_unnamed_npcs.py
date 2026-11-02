"""The NPCs and spawn points the client gives no Russian name, with where they stand (nothing of them goes to the map).

Reads client_extract/missing_maps (mob_spawns.tsv, world_npcs.tsv), client_extract/client_level_objects.tsv and the
NPC catalogs, and writes next to them:
  unnamed_npcs.tsv          an NPC (an id or an internal name of the client) without a Russian name: where it stands
  unresolved_sp_points.tsv  spawn points (SP) that name no NPC at all: a group («P1») or nothing; the client only
                            says «something spawns here», the server decides what
Both have the zone, its name, the game coordinates and the source of the row; `on_map` says if the zone has a map in
the program. Dev tool. Usage: python tools/list_unnamed_npcs.py
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = ROOT / "client_extract"
SOURCE = EXTRACT / "missing_maps"
OUT_NPCS = SOURCE / "unnamed_npcs.tsv"
OUT_SP = SOURCE / "unresolved_sp_points.tsv"
NPC_COLUMNS = ["npc_id", "internal_name", "ui_type", "map_id", "zone_name", "game_x", "game_y", "game_z", "on_map", "source"]
SP_COLUMNS = ["group_name", "map_id", "zone_name", "game_x", "game_y", "game_z", "on_map", "source"]


def tsv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> None:
    zone_names = {line.split("\t")[0]: line.rstrip("\n").split("\t")[1] for line in
                  (ROOT / "data" / "map_names.tsv").read_text(encoding="utf-8").splitlines() if "\t" in line}
    on_map = set(json.loads((ROOT / "data" / "maps" / "maps.json").read_text(encoding="utf-8")))
    with gzip.open(ROOT / "data" / "game" / "npcs.json.gz", "rt", encoding="utf-8") as f:
        named = {str(r["id"]) for r in json.load(f)["records"] if r.get("name")}
    catalog = {r["npc_id"]: r for r in tsv(EXTRACT / "client_npcs.tsv")}
    by_internal = {r["internal_name"].lower(): r for r in catalog.values()}

    def zone(map_id: str) -> tuple[str, str]:
        return zone_names.get(map_id, ""), "yes" if map_id in on_map else "no"

    npcs: list[list[str]] = []
    sp: list[list[str]] = []
    for r in tsv(SOURCE / "world_npcs.tsv"):  # NPCs of the client's world files: an id, no name
        if r["npc_id"] in named:
            continue
        c = catalog.get(r["npc_id"], {})
        name, mapped = zone(r["map_id"])
        npcs.append([r["npc_id"], c.get("internal_name", ""), c.get("ui_type", ""), r["map_id"], name,
                     r["game_x"], r["game_y"], r["game_z"], mapped, "world_npcs.tsv"])
    for r in tsv(SOURCE / "mob_spawns.tsv"):  # spawn points of the levels (SP)
        name, mapped = zone(r["map_id"])
        if r["npc_id"]:
            if r["npc_id"] not in named:
                c = catalog.get(r["npc_id"], {})
                npcs.append([r["npc_id"], c.get("internal_name", r["internal_name"]), c.get("ui_type", ""), r["map_id"], name,
                             r["game_x"], r["game_y"], r["game_z"], mapped, "mob_spawns.tsv"])
        else:
            sp.append([r["internal_name"], r["map_id"], name, r["game_x"], r["game_y"], r["game_z"], mapped, "mob_spawns.tsv"])
    for r in tsv(EXTRACT / "client_level_objects.tsv"):  # the same for the outdoor zones, with their NPC names
        if r["object_type"] != "SP" or r["npc_russian_name"].strip():
            continue
        name, mapped = zone(r["map_id"])
        internal = r["npc_internal_name"]
        c = by_internal.get(internal.lower())
        if c and c["npc_id"] not in named and not internal.lower().startswith(("p1", "p2")):
            npcs.append([c["npc_id"], internal, c.get("ui_type", ""), r["map_id"], name, r["game_x"], r["game_y"], r["game_z"],
                         mapped, "client_level_objects.tsv"])
        else:
            sp.append([internal, r["map_id"], name, r["game_x"], r["game_y"], r["game_z"], mapped, "client_level_objects.tsv"])

    for path, columns, rows in ((OUT_NPCS, NPC_COLUMNS, npcs), (OUT_SP, SP_COLUMNS, sp)):
        rows.sort(key=lambda r: (r[columns.index("map_id")], r[0], float(r[columns.index("game_x")] or 0)))
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t", lineterminator="\n")
            writer.writerow(columns)
            writer.writerows(rows)
    print(f"unnamed NPCs: {len(npcs)} rows, {len({r[0] for r in npcs})} ids, {len({r[3] for r in npcs})} zones -> {OUT_NPCS}")
    print(f"  on a map in the program: {sum(1 for r in npcs if r[8] == 'yes')} rows; by kind:",
          Counter(r[2] or "(no type)" for r in npcs).most_common(6))
    print(f"unresolved spawn points: {len(sp)} rows, groups {Counter(r[0] or '(none)' for r in sp).most_common(4)} -> {OUT_SP}")


if __name__ == "__main__":
    main()
