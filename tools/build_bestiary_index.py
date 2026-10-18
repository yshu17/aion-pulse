"""Build the compact, searchable SQLite index used by the Bestiary tab.

The source JSON is an auditable archive. The application reads this derived
index instead so a search never parses 1.4 million drop rows at startup.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import zlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from watcher.bestiary_classify import plan
from watcher.bestiary_store import DETAIL_DICT
from watcher.bestiary_labels import faction_for, race_label
from tools.build_bestiary_data import SITE_MAP_IDS


def _text(value: object) -> str:
    return str(value or "").strip()


def _pack(value: object) -> bytes:
    return zlib.compress(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)


def _pack_detail(value: object) -> bytes:
    packer = zlib.compressobj(9, zdict=DETAIL_DICT)
    return packer.compress(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + packer.flush()


def build(source: Path, areas_source: Path, output: Path) -> tuple[int, int]:
    with gzip.open(source, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    with gzip.open(areas_source, "rt", encoding="utf-8") as stream:
        areas = json.load(stream)["areas"]
    services_path = source.with_name("services.json.gz")
    services = {}
    if services_path.exists():
        with gzip.open(services_path, "rt", encoding="utf-8") as stream:
            services = json.load(stream).get("npcs", {})

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    con = sqlite3.connect(temporary)
    try:
        con.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE npc (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                search_text TEXT NOT NULL,
                category TEXT NOT NULL,
                role TEXT NOT NULL,
                kind TEXT NOT NULL,
                race TEXT NOT NULL,
                faction TEXT NOT NULL,
                rank TEXT NOT NULL,
                level TEXT,
                icon_asset TEXT NOT NULL,
                zone_names TEXT NOT NULL,
                point_count INTEGER NOT NULL,
                drop_count INTEGER NOT NULL,
                has_profile INTEGER NOT NULL,
                detail BLOB NOT NULL,
                service INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE item (
                item_id TEXT PRIMARY KEY, name TEXT NOT NULL, rarity TEXT NOT NULL, icon TEXT NOT NULL
            );
            CREATE TABLE shared (key TEXT PRIMARY KEY, data BLOB NOT NULL);
            CREATE TABLE npc_stock (npc_id TEXT NOT NULL, name TEXT NOT NULL, shown TEXT NOT NULL);
            CREATE TABLE npc_zone (
                npc_id TEXT NOT NULL,
                map_id TEXT NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (npc_id, map_id)
            );
            CREATE TABLE npc_area (
                npc_id TEXT NOT NULL,
                map_id TEXT NOT NULL,
                area_id TEXT NOT NULL,
                point_count INTEGER NOT NULL,
                center_x REAL NOT NULL,
                center_y REAL NOT NULL,
                names TEXT NOT NULL,
                polygon TEXT NOT NULL,
                PRIMARY KEY (npc_id, map_id, area_id)
            );
            CREATE TABLE npc_region (
                npc_id TEXT NOT NULL, map_id TEXT NOT NULL, name TEXT NOT NULL,
                PRIMARY KEY (npc_id, map_id, name)
            );
            """
        )
        zones = data["zones"]
        rows = []
        for record in data["records"]:
            kb = record.get("kb") or {}
            rows.append({
                "id": str(record["id"]),
                "name": _text(record.get("name") or record.get("site_name") or record.get("internal_name")) or str(record["id"]),
                "level": _text(kb.get("level") or record.get("site_level")), "category": record.get("category") or "",
                "points": len(record.get("points") or []), "drops": len(kb.get("drops") or []), "profile": int(bool(kb)),
            })
        donors, service_ids = plan(rows)  # spawn points for records without their own; technical and duplicate records
        by_id = {str(record["id"]): record for record in data["records"]}
        names = {row["id"]: row["name"] for row in rows}
        shared: dict[str, bytes] = {}  # identical drop and stock lists are stored once

        def share(value: list) -> str:
            blob = _pack(value)
            key = hashlib.sha1(blob).hexdigest()[:20]
            shared[key] = blob
            return key

        items: dict[str, tuple] = {}  # drop items are stored once and referenced by id from every NPC
        for record in data["records"]:
            kb = record.get("kb") or {}
            service = services.get(str(record["id"]), {})
            badges = kb.get("badges") or {}
            points = record.get("points") or []
            donor_id = donors.get(str(record["id"]))
            if donor_id:
                points = by_id[donor_id].get("points") or []
            mapped_ids = sorted({str(point["map_id"]) for point in points if point.get("map_id")})
            zone_names = [str(zones.get(map_id, map_id)) for map_id in mapped_ids]
            for location in kb.get("locations") or []:
                name = _text(location.get("name"))
                if name and name not in zone_names:
                    zone_names.append(name)
            name = _text(record.get("name") or record.get("site_name") or record.get("internal_name")) or str(record["id"])
            race = race_label(_text(record.get("race")), _text(badges.get("race")))
            faction = faction_for(_text(record.get("race")), _text(badges.get("race")))
            raw_kind = _text(badges.get("type") or record.get("role") or record.get("category"))
            kind = {"monster": "Монстр", "npc": "NPC", "merchant": "Торговец"}.get(raw_kind, raw_kind)
            category = {"монстр": "monster", "npc": "npc", "торговец": "npc"}.get(kind.casefold(), record.get("category") or "")
            role = _text(service.get("role") or record.get("role")).casefold()
            if service.get("tabs") or role in ("merchant", "coin_merchant"):
                role, kind, category = "merchant", "Торговец", "npc"
            rank = _text(badges.get("rank"))
            search_text = " ".join(
                _text(record.get(key)) for key in ("name", "site_name", "local_name", "internal_name", "id")
            ).casefold()
            drops = kb.get("drops") or []
            for drop in drops:
                items.setdefault(str(drop.get("item_id")), (
                    _text(drop.get("name")), _text(drop.get("rarity")), Path(_text(drop.get("icon"))).name,
                ))
            con.executemany(
                "INSERT INTO npc_stock VALUES (?,?,?)",
                ((str(record["id"]), name.casefold(), name) for name in {_text(entry.get("name")) for entry in service.get("stock", [])} if name),
            )
            detail = {
                "id": str(record["id"]),
                "name": name,
                "internal_name": record.get("internal_name") or "",
                "category": category,
                "role": role,
                "title": service.get("title", ""),
                "description": service.get("description", ""),
                "stock": share(service["stock"]) if service.get("stock") else "",
                "trade_tabs": service.get("tabs", []),
                "stock_source": service.get("source", ""),
                "race": race,
                "faction": faction,
                "kind": kind,
                "rank": rank,
                "level": kb.get("level") or record.get("site_level"),
                "hp_bar": kb.get("hp_bar"),
                "icon_asset": record.get("icon_asset") or "",
                "stats": kb.get("stats") or {},
                "drops": share([str(drop.get("item_id")) for drop in drops]) if drops else "",
                "points": points,
                "points_from": names[donor_id] if donor_id else "",
                "kb_locations": [
                    {"slug": loc.get("slug"), "name": loc.get("name"), "count": len(loc.get("points") or [])}
                    for loc in kb.get("locations") or []
                ],
                "kb_url": record.get("kb_url") or "",
                "kb_status": record.get("kb_status") or "",
                "seller_inventory_state": record.get("seller_inventory_state") or "",
            }
            for label, value in (("Макс. ХП", record.get("site_hp")), ("Опыт", record.get("site_experience"))):
                if label not in detail["stats"] and value is not None:
                    detail["stats"][label] = str(value)
            con.execute(
                "INSERT INTO npc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(record["id"]), name, search_text, category,
                    role, kind, race, faction, rank,
                    _text(detail["level"]), _text(detail["icon_asset"]), ", ".join(zone_names),
                    len(points), len(drops), int(bool(kb)), _pack_detail(detail), int(str(record["id"]) in service_ids),
                ),
            )
            con.executemany(
                "INSERT OR IGNORE INTO npc_zone VALUES (?,?,?)",
                ((str(record["id"]), map_id, str(zones.get(map_id, map_id))) for map_id in mapped_ids),
            )
            for location in kb.get("locations") or []:
                location_name = _text(location.get("name") or location.get("slug"))
                slug = _text(location.get("slug")).casefold()
                map_id = SITE_MAP_IDS.get(slug) or next((key for key, value in zones.items() if value == location_name), "kb:" + slug)
                if location_name:
                    con.execute("INSERT OR IGNORE INTO npc_zone VALUES (?,?,?)", (str(record["id"]), map_id, location_name))
                for point in location.get("points") or []:
                    region = _text((point.get("area") or {}).get("name"))
                    if region:
                        con.execute("INSERT OR IGNORE INTO npc_region VALUES (?,?,?)", (str(record["id"]), map_id, region))
        con.executemany("INSERT INTO item VALUES (?,?,?,?)", ((key, *value) for key, value in items.items()))
        con.executemany("INSERT INTO shared VALUES (?,?)", shared.items())
        areas = areas + [  # a record that takes its points from a donor takes the donor's areas too
            {**area, "npc_id": npc_id} for npc_id, donor_id in donors.items() for area in areas if str(area["npc_id"]) == donor_id
        ]
        area_rows = [
            (
                str(area["npc_id"]), str(area["map_id"]), str(area["area_id"]), int(area["point_count"]),
                float(area["center"][0]), float(area["center"][1]),
                json.dumps(area.get("area_names") or [], ensure_ascii=False, separators=(",", ":")),
                json.dumps(area.get("polygon") or [], separators=(",", ":")),
            )
            for area in areas
        ]
        con.executemany("INSERT OR REPLACE INTO npc_area VALUES (?,?,?,?,?,?,?,?)", area_rows)
        for area in areas:
            for name in area.get("area_names") or []:
                con.execute("INSERT OR IGNORE INTO npc_region VALUES (?,?,?)", (str(area["npc_id"]), str(area["map_id"]), name))
        con.executescript(
            """
            CREATE INDEX npc_filter ON npc(category, race, rank);
            CREATE INDEX npc_zone_map ON npc_zone(map_id, npc_id);
            CREATE INDEX npc_area_id ON npc_area(npc_id, map_id);
            CREATE INDEX npc_region_filter ON npc_region(map_id,name,npc_id);
            CREATE INDEX npc_service ON npc(service);
            CREATE INDEX npc_stock_npc ON npc_stock(npc_id);
            PRAGMA user_version=6;
            """
        )
        con.commit()
    except BaseException:
        con.close()
        temporary.unlink(missing_ok=True)
        raise
    con.execute("VACUUM")
    con.close()
    temporary.replace(output)
    return len(data["records"]), len(areas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "local/bestiary/npcs.json.gz")
    parser.add_argument("--areas", type=Path, default=ROOT / "local/bestiary/mob_areas.json.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "local/bestiary/npcs.sqlite")
    args = parser.parse_args()
    records, areas = build(args.source, args.areas, args.output)
    print(f"Built {args.output}: {records} NPC, {areas} areas, {args.output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
