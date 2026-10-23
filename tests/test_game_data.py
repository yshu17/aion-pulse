"""The game data core: the exported tables become sections; links, unknown values and repeatability are checked."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from core.game_data.build import BuildError, Sources, build_all
from core.game_data.layout import SECTION_FILES
from core.game_data.store import GameData
from core.game_data.tables import read_pairs, read_tsv


def write(path: Path, header: str, *rows: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def src(tmp_path: Path) -> Sources:
    t = tmp_path / "in"
    return Sources(
        items=write(t / "items.tsv", "item_id\tinternal_name\titem_type\tweapon_type\tarmor_type\titem_level\tclient_price\ticon_name\tsource",
                    "100000002\tpick\tnormal\t1h_sword\t\t1\t5\tIcon_A\tclient", "100000001\tsword\tnormal\t1h_sword\t\t3\t\tIcon_B\tclient",
                    "152000901\therb\tnormal\t\t\t1\t2\tIcon_C\tclient"),
        item_names=write(t / "item_names.tsv", "item_id\tname_ru\tsource", "100000001\tМеч\tclient", "152000901\tТрава\tclient"),
        legacy_item_names=t / "legacy.tsv",
        legacy_watch_items=t / "watch.csv",
        recipes=write(t / "recipes.tsv", "recipe_id\tproduct_item_id\tproduct_count\tprofession\tlevel\trace\tsource", "155000002\t100000001\t1\tarms\t5\tpc_light\tclient",
                      "155000001\t100000002\t3\tconvert\t1\tall\tclient"),
        recipe_ingredients=write(t / "ing.tsv", "recipe_id\tposition\titem_id\tcount\tsource", "155000002\t2\t152000901\t4\tclient", "155000002\t1\t100000001\t1\tclient",
                                 "155000001\t1\t999\t1\tclient"),  # 999 is not an item
        recipe_names=write(t / "rn.tsv", "recipe_id\tname_ru", "155000001\tКирка"),
        npcs=write(t / "npcs.tsv", "npc_id\tinternal_name\tfunction_type\tui_type\tai_name\ttribe\trace_type\tsource", "203060\ttrader\ttrade\tgeneral\t\tGeneral\t\tclient",
                   "210065\tgoblin\t\tgeneral\t\tGoblin\t\tclient"),
        npc_names=write(t / "nn.tsv", "npc_id\tname_ru", "203060\tТорговец"),
        maps=write(t / "maps.tsv", "map_id\tfile\tsize\tside\tsource", "110010000\tclient/lc1.jpg\t1232\tlight\tclient"),
        map_names=write(t / "mn.tsv", "map_id\tname_ru", "110010000\tЭлизиум"),
        location_labels=write(t / "ll.tsv", "map_id\tstring_key\tdisplay_level\tgame_x\tgame_y\tgame_z\tsource", "110010000\tSTR_A\tmain\t1872.5\t1511.25\t813\tclient"),
        location_names=write(t / "ln.tsv", "string_key\tname_ru", "STR_A\tРайон"),
        npc_locations=write(t / "np.tsv", "map_id\tnpc_id\tgame_x\tgame_y\tgame_z\tzone\tsource", "110010000\t203060\t1\t2\t3\tlc1\tclient",
                            "110010000\t777\t1\t2\t3\tlc1\tclient"),  # 777 is not an NPC
        vendors=write(t / "v.tsv", "npc_id\titem_id\tprice\tcurrency\tlimit\ttrade_kind\tsource", "203060\t152000901\t\t\t\ttrade_info\tclient"),
        quest_info=write(t / "qi.tsv", "quest_id\tname_ru\tstart_npc_id\tend_npc_id\tmin_level\tmax_level\trace\tcategory\trepeatable", "85\tСимвол\t\t\t99\t0\tpc_light pc_dark\tquest | Тест\tno",
                         "1000\tВступление\t\t\t1\t0\tpc_light\tquest | Фоэта\tyes"),
        quest_npcs=write(t / "qn.tsv", "quest_id\tgiver_npc_id\tender_npc_id\tsource", "85\t203060\t\tclient", "1000\t\t\tclient"),
        quest_rewards=write(t / "qr.tsv", "quest_id\treward_type\tgroup\titem_id\tamount\tsource", "85\texp\tg1\t\t100\tclient", "85\titem\tg2\t100000001\t2\tclient"),
        quest_names=write(t / "qnm.tsv", "quest_id\tname_ru", "85\tСимвол избранного"),
        skills=write(t / "sk.tsv", "id\tclass\tlevel\tkind\tmp\tcooldown_ms\tcast_ms\trange\trequires\tsource", '1\t"[""SCOUT"", ""WARRIOR""]"\t1\tPassive\t\t\t\t\t\tclient', "2\t\t\tActive\t10\t5000\t\t1.5\t\tclient"),
        skill_names=write(t / "skn.tsv", "id\tname_ru", "1\tМеч: теория"),
        skill_learns=write(t / "sl.tsv", "learn_id\tskill_name\tclass\trace\tlevel\tstigma_display\tsource", "1\tP_X\tWARRIOR\tAll\t1\t0\tclient"),
        stigmas=write(t / "st.tsv", "record_type\tskill_id\tclass\tlevel\tslot_number\tactive_rank\trank_max\trequires\tsource", "slot\t\tassassin\t\t1\t1\t1\t\tclient"),
        classes=write(t / "cl.tsv", "class\trace\tlevel\tbase_stats\tper_level\tsource", "ASSASSIN\tPC_DARK\t\t\t\tclient", "ASSASSIN\tPC_LIGHT\t\t\t\tclient"),
        class_names=write(t / "cln.tsv", "class\tname_ru", "ASSASSIN\tУбийца"),
        drops=write(t / "d.tsv", "npc_id\titem_id\tchance_min\tchance_max\tcount_min\tcount_max\tsource", "210065\t100000001\t\t\t\t\tsite", "210065\t152000901\t0.5\t0.7\t1\t2\tsite",
                    "203060\t100000001\t\t\t\t\tsite", "210065\t100000001\t\t\t\t\tsite"),  # a repeated pair
    )


def sha(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_reads_empty_cells_as_unknown_and_missing_files_as_empty_tables(tmp_path):
    table = write(tmp_path / "a.tsv", "id\tname", "1\t", "2\tx")
    assert read_tsv(table) == [{"id": "1", "name": None}, {"id": "2", "name": "x"}]
    assert read_tsv(tmp_path / "nope.tsv") == [] and read_tsv(None) == []
    (tmp_path / "p.tsv").write_text("100\tМеч\n\ttext\nabc\tx\n", encoding="utf-8")
    assert read_pairs(tmp_path / "p.tsv") == {"100": "Меч"}


def test_items_are_sorted_by_id_and_unknown_stays_unknown(src, tmp_path):
    build_all(src, tmp_path / "out")
    data = GameData(tmp_path / "out")
    records = data.records("items")
    assert [r["id"] for r in records] == ["100000001", "100000002", "152000901"]  # numbers as numbers
    sword, pick = records[0], records[1]
    assert (sword["name"], sword["level"], sword["price"], sword["armor"]) == ("Меч", 3, None, None)
    assert pick["name"] is None  # no name anywhere: unknown, not an empty string
    assert data.by_id("items")["152000901"]["icon"] == "Icon_C"


def test_a_name_the_client_lacks_comes_from_the_legacy_file_and_says_so(src, tmp_path):
    (tmp_path / "in" / "legacy.tsv").write_text("100000002\tКирка гоблинов\n", encoding="utf-8")
    (tmp_path / "in" / "watch.csv").write_text("id,name,level,category,grade,icon,kind\n100000001,Меч,3,Оружие,epic,Icon_B,Меч\n", encoding="utf-8")
    report = build_all(src, tmp_path / "out")
    items = GameData(tmp_path / "out").by_id("items")
    assert items["100000002"]["name"] == "Кирка гоблинов" and items["100000002"]["name_source"] == "legacy"
    assert "name_source" not in items["100000001"]  # a client name carries no mark
    assert (items["100000001"]["category"], items["100000001"]["grade"]) == ("Оружие", "epic")
    assert report["items_with_legacy_name"] == 1 and report["items_without_name"] == 0


def test_recipes_keep_the_order_of_their_ingredients(src, tmp_path):
    build_all(src, tmp_path / "out")
    recipe = GameData(tmp_path / "out").by_id("recipes")["155000002"]
    assert recipe["ingredients"] == [["100000001", 1], ["152000901", 4]] and recipe["combo"] is None and recipe["name"] is None


def test_quests_join_levels_npcs_and_rewards(src, tmp_path):
    build_all(src, tmp_path / "out")
    quests = GameData(tmp_path / "out").by_id("quests")
    first = quests["85"]
    assert (first["name"], first["min_level"], first["race"], first["giver"], first["ender"]) == ("Символ избранного", 99, ["pc_light", "pc_dark"], "203060", None)
    assert first["rewards"] == [{"type": "exp", "group": "g1", "item": None, "amount": 100}, {"type": "item", "group": "g2", "item": "100000001", "amount": 2}]
    assert quests["1000"]["repeatable"] is True and quests["1000"]["rewards"] == [] and quests["1000"]["giver"] is None


def test_skills_classes_and_big_tables(src, tmp_path):
    build_all(src, tmp_path / "out")
    data = GameData(tmp_path / "out")
    skills = data.section("skills")
    assert skills["skills"][0]["classes"] == ["SCOUT", "WARRIOR"] and skills["skills"][1]["classes"] is None
    assert skills["skills"][1]["range"] == 1.5 and skills["learns"][0]["skill"] == "P_X"
    classes = data.by_id("classes")
    assert classes["ASSASSIN.PC_DARK"]["base_stats"] is None and classes["ASSASSIN.PC_DARK"]["name"] == "Убийца"
    columns, rows = data.table("vendors")
    assert columns == ["npc", "item", "price", "currency", "limit", "kind"] and rows == [["203060", "152000901", None, None, None, "trade_info"]]
    assert data.table("labels")[1] == [["110010000", "STR_A", "main", 1872.5, 1511.25, 813.0, "Район"]]


def test_drops_are_in_sqlite_by_npc_and_by_item(src, tmp_path):
    report = build_all(src, tmp_path / "out")
    data = GameData(tmp_path / "out")
    assert report["drops"] == {"records": 3, "duplicates": 1, "missing_inputs": []}  # the repeated pair is counted once
    assert data.drops_of_npc("210065") == [
        {"item_id": 100000001, "chance_min": None, "chance_max": None, "count_min": None, "count_max": None},
        {"item_id": 152000901, "chance_min": 0.5, "chance_max": 0.7, "count_min": 1, "count_max": 2}]
    assert [row["npc_id"] for row in data.droppers_of("100000001")] == [203060, 210065]
    assert data.drops_of_npc("1") == [] and data.drops_of_npc("abc") == []
    data.close()


def test_broken_links_are_counted_and_a_strict_build_stops_without_writing(src, tmp_path):
    report = build_all(src, tmp_path / "out")
    assert report["ok"] is False
    assert report["broken_links"]["recipes.ingredient -> items"] == {"count": 1, "samples": ["999"]}
    assert report["broken_links"]["npc_points.npc -> npcs"] == {"count": 1, "samples": ["777"]}
    assert not [kind for kind in report["broken_links"] if kind.startswith("drops.")]  # the drops of the fixture point at real IDs
    with pytest.raises(BuildError) as error:
        build_all(src, tmp_path / "strict", strict=True)
    assert error.value.args[0]["ok"] is False and not (tmp_path / "strict").exists()


def test_the_same_input_gives_the_same_bytes(src, tmp_path):
    build_all(src, tmp_path / "a", built="2026-10-23")
    build_all(src, tmp_path / "b", built="2026-10-23")
    assert sha(tmp_path / "a") == sha(tmp_path / "b")
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 1 and manifest["built"] == "2026-10-23" and set(SECTION_FILES) <= set(manifest["sections"])
    assert manifest["sections"]["items"]["records"] == 3 and manifest["sections"]["drops"]["records"] == 3
    assert manifest["sections"]["items"]["sha256"] == hashlib.sha256((tmp_path / "a" / "items.json.gz").read_bytes()).hexdigest()
    assert gzip.decompress((tmp_path / "a" / "items.json.gz").read_bytes()).startswith(b'{"schema":1,"section":"items"')


def test_a_missing_source_builds_an_empty_section_and_is_named(tmp_path):
    report = build_all(Sources(), tmp_path / "out")
    assert report["sections"]["items"] == {"records": 0, "missing_inputs": ["items", "item_names"]}
    assert report["drops"]["missing_inputs"] == ["drops"] and report["ok"] is True
    data = GameData(tmp_path / "out")
    assert data.usable and data.records("items") == [] and data.drops_of_npc("1") == []


def test_a_missing_or_broken_folder_reads_as_empty(tmp_path):
    data = GameData(tmp_path / "nothing")
    assert not data.usable and data.records("items") == [] and data.by_id("npcs") == {} and data.table("vendors") == ([], [])
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "manifest.json").write_text("not json", encoding="utf-8")
    (tmp_path / "bad" / "items.json.gz").write_bytes(b"not gzip")
    assert GameData(tmp_path / "bad").records("items") == []


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT / "client_extract" / "items" / "items.tsv").is_file(), reason="the client exports are not on this computer")
def test_the_real_exports_build_into_the_agreed_counts(tmp_path):
    """The numbers of the Codex export (23.10.2026); the links of the client data have one known gap: quest givers."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_game_data", ROOT / "tools" / "build_game_data.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    report = build_all(tool.project_sources(ROOT), tmp_path / "game")
    counts = {name: info["records"] for name, info in report["sections"].items()}
    assert counts == {"items": 62490, "recipes": 7671, "npcs": 30397, "maps": 20, "labels": 620, "npc_points": 43621, "vendors": 41516,
                      "quests": 4643, "skills": 7560, "stigmas": 617, "classes": 24}
    assert report["drops"]["records"] == 1441972 and report["items_without_name"] == 73
    assert set(report["broken_links"]) <= {"quests.giver -> npcs"} and report["broken_links"].get("quests.giver -> npcs", {"count": 0})["count"] <= 39
    data = GameData(tmp_path / "game")
    assert data.by_id("items")["100000001"]["name"] == "Меч Циркулоса"
    assert data.drops_of_npc("210065")  # a goblin drops something
