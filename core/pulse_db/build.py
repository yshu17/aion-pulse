"""Build data/pulse.db, the one game database of Pulse+ (docs/ADR-002-pulse-db.md), from the files built today.

    report = build(Sources(spawns=..., npc_points=..., npcs=..., bestiary=...), Path("data/pulse.db"))

Stage 1, the NPCs and all their points: ``npc`` (every id any source knows, the bestiary's fields first, the map's
flags), ``npc_alias`` (a marker of the map «poi:Имя» → the NPCs of that name) and ``npc_point`` (the map's points, then
the game data's, then the bestiary's own; a place already there to a unit is not added again).
Stage 2, the bestiary's cards as tables: ``npc`` gets the card's columns (listed, category, title, search_text,
sort_key, profile JSON …), ``npc_stock``, ``npc_zone``, ``npc_region``, ``npc_area``. The point
count of an NPC is the one table's, so the list, the card and the map show the same number.
Stage 3, ``item``: every item once — the catalog of cards (its fields win), the descriptions, the bestiary's drops
(packed lists ``npc.drops`` / ``item.dropped_by``) and the names of chat links.
Stage 4, the game data's ``quest`` (with the chat links' quest names), ``recipe`` / ``recipe_part`` and ``vendor_item``;
the client's drop list is a part of the bestiary's, so no table.
Stage 5 (map:45), the client's catalog export (core/pulse_db/catalog.py): ``title``, ``skill``, ``skill_book``, ``stigma``, ``pet``,
the client's name, level and grade of every item (its quality where it has no grade), its picture where the item has none, and
``db_section`` / ``db_section_entry``: the ten sections of «База данных», their rule, size and ids.
The schema is core/pulse_db/schema.sql; ``PRAGMA user_version`` is SCHEMA_VERSION. The same input gives the same rows.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import sqlite3
import zlib
from dataclasses import dataclass
from pathlib import Path

from core.bestiary.bestiary_store import BestiaryStore
from core.pulse_db.aidb_quests import read_guides
from core.pulse_db.aidb_skills import read_skill_damage
from core.pulse_db.catalog import RULES, SECTIONS, read_client, section_entries
from core.pulse_db.gear import gear_rows
from core.pulse_db.quest_steps import quest_steps

SCHEMA_VERSION = 9
SCHEMA = Path(__file__).with_name("schema.sql")
# what of a bestiary card has a table or a column of its own; the rest goes into npc.profile
CARD_COLUMNS = {"id", "name", "internal_name", "category", "role", "title", "description", "race", "faction", "kind", "rank",
                "level", "hp_bar", "icon_asset", "points", "drops", "stock"}


@dataclass(frozen=True)
class Sources:
    spawns: Path       # data/maps/spawns.json
    npc_points: Path   # data/game/npc_points.json.gz
    npcs: Path         # data/game/npcs.json.gz
    bestiary: Path     # local/bestiary/npcs.sqlite (tools/build_bestiary_index.py)
    item_names: Path | None = None  # data/item_names.tsv: id<TAB>name of chat links
    catalog: Path | None = None     # data/watch_items.csv: the items with a card
    specs: Path | None = None       # data/item_specs.json.gz: the cards' descriptions
    items: Path | None = None       # data/game/items.json.gz: the client's own item list
    quests: Path | None = None      # data/game/quests.json.gz
    quest_names: Path | None = None  # data/quest_names.tsv: id<TAB>name of chat links
    recipes: Path | None = None     # data/game/recipes.json.gz
    vendors: Path | None = None     # data/game/vendors.json.gz
    client_catalog: Path | None = None  # client_extract/fresh_catalog/catalog.sqlite: grade fallback, skills, books, stigmas, titles, pets
    icons: Path | None = None       # data/icons: a picture is linked only when its file is there
    quest_dir: Path | None = None   # client_extract/raw/Data/quest: quest_monster.csv, quest_script_monster.csv (the quests' steps)
    aidb_pages: Path | None = None  # downloads/aidb_quests/pages: <quest id>.html of aidb.ru (tools/fetch_aidb_quests.py)
    aidb_skills: Path | None = None  # downloads/aidb_skills/pages: <skill id>.html of aidb.ru (tools/fetch_aidb_skills.py)
    client_raw: Path | None = None  # client_extract/fresh_catalog/raw: client_setitem.xml and the string files (the gear sets)


ITEM_FIELDS = ("id", "name", "level", "category", "grade", "kind", "icon", "drop_icon", "catalog_ord", "spec")


def _client_name(text) -> str:
    """The client writes «Временно>» without its «<»; the older lists and the game's own names keep «<Временно>»."""
    name = str(text or "").strip()
    return "<" + name if name.startswith("Временно>") else name


