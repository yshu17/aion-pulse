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
    "dungeon": ("landmark", "Вход в данж"),
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
    "quest_give": ("quest", "Задание"),
    "quest_important": ("quest", "Важное задание"),
    "quest_event": ("quest", "Событие"),
}
QUEST_MAX_LEVEL = 55  # version 2.0: later quests are left out
# client quest category1 -> map type; the most important type of an NPC's quests picks its icon
QUEST_KINDS = {"important": "quest_important", "significant": "quest_important", "mission": "quest_important",
               "event": "quest_event"}
QUEST_ORDER = ["quest_important", "quest_give", "quest_event"]
QUEST_NOTE_MAX = 6
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
    if kind == "DP":
        return "direct_portal"
    if kind == "HSP":
        return f"gather_{gather_kind(row.get('object_name', ''))}"
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


# level objects that mark a landmark the game's map shows: (pattern on the object name, layer type).
# The mission files' «Portal» objects are CryEngine visibility portals (caves, rooms), not the game's portals;
# the only passages a player sees are the doors into the Silentera Tunnel.
# The name comes from the client's Russian strings (client_extract/raw/strings_ru.tsv) by key: {id} = the number
# caught in the object name; without a string, the nearest area label names the point.
LANDMARKS = [
    (re.compile(r"^Ab1_(\d{4})_Gatecontrol", re.I), "fortress", "_SV_{id}"),  # each siege fortress has a gate control
    (re.compile(r"door_Underpass_IN", re.I), "portal", "STR_DIC_W_Underpass_SZ_S2"),  # «Проход в тоннель Силентера»
]
LANDMARK_NAME_M = 60  # the area name of a landmark stands within this many metres of it


def landmark_points(entities: list[dict], labels: dict[str, list[tuple[float, float, str]]],
                    strings: dict[str, str] | None = None) -> dict[str, list[dict]]:
    """Siege fortresses and Silentera entrances from the level objects (client_level_entities.tsv).
    strings: client string key -> Russian text; labels: map id -> [(game y, game x, area name)] as a fallback."""
    strings = strings or {}
    out: dict[str, list[dict]] = {}
    seen: set[tuple[str, str, str]] = set()
    for row in entities:
        found = next(((m, t, k) for pattern, t, k in LANDMARKS if (m := pattern.search(row.get("name", "")))), None)
        if found is None:
            continue
        match, type_, key_rule = found
        key_part = key_rule.format(id=match.group(1) if match.groups() else "")
        text = next((v for k, v in strings.items() if k == key_part or (key_part.startswith("_") and k.endswith(key_part))), "")
        key = (row["map_id"], type_, match.group(1) if match.groups() else row["name"])
        if key in seen:
            continue
        seen.add(key)
        gx, gy = float(row["game_x"]), float(row["game_y"])
        named = [(math.hypot(ly - gy, lx - gx), text) for ly, lx, text in labels.get(row["map_id"], [])]
        dist, label = min(named, default=(math.inf, ""))
        name = text.split(";")[0] or (" ".join(label.split()) if dist < LANDMARK_NAME_M else "")
        out.setdefault(row["map_id"], []).append({"t": type_, "x": 0.0, "y": 0.0, "gx": round(gx, 1),
                                                   "gy": round(gy, 1), "name": name})
    return out


def world_npcs(text: str, code: str) -> list[tuple[str, str, float, float]]:
    """<npc_info> of a client_world_<zone>.xml: (npc id, zone code, game x, game y) of every placed NPC."""
    return [(nid, code, float(x), float(y)) for nid, x, y in re.findall(
        r"<npc_info>.*?<nameid>(\d+)</nameid>.*?<x>([\d.]+)</x>\s*<y>([\d.]+)</y>", text, re.S)]


# The client's dungeon entrances and gates are objects (ids 700000+) placed by <npc_info> like NPCs:
# «Вход в храм Удас» is DF4_IDTemple_Up_IN. Quest doors (_Q2076) and exits (_Out) are left out; the Silentera
# tunnel's own entrances come from the level data (door_Underpass_IN), its exits from here.
ENTRANCE = re.compile(r"(_In|_IN|_Entrance(_[LD])?)$")
GATE = re.compile(r"AbyssGate|UnderPass_out")


