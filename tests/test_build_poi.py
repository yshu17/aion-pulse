import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import build_poi  # noqa: E402


def obj(object_type="SP", name="", function="", ru="", map_id="220070000", x="10.5", y="20.25"):
    return {
        "map_id": map_id, "object_type": object_type, "object_name": name, "function_type": function,
        "npc_russian_name": ru, "npc_internal_name": "", "game_x": "100.0", "game_y": "200.0",
        "image_x": x, "image_y": y,
    }


def test_gather_kind():
    assert build_poi.gather_kind("HSPDF1_Alder_herb2") == "herb"
    assert build_poi.gather_kind("HSPDF1_x_vege3") == "vegetable"
    assert build_poi.gather_kind("HSPDF4_y_noblemetal12") == "noblemetal"
    assert build_poi.gather_kind("HSP_odd_a") == "other"
    assert build_poi.gather_kind("HSPDF4A_Harvest noblemetal_3b1") == "noblemetal"
    assert build_poi.gather_kind("HSPDF2_B1_Harvest_Metal_B3") == "metal"
    assert build_poi.gather_kind("HSPLF4_Harvest_C_2_400OD1") == "aether"
    assert build_poi.gather_kind("HSPDF2_Harvest_Crack_C1_od_A1") == "aether"
    assert build_poi.gather_kind("HSPDF4_Harvest_Munihelr2") == "other"


def test_classify_object():
    c = build_poi.classify_object
    assert c(obj(function="Teleport")) == "teleport"
    assert c(obj(function="Coin_merchant")) == "coin_merchant"
    assert c(obj(function="vendor")) == "vendor"
    assert c(obj(function="Stigma_master")) == "stigma"
    assert c(obj("Portal", "PortalVisArea_OP8")) is None  # CryEngine visibility portals, not the game's
    assert c(obj("DP", "DPDf1_DirectPortal3")) == "direct_portal"
    assert c(obj("HSP", "HSPDF1_Alder_herb2")) == "gather_herb"
    assert c(obj("KP", "DF1_KeyPoints_Alder_3")) is None  # mission key points: not the quest givers
    assert c(obj("MP", "Mappiont_DC1_SUB_C")) is None
    assert c(obj("SP")) is None  # plain monster spawns are not a layer
    assert c(obj(function="Unknown_role")) is None


def test_build_keeps_calibrated_zones_and_rounds(tmp_path):
    rows = [
        obj("HSP", "HSPDF4_a_herb1", x="1686.054", y="793.149"),
        obj("HSP", "HSPDF4_a_herb2", map_id="210020000"),  # zone without a map
        obj("HSP", "HSPDF4_a_herb3", x="", y=""),  # no pixels
    ]
    entities = [{"map_id": "220070000", "entity_class": "AbyssArtifacts", "name": f"Artifact_30111_1_1_{side}",
                 "game_x": "1", "game_y": "2", "image_x": "3", "image_y": "4"} for side in ("Li", "Da", "Dr")]
    data = build_poi.build(rows, entities, {"220070000", "210050000"}, gather=True)  # one artifact for 3 sides
    points = data["zones"]["220070000"]
    assert {p["t"] for p in points} == {"gather_herb", "artifact"} and len(points) == 2
    herb = next(p for p in points if p["t"] == "gather_herb")
    assert herb == {"t": "gather_herb", "x": 1686.1, "y": 793.1, "gx": 100.0, "gy": 200.0, "name": ""}
    assert "210020000" not in data["zones"]
    assert data["types"]["gather_herb"]["name"] == "Травы"  # no icon file while gathering is off
    assert data["types"]["artifact"] == {"group": "landmark", "name": "Артефакт", "icon": "artifact.png"}
    json.dumps(data)  # serialisable
    plain = build_poi.build(rows, entities, {"220070000", "210050000"})  # gathering is off in the program
    assert [p["t"] for p in plain["zones"]["220070000"]] == ["artifact"] and "gather_herb" not in plain["types"]


