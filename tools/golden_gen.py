"""Golden results of the Python core, the reference for the TypeScript port (launcher/, branch pulse+).

    python tools/golden_gen.py            # rewrite tests/golden/*.json from the current core
    python -m pytest tests/test_golden.py # check the files still match the core

Each file is {"case": {...}} with inputs and the expected output. Real bundled data is summarised by counts and a hash,
so the files stay small and the port is still checked against the real data.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
GOLDEN = ROOT / "tests" / "golden"


def _digest(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def settings_cases() -> dict:
    from core.settings.config import Config, read_config, save_config

    defaults = asdict(Config())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text(json.dumps({
            "keywords": ["wts", 5], "cooldown_sec": 30, "alert_mode": "nag", "react_sec": "30",
            "notify_corner": "top", "unknown_key": 1,
        }, ensure_ascii=False), encoding="utf-8")
        cfg, notice = read_config(path)
        mixed = asdict(cfg)
        path.write_text("не json", encoding="utf-8")
        broken_cfg, broken_notice = read_config(path)
        save_config(path, Config(keywords=["хил"], watch_items=["1"]))
        saved = json.loads(path.read_text(encoding="utf-8"))
    return {
        "defaults": defaults,
        "mixed_types": {"config": mixed, "notice": notice},
        "broken_file": {"config": asdict(broken_cfg), "notice_starts": broken_notice[:20]},
        "saved_keys": {"keywords": saved["keywords"], "watch_items": saved["watch_items"]},
    }


def loader_cases() -> dict:
    from core.items.catalog import load_item_names, load_link_names, load_watch_items
    from core.map.zones import load_zones

    data = ROOT / "data"
    names = load_item_names(data / "item_names.tsv")
    maps, quests = load_link_names(data)
    watch = load_watch_items(data / "watch_items.csv")
    zones = load_zones(data / "maps", maps)
    sample_id = sorted(names)[0]
    return {
        "item_names": {"count": len(names), "digest": _digest(sorted(names.items())), "sample": [sample_id, names[sample_id]]},
        "link_names": {"maps": len(maps), "quests": len(quests), "digest": _digest([sorted(maps.items()), sorted(quests.items())])},
        "watch_items": {"count": len(watch), "digest": _digest([[w.id, w.name, w.level, w.category, w.grade, w.kind] for w in watch])},
        # zones in full: their coefficients are floats such as 1.0 and -0.0, which Python and JavaScript print
        # differently, so a hash of the text would not match; the values themselves do
        "zones": {"count": len(zones), "list": [
            {"map_id": z.map_id, "name": z.name, "file": z.path.name, "size": z.size, "kx": list(z.kx),
             "ky": list(z.ky), "side": z.side, "labels": len(z.labels), "layers": [layer[0] for layer in z.layers]}
            for z in sorted(zones.values(), key=lambda zone: zone.map_id)]},
    }


def browser_cases() -> dict:
    from core.items.browser import ALL_TYPES, ItemBrowser, ItemFilter
    from core.items.catalog import load_watch_items

    items = load_watch_items(ROOT / "data" / "watch_items.csv")
    b = ItemBrowser(items, checked=[items[0].id, items[5].id, "no-such-id"], collapsed=["Лата", "Нет такой"])
    out = {
        "groups": [[name, len(group)] for name, group in b.groups.items()],
        "order_head": b.order[:20],
        "checked_ids": b.checked_ids(),
        "collapsed": b.collapsed,
        "grades": b.grades,
        "levels": b.levels,
        "type_choices": b.type_choices(),
        "search": {},
    }
    for query in ("кираса рудр", "меч", "55", "рудр 55", "щит фланаса", "ЁЛКА", "", "  "):
        found = b.search(query)
        out["search"][query] = {"count": found, "head": b.matches[:10], "current": b.current_match()}
    b.search("меч")
    out["steps"] = [b.step(1), b.step(1), b.step(-1), b.step(-1), b.step(-1)]
    f1 = b.toggle_grade("epic")
    b.set_filter(f1)
    f2 = b.toggle_grade("legend")
    b.set_filter(f2)
    out["grade_toggles"] = [sorted(f1.grades), sorted(f2.grades), len(b.visible),
                            [b.chip_state(g) for g in b.grades], b.chip_state("epic", enabled=False)]
    b.set_filter(b.toggle_grade("epic"))
    b.set_filter(b.toggle_grade("legend"))
    out["grades_back"] = sorted(b.filter.grades)
    f3 = b.with_levels_type(55, 50, "Оружие: Меч")
    b.set_filter(f3)
    out["levels_type"] = {"filter": [f3.level_min, f3.level_max, f3.type, f3.active], "visible": len(b.visible),
                          "shown": [[name, len(group)] for name, group in b.shown.items()]}
    b.set_all(True)
    out["set_all"] = {"checked": len(b.checked), "group_checked": {name: b.group_checked(name) for name in b.shown}}
    b.set_filter(ItemFilter())
    b.set_group("Оружие", False)
    b.toggle_item(items[1].id)
    out["after_group"] = {"checked": len(b.checked), "has_item1": items[1].id in b.checked}
    first = b.order[0]
    b.toggle_collapsed(b.group_of[first])
    out["expand"] = [b.expand_for(first), b.expand_for(first), b.collapsed]
    out["all_types"] = [b.with_levels_type(0, 0, ALL_TYPES).type, ItemFilter().active]
    return out


RAW_RECIPES = [
    {"product": " Меч наемника ", "product_id": "100000123", "count": 2, "skill": "Оружейное дело", "level": 300,
     "ingredients": [["Железо", 5], ["Кожа", "2"], ["Пусто", "x"], ["", 3], ["Клей"]]},
    {"product": "Меч наемника", "skill": "Оружейное дело", "level": "310", "ingredients": [["Сталь", 0]]},
    {"product": "Зелье", "count": 0, "level": None, "ingredients": [["Трава", -4]]},
    {"product": "Без ингредиентов", "ingredients": []},
    {"product": "", "ingredients": [["Железо", 1]]},
    "не рецепт",
    {"product": "Плохой уровень", "level": "высокий", "ingredients": [["Железо", 1]]},
]


def recipe_cases() -> dict:
    from core.items.recipes import RecipeBook, _recipe, recipe_block, with_recipe

    parsed = [_recipe(raw) for raw in RAW_RECIPES]
    book = RecipeBook([r for r in parsed if r is not None])

    def show(recipes):
        return [[r.product, r.skill, r.level, r.count, [list(i) for i in r.ingredients], r.product_id] for r in recipes]

    spec = {"name": "Меч наемника", "grade": "rare", "blocks": [{"kind": "text", "text": "x"}]}
    return {
        "raw": RAW_RECIPES,
        "parsed": [None if r is None else show([r])[0] for r in parsed],
        "count": len(book),
        "by_id": show(book.for_item("что угодно", "100000123")),
        "by_name": show(book.for_item("МЕЧ НАЕМНИКА")),
        "missing": show(book.for_item("нет такого", "1")),
        "block": recipe_block(book.for_item("Зелье")),
        "no_block": recipe_block([]),
        "with_recipe": with_recipe(spec, book.for_item("Зелье")),
        "without": with_recipe(spec, []),
    }


def spec_cases() -> dict:
    from core.items.specs import load_specs

    specs = load_specs(ROOT / "data" / "item_specs.json.gz")
    ids = sorted(specs)
    sample = [ids[0], ids[len(ids) // 2], ids[-1]]
    return {"count": len(specs), "sample": {item_id: specs[item_id] for item_id in sample},
            "has_missing": "no-such-id" in specs}


def write_all() -> list[Path]:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    written = []
    for name, build in (("settings", settings_cases), ("loaders", loader_cases), ("browser", browser_cases),
                        ("recipes", recipe_cases), ("specs", spec_cases)):
        path = GOLDEN / f"{name}.json"
        path.write_text(json.dumps({"case": build()}, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    import golden_bestiary
    import golden_chat
    import golden_map
    import golden_notify
    import golden_schedule

    for name, case in {**golden_chat.all_cases(), **golden_notify.all_cases(), **golden_schedule.all_cases(),
                       **golden_map.all_cases(), **golden_bestiary.all_cases()}.items():
        path = GOLDEN / f"{name}.json"
        path.write_text(json.dumps({"case": case}, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    golden_bestiary.build_fixture(golden_bestiary.FIXTURE)  # the database the TypeScript store tests read
    written.append(golden_bestiary.FIXTURE)
    real = golden_bestiary.write_real()  # local only: the real NPC database is not in the repository
    if real:
        written.append(real)
    return written


if __name__ == "__main__":
    for path in write_all():
        print("written", path.relative_to(ROOT))
