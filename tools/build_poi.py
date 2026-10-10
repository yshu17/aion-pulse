"""Build data/maps/poi.json (points of interest for the map tab) from the client level data.

Input: client_extract/client_level_objects.tsv and client_level_entities.tsv (exported by
tools/export_client_level_data.py from the client's mission XML) and data/maps/maps.json (the zones
that have a calibrated map). Only rows with map pixels in those zones are kept.

Output:
    {"version": 1,
     "types": {"teleport": {"group": "npc", "name": "Привратник"}, ...},
     "zones": {"220070000": [{"t": "teleport", "x": 1686.1, "y": 793.1, "gx": 792.6, "gy": 1685.0,
                              "name": "Раниу"}, ...]}}
x/y are map pixels, gx/gy game coordinates (1 unit ≈ 1 m).
Dev tool. Usage: python tools/build_poi.py [client_extract_dir]
"""

import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# type -> (group, Russian name); the order is the order of the filter panel
TYPES = {
    "teleport": ("npc", "Привратник"),
    "warehouse": ("npc", "Заведующий складом"),
    "merchant": ("npc", "Торговец"),
    "coin_merchant": ("npc", "Товары за монеты"),
    "vendor": ("npc", "Посредник"),
    "stigma": ("npc", "Мастер стигм"),
    "postbox": ("npc", "Почтовый ящик"),
    "bindstone": ("npc", "Кибелиск"),
    "fortress": ("landmark", "Крепость"),
    "artifact": ("landmark", "Артефакт"),
    "portal": ("landmark", "Портал"),
    "direct_portal": ("landmark", "Точка перемещения"),
    "gather_herb": ("gather", "Травы"),
    "gather_plant": ("gather", "Растения"),
    "gather_berry": ("gather", "Ягоды"),
    "gather_vegetable": ("gather", "Овощи"),
    "gather_tree": ("gather", "Дерево"),
    "gather_metal": ("gather", "Металлы"),
    "gather_noblemetal": ("gather", "Драг. металл"),
    "gather_jewelry": ("gather", "Камни"),
    "gather_aether": ("gather", "Эфир"),
    "gather_fish": ("gather", "Рыба"),
    "gather_shell": ("gather", "Ракушки"),
    "gather_other": ("gather", "Прочий сбор"),
    "quest_point": ("quest", "Точка задания"),
}
FUNCTIONS = {
    "Teleport": "teleport",
    "Warehouse": "warehouse",
    "Merchant": "merchant",
    "Coin_merchant": "coin_merchant",
    "vendor": "vendor",
    "Stigma_master": "stigma",
    "Postbox": "postbox",
    "Bindstone": "bindstone",
}
SAME_SPOT_M = 1.0  # the world XML lists a few NPCs twice at the same spot
# searched in this order: «noblemetal» before «metal»
GATHER_KINDS = ["noblemetal", "metal", "jewelry", "herb", "plant", "berry", "vegetable", "vege", "tree", "fish",
                "shell", "od"]
GATHER_ALIASES = {"vege": "vegetable", "od": "aether"}


def gather_kind(object_name: str) -> str:
    """Resource kind from a gathering point name, e.g. «HSPDF1_Alder_herb2» or
    «HSPDF4A_Harvest noblemetal_3b1» -> «herb» / «noblemetal»; «od» means aether."""
    tokens = {re.sub(r"\d+[a-z]?$", "", t) for t in re.split(r"[_ ]+", object_name.lower())}
    tokens |= {re.sub(r"^\d+", "", t) for t in tokens}  # «400od» -> «od»
    for kind in GATHER_KINDS:
        if kind in tokens:
            return GATHER_ALIASES.get(kind, kind)
    return "other"


def classify_object(row: dict) -> str | None:
    """Layer type of a level object row, None for rows that are not shown (plain spawns, …)."""
    function = row.get("function_type") or ""
    if function:
        return FUNCTIONS.get(function)
    kind = row.get("object_type")
    if kind == "Portal":
        return "portal"
    if kind == "DP":
        return "direct_portal"
    if kind == "HSP":
        return f"gather_{gather_kind(row.get('object_name', ''))}"
    if kind in ("KP", "MP"):
        return "quest_point"
    return None


def _point(type_: str, row: dict, name: str) -> dict | None:
    try:
        return {
            "t": type_,
            "x": round(float(row["image_x"]), 1),
            "y": round(float(row["image_y"]), 1),
            "gx": round(float(row["game_x"]), 1),
            "gy": round(float(row["game_y"]), 1),
            "name": name,
        }
    except (KeyError, ValueError):
        return None  # no map pixels: zone without a calibrated map


def build(objects: list[dict], entities: list[dict], zones: set[str]) -> dict:
    out: dict[str, list[dict]] = {}
    for row in objects:
        if row.get("function_type"):
            continue  # functional NPCs come from the client's world XML only (service_points), as the game's map
        type_ = classify_object(row)
        if type_ is None or row.get("map_id") not in zones:
            continue
        name = row.get("npc_russian_name") or ""
        point = _point(type_, row, name)
        if point is not None:
            out.setdefault(row["map_id"], []).append(point)
    artifacts = set()
    for row in entities:
        if row.get("entity_class") == "AbyssArtifacts" and row.get("map_id") in zones:
            point = _point("artifact", row, "")
            spot = (row["map_id"], point and point["gx"], point and point["gy"])
            if point is not None and spot not in artifacts:  # each artifact is listed for Li / Da / Dr
                artifacts.add(spot)
                out.setdefault(row["map_id"], []).append(point)
    used = {p["t"] for points in out.values() for p in points}
    icons = ROOT / "data" / "maps" / "icons"
    types = {}
    for t, (g, n) in TYPES.items():
        if t in used:
            types[t] = {"group": g, "name": n}
            if (icons / f"{t}.png").is_file():
                types[t]["icon"] = f"{t}.png"  # made by tools/build_map_icons.py
    return {"version": 1, "types": types, "zones": out}