def test_functional_npcs_only_from_the_world_xml_and_neighbours_kept():
    rows = [obj(function="Teleport", ru="Раниу из миссии"), obj("HSP", "HSPDF4_a_herb1")]
    data = build_poi.build(rows, [], {"220070000"}, gather=True)
    assert {p["t"] for p in data["zones"]["220070000"]} == {"gather_herb"}  # mission NPCs are not used
    service = [  # client_world_*.xml (Codex: npc_service_coords.tsv)
        {"zone": "df4", "npc_id": "799330", "russian_name": "Раниу", "function_type": "Teleport", "x": "793", "y": "1685"},
        {"zone": "df4", "npc_id": "799260", "russian_name": "Эфирный корабль", "function_type": "Teleport",
         "x": "796", "y": "1681"},  # 5 m away: another NPC, kept
        {"zone": "df4", "npc_id": "799260", "russian_name": "Эфирный корабль", "function_type": "Teleport",
         "x": "796.2", "y": "1681"},  # listed twice: dropped
        {"zone": "df4", "npc_id": "2", "russian_name": "Кибелиск", "function_type": "Bindstone", "x": "500", "y": "600"},
        {"zone": "lf1", "npc_id": "3", "russian_name": "Чужая зона", "function_type": "Teleport", "x": "1", "y": "1"},
    ]
    added = build_poi.merge(data, build_poi.service_points(service, {"df4": "220070000"}))
    points = [p for p in data["zones"]["220070000"] if p["t"] != "gather_herb"]
    assert added == 3 and sorted(p["name"] for p in points) == ["Кибелиск", "Раниу", "Эфирный корабль"]
    kisk = next(p for p in points if p["t"] == "bindstone")
    assert (kisk["gx"], kisk["gy"]) == (500.0, 600.0)
    assert data["types"]["bindstone"]["name"] == "Кибелиск"


def test_siege_fortresses_from_gate_controls_named_by_the_nearest_area():
    entities = [
        {"map_id": "220070000", "entity_class": "PlaceableObject", "name": "Ab1_3021_Gatecontrol_1",
         "game_x": "1880.2", "game_y": "1147.4", "image_x": "", "image_y": ""},
        {"map_id": "220070000", "entity_class": "PlaceableObject", "name": "Ab_Castledoor_F_2",
         "game_x": "727", "game_y": "2282", "image_x": "", "image_y": ""},  # a door, not a fortress
    ]
    labels = {"220070000": [(1158.0, 1870.0, "Храм красной\nземли"), (100.0, 100.0, "Далеко")]}  # game y, game x
    points = build_poi.landmark_points(entities, labels)["220070000"]
    assert points == [{"t": "fortress", "x": 0.0, "y": 0.0, "gx": 1880.2, "gy": 1147.4, "name": "Храм красной земли"}]
    by_string = build_poi.landmark_points(entities, {}, {"STR_DF4_SV_3021": "Храм красной земли"})["220070000"]
    assert by_string[0]["name"] == "Храм красной земли"  # the client's string, no label needed


def test_silentera_entrances_are_the_portals():
    entities = [
        {"map_id": "220070000", "entity_class": "PlaceableObject", "name": "door_Underpass_IN_01a1",
         "game_x": "1449.4", "game_y": "904.2", "image_x": "", "image_y": ""},
        {"map_id": "210050000", "entity_class": "PlaceableObject", "name": "PlaceableObject_door_Underpass_IN_01a",
         "game_x": "1363", "game_y": "2304", "image_x": "", "image_y": ""},
    ]
    labels = {"220070000": [(930.0, 1430.0, "Вход в тоннель\nСилентера")]}  # game y, game x
    points = build_poi.landmark_points(entities, labels)
    assert points["220070000"] == [{"t": "tunnel", "x": 0.0, "y": 0.0, "gx": 1449.4, "gy": 904.2,
                                    "name": "Вход в тоннель Силентера"}]  # no string: the nearest area label
    assert points["210050000"][0]["name"] == ""  # no area name close enough
    strings = {"STR_DIC_W_Underpass_SZ_S2": "Проход в тоннель Силентера;Вход в тоннель из Келькмароса."}
    named = build_poi.landmark_points(entities, labels, strings)
    assert {p["name"] for z in named.values() for p in z} == {"Проход в тоннель Силентера"}  # the client's string


