"""The sections «Оружие», «Броня», «Украшения» hold the client's low-level and variant equipment too, not only the old site catalog's
(level 45 and up): an item the catalog never had gets its category and type from the client's own group (core/pulse_db/gear.py)."""

import gzip
import json
import sqlite3

from core.pulse_db.build import Sources, build
from core.pulse_db.gear import category_of, fill_categories
from tests.test_pulse_db import item_sources


def test_a_group_gives_the_category_and_type_the_site_catalog_uses():
    assert category_of("sword") == ("Оружие", "Меч")
    assert category_of("greatsword") == ("Оружие", "Двуручный меч")
    assert category_of("spellbook") == ("Оружие", "Гримуар")
    assert category_of("orb") == ("Оружие", "Орб")
    assert category_of("rb_torso") == ("Ткань", None)
    assert category_of("lt_shoes") == ("Кожа", None)
    assert category_of("ch_glove") == ("Кольчуга", None)
    assert category_of("pl_shoulder") == ("Лата", None)
    assert category_of("ring") == ("Украшения", "Кольца")
    assert category_of("earring") == ("Украшения", "Серьги")
    assert category_of("necklace") == ("Украшения", "Ожерелья")
    assert category_of("belt") == ("Украшения", "Пояса")
    assert category_of("shield") == ("Щиты", None)
    assert category_of("head") == ("Головные уборы", None)
    assert category_of("wing") == ("Крылья", None)
    assert category_of("unknown") is None


def row(item_id, group):
    return (item_id, "Предмет", None, "common", 10, "main", group, "", "[]", "{}", "[]", None, None, 1)


def test_only_an_item_without_a_category_is_filled_and_the_catalogs_own_wins():
    items = {1: {"category": None, "kind": None}, 2: {"category": "Оружие", "kind": "Меч"}, 3: {"category": "", "kind": ""}}
    filled = fill_categories(items, [row(1, "sword"), row(2, "dagger"), row(3, "rb_torso"), row(4, "sword")])  # 4 is no known item
    assert filled == 2
    assert (items[1]["category"], items[1]["kind"]) == ("Оружие", "Меч")
    assert (items[2]["category"], items[2]["kind"]) == ("Оружие", "Меч")  # the catalog keeps its own
    assert (items[3]["category"], items[3]["kind"]) == ("Ткань", None)


def test_the_sections_list_low_level_equipment_and_its_level_range_finds_it(tmp_path):
    base = item_sources(tmp_path)  # the catalog: 901 «Меч, древний» level 55 (Оружие), 902 «Зелье жизни» (Припасы)
    with gzip.open(tmp_path / "items.json.gz", "wt", encoding="utf-8") as out:
        json.dump({"schema": 1, "section": "items", "records": [
            {"id": "950", "name": "Меч стражника", "level": 10, "grade": "common"},
            {"id": "951", "name": "Кожаная куртка", "level": 11, "grade": "common"},
            {"id": "952", "name": "Кольцо новичка", "level": 12, "grade": "common"},
            {"id": "953", "name": "Тестовый меч", "level": 10, "grade": "common"}]}, out, ensure_ascii=False)
    catalog = sqlite3.connect(tmp_path / "catalog.sqlite")
    catalog.executescript("""CREATE TABLE entries (section TEXT NOT NULL, id TEXT NOT NULL, internal_name TEXT, name_ru TEXT,
        description_ru TEXT, icon_key TEXT, icon_path TEXT, fields_json TEXT NOT NULL, source_pak TEXT NOT NULL, PRIMARY KEY(section, id));""")
    rows = [("950", "Меч стражника", {"weapon_type": "1h_sword", "equipment_slots": "main_or_sub", "quality": "common", "level": "10"}),
            ("951", "Кожаная куртка", {"armor_type": "leather", "equipment_slots": "torso", "quality": "common", "level": "11"}),
            ("952", "Кольцо новичка", {"equipment_slots": "right_or_left_finger", "quality": "common", "level": "12"}),
            ("953", "Тестовый меч", {"weapon_type": "1h_sword", "equipment_slots": "main_or_sub", "quality": "common", "level": "10"})]
    catalog.executemany("INSERT INTO entries VALUES ('items', ?, ?, ?, NULL, NULL, NULL, ?, 'x.pak')", [(i, n.lower(), n, json.dumps(f)) for i, n, f in rows])
    catalog.commit()
    catalog.close()
    out = tmp_path / "pulse.db"
    build(Sources(**{**base.__dict__, "items": tmp_path / "items.json.gz", "client_catalog": tmp_path / "catalog.sqlite"}), out)
    db = sqlite3.connect(out)
    section = lambda key: {r[0] for r in db.execute("SELECT entity_id FROM db_section_entry WHERE section = ?", (key,))}
    assert 950 in section("weapons") and 951 in section("armour") and 952 in section("jewels")
    assert 953 not in section("weapons")  # a test item is never listed
    assert 901 in section("weapons")  # the catalog's own rows stay
    assert db.execute("SELECT category, kind FROM item WHERE id = 950").fetchone() == ("Оружие", "Меч")
    assert db.execute("SELECT category, kind FROM item WHERE id = 951").fetchone() == ("Кожа", None)
    assert db.execute("SELECT category, kind FROM item WHERE id = 952").fetchone() == ("Украшения", "Кольца")
    # the level range of the sections: 10 to 12 finds the three, and the «Что искать» list (catalog_ord) did not grow
    for key, expected in (("weapons", 950), ("armour", 951), ("jewels", 952)):
        found = db.execute("SELECT t.id FROM db_section_entry e JOIN item t ON t.id = e.entity_id WHERE e.section = ? AND t.level BETWEEN 10 AND 12",
                           (key,)).fetchall()
        assert found == [(expected,)], key
    assert db.execute("SELECT count(*) FROM item WHERE id IN (950, 951, 952) AND catalog_ord IS NOT NULL").fetchone()[0] == 0
