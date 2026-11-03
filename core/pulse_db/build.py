"""Build data/pulse.db, the one game database of Pulse+ (docs/ADR-002-pulse-db.md), from the files built today.

    report = build(Sources(spawns=..., npc_points=..., npcs=..., bestiary=...), Path("data/pulse.db"))

Stage 1, the NPCs and all their points: ``npc`` (every id any source knows, the bestiary's fields first, the map's
flags), ``npc_alias`` (a marker of the map «poi:Имя» → the NPCs of that name) and ``npc_point`` (the map's points, then
the game data's, then the bestiary's own; a place already there to a unit is not added again).
Stage 2, the bestiary's cards as tables: ``npc`` gets the card's columns (listed, category, title, search_text,
sort_key, profile JSON …), ``item``, ``npc_drop``, ``npc_stock``, ``npc_zone``, ``npc_region``, ``npc_area``. The point
count of an NPC is the one table's, so the list, the card and the map show the same number.
The schema is core/pulse_db/schema.sql; ``PRAGMA user_version`` is SCHEMA_VERSION. The same input gives the same rows.
"""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.bestiary.bestiary_store import BestiaryStore

SCHEMA_VERSION = 2
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
    items: dict[str, tuple] = {}
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
                items.setdefault(item_id, (item_id, item.get("name") or "", name_key(item.get("name") or ""), item.get("rarity"), item.get("icon")))
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
                items.setdefault(str(item_id), (str(item_id), name or "", name_key(name or ""), rarity, icon))
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
    db.executemany("INSERT INTO item (id, name, name_key, rarity, icon, dropped_by) VALUES (?,?,?,?,?,?)",
                   sorted((int(i), *rest, pack_ids(sorted(dropped_by[i]), delta=True) if i in dropped_by else None)
                          for i, *rest in items.values()))
    db.executemany("INSERT INTO npc_stock (npc_id, ord, item_id, name, name_key, rarity, level, icon, grp, trade_mode) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?)", stock)
    db.executemany("INSERT INTO npc_zone (npc_id, map_id, name) VALUES (?,?,?)", places["npc_zone"])
    db.executemany("INSERT INTO npc_region (npc_id, map_id, name) VALUES (?,?,?)", places["npc_region"])
    db.executemany("INSERT INTO npc_area (npc_id, map_id, area_id, point_count, center_x, center_y, names, polygon) "
                   "VALUES (?,?,?,?,?,?,?,?)", places["npc_area"])
    db.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", [
        ("schema", str(SCHEMA_VERSION)), ("stage", "2: npc + points, the bestiary's cards (item, npc_drop, npc_stock, areas)")])
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()
    db.execute("VACUUM")
    db.close()
    try:
        os.replace(fresh, out)
    except PermissionError as error:  # Windows: a running Pulse+ holds the old file open
        raise PermissionError(f"{out} is in use (close Pulse+ first); the new database is left in {fresh}") from error
    return {"npcs": len(npcs), "aliases": len(aliases), "points": len(points.rows), "listed": sum(r["listed"] for r in npcs.values()),
            "drops": sum(len(v) for v in dropped_by.values()), "stock": len(stock), "items": len(items)}
