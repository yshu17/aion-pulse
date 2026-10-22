"""Golden results of core/bestiary for the TypeScript port (tests/golden/bestiary_*.json).

The store is checked on a small database that tools/build_bestiary_index.py builds from made-up records
(tests/golden/bestiary_fixture.sqlite, kept in the repository so the TypeScript tests need no Python). The real NPC
database is local data (local/bestiary/npcs.sqlite, not in the repository); when it is there, `real_cases()` writes
local/bestiary/golden_real.json and the TypeScript test replays it too.
"""

from __future__ import annotations

import gzip
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "golden" / "bestiary_fixture.sqlite"
REAL = ROOT / "local" / "bestiary" / "npcs.sqlite"
REAL_GOLDEN = ROOT / "local" / "bestiary" / "golden_real.json"


def _mob(npc_id, name, level, race="beast", rank="Обычный", drops=(), points=(), locations=(), kb=True, **extra):
    record = {"id": npc_id, "name": name, "site_name": name, "local_name": "", "internal_name": extra.pop("internal", ""),
              "category": extra.pop("category", "monster"), "role": extra.pop("role", ""), "race": race,
              "site_level": level, "icon_asset": "npc/" + npc_id + ".png", "kb_url": "https://kb.aionempire.com/npc/" + npc_id,
              "kb_status": "loaded" if kb else "client_only", "points": list(points), "kb": None}
    if kb:
        record["kb"] = {"badges": {"type": extra.pop("badge", "Монстр"), "race": extra.pop("badge_race", ""), "rank": rank},
                        "stats": {"Макс. ХП": str(1000 * (level or 1)), "Опыт": "12345"},
                        "drops": [{"item_id": i, "name": n, "rarity": r, "icon": "icons/" + i + ".png"} for i, n, r in drops],
                        "locations": list(locations), "level": level}
    record.update(extra)
    return record


def fixture_records() -> tuple[dict, dict, dict]:
    pt = lambda m, x, y: {"map_id": m, "x": x, "y": y, "gx": x * 2, "gy": y * 2}  # noqa: E731
    records = [
        _mob("210065", "Когтистая рефисма", 15, drops=[("1", "Прах рефисмы", "junk"), ("2", "Клык_100%", "common")],
             points=[pt("210010000", 100, 200), pt("210010000", 120, 210)],
             locations=[{"name": "Фоэта", "slug": "poeta", "points": [{"x": 1, "y": 2, "area": {"name": "Пастбище"}}]}]),
        _mob("210066", "Ёжик лесной", 45, drops=[("1", "Прах рефисмы", "junk"), ("3", "Ёлочная игла", "rare")],
             points=[pt("210010000", 300, 300)]),
        _mob("210067", "аист белый", 52, race="pc_light", rank="Элитный", points=[pt("210020000", 5, 5)]),
        _mob("210068", "Бык", None, race="pc_dark", kb=False),
        _mob("210069", "Древний дракон", 60, race="dragon", rank="Легенда", drops=[("4", "Чешуя дракона", "epic")]),
        _mob("210070", "Волк", 45, points=[pt("220010000", 10, 10)]),
        _mob("210071", "Волк", 45, points=[pt("220010000", 10, 10)], kb=False),
        _mob("210075", "Волк", 47, points=[pt("220010000", 40, 40)]),  # same name, another level: not a duplicate
        _mob("210072", "Test_mob_lv50", 50),
        _mob("210073", "Новые характеристики Волка", 46),
        _mob("210074", "Ящер-воин", 30, race="lizardman", rank="Герой", drops=[("5", "Хвост ящера", "common")],
             points=[pt("210020000", 7, 8)]),
        _mob("220000", "Торговец 100%", None, category="npc", role="merchant", race="", kb=False, internal="Merchant"),
        _mob("220001", "Страж ворот", 40, category="npc", race="pc_light", badge="NPC", badge_race="Элиец",
             points=[pt("110010000", 50, 50)], locations=[{"name": "Элизиум", "slug": "elysium", "points": []}]),
        _mob("220002", "Оружейник Элизиума", None, category="npc", race="pc_light", badge="Торговец",
             points=[pt("110010000", 60, 60)]),
        _mob("220003", "Хранитель Валон", 33, category="npc", race="naga", badge="NPC", points=[pt("210020000", 1, 2)]),
    ]
    zones = {"210010000": "Фоэта", "210020000": "Вертерон", "220010000": "Исхальген", "110010000": "Элизиум"}
    areas = {"areas": [
        {"npc_id": "210065", "map_id": "210010000", "area_id": "a1", "point_count": 2, "center": [110, 205],
         "area_names": ["Пастбище Акариоса"], "polygon": [[90, 190], [130, 190], [110, 220]]},
        {"npc_id": "210065", "map_id": "210010000", "area_id": "a2", "point_count": 5, "center": [10.5, 20.25],
         "area_names": ["Пастбище Акариоса", "Ручей"], "polygon": [[1, 2], [3, 4], [5, 6]]},
        {"npc_id": "210070", "map_id": "220010000", "area_id": "w", "point_count": 1, "center": [10, 10],
         "area_names": [], "polygon": []},
    ]}
    services = {"npcs": {
        "220000": {"tabs": ["Оружие"], "title": "Торговец оружием", "description": "Продаёт мечи.",
                   "stock": [{"item_id": "9", "name": "Меч новичка", "group": "Оружие"},
                             {"item_id": "10", "name": "Длинный меч новичка", "group": "Оружие"},
                             {"item_id": "11", "name": "Щит", "group": "Броня"}]},
        "220002": {"tabs": ["Оружие"], "stock": [{"item_id": "9", "name": "Меч новичка", "group": "Оружие"}],
                   "role": "merchant"},
    }}
    return {"zones": zones, "records": records}, areas, services


