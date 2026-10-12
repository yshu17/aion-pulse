"""Merge v4 client world data into the map POI store.

Uses the raw client extracts and the existing repeatable POI helpers. The game installation is never accessed.
Run after install_v4_maps.py. This rebuilds poi.json and labels.tsv with the authoritative v4 zone-code mapping.
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_poi as poi_builder  # noqa: E402

RAW = ROOT / "client_extract" / "raw"
MAPS = ROOT / "data" / "maps"
LABEL_LEVELS = {"main": "main", "zoom": "zoom", "fly_path": "zoom"}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def export_labels(strings: dict[str, str]) -> None:
    """Resolve the map label keys from the client Russian string table before writing the app's label index."""
    out, seen = [], set()
    for row in read_tsv(RAW / "subzone_labels.tsv"):
        level = LABEL_LEVELS.get(row["ui_map"].strip())
        name = " ".join((row.get("name_ru") or strings.get(row["string_key"], "")).replace("\\n", " ").split())
        if not level or not name:
            continue
        gx, gy = round(float(row["x"]), 1), round(float(row["y"]), 1)
        key = (row["map_id"], name, round(gx), round(gy))
        if key in seen:
            continue
        seen.add(key)
        if len(name) > 18 and " " in name:
            cut = min((i for i, ch in enumerate(name) if ch == " "), key=lambda i: abs(i - len(name) / 2))
            name = name[:cut] + "|" + name[cut + 1 :]
        out.append((row["map_id"], level, gx, gy, name))
    header = ["# Area labels resolved from client subzone_labels.tsv + strings_ru.tsv.",
              "# map_id<TAB>level<TAB>game x<TAB>game y<TAB>name (| = line break)"]
    (MAPS / "labels.tsv").write_text("\n".join([*header, *("\t".join(map(str, row)) for row in out)]) + "\n",
                                           encoding="utf-8")


def abyss_points(data: dict, strings: dict[str, str]) -> int:
    layers = {int(row["abyss_id"]): int(row["map_layer"])
              for row in read_tsv(RAW / "abyss_layer_areas.tsv")}
    zone = data["zones"].setdefault("400010000", [])
    added = 0

    for row in read_tsv(RAW / "abyss_fortress_areas.tsv"):
        points = [tuple(map(float, pair.split(","))) for pair in row["points_xy"].split(";") if pair]
        if len(points) < 3:
            continue
        gx = sum(x for x, _y in points) / len(points)
        gy = sum(y for _x, y in points) / len(points)
        fortress_id = int(row["abyss_id"])
        name_key = f"STR_Ab1_SZ_{fortress_id}_A"
        name = strings.get(name_key, "").split("\n", 1)[0].strip()
        point = {"t": "fortress", "x": 0.0, "y": 0.0, "gx": round(gx, 1), "gy": round(gy, 1),
                 "name": name or f"Крепость {fortress_id}", "layer": layers.get(fortress_id)}
        if not any(p["t"] == point["t"] and p.get("name") == point["name"] and p.get("layer") == point["layer"]
                   for p in zone):
            zone.append(point)
            added += 1

    labels = [row for row in read_tsv(RAW / "subzone_labels.tsv") if row["zone"] == "ab1" and row["name_ru"].strip()]
    for row in read_tsv(RAW / "abyss_artifacts.tsv"):
        match = re.search(r"Artifact_(\d{4})", row["name"])
        parent_id = int(match.group(1)) if match else None
        gx, gy = float(row["x"]), float(row["y"])
        nearest = min(labels, key=lambda label: (float(label["x"]) - gx) ** 2 + (float(label["y"]) - gy) ** 2,
                      default=None)
        name = nearest["name_ru"] if nearest and (float(nearest["x"]) - gx) ** 2 + (float(nearest["y"]) - gy) ** 2 < 100**2 else "Артефакт"
        point = {"t": "artifact", "x": 0.0, "y": 0.0, "gx": round(gx, 1), "gy": round(gy, 1),
                 "name": name, "layer": layers.get(parent_id)}
        if not any(p["t"] == point["t"] and abs(p["gx"] - point["gx"]) < 1 and abs(p["gy"] - point["gy"]) < 1
                   and p.get("layer") == point["layer"] for p in zone):
            zone.append(point)
            added += 1
    return added