def _client_quality(path: Path | None) -> dict[str, str]:
    """The client's quality (the catalog's ``fields_json.quality``) by item id, lower case: the grade of an item without one."""
    if not path or not path.is_file():
        return {}
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {str(i): str(json.loads(fields).get("quality") or "").lower()
                for i, fields in db.execute("SELECT id, fields_json FROM entries WHERE section = 'items'")}
    finally:
        db.close()


def _client_fields(items: dict[int, dict], sources: Sources) -> None:
    """The client's own name, level and grade win over the older lists for the same id; the quality fills a missing grade."""
    if not sources.items or not sources.items.is_file():
        return
    quality = _client_quality(sources.client_catalog)
    for r in _read_json(sources.items).get("records", []):
        item_id = str(r.get("id") or "").strip()
        if not item_id.isdigit() or int(item_id) not in items:
            continue
        row = items[int(item_id)]
        name = _client_name(r.get("name"))
        if name:
            row["name"] = name
        level = _level(r.get("level"))
        if level is not None:
            row["level"] = level
        grade = str(r.get("grade") or quality.get(item_id) or "").lower()
        if grade:
            row["grade"] = grade


def _items(sources: Sources, drops: dict[str, tuple]) -> dict[int, dict]:
    """Every item once: the catalog's fields first, then the bestiary's, then the chat links' names; the client's name, level and grade last."""
    items: dict[int, dict] = {}

    def item(item_id, **fields) -> None:
        text = str(item_id or "").strip()
        if not text.isdigit():
            return
        row = items.setdefault(int(text), {key: None for key in ITEM_FIELDS} | {"id": int(text), "name": ""})
        for key, value in fields.items():
            if value not in (None, "") and row[key] in (None, ""):
                row[key] = value

    if sources.catalog and sources.catalog.is_file():
        with sources.catalog.open(encoding="utf-8-sig", newline="") as stream:
            for ord_, r in enumerate(csv.DictReader(stream)):
                item(r.get("id"), name=r.get("name"), level=_level(r.get("level")), category=r.get("category") or "Прочее",
                     grade=r.get("grade"), kind=r.get("kind"), icon=r.get("icon"), catalog_ord=ord_)
    specs = _read_json(sources.specs) if sources.specs else {}
    for item_id, spec in specs.items():
        item(item_id, spec=spec if isinstance(spec, str) else json.dumps(spec, ensure_ascii=False, separators=(",", ":")))
    for item_id, (name, rarity, icon) in sorted(drops.items()):
        item(item_id, name=name, grade=rarity, drop_icon=icon)
    for r in _read_json(sources.items).get("records", []) if sources.items else []:  # the client's list (icons as data/icons)
        item(r.get("id"), name=r.get("name"), level=_level(r.get("level")), grade=r.get("grade"), icon=(r.get("icon") or "").lower())
    if sources.item_names and sources.item_names.is_file():
        for line in sources.item_names.read_text(encoding="utf-8").splitlines():
            item_id, tab, name = line.partition("\t")
            if tab:
                item(item_id, name=name.strip())
    _client_fields(items, sources)
    return items


def pack_ids(ids, delta: bool = False) -> bytes:
    """Ids as a packed list (schema.sql): 7 bits a byte, low first, the high bit while more follow; `delta` keeps steps."""
    out = bytearray()
    previous = 0
    for value in ids:
        step = value - previous if delta else value
        previous = value
        while step >= 0x80:
            out.append((step & 0x7F) | 0x80)
            step >>= 7
        out.append(step)
    return bytes(out)


def unpack_ids(blob: bytes | None, delta: bool = False) -> list[int]:
    out, value, shift, previous = [], 0, 0, 0
    for byte in blob or b"":
        value |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            continue
        previous = previous + value if delta else value
        out.append(previous)
        value = shift = 0
    return out


SPEC_DICT_SIZE = 32 * 1024  # zlib's window: the dictionary of item.spec (19 MB of JSON → 3.4 MB)


