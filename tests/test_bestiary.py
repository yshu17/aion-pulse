"""The generated index keeps exact IDs, Unicode search, map points and source detail."""

import gzip
import json

from tools.build_bestiary_index import build
from core.bestiary.bestiary_store import BestiaryStore


def test_bestiary_index_supports_links_filters_and_locations(tmp_path):
    source = tmp_path / "npcs.json.gz"
    areas = tmp_path / "areas.json.gz"
    database = tmp_path / "npcs.sqlite"
    records = {
        "zones": {"210010000": "Фоэта"},
        "records": [
            {
                "id": "210065", "name": "Когтистая рефисма", "site_name": "Когтистая рефисма",
                "local_name": "", "internal_name": "lepismа_3_n", "category": "npc",  # KB type overrides client heuristic
                "role": "", "race": "beast", "site_level": 15, "icon_asset": "npc/mob.jpg",
                "kb_url": "https://kb.aionempire.com/npc/210065", "kb_status": "loaded",
                "points": [{"map_id": "210010000", "x": 100, "y": 200, "gx": 11, "gy": 22}],
                "kb": {
                    "badges": {"type": "Монстр", "race": "Зверь", "rank": "Обычный"},
                    "stats": {"Макс. ХП": "282"},
                    "drops": [{"item_id": "1", "name": "Прах рефисмы", "rarity": "junk"}],
                    "locations": [{"name": "Фоэта", "points": [{"x": 1, "y": 2}]}],
                },
            },
            {
                "id": "220000", "name": "Торговец 100%", "site_name": "", "local_name": "",
                "internal_name": "Merchant", "category": "npc", "role": "merchant", "race": "",
                "site_level": None, "icon_asset": "", "kb_url": "", "kb_status": "client_only",
                "points": [], "kb": None,
            },
        ],
    }
    regions = {
        "areas": [{
            "npc_id": "210065", "map_id": "210010000", "area_id": "area-1",
            "point_count": 1, "center": [100, 200], "area_names": ["Пастбище Акариоса"],
            "polygon": [[90, 190], [110, 190], [100, 210]],
        }],
    }
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False)
    with gzip.open(areas, "wt", encoding="utf-8") as stream:
        json.dump(regions, stream, ensure_ascii=False)
    with gzip.open(source.with_name("services.json.gz"), "wt", encoding="utf-8") as stream:
        json.dump({"npcs": {"220000": {"tabs": ["Оружие"], "stock": [{"item_id": "1", "name": "Меч новичка"}]}}}, stream)

    assert build(source, areas, database) == (2, 1)
    store = BestiaryStore(database)
    try:
        for query in ("РЕФИСМА", "210065", "pulse://npc/210065", "https://kb.aionempire.com/npc/210065"):
            rows, count = store.search(query)
            assert count == 1
            assert rows[0]["id"] == "210065"
        assert store.search(category="monster", race="Зверь", rank="Обычный", map_id="210010000")[1] == 1
        assert store.search(category="merchant")[1] == 1
        rows, count = store.search("меч", category="merchant")  # a merchant is found by a sold item
        assert (count, rows[0]["id"], rows[0]["sold"]) == (1, "220000", "Меч новичка")
        assert store.search("меч", category="monster")[1] == 0
        rows, count = store.search("прах")  # a mob is found by a dropped item
        assert (count, rows[0]["id"], rows[0]["dropped"]) == (1, "210065", "Прах рефисмы")
        assert store.races() == ["Элийцы", "Асмодиане", "Балауры", "Другие"]
        assert store.search(race="Другие")[1] == 2
        assert store.search(race="Балауры")[1] == 0
        assert store.search("100%")[1] == 1  # SQL wildcard is escaped
        assert store.search("100_")[1] == 0
        assert store.search(min_level=15, max_level=15)[1] == 1
        assert store.search(min_level=16)[1] == 0
        assert store.search(max_level=20)[1] == 1  # unknown levels are excluded
        assert store.regions("210010000") == ["Пастбище Акариоса"]
        assert store.search(region="Пастбище Акариоса", map_id="210010000")[1] == 1
        assert store.search(region="Пастбище Акариоса", map_id="missing")[1] == 0
        detail = store.detail("210065")
        assert detail["stats"]["Макс. ХП"] == "282"
        assert detail["faction"] == "Другие"
        assert detail["drops"][0]["name"] == "Прах рефисмы"
        assert detail["points"][0]["gx"] == 11
        assert store.areas("210065")[0]["polygon"][2] == [100, 210]
    finally:
        store.close()


def test_profile_parser_reads_level_from_hp_bar():
    from tools.build_bestiary_data import parse_profile
    profile = parse_profile("215000", '''
      <div class="header-title npc-name">Легат Бакрам</div>
      <div class="hp-bar v-align-middle bar-3"><div class="icon"><span>50</span></div></div>
      <span class="npc-badge npc-badge--rank" data-key="hero">Героический</span>
      <div class="npc-stat"><div class="npc-stat-label">Макс. ХП</div><div class="npc-stat-value">1194594</div></div>
    ''')
    assert profile["level"] == 50
    assert profile["hp_bar"] == 3
    assert profile["badges"]["rank"] == "Героический"
    assert profile["stats"]["Макс. ХП"] == "1194594"


def test_factions_normalize_client_case_and_keep_species_separate():
    from core.bestiary.bestiary_labels import faction_for, race_label
    assert faction_for("PC_Light") == "Элийцы"
    assert faction_for("pc_dark") == "Асмодиане"
    assert faction_for("Drakan") == "Балауры"
    assert faction_for("Naga") == "Балауры"
    assert faction_for("Beast") == "Другие"
    assert race_label("Beast") == "Зверь"
    assert race_label("construct") == "Конструкт"


