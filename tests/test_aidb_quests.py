"""core/pulse_db/aidb_quests.py: a quest page of aidb.ru as a guide, and its place in pulse.db (map:46)."""

import json
import sqlite3
from pathlib import Path

from core.pulse_db.aidb_quests import parse_quest_page, read_guides
from core.pulse_db.build import Sources, build
from tests.test_pulse_db import game_sources

FIXTURE = Path(__file__).parent / "golden" / "aidb_quest_1001.html"  # a trimmed real page of /quests/1001-…


def test_a_quest_page_gives_the_facts_the_npcs_the_rewards_and_the_steps():
    guide = parse_quest_page(FIXTURE.read_text(encoding="utf-8"))
    assert (guide["icon"], guide["category"], guide["race"], guide["level"], guide["rec_level"], guide["repeat"]) == (
        "mission", "Миссии", "Элийцы", 2, 3, "1 раз")
    assert guide["name_en"] == "The Kerub Threat" and guide["notes"] == ["Нельзя разделить."]
    assert len(guide["classes"]) == 16 and guide["classes"][0] == "Воин"
    assert guide["zone"] == {"id": "210010000", "name": "Фоэта [Poeta]"}
    assert guide["giver"] == {"id": 203071, "name": "Муранес"} and guide["ender"] == {"id": 203053, "name": "Наемник"}
    assert guide["needs"] == [{"id": 182200001, "name": "Клык керубима", "count": 3}]
    assert guide["rewards"]["exp"] == 1000 and [i["id"] for i in guide["rewards"]["items"]] == [114100806, 114300816, 114500778]
    assert [s["text"] for s in guide["steps"]][:2] == ["Узнайте, что хочет сказать вам Муранес.", "Убейте монстра под названием Рогатый керубим (5)."]
    assert guide["steps"][1]["links"] == [{"kind": "npcs", "id": 210670, "name": "Рогатый керубим"}]
    assert guide["start"] == {"zone": "210010000", "x": 31.4, "y": 51.34}


def test_a_page_that_is_not_a_quest_gives_nothing():
    assert parse_quest_page("<html><body>404</body></html>") is None
    assert parse_quest_page("") is None


def test_the_folder_is_read_by_quest_id_and_the_guide_is_a_table_that_fills_missing_npcs(tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "1101.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")  # the fixture stands for quest 1101
    (pages / "7.html").write_text("<html>no</html>", encoding="utf-8")
    (pages / "9999.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")  # a quest the database does not have
    (pages / "notes.txt").write_text("x", encoding="utf-8")
    assert sorted(read_guides(pages)) == [1101, 9999]
    base = game_sources(tmp_path)
    out = tmp_path / "pulse.db"
    report = build(Sources(**{**base.__dict__, "aidb_pages": pages}), out)
    db = sqlite3.connect(out)
    row = db.execute("SELECT quest_id, icon, rec_level, zone_id, giver, giver_name, ender, source, steps FROM quest_guide").fetchall()
    assert [r[0] for r in row] == [1101]  # only the quests of the database
    assert row[0][1:8] == ("mission", 3, "210010000", None, "Муранес", None, "aidb.ru")  # NPC 203071 is unknown here: no false link
    assert len(json.loads(row[0][8])) == 5
    assert report["quest_guides"] == 1
    # a known NPC fills an empty giver, a given one is kept
    assert db.execute("SELECT giver FROM quest WHERE id = 1101").fetchone()[0] == "100"