def spec_dict(specs: list[bytes]) -> bytes:
    """The descriptions' shared dictionary: every 50th one (in id order) to 32 KB; the same specs give the same bytes."""
    return b"".join(specs[::50])[-SPEC_DICT_SIZE:]


def pack_spec(text: str, dictionary: bytes) -> bytes:
    packer = zlib.compressobj(9, zdict=dictionary)
    return packer.compress(text.encode("utf-8")) + packer.flush()


def unpack_spec(blob: bytes | None, dictionary: bytes) -> dict | None:
    if blob is None:
        return None
    unpacker = zlib.decompressobj(zdict=dictionary)
    return json.loads(unpacker.decompress(blob) + unpacker.flush())


def name_key(name: str) -> str:
    return name.casefold().replace("ё", "е")


def _level(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


class _Points:
    """The points in the order they come; a place already known for the NPC in the zone (to a unit) is skipped."""

    def __init__(self) -> None:
        self.rows: list[tuple] = []
        self._seen: set[tuple] = set()

    def add(self, npc: str, map_id: str, x, y, z, source: str) -> None:
        x, y, z = float(x), float(y), float(z or 0)
        key = (npc, map_id, round(x), round(y))
        if key in self._seen:
            return
        self._seen.add(key)
        self.rows.append((npc, map_id, x, y, z, source))


NPC_FIELDS = ("id", "name", "kind", "rank", "level", "race", "faction", "role", "icon", "deco", "sp_only", "source", "listed",
              "category", "internal_name", "title", "description", "search_text", "zone_names", "hp_bar", "has_profile",
              "service", "drop_count", "drops", "profile")


def _int(value) -> int | None:
    text = str(value if value is not None else "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


def _quests(sources: Sources) -> list[tuple]:
    """The game data's quests, then the chat links' names of the others; rows in id order."""
    rows: dict[int, tuple] = {}
    for r in _read_json(sources.quests).get("records", []) if sources.quests else []:
        quest_id = _int(r.get("id"))
        if quest_id is None:
            continue
        name = r.get("name") or ""
        race = r.get("race")
        rows[quest_id] = (quest_id, name, name_key(name), _int(r.get("min_level")), _int(r.get("max_level")),
                          ",".join(race) if isinstance(race, list) else race, r.get("category") or None,
                          int(bool(r.get("repeatable"))), r.get("giver"), r.get("ender"),
                          json.dumps(r.get("rewards") or [], ensure_ascii=False, separators=(",", ":")))
    if sources.quest_names and sources.quest_names.is_file():
        for line in sources.quest_names.read_text(encoding="utf-8").splitlines():
            quest_id, tab, name = line.partition("\t")
            if tab and _int(quest_id) is not None and int(quest_id) not in rows:
                rows[int(quest_id)] = (int(quest_id), name.strip(), name_key(name.strip()), None, None, None, None, None, None, None, None)
    return [rows[key] for key in sorted(rows)]


def _recipes(sources: Sources) -> tuple[list[tuple], list[tuple]]:
    """The recipes and their parts (in the recipe's order)."""
    recipes, parts = [], []
    for r in _read_json(sources.recipes).get("records", []) if sources.recipes else []:
        recipe_id = _int(r.get("id"))
        if recipe_id is None:
            continue
        name = r.get("name") or ""
        combo = [_int(i) for i in r.get("combo") or [] if _int(i) is not None]
        recipes.append((recipe_id, name, name_key(name), _int(r.get("product")), _int(r.get("count")), r.get("profession"),
                        _int(r.get("level")), r.get("race"), json.dumps(combo) if combo else None))
        for ord_, (item_id, count) in enumerate(r.get("ingredients") or []):
            if _int(item_id) is not None:
                parts.append((recipe_id, ord_, _int(item_id), _int(count) or 0))
    return sorted(recipes), sorted(parts)


def _vendors(sources: Sources) -> list[tuple]:
    """(npc, item, list) once each, from the game data's columns."""
    data = _read_json(sources.vendors) if sources.vendors else {}
    columns = data.get("columns", [])
    if not columns:
        return []
    npc, item, kind = columns.index("npc"), columns.index("item"), columns.index("kind")
    return sorted({(str(row[npc]), _int(row[item]), row[kind] or "") for row in data.get("rows", []) if _int(row[item]) is not None})


def build(sources: Sources, out: Path) -> dict:
    """Write the database to ``out`` (a fresh file) and return counts of what went in."""
    spawns = _read_json(sources.spawns)
    npcs: dict[str, dict] = {}

    def npc(npc_id: str, **fields) -> dict:
        row = npcs.get(npc_id)
        if row is None:
            row = npcs[npc_id] = {key: None for key in NPC_FIELDS}
            row.update(id=npc_id, name="", deco=0, sp_only=0, listed=0, has_profile=0, service=0, drop_count=0,
                       search_text="", zone_names="", source=fields["source"])
        for key, value in fields.items():
            if key != "source" and value not in (None, "") and row.get(key) in (None, "", 0):
                row[key] = value
        return row

    points = _Points()
    details: dict[str, dict] = {}
    drop_items: dict[str, tuple] = {}  # the bestiary's own data of a dropped item: name, rarity, picture
    dropped_by: dict[str, set[int]] = {}
    stock: list[tuple] = []
    places: dict[str, list[tuple]] = {"npc_zone": [], "npc_region": [], "npc_area": []}
    if sources.bestiary.is_file():
        store = BestiaryStore(sources.bestiary)
        db = sqlite3.connect(sources.bestiary)
        db.row_factory = sqlite3.Row
        for r in db.execute("SELECT id, name, search_text, category, role, kind, race, faction, rank, level, icon_asset, zone_names, "
                            "drop_count, has_profile, service FROM npc ORDER BY id"):
            npc_id = str(r["id"])
            detail = store.detail(npc_id) or {}
            details[npc_id] = detail
            profile = {key: value for key, value in sorted(detail.items()) if key not in CARD_COLUMNS}
            npc(npc_id, name=r["name"], kind=r["kind"], race=r["race"], faction=r["faction"], rank=r["rank"], level=_level(r["level"]),
                role=r["role"], icon=r["icon_asset"], listed=1, category=r["category"], internal_name=detail.get("internal_name"),
                title=detail.get("title"), description=detail.get("description"), search_text=r["search_text"],
                zone_names=r["zone_names"], hp_bar=detail.get("hp_bar"), has_profile=r["has_profile"], service=r["service"],
                drop_count=r["drop_count"], profile=json.dumps(profile, ensure_ascii=False, sort_keys=True), source="bestiary")
            ids = []
            for item in detail.get("drops") or []:
                item_id = str(item.get("item_id") or "")
                if not item_id.isdigit() or not npc_id.isdigit():
                    continue
                drop_items.setdefault(item_id, (item.get("name") or "", item.get("rarity"), item.get("icon")))
                ids.append(int(item_id))
                dropped_by.setdefault(item_id, set()).add(int(npc_id))
            if ids:
                npcs[npc_id]["drops"] = pack_ids(ids)
            for ord_, item in enumerate(detail.get("stock") or []):
                name = item.get("name") or ""
                stock.append((npc_id, ord_, item.get("item_id"), name, name_key(name), item.get("rarity"), item.get("level"),
                              item.get("icon_asset"), item.get("group"), item.get("trade_mode")))
        for item_id, name, rarity, icon in db.execute("SELECT item_id, name, rarity, icon FROM item ORDER BY item_id"):
            if str(item_id).isdigit():
                drop_items.setdefault(str(item_id), (name or "", rarity, icon))
        for table, columns in (("npc_zone", "npc_id, map_id, name"), ("npc_region", "npc_id, map_id, name"),
                               ("npc_area", "npc_id, map_id, area_id, point_count, center_x, center_y, names, polygon")):
            places[table] = [tuple(row) for row in db.execute(f"SELECT {columns} FROM {table} ORDER BY {columns}")]
        db.close()
    for record in _read_json(sources.npcs).get("records", []):
        role = (record.get("function") or "").lower() or None
        npc(str(record["id"]), name=record.get("name"), role=role, source="client")
    own = spawns.get("own", {})
    for npc_id, name in sorted(spawns.get("names", {}).items()):
        source = "map" if npc_id.startswith("poi:") else "own" if npc_id in own else "client"
        npc(npc_id, name=name, source=source)
    for npc_id in spawns.get("deco", []):
        if npc_id in npcs:
            npcs[npc_id]["deco"] = 1
    for npc_id in spawns.get("sp_only", []):
        if npc_id in npcs:
            npcs[npc_id]["sp_only"] = 1

    # the points: the map's first (what the map shows today), then the game data's and the bestiary's new places
    for map_id, rows in sorted(spawns.get("zones", {}).items()):
        for npc_id, x, y, z in rows:
            points.add(str(npc_id), str(map_id), x, y, z, "map")
    for map_id, npc_id, x, y, z, *_ in _read_json(sources.npc_points).get("rows", []):
        points.add(str(npc_id), str(map_id), x, y, z, "client")
    for npc_id, detail in sorted(details.items()):
        for p in detail.get("points") or []:
            if p.get("map_id") and p.get("gx") is not None:
                points.add(npc_id, str(p["map_id"]), p["gx"], p["gy"], p.get("gz"), "bestiary")
    for npc_id, *_ in points.rows:  # a point of an id no source names: the NPC is still listed (without a name)
        npc(npc_id, source="map")

    # a marker of the map is the NPC (the NPCs) of its name
    by_name: dict[str, list[str]] = {}
    for row in npcs.values():
        if not row["id"].startswith("poi:") and row["name"]:
            by_name.setdefault(name_key(row["name"]), []).append(row["id"])
    aliases = sorted((row["id"], target) for row in npcs.values() if row["id"].startswith("poi:")
                     for target in by_name.get(name_key(row["name"]), []))

    # the point count of each NPC: its own points and its aliases' (the map shows the same)
    counts: dict[str, int] = {}
    for npc_id, *_ in points.rows:
        counts[npc_id] = counts.get(npc_id, 0) + 1
    alias_of: dict[str, list[str]] = {}
    for alias, target in aliases:
        alias_of.setdefault(target, []).append(alias)

    out.parent.mkdir(parents=True, exist_ok=True)
    fresh = out.with_name(out.name + ".new")  # built aside, then put in place in one step
    if fresh.exists():
        fresh.unlink()
    db = sqlite3.connect(fresh)
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    rows = []
    for r in sorted(npcs.values(), key=lambda r: r["id"]):
        name = r["name"] or ""
        count = counts.get(r["id"], 0) + sum(counts.get(alias, 0) for alias in alias_of.get(r["id"], []))
        search = r["search_text"] or f"{name_key(name)} {r['id']}"
        rows.append((r["id"], name, name_key(name), r["kind"], r["rank"], r["level"], r["race"], r["faction"], r["role"], r["icon"],
                     r["deco"], r["sp_only"], r["source"], r["listed"], r["category"], r["internal_name"], r["title"], r["description"],
                     search, name_key(name), r["zone_names"] or "", r["hp_bar"], r["has_profile"] or 0, r["service"] or 0, count,
                     r["drop_count"] or 0, r["drops"], r["profile"]))
    db.executemany(
        "INSERT INTO npc (id, name, name_key, kind, rank, level, race, faction, role, icon, deco, sp_only, source, listed, category, "
        "internal_name, title, description, search_text, sort_key, zone_names, hp_bar, has_profile, service, point_count, drop_count, drops, "
        "profile) VALUES (" + ",".join("?" * 28) + ")", rows)
    db.executemany("INSERT INTO npc_alias (alias, npc_id) VALUES (?, ?)", aliases)
    db.executemany("INSERT INTO npc_point (npc_id, map_id, x, y, z, source) VALUES (?,?,?,?,?,?)", points.rows)
    items = _items(sources, drop_items)
    client = read_client(sources.client_catalog, sources.icons)
    if sources.icons and client["item_icon"]:  # the client's picture where the item has none or its file is missing; else NULL
        for item_id, row in items.items():
            if row["icon"] and (sources.icons / f"{row['icon']}.png").is_file():
                continue
            row["icon"] = client["item_icon"].get(item_id)
    dictionary = spec_dict([r["spec"].encode("utf-8") for _, r in sorted(items.items()) if r["spec"]])
    db.executemany(
        "INSERT INTO item (id, name, name_key, level, category, grade, kind, icon, drop_icon, catalog_ord, spec, dropped_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(i, r["name"], name_key(r["name"]), r["level"], r["category"], r["grade"], r["kind"], r["icon"], r["drop_icon"],
          r["catalog_ord"], pack_spec(r["spec"], dictionary) if r["spec"] else None, pack_ids(sorted(dropped_by[str(i)]), delta=True) if str(i) in dropped_by else None)
         for i, r in sorted(items.items())])
    db.executemany("INSERT INTO npc_stock (npc_id, ord, item_id, name, name_key, rarity, level, icon, grp, trade_mode) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?)", stock)
    quests = _quests(sources)
    recipes, parts = _recipes(sources)
    vendors = _vendors(sources)
    db.executemany("INSERT INTO quest (id, name, name_key, min_level, max_level, race, category, repeatable, giver, ender, rewards) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?)", quests)
    db.executemany("INSERT INTO recipe (id, name, name_key, product, count, profession, level, race, combo) VALUES (?,?,?,?,?,?,?,?,?)",
                   recipes)
    db.executemany("INSERT INTO recipe_part (recipe_id, ord, item_id, count) VALUES (?,?,?,?)", parts)
    db.executemany("INSERT INTO vendor_item (npc_id, item_id, kind) VALUES (?,?,?)", vendors)
    db.executemany("INSERT INTO npc_zone (npc_id, map_id, name) VALUES (?,?,?)", places["npc_zone"])
    db.executemany("INSERT INTO npc_region (npc_id, map_id, name) VALUES (?,?,?)", places["npc_region"])
    db.executemany("INSERT INTO npc_area (npc_id, map_id, area_id, point_count, center_x, center_y, names, polygon) "
                   "VALUES (?,?,?,?,?,?,?,?)", places["npc_area"])
    npc_by_internal = {str(r["internal_name"]).lower(): (r["id"], r["name"]) for r in npcs.values() if r.get("internal_name") and r["name"]}
    quest_ids = {str(f.get("name") or "").upper(): qid for qid, f in client["quest_fields"].items() if f.get("name")}
    steps = quest_steps(sources.quest_dir, client["quest_fields"], npc_by_internal, client["item_internal"], quest_ids)
    db.executemany("UPDATE quest SET steps = ? WHERE id = ?",
                   [(json.dumps(s, ensure_ascii=False, separators=(",", ":")), qid) for qid, s in sorted(steps.items())])
    guides = read_guides(sources.aidb_pages)
    known = {qid for (qid,) in db.execute("SELECT id FROM quest")}
    npc_ids = set(npcs)
    guide_rows = []
    for qid, g in sorted(guides.items()):
        if qid not in known:
            continue
        giver, ender, zone = g["giver"], g["ender"], g["zone"] or {}
        guide_rows.append((
            qid, g["name_en"], g["icon"], g["category"], g["race"], json.dumps(g["classes"], ensure_ascii=False), g["level"], g["rec_level"],
            g["repeat"], json.dumps(g["notes"], ensure_ascii=False), zone.get("id"), zone.get("name"),
            str(giver["id"]) if giver and str(giver["id"]) in npc_ids else None, giver["name"] if giver else None,
            str(ender["id"]) if ender and str(ender["id"]) in npc_ids else None, ender["name"] if ender else None,
            json.dumps(g["needs"], ensure_ascii=False), g["rewards"]["exp"], g["rewards"]["gold"], g["rewards"]["abyss"], g["title"],
            json.dumps({"items": g["rewards"]["items"], "choice": g["rewards"]["choice"]}, ensure_ascii=False),
            json.dumps(g["steps"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(g["start"]) if g["start"] else None))
    db.executemany("INSERT INTO quest_guide (quest_id, name_en, icon, category, race, classes, level, rec_level, repeat, notes, zone_id, zone_name, "
                   "giver, giver_name, ender, ender_name, needs, exp, gold, abyss, title, rewards, steps, start) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", guide_rows)
    # the NPC that starts / takes back a quest where the client's data and the older lists name none (known NPCs only)
    db.execute("UPDATE quest SET giver = (SELECT giver FROM quest_guide g WHERE g.quest_id = quest.id) "
               "WHERE giver IS NULL AND (SELECT giver FROM quest_guide g WHERE g.quest_id = quest.id) IS NOT NULL")
    db.execute("UPDATE quest SET ender = (SELECT ender FROM quest_guide g WHERE g.quest_id = quest.id) "
               "WHERE ender IS NULL AND (SELECT ender FROM quest_guide g WHERE g.quest_id = quest.id) IS NOT NULL")
    stones = {}
    for item_id, row in items.items():  # the card's manastone slots
        for block in (json.loads(row["spec"]).get("blocks", []) if row["spec"] else []):
            if block.get("kind") == "stones":
                stones[item_id] = {"count": block.get("count"), "bonus": block.get("bonus", 0)}
    gear = gear_rows(sources.client_catalog, sources.client_raw, stones)
    set_of = {item: sid for sid, _, members, _ in gear["set"] for item in json.loads(members)}
    db.executemany("INSERT INTO gear_item (id, name, name_key, icon, grade, level, slot, grp, races, classes, basic, bonus, stones, stones_bonus, enchant, set_id) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(r[0], r[1], name_key(r[1]), *r[2:], set_of.get(r[0])) for r in gear["item"]])
    db.executemany("INSERT INTO gear_stone (id, name, icon, grade, level, stat, value) VALUES (?,?,?,?,?,?,?)", gear["stone"])
    db.executemany("INSERT INTO gear_set (id, name, items, bonuses) VALUES (?,?,?,?)", gear["set"])
    db.executemany("INSERT INTO title (id, name, name_key, description, race, stats, icon) VALUES (?,?,?,?,?,?,?)", client["title"])
    db.executemany("INSERT INTO skill (id, internal_name, name, name_key, description, icon, stigma) VALUES (?,?,?,?,?,?,?)", client["skill"])
    db.executemany("INSERT INTO skill_book (item_id, skill, skill_id, classes) VALUES (?,?,?,?)",
                   [r[:4] for r in client["skill_book"] if r[0] in items])
    db.executemany("INSERT INTO stigma (item_id, skill, skill_id, gain_level, requires) VALUES (?,?,?,?,?)",
                   [r[:5] for r in client["stigma"] if r[0] in items])
    damage = read_skill_damage(sources.aidb_skills)
    db.executemany("INSERT INTO skill_damage (skill_id, text, dmg_min, dmg_max) VALUES (?,?,?,?)",
                   [(sid, d["text"], d["min"], d["max"]) for sid, d in sorted(damage.items()) if sid in {r[0] for r in client["skill"]}])
    db.executemany("INSERT INTO pet (id, internal_name, name, name_key, description, functions, icon) VALUES (?,?,?,?,?,?,?)", client["pet"])
    entries = section_entries(items, quests, recipes, client)
    sizes: dict[str, int] = {}
    for section, _ in entries:
        sizes[section] = sizes.get(section, 0) + 1
    db.executemany("INSERT INTO db_section (key, title, ord, entity, rule, count) VALUES (?,?,?,?,?,?)",
                   [(key, title, ord_, entity, RULES[key], sizes.get(key, 0)) for ord_, (key, title, entity) in enumerate(SECTIONS)])
    db.executemany("INSERT INTO db_section_entry (section, entity_id) VALUES (?, ?)", entries)
    db.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", [
        ("schema", str(SCHEMA_VERSION)), ("spec_dict", dictionary), ("title", "client" if client["title"] else "not built"),
        ("stage", "5: npc + points, the bestiary's cards, every item, quests, recipes, vendors, the client's catalog sections, skill damage (aidb)")])
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()
    db.execute("VACUUM")
    db.close()
    try:
        os.replace(fresh, out)
    except PermissionError as error:  # Windows: a running Pulse+ holds the old file open
        raise PermissionError(f"{out} is in use by a running Pulse+; the new database is left in {fresh}: "
                              "Pulse+ takes it at its next start (docs/ADR-003-pulse-db-replace.md)") from error
    return {"npcs": len(npcs), "aliases": len(aliases), "points": len(points.rows), "listed": sum(r["listed"] for r in npcs.values()),
            "drops": sum(len(v) for v in dropped_by.values()), "stock": len(stock), "items": len(items),
            "catalog": sum(r["catalog_ord"] is not None for r in items.values()), "quests": len(quests), "recipes": len(recipes),
            "vendor_items": len(vendors), "titles": len(client["title"]), "skills": len(client["skill"]),
            "skill_books": len(client["skill_book"]), "stigmas": len(client["stigma"]), "pets": len(client["pet"]), "quest_steps": len(steps), "quest_guides": len(guide_rows), "gear_items": len(gear["item"]), "sections": sizes}