def service_points(rows: list[dict], zone_ids: dict[str, str]) -> dict[str, list[dict]]:
    """Functional NPCs from the client's world XML (client_world_<zone>.xml <npc_info>, the list the game's own map
    and NPC search use; client_extract/raw/npc_service_coords.tsv by Codex). x / y are game coordinates."""
    out: dict[str, list[dict]] = {}
    for row in rows:
        type_ = FUNCTIONS.get(row.get("function_type", ""))
        map_id = zone_ids.get(row.get("zone", ""))
        if type_ and map_id:
            out.setdefault(map_id, []).append({"t": type_, "x": 0.0, "y": 0.0, "gx": round(float(row["x"]), 1),
                                               "gy": round(float(row["y"]), 1), "name": row.get("russian_name", "")})
    return out


GATE_RE = re.compile(r"^Ab1_(\d{4})_Gatecontrol", re.I)
FORTRESS_NAME_M = 60  # the area name of a fortress stands within this many metres of its gate control


def fortress_points(entities: list[dict], labels: dict[str, list[tuple[float, float, str]]]) -> dict[str, list[dict]]:
    """Siege fortresses: each has a gate control object «Ab1_<abyss id>_Gatecontrol_N» in the level data.
    labels: map id -> [(game y, game x, area name)]; the nearest one names the fortress."""
    out: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for row in entities:
        match = GATE_RE.match(row.get("name", ""))
        if not match or (row["map_id"], match.group(1)) in seen:
            continue
        seen.add((row["map_id"], match.group(1)))
        gx, gy = float(row["game_x"]), float(row["game_y"])
        named = [(math.hypot(ly - gy, lx - gx), text) for ly, lx, text in labels.get(row["map_id"], [])]
        dist, text = min(named, default=(math.inf, ""))
        name = " ".join(text.split()) if dist < FORTRESS_NAME_M else ""
        out.setdefault(row["map_id"], []).append({"t": "fortress", "x": 0.0, "y": 0.0, "gx": round(gx, 1),
                                                   "gy": round(gy, 1), "name": name})
    return out


def merge(data: dict, extra: dict[str, list[dict]], radius: float = SAME_SPOT_M) -> int:
    """Add points except exact repeats (same type and name within radius metres): two different NPCs standing
    next to each other (a teleporter and an ether ship) both stay. Returns how many were added.
    x / y stay 0: the program places points from game coordinates with each zone's map transform."""
    added = 0
    for map_id, points in extra.items():
        known = data["zones"].setdefault(map_id, [])
        for point in points:
            if any(p["t"] == point["t"] and p["name"] == point["name"]
                   and math.hypot(p["gx"] - point["gx"], p["gy"] - point["gy"]) < radius for p in known):
                continue
            known.append(point)
            added += 1
            if point["t"] not in data["types"] and point["t"] in TYPES:
                group, name = TYPES[point["t"]]
                data["types"][point["t"]] = {"group": group, "name": name}
                if (ROOT / "data" / "maps" / "icons" / f"{point['t']}.png").is_file():
                    data["types"][point["t"]]["icon"] = f"{point['t']}.png"
        if not known:
            del data["zones"][map_id]
    return added


def read_tsv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "client_extract"
    zones = set(json.loads((ROOT / "data" / "maps" / "maps.json").read_text(encoding="utf-8")))
    objects = read_tsv(source / "client_level_objects.tsv")
    data = build(objects, read_tsv(source / "client_level_entities.tsv"), zones)
    zone_ids = {row["zone"]: row["map_id"] for row in objects if row["map_id"] in zones}
    service = source / "raw" / "npc_service_coords.tsv"
    if service.is_file():
        print(f"client world xml: {merge(data, service_points(read_tsv(service), zone_ids))} functional NPCs")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tools"))
    from build_newmaps import zonemaps
    from watcher.mapview import load_labels

    frames = zonemaps()
    labels = {}  # area names in game coordinates: svg units are metres from the zonemap offset
    for code, (_view, rows) in load_labels(ROOT / "data" / "maps" / "labels.tsv").items():
        frame = frames.get(code)
        if frame:
            labels[frame["id"]] = [(x + frame["offset"][0], y + frame["offset"][1], t) for x, y, t in rows]
    entities = read_tsv(source / "client_level_entities.tsv")
    print(f"fortresses: {merge(data, fortress_points([e for e in entities if e['map_id'] in zones], labels))}")
    out = ROOT / "data" / "maps" / "poi.json"
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts: dict[str, int] = {}
    for points in data["zones"].values():
        for p in points:
            counts[p["t"]] = counts.get(p["t"], 0) + 1
    print(f"{sum(counts.values())} points, {out.stat().st_size // 1024} KB")
    for type_, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {type_:18s} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
