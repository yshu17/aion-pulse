"""Check a built data/pulse.db against the fresh client export (map:45, step 5). Read-only.

    python tools/check_pulse_db.py [data/pulse.db] [--before old.db]

Writes client_extract/fresh_catalog/CHECKS.md and CHECKS.json: integrity, schema, the ten sections and their rule, unique ids,
every link (skill books, stigmas, recipes, sections), the pictures' files, a few ids side by side with the client's record,
the quests' givers the game data could not pair (no false links), and, with --before, the row counts of the older tables.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRESH = ROOT / "client_extract" / "fresh_catalog"
ICONS = ROOT / "data" / "icons"
SAMPLE = {"item": [100001447, 169500001, 140000001, 152020049, 100001022], "title": [1], "pet": [900161]}


def ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def one(db, sql, *args):
    return db.execute(sql, args).fetchone()[0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", nargs="?", type=Path, default=ROOT / "data" / "pulse.db")
    parser.add_argument("--before", type=Path)
    args = parser.parse_args(argv)
    db, cat = ro(args.db), ro(FRESH / "catalog.sqlite")
    r: dict = {"db": str(args.db), "integrity": one(db, "PRAGMA integrity_check"), "user_version": one(db, "PRAGMA user_version")}

    r["sections"] = [dict(zip(("key", "title", "count", "entries", "rule"), row)) for row in db.execute(
        "SELECT s.key, s.title, s.count, (SELECT count(*) FROM db_section_entry e WHERE e.section = s.key), s.rule "
        "FROM db_section s ORDER BY s.ord")]
    # the catalog's lists against the client's own wide categories
    wide = {"weapons": "weapons", "armour": "armor", "jewels": "jewelry", "skill_books": "skill_books", "stigmas": "stigmas"}
    client_cat = {}
    for c, i in cat.execute("SELECT category, id FROM categories WHERE section = 'items'"):
        client_cat.setdefault(c, set()).add(int(i))
    r["visible_vs_client"] = {}
    for key, c in wide.items():
        ids = {i for (i,) in db.execute("SELECT entity_id FROM db_section_entry WHERE section = ?", (key,))}
        r["visible_vs_client"][key] = {"listed": len(ids), "client_category": len(client_cat.get(c, ())),
                                       "listed_in_client_category": len(ids & client_cat.get(c, set())),
                                       "listed_outside": sorted(ids - client_cat.get(c, set()))[:20]}

    r["links"] = {
        "skill_book_without_skill": one(db, "SELECT count(*) FROM skill_book WHERE skill_id IS NULL"),
        "skill_book_broken": one(db, "SELECT count(*) FROM skill_book b LEFT JOIN skill s ON s.id = b.skill_id WHERE b.skill_id IS NOT NULL AND s.id IS NULL"),
        "skill_book_not_item": one(db, "SELECT count(*) FROM skill_book b LEFT JOIN item i ON i.id = b.item_id WHERE i.id IS NULL"),
        "stigma_without_skill": one(db, "SELECT count(*) FROM stigma WHERE skill_id IS NULL"),
        "stigma_broken": one(db, "SELECT count(*) FROM stigma g LEFT JOIN skill s ON s.id = g.skill_id WHERE g.skill_id IS NOT NULL AND s.id IS NULL"),
        "recipe_product_not_item": one(db, "SELECT count(*) FROM recipe r LEFT JOIN item i ON i.id = r.product WHERE r.product IS NOT NULL AND i.id IS NULL"),
        "recipe_part_not_item": one(db, "SELECT count(*) FROM recipe_part p LEFT JOIN item i ON i.id = p.item_id WHERE i.id IS NULL"),
        "section_entry_broken": sum(one(db, f"SELECT count(*) FROM db_section_entry e LEFT JOIN {t} x ON x.id = e.entity_id "
                                            f"WHERE e.section IN (SELECT key FROM db_section WHERE entity = ?) AND x.id IS NULL", t)
                                    for t in ("item", "title", "pet", "quest", "recipe")),
    }
    r["links"]["skill_book_without_skill_names"] = [n for (n,) in db.execute(
        "SELECT DISTINCT skill FROM skill_book WHERE skill_id IS NULL ORDER BY skill LIMIT 30")]
    r["links"]["stigma_without_skill_names"] = [n for (n,) in db.execute(
        "SELECT DISTINCT coalesce(skill, '(none)') FROM stigma WHERE skill_id IS NULL ORDER BY 1 LIMIT 30")]

    def missing(sql, folder=""):
        rows = db.execute(sql).fetchall()
        lost = [i for i, icon in rows if icon and not (ICONS / f"{icon}.png").is_file()]
        return {"with_picture": sum(1 for _, icon in rows if icon), "without_picture": sum(1 for _, icon in rows if not icon),
                "file_missing": len(lost), "file_missing_ids": lost[:20]}
    r["pictures"] = {"item": missing("SELECT id, icon FROM item"), "skill": missing("SELECT id, icon FROM skill"),
                     "pet": missing("SELECT id, icon FROM pet")}

    titles = db.execute("SELECT t.race, count(*) FROM title t GROUP BY t.race").fetchall()
    internal = {int(i): n for i, n in cat.execute("SELECT id, internal_name FROM entries WHERE section = 'titles'")}
    by_race = {}
    for tid, race in db.execute("SELECT id, race FROM title"):
        prefix = (internal.get(tid) or "").split("_")[0].lower()
        by_race.setdefault(f"{race}", {}).setdefault(prefix, 0)
        by_race[f"{race}"][prefix] += 1
    r["titles"] = {"by_race": titles, "race_by_name_prefix": by_race}

    r["samples"] = []
    for iid in SAMPLE["item"]:
        row = db.execute("SELECT id, name, level, grade, category, icon FROM item WHERE id = ?", (iid,)).fetchone()
        src = cat.execute("SELECT name_ru, fields_json, icon_path FROM entries WHERE section = 'items' AND id = ?", (str(iid),)).fetchone()
        f = json.loads(src[1]) if src else {}
        extra = {}
        for table in ("skill_book", "stigma"):
            link = db.execute(f"SELECT skill, skill_id FROM {table} WHERE item_id = ?", (iid,)).fetchone()
            if link:
                extra[table] = {"skill": link[0], "skill_id": link[1],
                                "skill_name": one(db, "SELECT name FROM skill WHERE id = ?", link[1]) if link[1] else None}
        r["samples"].append({"id": iid, "db": row, "client": {"name": src[0] if src else None, "level": f.get("level"),
                             "quality": f.get("quality"), "icon": src[2] if src else None}, **extra})
    for tid in SAMPLE["title"]:
        r["samples"].append({"title": db.execute("SELECT * FROM title WHERE id = ?", (tid,)).fetchone(),
                             "client": cat.execute("SELECT name_ru, description_ru FROM entries WHERE section='titles' AND id = ?", (str(tid),)).fetchone()})
    for pid in SAMPLE["pet"]:
        r["samples"].append({"pet": db.execute("SELECT * FROM pet WHERE id = ?", (pid,)).fetchone(),
                             "client": cat.execute("SELECT name_ru, icon_path FROM entries WHERE section='pets' AND id = ?", (str(pid),)).fetchone()})

    report = json.loads((ROOT / "data" / "game" / "report.json").read_text(encoding="utf-8"))
    npc_ids = {i for (i,) in db.execute("SELECT id FROM npc")}
    unpaired = [(q, g) for q, g in db.execute("SELECT id, giver FROM quest WHERE giver IS NOT NULL") if g not in npc_ids]
    unpaired += [(q, e) for q, e in db.execute("SELECT id, ender FROM quest WHERE ender IS NOT NULL") if e not in npc_ids]
    r["quest_npcs"] = {"report_broken_links": report.get("broken_links"), "quest_links_to_no_npc": len(unpaired),
                       "examples": unpaired[:10],
                       "givers_null": one(db, "SELECT count(*) FROM quest WHERE giver IS NULL"),
                       "enders_null": one(db, "SELECT count(*) FROM quest WHERE ender IS NULL")}

    if args.before:
        old = ro(args.before)
        tables = [t for (t,) in old.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        r["older_tables"] = {t: [one(old, f"SELECT count(*) FROM {t}"), one(db, f"SELECT count(*) FROM {t}")] for t in tables}

    (FRESH / "CHECKS.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    md = ["# Проверка `data/pulse.db` (map:45, пункт 5)", "",
          f"`python tools/check_pulse_db.py` — integrity `{r['integrity']}`, `user_version` {r['user_version']}.", "",
          "## Разделы", "", "| Раздел | В меню | Строк | Правило |", "|---|---:|---:|---|"]
    md += [f"| {s['title']} | {s['count']} | {s['entries']} | {s['rule']} |" for s in r["sections"]]
    md += ["", "## Видимый список против широкой клиентской категории", "", "| Раздел | В списке | Категория клиента | Из них в категории |", "|---|---:|---:|---:|"]
    md += [f"| {k} | {v['listed']} | {v['client_category']} | {v['listed_in_client_category']} |" for k, v in r["visible_vs_client"].items()]
    md += ["", "## Связи", ""] + [f"- {k}: {v}" for k, v in r["links"].items()]
    md += ["", "## Значки", ""] + [f"- {k}: {v}" for k, v in r["pictures"].items()]
    md += ["", "## Титулы: сторона", "", f"- {r['titles']}"]
    md += ["", "## Ручная сверка", ""] + [f"- {json.dumps(s, ensure_ascii=False, default=list)}" for s in r["samples"]]
    md += ["", "## NPC заданий", "", f"- {json.dumps(r['quest_npcs'], ensure_ascii=False, default=list)}"]
    if "older_tables" in r:
        md += ["", "## Прежние таблицы (до → после)", ""] + [f"- {t}: {a} → {b}" for t, (a, b) in r["older_tables"].items()]
    (FRESH / "CHECKS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("integrity", "user_version", "links", "pictures", "quest_npcs")}, ensure_ascii=False, default=list)[:3000])
    print(json.dumps(r["visible_vs_client"], ensure_ascii=False)[:1500])
    print(json.dumps(r["titles"], ensure_ascii=False))
    if "older_tables" in r:
        print("older tables changed:", {t: v for t, v in r["older_tables"].items() if v[0] != v[1]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