def main() -> int:
    index = json.loads((MAPS / "maps.json").read_text(encoding="utf-8"))
    frames = read_tsv(RAW / "zone_map_frames.tsv")
    zone_ids = {row["zone"]: row["map_id"] for row in frames if row["map_id"] in index}
    strings: dict[str, str] = {}
    with (RAW / "strings_ru.tsv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if len(row) >= 2:
                strings[row[0]] = row[1]
    export_labels(strings)
    objects = read_tsv(ROOT / "client_extract" / "client_level_objects.tsv")
    entities = read_tsv(ROOT / "client_extract" / "client_level_entities.tsv")
    # These v4 zone codes have authoritative map ids in the client's zonemap export.
    # Older object exports can contain a conflicting map_id; normalize by world zone code first.
    for row in objects:
        if row.get("zone", "").lower() in zone_ids:
            row["map_id"] = zone_ids[row["zone"].lower()]
    for row in entities:
        if row.get("zone", "").lower() in zone_ids:
            row["map_id"] = zone_ids[row["zone"].lower()]
    for row in objects:
        code = row.get("zone", "").lower()
        if code and code not in zone_ids and row.get("map_id") in index:
            zone_ids[code] = row["map_id"]

    zones = set(index)
    data = poi_builder.build(objects, entities, zones)

    labels: dict[str, list[tuple[float, float, str]]] = {}
    labels_path = MAPS / "labels.tsv"
    for line in labels_path.read_text(encoding="utf-8-sig").splitlines():
        parts = line.split("\t")
        if line.startswith("#") or len(parts) != 5:
            continue
        labels.setdefault(parts[0], []).append((float(parts[3]), float(parts[2]), parts[4].replace("|", " ")))
    added_landmarks = poi_builder.merge(data, poi_builder.landmark_points(
        [row for row in entities if row["map_id"] in zones], labels, strings))

    service_rows = read_tsv(RAW / "npc_service_coords.tsv")
    service_functions = {name.casefold(): name for name in poi_builder.FUNCTIONS}
    for row in service_rows:
        canonical = service_functions.get(row["function_type"].casefold())
        if canonical:
            row["function_type"] = canonical
    races = {row["npc_id"]: row["race_type"] for row in read_tsv(ROOT / "client_extract" / "client_npcs.tsv")}
    added_services = poi_builder.merge(data, poi_builder.service_points(service_rows, zone_ids, races))

    spawns: dict[str, list[tuple[str, float, float]]] = {}
    for code in zone_ids:
        path = RAW / "Data" / "world" / "world" / f"client_world_{code}.txt.xml"
        if not path.is_file():
            path = RAW / "Data" / "world" / "world" / f"client_world_{code}.xml"
            if not path.is_file():
                continue
            text = path.read_bytes().decode("utf-16", errors="replace")
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        for npc_id, map_id, gx, gy in poi_builder.world_npcs(text, code):
            spawns.setdefault(npc_id, []).append((map_id, gx, gy))

    npc_rows = {row["npc_id"]: row for row in read_tsv(ROOT / "client_extract" / "client_npcs.tsv")}
    added_entrances = poi_builder.merge(data, poi_builder.entrance_points(npc_rows, spawns, zone_ids))
    link_path = ROOT / "downloads" / "aiondb_quests" / "quest_start_npc.tsv"
    quest_path = RAW / "quest_givers.tsv"
    added_quests = 0
    if link_path.is_file() and quest_path.is_file():
        quests = {row["quest_id"]: row for row in read_tsv(quest_path)}
        links = read_tsv(link_path)
        names = {npc_id: row["russian_name"] for npc_id, row in npc_rows.items()}
        added_quests = poi_builder.merge(data, poi_builder.quest_points(quests, links, spawns, zone_ids, names))

    bosses = RAW / "raid_boss_spawns.tsv"
    if bosses.is_file():
        boss_rows = [row for row in read_tsv(bosses) if row["map_id"] in zones]
        poi_builder.merge(data, poi_builder.raid_boss_points(boss_rows))

    added_abyss = abyss_points(data, strings)
    data["types"].setdefault("fortress", {"group": "landmark", "name": "Крепость", "icon": "fortress.png"})
    data["types"].setdefault("artifact", {"group": "landmark", "name": "Артефакт", "icon": "artifact.png"})
    out = MAPS / "poi.json"
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"v4 POI rebuilt: landmarks={added_landmarks}, services={added_services}, entrances={added_entrances}, quests={added_quests}, "
          f"Abyss fortresses/artifacts={added_abyss}; wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