def entrance_points(npcs: dict[str, dict], spawns: dict[str, list[tuple[str, float, float]]],
                    zone_ids: dict[str, str]) -> dict[str, list[dict]]:
    """Dungeon entrances and gates (Abyss gates, Silentera exits) placed in mapped zones."""
    out: dict[str, list[dict]] = {}
    for nid, places in spawns.items():
        npc = npcs.get(nid)
        if npc is None or int(nid) < 700000:
            continue
        internal, name = npc["internal_name"], npc["russian_name"]
        if GATE.search(internal):
            type_ = "portal"
        elif (ENTRANCE.search(internal) and name.startswith("Вход") and "UnderPass" not in internal
              and not re.search(r"_Q\d+", internal)):
            type_ = "dungeon"
        else:
            continue
        for code, gx, gy in sorted(set(places)):
            if code in zone_ids:
                out.setdefault(zone_ids[code], []).append({"t": type_, "x": 0.0, "y": 0.0, "gx": round(gx, 1),
                                                           "gy": round(gy, 1), "name": name})
    return out


def quest_points(quests: dict[str, dict], links: list[dict], spawns: dict[str, list[tuple[str, float, float]]],
                 zone_ids: dict[str, str], names: dict[str, str]) -> dict[str, list[dict]]:
    """NPCs that give quests, one point per placed NPC.

    quests: our client's quests (quest_givers.tsv by Codex); links: quest -> start NPC from aiondb.ru
    (downloads/aiondb_quests/quest_start_npc.tsv; the client has no such link); spawns: npc id -> where the client
    places it. Kept: quests of our client up to level QUEST_MAX_LEVEL whose NPC the client places in a mapped zone.
    """
    by_npc: dict[str, list[dict]] = {}
    for link in links:
        quest = quests.get(link["quest_id"])
        if quest is None or int(quest.get("min_level") or 0) > QUEST_MAX_LEVEL:
            continue
        by_npc.setdefault(link["start_npc_id"], []).append(quest)
    out: dict[str, list[dict]] = {}
    for npc, given in by_npc.items():
        kinds = {QUEST_KINDS.get(q["category"].split("|")[0].strip(), "quest_give") for q in given}
        type_ = next(t for t in QUEST_ORDER if t in kinds)
        titles = sorted({q["name_ru"] for q in given})
        note = f"Задания ({len(titles)}): " + "; ".join(titles[:QUEST_NOTE_MAX]) + ("; …" if len(titles) > QUEST_NOTE_MAX else "")
        for code, gx, gy in spawns.get(npc, []):
            if code in zone_ids:
                out.setdefault(zone_ids[code], []).append({"t": type_, "x": 0.0, "y": 0.0, "gx": round(gx, 1),
                                                           "gy": round(gy, 1), "name": names.get(npc, ""),
                                                           "note": note})
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
    strings_path = source / "raw" / "strings_ru.tsv"
    strings = dict(r[:2] for r in csv.reader(open(strings_path, encoding="utf-8"), delimiter="	") if len(r) >= 2)         if strings_path.is_file() else {}
    landmarks = landmark_points([e for e in entities if e["map_id"] in zones], labels, strings)
    print(f"fortresses and entrances: {merge(data, landmarks)}")
    spawns: dict[str, list[tuple[str, float, float]]] = {}
    for code in zone_ids:
        world = source / "raw" / "Data" / "world" / "world" / f"client_world_{code}"
        text = (world.with_suffix(".txt.xml").read_text(encoding="utf-8") if world.with_suffix(".txt.xml").is_file()
                else world.with_suffix(".xml").read_bytes().decode("utf-16", errors="replace"))
        for nid, zone, gx, gy in world_npcs(text, code):
            spawns.setdefault(nid, []).append((zone, gx, gy))
    npcs = {r["npc_id"]: r for r in read_tsv(source / "client_npcs.tsv")}
    print(f"dungeon entrances and gates: {merge(data, entrance_points(npcs, spawns, zone_ids))}")
    links_path = ROOT / "downloads" / "aiondb_quests" / "quest_start_npc.tsv"
    quests_path = source / "raw" / "quest_givers.tsv"
    if links_path.is_file() and quests_path.is_file():
        quests = {r["quest_id"]: r for r in csv.DictReader(open(quests_path, encoding="utf-8-sig"), delimiter="\t")}
        names = {nid: r["russian_name"] for nid, r in npcs.items()}
        with open(links_path, encoding="utf-8", newline="") as f:
            links = list(csv.DictReader(f, delimiter="\t"))
        print(f"quest givers: {merge(data, quest_points(quests, links, spawns, zone_ids, names))}")
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