def build_fixture(output: Path) -> None:
    from tools.build_bestiary_index import build

    data, areas, services = fixture_records()
    tmp = Path(tempfile.mkdtemp())
    for name, value in (("npcs.json.gz", data), ("areas.json.gz", areas), ("services.json.gz", services)):
        with gzip.open(tmp / name, "wt", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
    build(tmp / "npcs.json.gz", tmp / "areas.json.gz", output)
    shutil.rmtree(tmp, ignore_errors=True)


SEARCHES = [
    {}, {"text": "РЕФИСМА"}, {"text": "210065"}, {"text": "pulse://npc/210065"}, {"text": " https://kb.aionempire.com/npc/210070 "},
    {"text": "меч"}, {"text": "меч", "category": "merchant"}, {"text": "меч", "category": "monster"}, {"text": "прах"},
    {"text": "ёлочная"}, {"text": "100%"}, {"text": "100_"}, {"text": "клык_"}, {"text": "волк"}, {"category": "monster"},
    {"category": "npc"}, {"category": "merchant"}, {"category": "service"}, {"category": "low"},
    {"category": "monster", "hide_low": True}, {"race": "Элийцы"}, {"race": "Асмодиане"}, {"race": "Балауры"},
    {"race": "Другие"}, {"race": "Зверь"}, {"rank": "Элитный"}, {"map_id": "210010000"},
    {"min_level": 15, "max_level": 45}, {"min_level": 46}, {"max_level": 20},
    {"region": "Пастбище Акариоса"}, {"region": "Пастбище Акариоса", "map_id": "210010000"},
    {"region": "Пастбище Акариоса", "map_id": "missing"}, {"region": "Пастбище"},
    {"order": "level_asc"}, {"order": "level_desc"}, {"order": "name_asc"}, {"order": "name_desc"}, {"order": "nope"},
    {"order": "name_asc", "offset": 2, "limit": 3}, {"limit": 0}, {"text": "ж", "order": "name_desc"},
    {"text": "волк", "order": "name_desc"}, {"text": "волк", "order": "name_asc"},
]


def store_answers(store, searches, ids) -> dict:
    return {
        "version": store.version, "coverage": list(store.coverage()), "races": store.races(), "ranks": store.ranks(),
        "zones": [list(z) for z in store.zones()], "regions": [store.regions(), store.regions("210010000")],
        "search": [[s, *store.search(**s)] for s in searches],
        "detail": {i: store.detail(i) for i in ids},
        "areas": {i: store.areas(i) for i in ids},
    }


def store_cases() -> dict:
    from core.bestiary.bestiary_store import BestiaryStore, search_key, unpack_ids

    tmp = Path(tempfile.mkdtemp()) / "npcs.sqlite"
    build_fixture(tmp)
    store = BestiaryStore(tmp)
    try:
        ids = [r["id"] for r in fixture_records()[0]["records"]] + ["nope"]
        answers = store_answers(store, SEARCHES, ids)
    finally:
        store.close()
    import zlib
    answers["unpack_ids"] = [[blob.hex(), sorted(unpack_ids(blob))] for blob in
                             (zlib.compress(bytes([1, 2, 0x81, 0x01, 5])), zlib.compress(b""))]
    answers["search_key"] = [[t, search_key(t)] for t in ("  Волк ", "PULSE://NPC/12", "x https://kb.aionempire.com/npc/77 y",
                                                          "Straße", "")]
    return answers


def labels_cases() -> dict:
    from core.bestiary.bestiary_labels import FACTIONS, RACES, faction_for, race_label, stat_text

    pairs = [("pc_light", ""), ("PC_DARK_x", ""), ("gchief_light2", ""), ("ghenchman_dark", ""), ("Drakan", ""),
             ("naga", ""), ("dragon_castle_1", ""), ("beast", ""), ("beast", "Зверь"), ("", "Элиец"), ("", "ASMODIAN"),
             ("", " Балауры "), ("", "elyos"), ("humanoid", "Wolf"), ("", ""), ("magicalmonster", ""), ("x", "Ёж"),
             ("unknown", ""), ("pc_light", "Lightling"), ("", "naga")]
    return {
        "factions": list(FACTIONS), "races": RACES,
        "faction": [[a, b, faction_for(a, b)] for a, b in pairs],
        "race": [[a, b, race_label(a, b)] for a, b in pairs],
        "stat": [[v, stat_text(v)] for v in (123, 1234, "12345 / 1234567", "Ранг 3", 1000000, None, "999", -98765, 12.5)],
    }


def classify_cases() -> dict:
    from core.bestiary.bestiary_classify import above_max_level, is_main_npc, plan, stem_key, technical_name

    names = ["Волк", "", "  ", "123", "Test_mob", "BAb1_x_lv50", "Wolf", "Страж123", "NPC123", "Прозрачный NPC open IDStation",
             "LF3 элементаль", "GM Еvent", "Барoшунг", "Легион II", "Страж IV ворот", "Голем XIV", "Мастер-ключник",
             "test", "Тестер", "«Молот» (босс)", "Ab элементаль", "Страж 123", "a", "Ёж-12"]
    levels = [56, 55, "60", " 70 ", "x", None, 0, "", "56a", 100]
    sig = lambda p, s=0, d=0: [p, s, d]  # noqa: E731
    rows = [
        {"id": "1", "name": "Волк", "level": 45, "category": "monster", "points": 3, "drops": 1, "profile": 1, "sig": sig(1)},
        {"id": "2", "name": "волк", "level": 45, "category": "monster", "points": 0, "drops": 0, "profile": 0, "sig": sig(0)},
        {"id": "3", "name": "Волк", "level": 45, "category": "monster", "points": 3, "drops": 1, "profile": 0, "sig": sig(1)},
        {"id": "4", "name": "Новые характеристики Хранителя Валона", "level": 50, "category": "npc", "points": 0,
         "drops": 0, "profile": 0, "sig": sig(0, 5)},
        {"id": "5", "name": "Хранитель Валон", "level": 50, "category": "npc", "points": 7, "drops": 0, "profile": 1,
         "sig": sig(9)},
        {"id": "6", "name": "Test_x", "level": 1, "category": "monster", "points": 2, "drops": 0, "profile": 0, "sig": sig(2)},
        {"id": "7", "name": "Волк", "level": 45, "category": "monster", "points": 5, "drops": 2, "profile": 1, "sig": sig(4)},
        {"id": "8", "name": "Волк", "level": "45", "category": "monster", "points": 3, "drops": 4, "profile": 1, "sig": sig(1)},
        {"id": "9", "name": "Новые характеристики Ничто", "level": 1, "category": "npc", "points": 0, "drops": 0,
         "profile": 0, "sig": sig(0)},
        {"id": "10", "name": "Аист", "level": None, "category": "monster", "points": 0, "drops": 0, "profile": 0, "sig": sig(0)},
        {"id": "11", "name": "Аист", "level": None, "category": "monster", "points": 0, "drops": 0, "profile": 0, "sig": sig(0)},
    ]
    plans = []
    for subset in (rows, rows[:3], rows[3:6], [rows[1], rows[0]], []):
        tupled = [{**r, "sig": tuple(r["sig"])} for r in subset]
        donors, service = plan(tupled)
        plans.append([subset, donors, sorted(service)])
    return {
        "technical": [[n, technical_name(n)] for n in names],
        "stems": [[n, list(stem_key(n))] for n in names + ["хранителя Валона", "Хранитель Валон", "Новые Ёжики-123 abc", "Оса Ели дуб"]],
        "above": [[lv, cat, above_max_level(lv, cat)] for lv in levels for cat in ("monster", "npc")],
        "main": [[b, r, g, is_main_npc(b, r, g)] for b, r, g in
                 (("Торговец", "", False), (" функционер ", "", False), ("NPC", "Teleport", False), ("NPC", "", True),
                  ("", "", False), ("Монстр", "guard", False), ("", " STIGMA_MASTER", False))],
        "plans": plans,
    }


def card_cases() -> dict:
    from core.bestiary.card import (CATEGORY, KB_ITEM_URL, RARITY, SORTS, drops_empty_text, drops_note, filter_drops,
                                    filter_stock, locations_text, overview_rows, overview_text, place_counts,
                                    points_from_text, stock_note)

    details = [
        {}, {"level": 15, "rank": "Обычный", "stats": {"Макс. ХП": "282", "Опыт": "10"}, "faction": "Элийцы", "race": "Зверь",
             "title": "Страж", "description": "Охраняет мост.", "kb_status": "loaded",
             "stock": [{"name": "Меч", "group": "Оружие"}, {"name": "Щит", "group": "Броня"}, {"name": "Нож", "group": "Оружие"},
                       {"name": "Хлеб"}],
             "drops": [{"name": "Прах рефисмы"}, {"name": "Клык"}, {"name": None}, {"item_id": "5"}],
             "points": [{"map_id": "220010000"}, {"map_id": "210010000"}, {"map_id": 210010000}, {}, {"map_id": None}],
             "kb_locations": [{"name": "Фоэта"}, {"slug": "verteron"}, {}], "points_from": "Волк"},
        {"title": "", "description": "", "stock": [{"group": ""}], "kb_locations": [{}, {"name": "", "slug": "verteron"}], "kb_status": "client_only",
         "drops": [], "points": []},
        {"level": "", "rank": None, "stats": None, "faction": "", "race": "", "description": "Только описание"},
    ]
    names = {"210010000": "Фоэта", "220010000": "Исхальген", "": "—"}
    return {
        "consts": [CATEGORY, SORTS, RARITY, KB_ITEM_URL],
        "cards": [[d, [list(r) for r in overview_rows(d)], overview_text(d), [list(p) for p in place_counts(d, names)],
                   drops_empty_text(d), locations_text(d), points_from_text(d),
                   [[q, [[i, it] for i, it in filter_drops(d, q)], [[i, it] for i, it in filter_stock(d, q)]]
                    for q in ("", " МЕ ", "к", "оружие", "zzz")],
                   [drops_note(n, d) for n in (0, 2)]] for d in details],
        "stock_note": [[s, t, stock_note(s, t)] for s, t in ((0, 0), (1, 3), (3, 3))],
    }


def real_cases() -> dict | None:
    """Answers of the real local database, or None without it."""
    if not REAL.is_file():
        return None
    from core.bestiary.bestiary_store import BestiaryStore

    store = BestiaryStore(REAL)
    try:
        rows, _ = store.search(limit=40)
        mobs, _ = store.search(category="monster", order="level_desc", limit=10)
        sellers, _ = store.search(category="merchant", limit=10)
        ids = [r["id"] for r in rows + mobs + sellers]
        searches = [{"limit": 40}, {"text": "меч", "limit": 30}, {"text": "дракон", "order": "name_asc", "limit": 50},
                    {"text": "ё", "order": "name_desc", "limit": 50}, {"category": "low", "limit": 25},
                    {"category": "service", "limit": 25}, {"race": "Балауры", "rank": "Герой", "limit": 25},
                    {"order": "name_asc", "offset": 1000, "limit": 60}, {"order": "name_desc", "offset": 2000, "limit": 80}, {"order": "level_asc", "offset": 500, "limit": 60},
                    {"text": "чешуя", "category": "monster", "limit": 40}, {"text": "зелье", "category": "merchant", "limit": 40},
                    {"min_level": 30, "max_level": 35, "hide_low": True, "limit": 50}]
        regions = store.regions()
        if regions:
            searches.append({"region": regions[len(regions) // 2], "limit": 30})
        return store_answers(store, searches, ids)
    finally:
        store.close()


def write_real() -> Path | None:
    case = real_cases()
    if case is None:
        return None
    REAL_GOLDEN.write_text(json.dumps({"case": case}, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return REAL_GOLDEN


def all_cases() -> dict[str, dict]:
    return {"bestiary_store": store_cases(), "bestiary_labels": labels_cases(), "bestiary_classify": classify_cases(),
            "bestiary_card": card_cases()}
