"""Сравнение свежей выгрузки клиента с runtime-БД проекта (шаг map:45, пункт 1).

Только чтение: `catalog.sqlite` и `data/pulse.db` открываются в режиме ro.
Выход: `client_extract/fresh_catalog/COMPARISON.md` и `COMPARISON.json`.

Запуск из корня проекта:  python tools/compare_fresh_catalog.py

Сравнивается по ID. Русское имя и уровень берутся из клиента (`entries.name_ru`,
`fields_json.level`), из БД — `item.name`, `item.level`. Расхождения не исправляются,
только перечисляются. Записи не сливаются по имени.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "client_extract" / "fresh_catalog" / "catalog.sqlite"
PULSE = ROOT / "data" / "pulse.db"
OUT_DIR = ROOT / "client_extract" / "fresh_catalog"


def ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def client_items(cat: sqlite3.Connection) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for eid, internal, name_ru, fields, icon_path in cat.execute(
        "SELECT id, internal_name, name_ru, fields_json, icon_path FROM entries WHERE section='items'"
    ):
        f = json.loads(fields)
        out[int(eid)] = {
            "internal_name": internal,
            "name": name_ru,
            "level": _int(f.get("level")),
            "quality": f.get("quality"),
            "icon": Path(icon_path).stem if icon_path else None,
        }
    return out


def db_items(pulse: sqlite3.Connection) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for iid, name, level, grade, category, icon in pulse.execute(
        "SELECT id, name, level, grade, category, icon FROM item"
    ):
        out[int(iid)] = {"name": name, "level": level, "grade": grade, "category": category, "icon": icon}
    return out


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def diff_items(ci: dict, di: dict) -> dict:
    only_client = sorted(set(ci) - set(di))
    only_db = sorted(set(di) - set(ci))
    both = sorted(set(ci) & set(di))
    name_diff, level_diff, quality_pairs = [], [], Counter()
    for iid in both:
        c, d = ci[iid], di[iid]
        if c["name"] != d["name"]:
            name_diff.append({"id": iid, "client": c["name"], "db": d["name"]})
        if c["level"] != d["level"]:
            level_diff.append({"id": iid, "client": c["level"], "db": d["level"]})
        quality_pairs[(c["quality"], d["grade"])] += 1
    return {
        "client_unique": len(ci),
        "db_rows": len(di),
        "only_in_client": only_client,
        "only_in_db": only_db,
        "name_differs": name_diff,
        "level_differs": level_diff,
        "quality_to_grade": [{"client": q, "db": g, "count": n} for (q, g), n in sorted(quality_pairs.items(), key=lambda x: -x[1])],
    }


def client_quests(cat: sqlite3.Connection) -> dict[int, dict]:
    out = {}
    for eid, name_ru, fields in cat.execute("SELECT id, name_ru, fields_json FROM entries WHERE section='quests'"):
        f = json.loads(fields)
        out[int(eid)] = {"name": name_ru, "min": _int(f.get("minlevel_permitted")), "max": _int(f.get("maxlevel_permitted"))}
    return out


def db_quests(pulse: sqlite3.Connection) -> dict[int, dict]:
    return {int(i): {"name": n, "min": mn, "max": mx} for i, n, mn, mx in pulse.execute("SELECT id, name, min_level, max_level FROM quest")}


def diff_keyed(c: dict, d: dict) -> dict:
    both = sorted(set(c) & set(d))
    name_diff = [{"id": i, "client": c[i]["name"], "db": d[i]["name"]} for i in both if c[i]["name"] != d[i]["name"]]
    lvl_diff = [{"id": i, "client": [c[i]["min"], c[i]["max"]], "db": [d[i]["min"], d[i]["max"]]}
                for i in both if (c[i]["min"], c[i]["max"]) != (d[i]["min"], d[i]["max"])]
    return {
        "client_count": len(c),
        "db_count": len(d),
        "only_in_client": sorted(set(c) - set(d)),
        "only_in_db": sorted(set(d) - set(c)),
        "name_differs": name_diff,
        "level_differs": lvl_diff,
    }


def client_recipes(cat: sqlite3.Connection) -> dict[int, dict]:
    out = {}
    for eid, fields in cat.execute("SELECT id, fields_json FROM entries WHERE section='recipes'"):
        f = json.loads(fields)
        out[int(eid)] = {"product": f.get("product"), "count": _int(f.get("product_quantity")), "skill": f.get("combineskill")}
    return out


def db_recipes(pulse: sqlite3.Connection) -> dict[int, dict]:
    return {int(i): {"product": int(p) if p is not None else None, "count": c, "profession": pr}
            for i, p, c, pr in pulse.execute("SELECT id, product, count, profession FROM recipe")}


def diff_recipes(c: dict, d: dict, cat_items: dict[int, dict], db_it: dict[int, dict]) -> dict:
    internal_to_id = {str(v["internal_name"]).lower(): k for k, v in cat_items.items() if v["internal_name"]}  # case-insensitive: the recipes write «_30a», the client «_30A»
    both = sorted(set(c) & set(d))
    count_diff = [{"id": i, "client": c[i]["count"], "db": d[i]["count"]} for i in both if c[i]["count"] != d[i]["count"]]
    product_diff = []
    for i in both:
        cp = internal_to_id.get(str(c[i]["product"] or "").lower())
        if cp != d[i]["product"]:
            product_diff.append({"id": i, "client_product": c[i]["product"], "client_item_id": cp, "db_product": d[i]["product"]})
    return {
        "client_count": len(c),
        "db_count": len(d),
        "only_in_client": sorted(set(c) - set(d)),
        "only_in_db": sorted(set(d) - set(c)),
        "count_differs": count_diff,
        "product_differs": product_diff[:200],
        "product_differs_total": len(product_diff),
        "product_unresolved_client": sum(1 for i in c if internal_to_id.get(str(c[i]["product"] or "").lower()) is None),
    }


def counts_by_category(cat: sqlite3.Connection) -> dict[str, int]:
    return dict(cat.execute("SELECT category, COUNT(*) FROM categories GROUP BY category").fetchall())


def db_counts(pulse: sqlite3.Connection) -> dict[str, int]:
    return dict(pulse.execute("SELECT COALESCE(category,'-'), COUNT(*) FROM item GROUP BY category").fetchall())


def client_titles(cat):
    return {int(i) for (i,) in cat.execute("SELECT id FROM entries WHERE section='titles'")}


def db_title_count(pulse):
    return pulse.execute("SELECT COUNT(*) FROM title").fetchone()[0]


def render_md(res: dict) -> str:
    it = res["items"]
    lines = [
        "# Сравнение свежего клиента с `data/pulse.db`",
        "",
        "Создано `tools/compare_fresh_catalog.py`, только чтение. Ключ сравнения — ID. Записи не сливаются по русскому имени.",
        "",
        "## Предметы",
        "",
        f"- Клиент: {it['client_unique']} уникальных ID. `pulse.db`: {it['db_rows']} строк.",
        f"- Только в клиенте: {len(it['only_in_client'])}. Только в `pulse.db`: {len(it['only_in_db'])} → {it['only_in_db']}.",
        f"- Разное русское имя: {len(it['name_differs'])}. Разный уровень: {len(it['level_differs'])}.",
        "",
        "Соответствие `quality` клиента и `grade` БД (количество совпавших ID):",
        "",
        "| quality (клиент) | grade (БД) | Число |",
        "|---|---|---:|",
    ]
    lines += [f"| {r['client']} | {r['db']} | {r['count']} |" for r in it["quality_to_grade"]]
    lines += [""]
    lines += ["### Примеры разного имени (до 30)", ""]
    lines += [f"- {r['id']}: клиент «{r['client']}» / БД «{r['db']}»" for r in it["name_differs"][:30]] or ["- нет"]
    lines += ["", "### Примеры разного уровня (до 30)", ""]
    lines += [f"- {r['id']}: клиент {r['client']} / БД {r['db']}" for r in it["level_differs"][:30]] or ["- нет"]
    for key, title in [("quests", "Задания"), ("recipes", "Рецепты")]:
        r = res[key]
        lines += ["", f"## {title}", "", f"- Клиент: {r['client_count']}. БД: {r['db_count']}."]
        lines += [f"- Только в клиенте: {len(r['only_in_client'])}. Только в БД: {len(r['only_in_db'])}."]
        if key == "quests":
            lines += [f"- Разное имя: {len(r['name_differs'])}. Разный диапазон уровней: {len(r['level_differs'])}."]
            lines += [f"- Пример разного имени: {x['id']}: «{x['client']}» / «{x['db']}»" for x in r["name_differs"][:10]]
        else:
            lines += [f"- Разное количество результата: {len(r['count_differs'])}."]
            lines += [f"- Разный результат (ID предмета): {r['product_differs_total']}. Не найден в клиенте по internal_name: {r['product_unresolved_client']}."]
    lines += ["", "## Категории", "", "| Клиент `categories` | Число |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in res["categories_client"].items()]
    lines += ["", "| БД `item.category` | Число |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in res["categories_db"].items()]
    lines += ["", "## Титулы, питомцы, навыки", "",
              f"- Титулы: клиент {res['titles']['client']}, БД {res['titles']['db']}.",
              f"- Питомцы: клиент {res['pets_client']} (в БД таблицы нет).",
              f"- Навыки: клиент {res['skills_client']}. Дубли ID навыков см. `manifest.json`.",
              ""]
    lines += DECISIONS
    return "\n".join(lines) + "\n"


# what was decided for each disputed field and why (map:45, 07.11.2026); the counts above are recomputed on every run
DECISIONS = """## Решения (map:45)

