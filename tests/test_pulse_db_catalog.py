"""Checks for core/pulse_db/catalog.py and stage 5 of the build: the client's skills, skill books, stigmas, titles, pets and the
ten sections of «База данных» (map:45)."""

import json
import sqlite3

from core.pulse_db.build import SCHEMA_VERSION, Sources, build
from core.pulse_db.catalog import SECTIONS, read_client
from tests.test_pulse_db import game_sources


def catalog(path, icons):
    """A small export with the real tables of client_extract/fresh_catalog/catalog.sqlite."""
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE entries (section TEXT NOT NULL, id TEXT NOT NULL, internal_name TEXT, name_ru TEXT, description_ru TEXT,
          icon_key TEXT, icon_path TEXT, fields_json TEXT NOT NULL, source_pak TEXT NOT NULL, PRIMARY KEY(section, id));
        CREATE TABLE categories (category TEXT NOT NULL, section TEXT NOT NULL, id TEXT NOT NULL, PRIMARY KEY(category, section, id));
    """)
    rows = [
        ("skills", "11", "P_StatBoost_G1", "Укрепление I", "Навык книги", "icons/skills/p_statboost.png", {}),
        ("skills", "12", "Stigma_Heal_G2", "Исцеляющий свет II", None, "icons/skills/no_file.png", {}),
        ("items", "902", "skillbook_x", "Книга: укрепление", None, "icons/items/icon_item_skillbook_02.png",
         {"skill_to_learn": "p_statboost_g1", "fighter": "5", "mage": "0"}),  # the case differs from the skill's
        ("items", "907", "skillbook_lost", "", None, None, {"skill_to_learn": "No_Such_Skill"}),  # no Russian name: not listed
        ("items", "901", "item_stigma_heal_g2", "Исцеляющий свет II", None, None,
         {"gain_skill1": "Stigma_Heal_G2", "gain_level1": "9", "require_skill1": "Stigma_Missing", "require_skill1_lv": "2"}),
        ("titles", "1", "light_title01", "Хранитель Фоэты", "Все миссии выполнены.", None,
         {"title_race": "0", "title_priority": "4", "title_type": "0", "title_location": "STR_QUEST_ZONE01",
          "bonus_attrs": {"data": [{"bonus_attr": "maxHp 20"}]}}),
        ("titles", "2", "dark_title01", "", None, None, {"title_race": "1"}),
        ("pets", "900161", "Familiar_Cherubim", "Керубим", "Декоративный питомец.", "icons/pets/icon_familiar_cherubim_01.png",
         {"func_type1": "warehouse", "func_type_name1": "cash_warehouse"}),
    ]
    db.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?)",
                   [(s, i, n, ru, d, None, icon, json.dumps(f), "x.pak") for s, i, n, ru, d, icon, f in rows])
    db.executemany("INSERT INTO categories VALUES (?,?,?)", [("skill_books", "items", "902"), ("skill_books", "items", "907"),
                                                              ("stigmas", "items", "901"), ("stigma_skills", "skills", "12")])
    db.commit()
    db.close()
    (icons / "skills").mkdir(parents=True)
    (icons / "pets").mkdir()
    for rel in ("skills/p_statboost", "pets/icon_familiar_cherubim_01", "icon_item_skillbook_02"):
        (icons / f"{rel}.png").write_bytes(b"png")


def test_reads_skills_books_stigmas_titles_and_pets_without_guessing(tmp_path):
    icons = tmp_path / "icons"
    catalog(tmp_path / "catalog.sqlite", icons)
    client = read_client(tmp_path / "catalog.sqlite", icons)
    assert client["skill"] == [(11, "P_StatBoost_G1", "Укрепление I", "укрепление i", "Навык книги", "skills/p_statboost", 0),
                               (12, "Stigma_Heal_G2", "Исцеляющий свет II", "исцеляющий свет ii", None, None, 1)]  # no file: no picture
    assert client["skill_book"][0] == (902, "p_statboost_g1", 11, '{"fighter": 5}', 1)  # linked by name, any case
    assert client["skill_book"][1][:3] == (907, "No_Such_Skill", None)  # the client has no such skill: NULL, the name kept
    assert client["stigma"] == [(901, "Stigma_Heal_G2", 12, 9, '[["Stigma_Missing", null, 2]]', 1)]
    title = client["title"][0]
    assert title[:5] == (1, "Хранитель Фоэты", "хранитель фоэты", "Все миссии выполнены.", "pc_light")
    assert json.loads(title[5]) == {"bonus": ["maxHp 20"], "priority": 4, "type": 0, "location": "STR_QUEST_ZONE01"}
    assert client["pet"] == [(900161, "Familiar_Cherubim", "Керубим", "керубим", "Декоративный питомец.", '["warehouse"]',
                              "pets/icon_familiar_cherubim_01")]
    assert client["item_icon"][902] == "icon_item_skillbook_02" and client["item_icon"][907] is None


def test_no_export_gives_empty_tables(tmp_path):
    assert read_client(tmp_path / "missing.sqlite")["skill"] == []


def test_builds_the_ten_sections_with_their_rule_and_size(tmp_path):
    icons = tmp_path / "icons"
    catalog(tmp_path / "catalog.sqlite", icons)
    base = game_sources(tmp_path)
    out = tmp_path / "pulse.db"
    report = build(Sources(**{**base.__dict__, "client_catalog": tmp_path / "catalog.sqlite", "icons": icons}), out)
    db = sqlite3.connect(out)
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 8
    sections = db.execute("SELECT key, title, ord, entity, count FROM db_section ORDER BY ord").fetchall()
    assert [s[0] for s in sections] == [key for key, _, _ in SECTIONS]
    counts = {s[0]: s[4] for s in sections}
    entries = dict(db.execute("SELECT section, count(*) FROM db_section_entry GROUP BY section").fetchall())
    assert {k: v for k, v in counts.items() if v} == entries  # the size is the ids' count
    assert counts["skill_books"] == 1 and counts["stigmas"] == 1  # 907 has no Russian name
    assert counts["titles"] == 1 and counts["pets"] == 1  # the unnamed title is kept in the table, not listed
    assert db.execute("SELECT count(*) FROM title").fetchone()[0] == 2
    assert db.execute("SELECT value FROM meta WHERE key = 'title'").fetchone()[0] == "client"
    assert db.execute("SELECT skill_id FROM skill_book WHERE item_id = 902").fetchone()[0] == 11
    # every link points to a row: the books' and stigmas' skills, the sections' items
    assert db.execute("SELECT count(*) FROM skill_book b LEFT JOIN skill s ON s.id = b.skill_id "
                      "WHERE b.skill_id IS NOT NULL AND s.id IS NULL").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM db_section_entry e JOIN db_section s ON s.key = e.section "
                      "LEFT JOIN item i ON i.id = e.entity_id WHERE s.entity = 'item' AND i.id IS NULL").fetchone()[0] == 0
    # the client's picture where the item has none
    assert db.execute("SELECT icon FROM item WHERE id = 902").fetchone()[0] == "icon_item_skillbook_02"
    assert report["sections"]["items"] == db.execute("SELECT count(*) FROM item").fetchone()[0]
