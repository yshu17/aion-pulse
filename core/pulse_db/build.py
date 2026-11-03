"""Build data/pulse.db, the one game database of Pulse+ (docs/ADR-002-pulse-db.md), from the files built today.

    report = build(Sources(spawns=..., npc_points=..., npcs=..., bestiary=...), Path("data/pulse.db"))

Stage 1 holds the NPCs and all their points: ``npc`` (every id any source knows, the bestiary's fields first, the map's
flags), ``npc_alias`` (a marker of the map «poi:Имя» → the NPCs of that name) and ``npc_point`` (the map's points, then
the game data's, then the bestiary's own; a place already there to a unit is not added again). The schema is
core/pulse_db/schema.sql; ``PRAGMA user_version`` is SCHEMA_VERSION. The same input gives the same rows.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.bestiary.bestiary_store import unpack_detail

SCHEMA_VERSION = 1
SCHEMA = Path(__file__).with_name("schema.sql")


@dataclass(frozen=True)
class Sources:
    spawns: Path       # data/maps/spawns.json
    npc_points: Path   # data/game/npc_points.json.gz
    npcs: Path         # data/game/npcs.json.gz
    bestiary: Path     # data/bestiary/npcs.sqlite


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


def build(sources: Sources, out: Path) -> dict:
    """Write the database to ``out`` (a fresh file) and return counts of what went in."""
    spawns = _read_json(sources.spawns)
    npcs: dict[str, dict] = {}

    def npc(npc_id: str, **fields) -> None:
        row = npcs.setdefault(npc_id, {"id": npc_id, "name": "", "kind": None, "rank": None, "level": None, "race": None,
                                       "faction": None, "role": None, "icon": None, "deco": 0, "sp_only": 0, "source": fields["source"]})
        for key, value in fields.items():
            if key != "source" and value not in (None, "") and row.get(key) in (None, "", 0):
                row[key] = value

    points = _Points()
    details: dict[str, dict] = {}
    if sources.bestiary.is_file():
        db = sqlite3.connect(sources.bestiary)
        for npc_id, name, kind, race, faction, rank, level, role, icon, blob in db.execute(
                "SELECT id, name, kind, race, faction, rank, level, role, icon_asset, detail FROM npc ORDER BY id"):
            npc(str(npc_id), name=name, kind=kind, race=race, faction=faction, rank=rank, level=_level(level), role=role,
                icon=icon, source="bestiary")
            if blob:
                details[str(npc_id)] = unpack_detail(blob)
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

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    db.executemany(
        "INSERT INTO npc (id, name, name_key, kind, rank, level, race, faction, role, icon, deco, sp_only, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r["id"], r["name"] or "", name_key(r["name"] or ""), r["kind"], r["rank"], r["level"], r["race"], r["faction"],
          r["role"], r["icon"], r["deco"], r["sp_only"], r["source"]) for r in sorted(npcs.values(), key=lambda r: r["id"])])
    db.executemany("INSERT INTO npc_alias (alias, npc_id) VALUES (?, ?)", aliases)
    db.executemany("INSERT INTO npc_point (npc_id, map_id, x, y, z, source) VALUES (?,?,?,?,?,?)", points.rows)
    db.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", [("schema", str(SCHEMA_VERSION)), ("stage", "1: npc, npc_alias, npc_point")])
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()
    db.execute("VACUUM")
    db.close()
    return {"npcs": len(npcs), "aliases": len(aliases), "points": len(points.rows)}