def test_profile_cache_keeps_success_after_network_failure(tmp_path):
    from tools.build_bestiary_data import load_cache
    cache = tmp_path / "profiles.jsonl"
    cache.write_text('\n'.join(json.dumps(row) for row in [
        {"id": "1", "name": "Creature", "parser_version": 2},
        {"id": "1", "error": "timeout"},
    ]) + '\n' + '{"id":', encoding="utf-8")
    assert load_cache(cache)["1"]["name"] == "Creature"


def test_profile_scraper_stops_after_repeated_network_failures(tmp_path, monkeypatch):
    from tools import build_bestiary_data as importer
    monkeypatch.setattr(importer, "fetch_profile", lambda npc_id: {"id": npc_id, "error": "timeout"})
    cache = tmp_path / "profiles.jsonl"
    importer.scrape([str(i) for i in range(100)], cache, workers=1)
    report = json.loads(cache.with_name("import-status.json").read_text(encoding="utf-8"))
    assert report["stopped_on_network_errors"] is True
    assert report["remaining"] == 100
    assert len(report["errors"]) == 4


def test_manual_points_give_a_record_a_pin_and_a_circle_area():
    from tools.build_bestiary_index import apply_manual_points

    data = {"records": [{"id": 1, "name": "Босс", "points": []}, {"id": 2, "name": "Другой"}]}
    areas = []
    added = apply_manual_points(data, areas, {"1": {"map_id": "220070000", "points": [[1421, 1346]]}, "9": {"map_id": "x", "points": [[1, 2]]}},
                                lambda map_id, x, y: (y, x))
    assert added == 1  # an id that is not in the data is skipped
    point = data["records"][0]["points"][0]
    assert (point["gx"], point["gy"], point["x"], point["y"], point["source"]) == (1421.0, 1346.0, 1346.0, 1421.0, "manual")
    assert "points" not in data["records"][1]
    assert areas[0]["npc_id"] == "1" and areas[0]["center"] == [1346.0, 1421.0] and len(areas[0]["polygon"]) == 8


def _mobs_database(tmp_path, mobs):
    """A real index built from a few monsters: (id, name, level)."""
    source, areas, database = tmp_path / "npcs.json.gz", tmp_path / "areas.json.gz", tmp_path / "npcs.sqlite"
    records = {"zones": {}, "records": [
        {"id": npc_id, "name": name, "site_name": name, "local_name": "", "internal_name": "", "category": "monster",
         "role": "", "race": "beast", "site_level": level, "icon_asset": "", "kb_url": "", "kb_status": "client_only",
         "points": [], "kb": None}
        for npc_id, name, level in mobs]}
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False)
    with gzip.open(areas, "wt", encoding="utf-8") as stream:
        json.dump({"areas": []}, stream)
    build(source, areas, database)
    return BestiaryStore(database)


def test_sorting_by_level_and_by_name_both_ways(tmp_path):
    store = _mobs_database(tmp_path, [("1", "Волк", 45), ("2", "Аист", 52), ("3", "Ёж", 41), ("4", "Бык", None)])
    try:
        names = lambda order: [r["name"] for r in store.search("", "monster", order=order)[0]]
        assert names("level_asc") == ["Ёж", "Волк", "Аист", "Бык"]  # no level: last
        assert names("level_desc") == ["Аист", "Волк", "Ёж", "Бык"]
        assert names("name_asc")[:2] == ["Аист", "Бык"] and names("name_desc")[-2:] == ["Бык", "Аист"]
    finally:
        store.close()


def test_monsters_below_40_have_their_own_group(tmp_path):
    store = _mobs_database(tmp_path, [("1", "Кабан", 5), ("2", "Волк", 39), ("3", "Медведь", 40), ("4", "Лось", 55)])
    try:
        names = lambda **kw: sorted(r["name"] for r in store.search("", **kw)[0])
        assert names(category="low") == ["Волк", "Кабан"]
        assert names(category="", hide_low=True) == ["Лось", "Медведь"]  # every other group leaves them out
        assert names(category="monster", hide_low=True) == ["Лось", "Медведь"]
        assert len(names(category="")) == 4  # the map's search still finds them
    finally:
        store.close()


def test_zone_npc_points_for_elysium_only_for_npcs_with_a_function():
    from tools.add_zone_npc_points import add_points, has_function

    assert has_function("Merchant") and has_function("Teleport") and has_function("TELEPORT") and has_function("Stigma_master")
    assert not has_function("") and not has_function("Guard")
    catalog = {"zones": {}, "records": [{"id": "1", "name": "Торговец"}, {"id": "2", "name": "Стражник"},
                                         {"id": "3", "name": "Арена-NPC"}]}
    flat = {"x": [1.0, 0.0], "y": [1.0, 0.0], "size": 3000}
    maps = {map_id: flat for map_id in ("110010000", "110020000", "110070000", "120020000", "120080000")}
    import tools.add_zone_npc_points as module
    original = module.world_npcs
    module.world_npcs = lambda extract, code: {"lc1": [("1", 100.0, 200.0, 5.0), ("2", 110.0, 210.0, 5.0)],
                                               "arena_l_lobby": [("3", 50.0, 60.0, 1.0)]}.get(code, [])
    try:
        counts = add_points(catalog, maps, None, {"1": "Merchant", "2": "", "3": ""})
        add_points(catalog, maps, None, {"1": "Merchant", "2": "", "3": ""})  # again: nothing repeated
    finally:
        module.world_npcs = original
    by_id = {r["id"]: r.get("points", []) for r in catalog["records"]}
    assert len(by_id["1"]) == 1 and by_id["2"] == []  # Elysium: the guard has no function, so no point
    assert len(by_id["3"]) == 1  # the arena takes every NPC
    assert counts[("lc1", "skipped: no function")] == 1
