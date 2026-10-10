import json

import pytest

from watcher.poi import Poi, PoiStore, cluster

Z = "220070000"


@pytest.fixture
def store(tmp_path):
    data = {
        "version": 1,
        "types": {
            "teleport": {"group": "npc", "name": "Привратник", "icon": "teleport.png"},
            "warehouse": {"group": "npc", "name": "Заведующий складом"},
            "gather_herb": {"group": "gather", "name": "Травы"},
        },
        "zones": {
            Z: [
                {"t": "teleport", "x": 100, "y": 100, "gx": 1000, "gy": 1000, "name": "Раниу"},
                {"t": "teleport", "x": 900, "y": 900, "gx": 9000, "gy": 9000, "name": "Сэти"},
                {"t": "warehouse", "x": 120, "y": 100, "gx": 1003, "gy": 1004, "name": "Ёжик"},
                {"t": "gather_herb", "x": 500, "y": 500, "gx": 5000, "gy": 5000, "name": ""},
                {"t": "unknown_kind", "x": 1, "y": 1, "gx": 1, "gy": 1, "name": "?"},
            ],
            "210050000": [{"t": "teleport", "x": 5, "y": 5, "gx": 5, "gy": 5, "name": "Другая зона"}],
        },
    }
    path = tmp_path / "poi.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return PoiStore.load(path)


def test_load_and_types(store):
    assert store.types["teleport"]["name"] == "Привратник"
    assert store.type_name("gather_herb") == "Травы"
    assert store.type_name("unknown_kind") == "unknown_kind"
    assert store.groups() == {"npc": ["teleport", "warehouse"], "gather": ["gather_herb"]}


def test_missing_or_broken_file_gives_empty_store(tmp_path):
    assert PoiStore.load(tmp_path / "nope.json").in_zone(Z, {"teleport"}) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert PoiStore.load(bad).types == {}


def test_in_zone_filters_by_type(store):
    names = {p.name for p in store.in_zone(Z, {"teleport"})}
    assert names == {"Раниу", "Сэти"}
    assert store.in_zone(Z, set()) == []
    assert store.in_zone("999", {"teleport"}) == []


def test_counts(store):
    assert store.counts(Z) == {"teleport": 2, "warehouse": 1, "gather_herb": 1, "unknown_kind": 1}


def test_search_by_name_and_type_name(store):
    everything = set(store.types) | {"unknown_kind"}
    assert [p.name for p in store.search(Z, "раниу", everything)] == ["Раниу"]
    assert [p.name for p in store.search(Z, "ежик", everything)] == ["Ёжик"]  # «ё» = «е»
    assert {p.name for p in store.search(Z, "привратн", everything)} == {"Раниу", "Сэти"}
    assert store.search(Z, "раниу", {"warehouse"}) == []  # hidden layers are not searched
    assert store.search(Z, "  ", everything) == []


def test_nearest_in_metres(store):
    poi, metres = store.nearest(Z, 1000, 1000, "warehouse")
    assert poi.name == "Ёжик" and metres == pytest.approx(5.0)
    poi, metres = store.nearest(Z, 8000, 8000, "teleport")
    assert poi.name == "Сэти" and metres == pytest.approx(1414.2, abs=0.1)
    assert store.nearest(Z, 0, 0, "stigma") is None


def test_cluster_merges_close_points_and_splits_when_zoomed():
    pts = [Poi(Z, "gather_herb", x, 0, 0, 0, "") for x in (0, 5, 10, 300)]
    merged = cluster(pts, lambda x, y: (x, y), 40)
    sizes = sorted(len(members) for _x, _y, members in merged)
    assert sizes == [1, 3]
    centre = next((x, y) for x, y, members in merged if len(members) == 3)
    assert centre == pytest.approx((5, 0))
    split = cluster(pts, lambda x, y: (x * 10, y * 10), 40)  # zoomed in ×10
    assert sorted(len(m) for _x, _y, m in split) == [1, 1, 1, 1]


def test_cluster_key_merges_across_types():
    pts = [Poi(Z, "gather_herb", 0, 0, 0, 0, ""), Poi(Z, "gather_metal", 5, 0, 0, 0, "")]
    assert len(cluster(pts, lambda x, y: (x, y), 40)) == 2  # default: per type
    assert len(cluster(pts, lambda x, y: (x, y), 40, key=lambda p: "gather")) == 1


def test_projected_recomputes_map_pixels_from_game_coordinates(store):
    moved = store.projected({Z: lambda gx, gy: (gy / 10, gx / 10)})
    raniu = next(p for p in moved.in_zone(Z, {"teleport"}) if p.name == "Раниу")
    assert (raniu.x, raniu.y) == (100, 100) and (raniu.gx, raniu.gy) == (1000, 1000)
    other = moved.in_zone("210050000", {"teleport"})[0]
    assert (other.x, other.y) == (5, 5)  # no transform for this zone: kept as stored

