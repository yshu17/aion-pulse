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
}
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
        type_ = classify_object(row)
        if type_ is None or row.get("map_id") not in zones:
            continue
        name = row.get("npc_russian_name") or ""
        point = _point(type_, row, name)
        if point is not None:
            out.setdefault(row["map_id"], []).append(point)
    for row in entities:
        if row.get("entity_class") == "AbyssArtifacts" and row.get("map_id") in zones:
            point = _point("artifact", row, "")
            if point is not None:
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


def read_tsv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "client_extract"
    zones = set(json.loads((ROOT / "data" / "maps" / "maps.json").read_text(encoding="utf-8")))
    data = build(read_tsv(source / "client_level_objects.tsv"), read_tsv(source / "client_level_entities.tsv"), zones)
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
