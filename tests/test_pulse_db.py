"""Checks for core/pulse_db: one game database (data/pulse.db) built from the map's, the game data's and the bestiary's files."""

import gzip
import json
import shutil
import sqlite3
import zlib
from pathlib import Path

from core.bestiary.bestiary_store import DETAIL_DICT
from core.pulse_db.build import SCHEMA_VERSION, Sources, build, pack_ids, unpack_ids, unpack_spec

FIXTURE = Path(__file__).parent / "golden" / "bestiary_fixture.sqlite"  # a small real bestiary (15 NPCs, drops, goods, areas)


def pack(detail: dict) -> bytes:
    packer = zlib.compressobj(zdict=DETAIL_DICT)
    return packer.compress(json.dumps(detail, ensure_ascii=False).encode("utf-8")) + packer.flush()


def sources(tmp_path) -> Sources:
    spawns = {
        "names": {"100": "Лесной руфиллин", "poi:Теграк": "Теграк", "300": "Житель"},
        "zones": {"220050000": [["100", 653.2, 1692.4, 10.0], ["100", 700.0, 1700.0, 10.0]],
                  "220070000": [["poi:Теграк", 1769.1, 1765.7, 0.0], ["300", 5.0, 6.0, 0.0]]},
        "sp_only": ["100"], "deco": ["300"],
    }
    (tmp_path / "spawns.json").write_text(json.dumps(spawns, ensure_ascii=False), encoding="utf-8")
    points = {"schema": 1, "section": "npc_points", "columns": ["map", "npc", "x", "y", "z", "zone"],
              "rows": [["220050000", "100", 653.0, 1692.0, 10.0, "x"],  # the same place as the map's: one point
                       ["220050000", "100", 900.0, 900.0, 10.0, "x"]]}
    with gzip.open(tmp_path / "npc_points.json.gz", "wt", encoding="utf-8") as out:
        json.dump(points, out)
    npcs = {"schema": 1, "section": "npcs", "records": [
        {"id": "100", "name": "Лесной руфиллин", "function": None, "ui": "general", "tribe": "Beast", "race": None, "source": "client"},
        {"id": "400", "name": "Ёжик", "function": "Merchant", "ui": "general", "tribe": "General", "race": "pc_light", "source": "client"},
    ]}
    with gzip.open(tmp_path / "npcs.json.gz", "wt", encoding="utf-8") as out:
        json.dump(npcs, out)
    shutil.copy(FIXTURE, tmp_path / "bestiary.sqlite")  # the real schema; two NPCs of the test are added to it
    db = sqlite3.connect(tmp_path / "bestiary.sqlite")
    rows = [
        ("100", "Лесной руфиллин", "лесной руфиллин 100", "monster", "", "Монстр", "Зверь", "Другие", "Обычный", "49", "npc/a.jpg", "", 1, 0, 1,
         pack({"id": "100", "name": "Лесной руфиллин", "points": [{"map_id": "220050000", "gx": 1000.0, "gy": 1000.0, "gz": 1.0}]}), 0),
        ("799323", "Теграк", "теграк 799323", "npc", "", "Стражник", "Асмодианин", "Асмодиане", "Легендарный", "60", "", "", 0, 0, 1,
         pack({"id": "799323", "name": "Теграк", "points": []}), 0),
    ]
    db.executemany("INSERT INTO npc (id, name, search_text, category, role, kind, race, faction, rank, level, icon_asset, zone_names, "
                   "point_count, drop_count, has_profile, detail, service) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    db.commit()
    db.close()
    return Sources(spawns=tmp_path / "spawns.json", npc_points=tmp_path / "npc_points.json.gz", npcs=tmp_path / "npcs.json.gz",
                   bestiary=tmp_path / "bestiary.sqlite")


def test_builds_one_npc_table_from_every_source(tmp_path):
    out = tmp_path / "pulse.db"
    report = build(sources(tmp_path), out)
    db = sqlite3.connect(out)
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    rows = {r[0]: r for r in db.execute("SELECT id, name, name_key, rank, level, deco, sp_only, role, source FROM npc")}
    assert rows["100"][1:7] == ("Лесной руфиллин", "лесной руфиллин", "Обычный", 49, 0, 1)  # the bestiary's fields, the map's flags
    assert rows["300"][5] == 1  # decorative, known only by the map
    assert rows["400"][2] == "ежик" and rows["400"][7] == "merchant"  # «ё» folded; the client's function as the role
    assert rows["poi:Теграк"][8] == "map"
    assert report["npcs"] == len(rows)


def test_merges_the_three_point_sets_without_doubles(tmp_path):
    out = tmp_path / "pulse.db"
    report = build(sources(tmp_path), out)
    db = sqlite3.connect(out)
    points = db.execute("SELECT x, y, source FROM npc_point WHERE npc_id = '100' ORDER BY x").fetchall()
    # the map's two, the game data's new one (the other is the map's place to a unit), the bestiary's own
    assert points == [(653.2, 1692.4, "map"), (700.0, 1700.0, "map"), (900.0, 900.0, "client"), (1000.0, 1000.0, "bestiary")]
    assert report["points"] == db.execute("SELECT count(*) FROM npc_point").fetchone()[0]
    orphans = db.execute("SELECT count(*) FROM npc_point WHERE npc_id NOT IN (SELECT id FROM npc)").fetchone()[0]
    assert orphans == 0


def test_links_a_map_marker_to_the_npc_of_its_name(tmp_path):
    out = tmp_path / "pulse.db"
    build(sources(tmp_path), out)
    db = sqlite3.connect(out)
    assert db.execute("SELECT npc_id FROM npc_alias WHERE alias = 'poi:Теграк'").fetchall() == [("799323",)]
    # the bestiary's Теграк has no point of its own; through the alias it has the map's one
    points = db.execute("SELECT map_id, x, y FROM npc_point WHERE npc_id = ?1 OR npc_id IN (SELECT alias FROM npc_alias WHERE npc_id = ?1)",
                        ("799323",)).fetchall()
    assert points == [("220070000", 1769.1, 1765.7)]


def test_same_input_gives_the_same_database_rows(tmp_path):
    first, second = tmp_path / "a.db", tmp_path / "b.db"
    src = sources(tmp_path)
    build(src, first)
    build(src, second)
    dump = lambda path: list(sqlite3.connect(path).iterdump())  # noqa: E731
    assert dump(first) == dump(second)


def test_holds_the_bestiary_cards_as_tables_goods_drops_and_areas(tmp_path):
    out = tmp_path / "pulse.db"
    build(sources(tmp_path), out)
    db = sqlite3.connect(out)
    db.row_factory = sqlite3.Row
    fixture = sqlite3.connect(FIXTURE)
    listed = db.execute("SELECT count(*) FROM npc WHERE listed = 1").fetchone()[0]
    assert listed == fixture.execute("SELECT count(*) FROM npc").fetchone()[0] + 2  # every bestiary record, the client-only ones not
    ids = unpack_ids(db.execute("SELECT drops FROM npc WHERE id = '210065'").fetchone()[0])
    drops = [db.execute("SELECT name, grade FROM item WHERE id = ?", (i,)).fetchone() for i in ids]
    assert len(drops) == 2 and drops[0]["grade"] == "junk"
    assert 210065 in unpack_ids(db.execute("SELECT dropped_by FROM item WHERE id = ?", (ids[0],)).fetchone()[0], delta=True)
    goods = db.execute("SELECT name, grp FROM npc_stock WHERE npc_id = '220000' ORDER BY ord").fetchall()
    assert len(goods) == 3 and goods[0]["grp"]
    row = db.execute("SELECT category, sort_key, drop_count, profile FROM npc WHERE id = '210065'").fetchone()
    assert row["category"] == "monster" and row["drop_count"] == 2 and row["sort_key"] == row["sort_key"].casefold()
    assert isinstance(json.loads(row["profile"]), dict)
    areas = fixture.execute("SELECT count(*) FROM npc_area").fetchone()[0]
    assert db.execute("SELECT count(*) FROM npc_area").fetchone()[0] == areas
    # the point count of the list is the one table's: the bestiary's own point and the map's two of NPC 100
    assert db.execute("SELECT point_count FROM npc WHERE id = '100'").fetchone()[0] == 4
    assert db.execute("SELECT point_count FROM npc WHERE id = '799323'").fetchone()[0] == 1  # through the map's marker


def item_sources(tmp_path) -> Sources:
    """The bestiary's sources and the three item files: chat link names, the catalog of item cards, their descriptions."""
    base = sources(tmp_path)
    # ids clear of the bestiary fixture's items (1-5)
    (tmp_path / "item_names.tsv").write_text("901\tСтарое имя\n902\tЗелье жизни\n907\tТолько в ссылках\nmeta\tне id\n", encoding="utf-8")
    (tmp_path / "watch_items.csv").write_text(
        "﻿id,name,level,category,grade,icon,kind\n"
        "902,Зелье жизни,1,Припасы,common,icon_item_potion,\n"
        "901,\"Меч, древний\",55,Оружие,unique,icon_item_sword,Меч\n", encoding="utf-8")
    with gzip.open(tmp_path / "item_specs.json.gz", "wt", encoding="utf-8") as out:
        json.dump({"901": {"name": "Меч, древний", "grade": "unique", "blocks": [{"kind": "hr"}]},
                   "902": json.dumps({"name": "Зелье жизни", "grade": "common", "blocks": []})}, out)  # values may be JSON text
    return Sources(spawns=base.spawns, npc_points=base.npc_points, npcs=base.npcs, bestiary=base.bestiary,
                   item_names=tmp_path / "item_names.tsv", catalog=tmp_path / "watch_items.csv", specs=tmp_path / "item_specs.json.gz")


def test_holds_every_item_once_names_cards_and_descriptions(tmp_path):
    out = tmp_path / "pulse.db"
    report = build(item_sources(tmp_path), out)
    db = sqlite3.connect(out)
    db.row_factory = sqlite3.Row
    rows = {r["id"]: r for r in db.execute("SELECT * FROM item")}
    # the catalog's fields win over the older name list; its order is kept for the «Что искать» list
    assert dict(rows[901]) | {"spec": None, "dropped_by": None} == {
        "id": 901, "name": "Меч, древний", "name_key": "меч, древний", "level": 55, "category": "Оружие", "grade": "unique",
        "kind": "Меч", "icon": "icon_item_sword", "drop_icon": None, "catalog_ord": 1, "spec": None, "dropped_by": None}
    dictionary = db.execute("SELECT value FROM meta WHERE key = 'spec_dict'").fetchone()[0]  # the descriptions are deflated with it
    assert unpack_spec(rows[901]["spec"], dictionary)["blocks"] == [{"kind": "hr"}]
    assert unpack_spec(rows[902]["spec"], dictionary)["name"] == "Зелье жизни"
    assert rows[902]["catalog_ord"] == 0
    assert (rows[907]["name"], rows[907]["catalog_ord"], rows[907]["spec"]) == ("Только в ссылках", None, None)  # a chat link's name only
    # the bestiary's drops are the same rows: its picture and grade where the catalog has none
    drop = db.execute("SELECT grade, drop_icon, dropped_by FROM item WHERE dropped_by IS NOT NULL LIMIT 1").fetchone()
    assert drop["grade"] and drop["drop_icon"]
    assert report["catalog"] == 2 and report["items"] == len(rows)


def test_packs_id_lists_both_ways():
    assert pack_ids([166000103]).hex() == "e7eb934f"
    assert unpack_ids(pack_ids([100, 105, 106], delta=True), delta=True) == [100, 105, 106]
    assert unpack_ids(pack_ids([5, 1, 300])) == [5, 1, 300]  # the card's order kept
    assert unpack_ids(None) == []
