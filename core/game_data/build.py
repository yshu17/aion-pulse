"""Build the game data folder from the exported client tables.

    sources = Sources(items=Path(".../items.tsv"), item_names=..., ...)     # every input file is a parameter
    report = build_all(sources, Path("data/game"), built="2026-10-23", client_build=None, strict=False)

What is written into ``out_dir``: ``manifest.json`` (schema, build date if given, per section file, record count, SHA-256),
``report.json`` (counts, missing inputs, links to IDs that do not exist), one file per section (see sections.py and
layout.py) and ``drops.sqlite``. The same input gives the same bytes: records are sorted, gzip has no time stamp.

Links are checked before anything is written. ``strict=True`` stops with `BuildError` when a link points to an ID that
the target section does not have (GAME_DATA.md: «при битой ссылке сборка падает»); otherwise they are listed in the
report (a count and the first ten IDs) and the build goes on, because the client itself has some.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, fields
from pathlib import Path

from . import sections
from .layout import DROPS_FILE, DROPS_VERSION, MANIFEST, REPORT, SCHEMA, SECTION_FILES
from .tables import iter_tsv, read_pairs, read_tsv, to_float, to_int


class BuildError(Exception):
    """Strict build: links to IDs that do not exist (``args[0]`` is the report)."""


@dataclass
class Sources:
    """The input files. ``None`` or a missing file is an empty table: the section is built empty and named in the report."""

    items: Path | None = None
    item_names: Path | None = None
    legacy_item_names: Path | None = None  # data/item_names.tsv, no header: names for items the client strings lack
    legacy_watch_items: Path | None = None  # data/watch_items.csv: category and grade (not in the client tables)
    recipes: Path | None = None
    recipe_ingredients: Path | None = None
    recipe_combinations: Path | None = None
    recipe_names: Path | None = None
    npcs: Path | None = None
    npc_names: Path | None = None
    maps: Path | None = None
    map_names: Path | None = None
    location_labels: Path | None = None
    location_names: Path | None = None
    npc_locations: Path | None = None
    vendors: Path | None = None
    quest_info: Path | None = None  # client_extract/raw/quest_givers.tsv: level, race, category
    quest_npcs: Path | None = None
    quest_rewards: Path | None = None
    quest_names: Path | None = None
    skills: Path | None = None
    skill_names: Path | None = None
    skill_learns: Path | None = None
    stigmas: Path | None = None
    classes: Path | None = None
    class_names: Path | None = None
    drops: Path | None = None


# the input files of each section, for the «missing» list of the report
INPUTS = {
    "items": ["items", "item_names"],
    "recipes": ["recipes", "recipe_ingredients", "recipe_names"],
    "npcs": ["npcs", "npc_names"],
    "maps": ["maps", "map_names"],
    "labels": ["location_labels"],
    "npc_points": ["npc_locations"],
    "vendors": ["vendors"],
    "quests": ["quest_info", "quest_npcs", "quest_rewards", "quest_names"],
    "skills": ["skills", "skill_names", "skill_learns"],
    "stigmas": ["stigmas"],
    "classes": ["classes", "class_names"],
    "drops": ["drops"],
}
SAMPLES = 10  # IDs shown for each kind of broken link


def _json_bytes(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _gzip_bytes(data: bytes) -> bytes:
    # compresslevel and mtime fixed: the same data is the same bytes on every run
    return gzip.compress(data, compresslevel=9, mtime=0)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class _Links:
    """Counts the links to IDs that do not exist, by kind («recipes.product -> items»)."""

    def __init__(self, known: dict[str, set[str]]):
        self.known = known
        self.broken: dict[str, dict] = {}

    def check(self, kind: str, target: str, value: str | int | None) -> None:
        if value is None:
            return
        if str(value) not in self.known[target]:
            entry = self.broken.setdefault(kind, {"count": 0, "samples": []})
            entry["count"] += 1
            if len(entry["samples"]) < SAMPLES and str(value) not in entry["samples"]:
                entry["samples"].append(str(value))


def build_all(sources: Sources, out_dir: Path, built: str | None = None, client_build: str | None = None, strict: bool = False) -> dict:
    out_dir = Path(out_dir)
    skip = ("drops", "legacy_item_names", "legacy_watch_items")
    rows = {f.name: read_tsv(getattr(sources, f.name)) for f in fields(Sources) if f.name not in skip}
    rows["legacy_watch_items"] = read_tsv(sources.legacy_watch_items, delimiter=",")
    legacy_names = read_pairs(sources.legacy_item_names)

    data: dict[str, object] = {
        "items": sections.items(rows["items"], rows["item_names"], legacy_names, rows["legacy_watch_items"]),
        "recipes": sections.recipes(rows["recipes"], rows["recipe_ingredients"], rows["recipe_combinations"], rows["recipe_names"]),
        "npcs": sections.npcs(rows["npcs"], rows["npc_names"]),
        "maps": sections.maps(rows["maps"], rows["map_names"]),
        "labels": sections.labels(rows["location_labels"], rows["location_names"]),
        "npc_points": sections.npc_points(rows["npc_locations"]),
        "vendors": sections.vendors(rows["vendors"]),
        "quests": sections.quests(rows["quest_info"], rows["quest_npcs"], rows["quest_rewards"], rows["quest_names"]),
        "skills": sections.skills(rows["skills"], rows["skill_names"], rows["skill_learns"]),
        "stigmas": sections.stigmas(rows["stigmas"]),
        "classes": sections.classes(rows["classes"], rows["class_names"]),
    }
    known = {
        "items": {r["id"] for r in data["items"]},  # type: ignore[union-attr]
        "npcs": {r["id"] for r in data["npcs"]},  # type: ignore[union-attr]
        "maps": {r["id"] for r in data["maps"]},  # type: ignore[union-attr]
    }
    links = _Links(known)
    for recipe in data["recipes"]:  # type: ignore[union-attr]
        links.check("recipes.product -> items", "items", recipe["product"])
        for item, _ in recipe["ingredients"]:
            links.check("recipes.ingredient -> items", "items", item)
        for item in recipe["combo"] or []:
            links.check("recipes.combo -> items", "items", item)
    for row in data["vendors"]:  # type: ignore[union-attr]
        links.check("vendors.npc -> npcs", "npcs", row[0])
        links.check("vendors.item -> items", "items", row[1])
    for quest in data["quests"]:  # type: ignore[union-attr]
        links.check("quests.giver -> npcs", "npcs", quest["giver"])
        links.check("quests.ender -> npcs", "npcs", quest["ender"])
        for reward in quest["rewards"]:
            links.check("quests.reward -> items", "items", reward["item"])
    for row in data["npc_points"]:  # type: ignore[union-attr]
        links.check("npc_points.map -> maps", "maps", row[0])
        links.check("npc_points.npc -> npcs", "npcs", row[1])
    for row in data["labels"]:  # type: ignore[union-attr]
        links.check("labels.map -> maps", "maps", row[0])

    drops_info = {"records": 0, "duplicates": 0, "built": False}
    drops_path = out_dir / DROPS_FILE
    if sources.drops is not None and Path(sources.drops).is_file():
        drops_info = write_drops(sources.drops, drops_path, links, build_only_check=strict and bool(links.broken))
    broken = links.broken
    report = {
        "schema": SCHEMA, "built": built, "client_build": client_build,
        "sections": {name: {"records": _count(data[name]), "missing_inputs": _missing(sources, name)} for name in data},
        "drops": {"records": drops_info["records"], "duplicates": drops_info["duplicates"], "missing_inputs": _missing(sources, "drops")},
        "items_without_name": sum(1 for r in data["items"] if r["name"] is None),  # type: ignore[union-attr]
        "items_with_legacy_name": sum(1 for r in data["items"] if r.get("name_source") == "legacy"),  # type: ignore[union-attr]
        "broken_links": broken,
        "ok": not broken,
    }
    if strict and broken:
        raise BuildError(report)

    manifest_sections = {}
    for name, filename in SECTION_FILES.items():
        payload = _wrap(name, data[name])
        raw = _json_bytes(payload)
        _write_atomic(out_dir / filename, _gzip_bytes(raw) if filename.endswith(".gz") else raw)
        manifest_sections[name] = {"file": filename, "records": report["sections"][name]["records"], "sha256": _sha256(out_dir / filename)}
    if drops_info["built"]:
        manifest_sections["drops"] = {"file": DROPS_FILE, "records": drops_info["records"], "sha256": _sha256(drops_path)}
    manifest = {"schema": SCHEMA, "built": built, "client_build": client_build, "sections": manifest_sections}
    _write_atomic(out_dir / MANIFEST, _json_bytes(manifest) + b"\n")
    _write_atomic(out_dir / REPORT, json.dumps(report, ensure_ascii=False, indent=1).encode("utf-8") + b"\n")
    return report


_TABLES = {"labels": sections.LABEL_COLUMNS, "npc_points": sections.NPC_POINT_COLUMNS, "vendors": sections.VENDOR_COLUMNS}


def _wrap(name: str, content: object) -> dict:
    if name in _TABLES:
        return {"schema": SCHEMA, "section": name, "columns": _TABLES[name], "rows": content}
    if name == "skills":
        return {"schema": SCHEMA, "section": name, **content}  # type: ignore[dict-item]
    return {"schema": SCHEMA, "section": name, "records": content}


def _count(content: object) -> int:
    if isinstance(content, dict):
        return len(content["skills"])
    return len(content)  # type: ignore[arg-type]


def _missing(sources: Sources, section: str) -> list[str]:
    return [field for field in INPUTS[section] if not (getattr(sources, field) and Path(getattr(sources, field)).is_file())]


def write_drops(source: Path, target: Path, links: _Links, build_only_check: bool = False) -> dict:
    """The drops into SQLite: ``drops(npc_id, item_id, chance_min, chance_max, count_min, count_max)`` with the key
    (npc_id, item_id) and an index by item, so both «what does this NPC drop» and «who drops this item» are quick.
    Unknown chance and count are NULL. Streamed: the table has 1.4 million rows."""
    info = {"records": 0, "duplicates": 0, "built": False}
    connection = None
    if not build_only_check:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.unlink(missing_ok=True)
        connection = sqlite3.connect(temporary)
        connection.executescript(
            "PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;"
            "CREATE TABLE drops(npc_id INTEGER NOT NULL, item_id INTEGER NOT NULL, chance_min REAL, chance_max REAL,"
            " count_min INTEGER, count_max INTEGER, PRIMARY KEY(npc_id, item_id)) WITHOUT ROWID;"
            "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;")
    batch: list[tuple] = []
    seen: set[tuple[int, int]] = set()
    for row in iter_tsv(source):
        npc, item = to_int(row.get("npc_id")), to_int(row.get("item_id"))
        if npc is None or item is None:
            continue
        links.check("drops.npc -> npcs", "npcs", npc)
        links.check("drops.item -> items", "items", item)
        if (npc, item) in seen:
            info["duplicates"] += 1
        seen.add((npc, item))
        batch.append((npc, item, to_float(row.get("chance_min")), to_float(row.get("chance_max")),
                      to_int(row.get("count_min")), to_int(row.get("count_max"))))
        if connection is not None and len(batch) >= 50_000:
            connection.executemany("INSERT OR REPLACE INTO drops VALUES (?,?,?,?,?,?)", batch)
            batch = []
    info["records"] = len(seen)
    if connection is None:
        return info
    if batch:
        connection.executemany("INSERT OR REPLACE INTO drops VALUES (?,?,?,?,?,?)", batch)
    connection.execute("CREATE INDEX drops_by_item ON drops(item_id, npc_id)")
    connection.execute("INSERT INTO meta VALUES ('source', 'site')")
    connection.execute(f"PRAGMA user_version={DROPS_VERSION}")
    connection.commit()
    connection.close()
    os.replace(temporary, target)
    info["built"] = True
    return info