def test_dungeon_entrances_and_abyss_gates_from_the_world_xml():
    npcs = {  # client_npcs.tsv: the client's own objects, placed by <npc_info> of client_world_*.xml
        "730278": {"internal_name": "DF4_IDTemple_Up_IN", "russian_name": "Вход в храм Удас"},
        "730486": {"internal_name": "IDDramata_FOBJ_Entrance_D", "russian_name": "Вход в пещеру Мариссы"},
        "730063": {"internal_name": "DF2_OP_AbyssGate", "russian_name": "Врата Бездны Морхейма"},
        "730271": {"internal_name": "DF4_UnderPass_out", "russian_name": "Вход в Келькмарос"},
        "730260": {"internal_name": "DF4_UnderPass_In", "russian_name": "Восточный вход в тоннель Силентера"},
        "700368": {"internal_name": "DC1_door_Q2076", "russian_name": "Вход на подземную арену"},  # quest door
        "730138": {"internal_name": "DF3_Seadoor_Out", "russian_name": "Выход из дворца Аллукины"},
    }
    spawns = {"730278": [("df4", 2266.5, 1605.2)], "730486": [("df4", 2972.3, 1212.9)],
              "730063": [("df2", 305.0, 2350.0)], "730271": [("underpass", 471.5, 1078.1)],
              "730260": [("df4", 1449.0, 904.9)], "700368": [("dc1", 978.2, 1556.5)],
              "730138": [("df3", 590.8, 2534.8)], "1": [("df4", 1.0, 1.0)]}
    zone_ids = {"df4": "220070000", "df2": "220020000", "underpass": "600010000", "dc1": "120010000",
                "df3": "220040000"}
    out = build_poi.entrance_points(npcs, spawns, zone_ids)
    kelk = sorted(out["220070000"], key=lambda p: p["gx"])
    assert [(p["t"], p["name"]) for p in kelk] == [("dungeon", "Вход в храм Удас"),
                                                   ("dungeon", "Вход в пещеру Мариссы")]
    assert (kelk[0]["gx"], kelk[0]["gy"]) == (2266.5, 1605.2)
    assert out["220020000"] == [{"t": "portal", "x": 0.0, "y": 0.0, "gx": 305.0, "gy": 2350.0,
                                 "name": "Врата Бездны Морхейма"}]
    assert out["600010000"][0]["t"] == "portal"  # the tunnel's exit to Kelkmaros
    assert "120010000" not in out and "220040000" not in out  # quest doors and exits are not dungeons


def test_raid_bosses_from_codex_table():
    rows = [{"map_id": "220070000", "boss_name_ru": "Теграк", "x": "1769.114868", "y": "1765.704102"},
            {"map_id": "210050000", "boss_name_ru": "Гера", "x": "1079.880371", "y": "1626.382568"}]
    out = build_poi.raid_boss_points(rows)
    assert out["220070000"] == [{"t": "raid_boss", "x": 0.0, "y": 0.0, "gx": 1769.1, "gy": 1765.7, "name": "Теграк"}]
    assert out["210050000"][0]["name"] == "Гера"


def test_quest_givers_placed_from_the_client_one_point_per_npc():
    quests = {  # client quest.xml (Codex: quest_givers.tsv)
        "100": {"quest_id": "100", "name_ru": "Первое", "min_level": "10", "category": "quest | Морхейм"},
        "101": {"quest_id": "101", "name_ru": "Важное", "min_level": "12", "category": "important | Морхейм"},
        "102": {"quest_id": "102", "name_ru": "Поздний мир", "min_level": "60", "category": "quest | Морхейм"},
        "103": {"quest_id": "103", "name_ru": "Праздник", "min_level": "1", "category": "event | Ивент"},
    }
    links = [{"quest_id": "100", "start_npc_id": "7"}, {"quest_id": "101", "start_npc_id": "7"},
             {"quest_id": "102", "start_npc_id": "8"},  # above level 55: not in the 2.0 range
             {"quest_id": "103", "start_npc_id": "9"},
             {"quest_id": "999", "start_npc_id": "9"},  # not in our client
             {"quest_id": "100", "start_npc_id": "404"}]  # the NPC is not placed in the client
    spawns = {"7": [("df2", 100.0, 200.0)], "8": [("df2", 1.0, 1.0)], "9": [("df2", 5.0, 5.0), ("dc1", 6.0, 6.0)]}
    zone_ids = {"df2": "220020000", "dc1": "120010000"}
    out = build_poi.quest_points(quests, links, spawns, zone_ids, {"7": "Миэя", "9": "Шуго"})
    morheim = sorted(out["220020000"], key=lambda p: p["gx"])
    assert [(p["t"], p["name"]) for p in morheim] == [("quest_event", "Шуго"), ("quest_important", "Миэя")]
    assert morheim[1]["note"] == "Задания (2): Важное; Первое"  # important wins the icon, all quests listed
    assert (morheim[1]["gx"], morheim[1]["gy"]) == (100.0, 200.0)
    assert out["120010000"][0]["t"] == "quest_event"  # the same NPC placed in two zones
    quests["104"] = {"quest_id": "104", "name_ru": "Для элийцев", "min_level": "50", "category": "quest | Ингисон",
                     "race": "pc_light"}
    elyos = build_poi.quest_points(quests, [{"quest_id": "104", "start_npc_id": "7"}], spawns, zone_ids, {})
    assert elyos["220020000"][0]["note"] == "Элийские задания (1): Для элийцев"
