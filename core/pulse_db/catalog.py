"""The client's catalog for data/pulse.db (map:45): skills, skill books, stigmas, titles, pets, and the ten sections of «База данных».

    client = read_client(Path("client_extract/fresh_catalog/catalog.sqlite"), icons=Path("data/icons"))
    entries = section_entries(items, quests, recipes, client)   # [(section, entity_id)], the visible rows of each section

``read_client`` reads the fresh export of the installed client (tools/export_fresh_catalog.py) read-only and returns plain rows:
ids as int, links by id, NULL (None) where the client does not confirm a link. A picture is a path of ``icons`` without «.png»
(«skills/…», «pets/…») and only when the file is there. Nothing here guesses: a skill book whose skill the client lacks keeps
``skill_id`` None and its ``skill`` name.

The sections (``SECTIONS``): key, title of the menu, entity table, and the rule of what the section lists (``RULES``).
The full client sets stay in client_extract/; the database holds what the list, the card, the search and the links need.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# key, the menu's title, the table its ids point to
SECTIONS = (
    ("items", "Предметы", "item"), ("weapons", "Оружие", "item"), ("armour", "Броня", "item"), ("jewels", "Украшения", "item"),
    ("skill_books", "Книги умений", "item"), ("stigmas", "Стигмы", "item"), ("titles", "Титулы", "title"),
    ("pets", "Питомцы", "pet"), ("quests", "Задания", "quest"), ("recipes", "Рецепты", "recipe"),
)
ARMOUR = ("Ткань", "Кожа", "Кольчуга", "Лата")
RULES = {
    "items": "every row of item (all the client's items and the older lists' ids)",
    "weapons": "item.category = 'Оружие': the catalog of item cards (data/watch_items.csv); the client's weapon_type is wider (variants, tests)",
    "armour": "item.category in Ткань, Кожа, Кольчуга, Лата: the catalog of item cards; shields and headgear are their own kinds",
    "jewels": "item.category = 'Украшения': the catalog of item cards",
    "skill_books": "the client's skill books (the export's category «skill_books», items with skill_to_learn) with a Russian name",
    "stigmas": "the client's stigma stones (the export's category «stigmas») with a Russian name",
    "titles": "every client title with a Russian name",
    "pets": "every client pet with a Russian name",
    "quests": "every row of quest",
    "recipes": "every row of recipe",
}
# the class columns of an item record: the value is the level the class may use it from, «0» is «not this class»
CLASSES = ("warrior", "fighter", "knight", "scout", "assassin", "ranger", "mage", "wizard", "elementalist", "priest", "cleric", "chanter")
# title_race of client_titles: 0 Элийцы, 1 Асмодиане, 2 both (light_title* are 0, dark_title* are 1)
TITLE_RACE = {"0": "pc_light", "1": "pc_dark", "2": "pc_light,pc_dark"}


def _key(name: str) -> str:
    return name.casefold().replace("ё", "е")


def _int(value) -> int | None:
    text = str(value if value is not None else "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


def _icon(icon_path: str | None, folder: str, icons: Path | None) -> str | None:
    """«icons/skills/x.png» of the export → «skills/x» when data/icons holds it, else None."""
    if not icon_path or not icons:
        return None
    stem = Path(icon_path).stem.lower()
    rel = f"{folder}/{stem}" if folder else stem
    return rel if (icons / f"{rel}.png").is_file() else None


def read_client(path: Path | None, icons: Path | None = None) -> dict:
    """Every row the new tables need, from the export; empty lists when there is no export."""
    out = {"skill": [], "skill_book": [], "stigma": [], "title": [], "pet": [], "item_icon": {}, "category": {},
           "item_internal": {}, "quest_fields": {}}
    if not path or not path.is_file():
        return out
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"entries", "categories"} <= tables:  # not an export of tools/export_fresh_catalog.py
            return out
        category: dict[str, set[int]] = {}
        for cat, section, eid in db.execute("SELECT category, section, id FROM categories"):
            category.setdefault(cat, set()).add(int(eid))
        out["category"] = category
        stigma_skills = category.get("stigma_skills", set())

        skills_by_name: dict[str, int] = {}
        for eid, internal, name, desc, icon_path in db.execute(
                "SELECT id, internal_name, name_ru, description_ru, icon_path FROM entries WHERE section = 'skills' ORDER BY CAST(id AS INTEGER)"):
            sid = int(eid)
            skills_by_name.setdefault((internal or "").lower(), sid)
            name = name or ""
            out["skill"].append((sid, internal or "", name, _key(name), desc or None, _icon(icon_path, "skills", icons),
                                 int(sid in stigma_skills)))

        def skill_id(internal) -> int | None:
            return skills_by_name.get(str(internal or "").lower())

        books = category.get("skill_books", set())
        stigmas = category.get("stigmas", set())
        for eid, internal, name, icon_path, fields in db.execute(
                "SELECT id, internal_name, name_ru, icon_path, fields_json FROM entries WHERE section = 'items'"):
            iid = int(eid)
            out["item_icon"][iid] = _icon(icon_path, "", icons)
            if internal:
                out["item_internal"].setdefault(internal.lower(), iid)
            if iid not in books and iid not in stigmas:
                continue
            f = json.loads(fields)
            classes = {c: int(f[c]) for c in CLASSES if _int(f.get(c))}
            if iid in books:
                skill = f.get("skill_to_learn")
                out["skill_book"].append((iid, skill or None, skill_id(skill), json.dumps(classes, sort_keys=True) if classes else None,
                                          int(bool(name))))
            if iid in stigmas:
                skill = f.get("gain_skill1")
                needs = [[f[f"require_skill{n}"], skill_id(f[f"require_skill{n}"]), _int(f.get(f"require_skill{n}_lv"))]
                         for n in (1, 2) if f.get(f"require_skill{n}")]
                out["stigma"].append((iid, skill or None, skill_id(skill), _int(f.get("gain_level1")),
                                      json.dumps(needs, ensure_ascii=False) if needs else None, int(bool(name))))

        out["quest_fields"] = {int(eid): json.loads(fields) for eid, fields in db.execute(
            "SELECT id, fields_json FROM entries WHERE section = 'quests'")}

        for eid, internal, name, desc, fields in db.execute(
                "SELECT id, internal_name, name_ru, description_ru, fields_json FROM entries WHERE section = 'titles'"):
            f = json.loads(fields)
            bonus = [b.get("bonus_attr") for b in ((f.get("bonus_attrs") or {}).get("data") or []) if isinstance(b, dict)]
            stats = {"bonus": [b for b in bonus if b], "priority": _int(f.get("title_priority")), "type": _int(f.get("title_type")),
                     "location": f.get("title_location")}
            name = name or ""
            out["title"].append((int(eid), name, _key(name), desc or None, TITLE_RACE.get(str(f.get("title_race"))),
                                 json.dumps(stats, ensure_ascii=False, sort_keys=True)))

        for eid, internal, name, desc, icon_path, fields in db.execute(
                "SELECT id, internal_name, name_ru, description_ru, icon_path, fields_json FROM entries WHERE section = 'pets'"):
            f = json.loads(fields)
            funcs = [f[k] for k in sorted(f) if k.startswith("func_type") and not k.startswith("func_type_name") and f[k]]
            name = name or ""
            out["pet"].append((int(eid), internal or "", name, _key(name), desc or None, json.dumps(funcs) if funcs else None,
                               _icon(icon_path, "pets", icons)))
    finally:
        db.close()
    for table in ("skill", "skill_book", "stigma", "title", "pet"):
        out[table].sort()
    return out


def section_entries(items: dict[int, dict], quests: list[tuple], recipes: list[tuple], client: dict) -> list[tuple[str, int]]:
    """(section, entity id) for each visible row, by RULES; ids of a section once."""
    rows: set[tuple[str, int]] = set()
    for iid, r in items.items():
        rows.add(("items", iid))
        if r.get("category") == "Оружие":
            rows.add(("weapons", iid))
        elif r.get("category") in ARMOUR:
            rows.add(("armour", iid))
        elif r.get("category") == "Украшения":
            rows.add(("jewels", iid))
    rows.update(("skill_books", r[0]) for r in client["skill_book"] if r[4] and r[0] in items)
    rows.update(("stigmas", r[0]) for r in client["stigma"] if r[5] and r[0] in items)
    rows.update(("titles", r[0]) for r in client["title"] if r[1])
    rows.update(("pets", r[0]) for r in client["pet"] if r[2])
    rows.update(("quests", r[0]) for r in quests)
    rows.update(("recipes", r[0]) for r in recipes)
    return sorted(rows)
