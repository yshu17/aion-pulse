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
    assert c(obj("Portal", "PortalDC1_Area2")) == "portal"
    assert c(obj("DP", "DPDf1_DirectPortal3")) == "direct_portal"
    assert c(obj("HSP", "HSPDF1_Alder_herb2")) == "gather_herb"
    assert c(obj("KP", "DF1_KeyPoints_Alder_3")) == "quest_point"
    assert c(obj("MP", "Mappiont_DC1_SUB_C")) == "quest_point"
    assert c(obj("SP")) is None  # plain monster spawns are not a layer
    assert c(obj(function="Unknown_role")) is None


def test_build_keeps_calibrated_zones_and_rounds(tmp_path):
    rows = [
        obj(function="Teleport", ru="Раниу", x="1686.054", y="793.149"),
        obj("HSP", "HSPDF4_a_herb1"),
        obj(function="Merchant", ru="Хирокин", map_id="210020000"),  # zone without a map
        obj(function="Merchant", ru="Без картинки", x="", y=""),  # no pixels
    ]
    entities = [{"map_id": "220070000", "entity_class": "AbyssArtifacts", "name": "Artifact_01",
                 "game_x": "1", "game_y": "2", "image_x": "3", "image_y": "4"}]
    data = build_poi.build(rows, entities, {"220070000", "210050000"})
    points = data["zones"]["220070000"]
    assert {p["t"] for p in points} == {"teleport", "gather_herb", "artifact"}
    tele = next(p for p in points if p["t"] == "teleport")
    assert tele == {"t": "teleport", "x": 1686.1, "y": 793.1, "gx": 100.0, "gy": 200.0, "name": "Раниу"}
    assert "210020000" not in data["zones"]
    assert data["types"]["teleport"]["group"] == "npc"
    assert data["types"]["gather_herb"]["name"] == "Травы"
    json.dumps(data)  # serialisable