| Поле / случай | Победивший источник | Причина |
|---|---|---|
| Имя, уровень, грейд предмета | клиент `data/game/items.json.gz` | Свежий клиент; старые значения шли из `watch_items.csv` (сайт) и дропа бестиария, которые раньше стояли первыми. 143 имени и 57 уровней были сайтовыми. |
| Грейд, когда у клиента его нет | клиент `catalog.sqlite` `fields_json.quality` (нижний регистр) | 25 720 предметов были без грейда; значения совпадают с набором `grade`. Один предмет без клиентской записи остался `NULL`. |
| «Временно> …» | клиент + восстановленная «<» | Клиент теряет «<» у двух предметов (100001022, 160003550). Строки «… -> …» не трогаются. |
| Имя, которого нет у клиента | прежний источник | 22 предмета без русской строки в клиенте: имя остаётся из чат-ссылок или дропа. |
| Квестовые предметы 182206878–182206880 | `items.json.gz` | `items.json` и локализация экспорта расходятся («Одушевленный эфир» / «Кусок иджиса»); оба значения видны в таблице выше. Не менялось. |
| Рецепт → результат | `recipe.product` (числовой ID) | 25 «расхождений» были регистром `internal_name` (`_30a` / `_30A`) в сравнении; после сравнения без регистра — 0. |
| ID 160010543 | оставлен, источник — `data/item_names.tsv` | «[Ивент] Конфеты идеального даэва» есть только в именах чат-ссылок; в установленном клиенте нет. Строка без уровня, грейда, значка и карточки; не удаляется молча. |
| Навыки 10729–10732 | первая запись клиента | В XML клиента у этих ID по две записи (Apostle-трансформация и вызов склада/торговца). В `entries` и в `skill` — первая, вторая в `duplicates` экспорта. |
| Повторные ID предметов 125040202, 110900273 | первая запись клиента | Повторы сохранены в `duplicates` экспорта. |
| Оружие / броня / украшения | каталог карточек (`item.category`) | Широкие категории клиента (9 090 / 18 705 / 3 308) включают варианты, тестовые и событийные записи. Все 3 332 / 6 419 / 1 514 видимых ID входят в широкие категории (`CHECKS.md`). |
| Книги умений, стигмы, титулы, питомцы | клиент, с русским именем | Новые разделы: `core/pulse_db/catalog.py` `RULES`. Связь книги и стигмы с навыком — по имени навыка без регистра; неподтверждённая — `NULL`. |
| Значки | `data/icons` (прежние 56×56) + новые из экспорта | Прежние 1 566 не заменены: тот же рисунок (визуальная сверка), другой размер и палитра. Добавлено 1 595 значков предметов, 1 384 навыков (только нужные книгам и стигмам), 149 питомцев. Значка нет у 71 предмета: 22 имени значков не найдены ни в PAK, ни в ресурсах проекта, у части записей имени значка нет вовсе: `icon` = `NULL`, список в `data/icons/fresh_catalog_icons.json`. |
| Выдающие NPC заданий | `data/game` как было | 39 непарных ссылок `quest.giver` из `data/game/report.json` остались как есть, новых связей не создано. |
""".splitlines()


def main(pulse_path: Path = PULSE) -> None:
    cat = ro(CATALOG)
    pulse = ro(pulse_path)
    ci = client_items(cat)
    di = db_items(pulse)
    res = {
        "items": diff_items(ci, di),
        "quests": diff_keyed(client_quests(cat), db_quests(pulse)),
        "recipes": diff_recipes(client_recipes(cat), db_recipes(pulse), ci, di),
        "categories_client": counts_by_category(cat),
        "categories_db": db_counts(pulse),
        "titles": {"client": len(client_titles(cat)), "db": db_title_count(pulse)},
        "pets_client": cat.execute("SELECT COUNT(*) FROM entries WHERE section='pets'").fetchone()[0],
        "skills_client": cat.execute("SELECT COUNT(*) FROM entries WHERE section='skills'").fetchone()[0],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "COMPARISON.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "COMPARISON.md").write_text(render_md(res), encoding="utf-8")
    print("items: client", res["items"]["client_unique"], "db", res["items"]["db_rows"],
          "only_client", len(res["items"]["only_in_client"]), "only_db", res["items"]["only_in_db"])
    print("quests:", res["quests"]["client_count"], res["quests"]["db_count"])
    print("recipes:", res["recipes"]["client_count"], res["recipes"]["db_count"], "count_diff", len(res["recipes"]["count_differs"]))


if __name__ == "__main__":
    import sys

    main(Path(sys.argv[1]) if len(sys.argv) > 1 else PULSE)
