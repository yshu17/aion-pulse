"""Collect the stat buffs of food and drinks from data/pulse.db into data/consumables/consumables.json.

The data of «Расходники» for the gear calculator's «Усиление» (tasks of 25.11.2026). Source: the item cards (item.spec,
deflated with meta «spec_dict») of the items 160000000-160019999; a buff is a card whose text names «stat +N» and how long
it lasts. Every «+N» of such a card must be a stat of STATS: an unknown one stops the build (nothing is dropped quietly).

Format: {"source": ..., "items": [{"id", "ids", "name", "kind": "food"|"drink"|"candy", "grade", "icon",
"item_level", "use_level", "minutes", "stats": [[stat name as the game writes it, number, is percent], ...],
"unknown": [bonuses the client gives no number for]}]}
  kind        from the client's picture (dish, drink, tea, juice, bottle, candy); the game's own «Тип» says «Еда» for juices too
  item_level  the item's level in the client; NOT the level needed to use it (items of level 60 are used from 50)
  use_level   «Можно использовать с N-го уровня» where the site's card says it (data/item_specs.json.gz), else null
Items of one name with one effect are one entry; "ids" keeps them all.

Usage: python tools/build_consumables.py
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "consumables" / "consumables.json"
FIRST, LAST = 160000000, 160019999

# the stats the cards of food and drinks name, as the game writes them
STATS = ("Восст. HP", "Восст. MP", "Макс. HP", "Макс. MP", "Физ. атака", "Физ. крит.", "Физ. защита", "Маг. крит.", "Маг. точность",
         "Маг. защита", "Сила магии", "Точность", "Уклонение", "Защ. от стихий", "Скорость атаки", "Скор. полёта", "Скорость")
# other words of some cards (the candies) for the same stats: one name each, so their sum is one line
ALIASES = {"Атака": "Физ. атака", "Точн. маг.": "Маг. точность", "Скор. атаки": "Скорость атаки", "Скор. движ.": "Скорость",
           "Скор. магии": "Скорость магии"}
BY_NAME = sorted((*STATS, *ALIASES), key=len, reverse=True)  # «Маг. точность» before «Точность», «Физ. атака» before «Атака»
BONUS = re.compile(r"\+\s?(\d+)(%?)")
NO_NUMBER = re.compile(r"(?:^|(?<=\. ))([А-ЯЁ][^.+%]*?)%?\s*\+(?=\.|$)")
TIME = re.compile(r"(?:Время действия:|В течение)\s*(\d+)\s*(мин|ч)")


class UnknownStat(ValueError):
    """A «+N» whose name is none of STATS."""


def clean(text: str) -> str:
    """The same repairs the program makes before showing a card (launcher/src/core/items/cardText.ts)."""
    text = text.replace("ElementalDefendAll", "Защ. от стихий")
    return re.sub(r"(?<=[A-Za-zА-Яа-яЁё.])%(?= \+)", "", text)


def _stat_before(head: str) -> str:
    head = head.rstrip()
    if head.endswith("Физ. крит"):
        head += "."
    for name in BY_NAME:
        if head.endswith(name):
            return ALIASES.get(name, name)
    raise UnknownStat(head[-40:])


def parse_card(text: str) -> dict | None:
    """{"stats": [[name, number, percent]], "unknown": [name], "minutes": n}, or None when it is not a lasting stat buff."""
    text = clean(text)
    time = TIME.search(text)
    bonuses = list(BONUS.finditer(text))
    if not time or not bonuses:
        return None
    stats = [[_stat_before(text[: m.start()]), int(m.group(1)), m.group(2) == "%"] for m in bonuses]
    return {"stats": stats, "unknown": [m.group(1).strip() for m in NO_NUMBER.finditer(text)],
            "minutes": int(time.group(1)) * (60 if time.group(2) == "ч" else 1)}


def kind_of(icon: str) -> str:
    icon = icon.lower()
    if "candy" in icon:
        return "candy"
    return "drink" if any(word in icon for word in ("drink", "tea", "juice", "bottle")) else "food"


def use_level(card: dict | None) -> int | None:
    found = re.search(r"использовать с (\d+)-го уровня", json.dumps(card or {}, ensure_ascii=False))
    return int(found.group(1)) if found else None


def merge_same(items: list[dict]) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for item in sorted(items, key=lambda x: x["id"]):
        key = (item["name"], item["minutes"], json.dumps([item["stats"], item["unknown"]], ensure_ascii=False))
        if key in merged:
            merged[key]["ids"].append(item["id"])
            merged[key]["use_level"] = merged[key]["use_level"] or item["use_level"]
        else:
            merged[key] = {**item, "ids": [item["id"]]}
    return list(merged.values())


def collect(db_path: Path, site_path: Path) -> list[dict]:
    site = json.loads(gzip.decompress(site_path.read_bytes()).decode("utf-8")) if site_path.is_file() else {}
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    dictionary = db.execute("SELECT value FROM meta WHERE key = 'spec_dict'").fetchone()[0]
    found, unknown = [], []
    for row in db.execute("SELECT id, name, grade, level, icon, spec FROM item WHERE id BETWEEN ? AND ? AND spec IS NOT NULL", (FIRST, LAST)):
        unpacker = zlib.decompressobj(zdict=dictionary)
        card = json.loads((unpacker.decompress(row["spec"]) + unpacker.flush()).decode("utf-8"))
        text = re.sub(r"\s+", " ", " ".join(b.get("text", "") for b in card.get("blocks", []) if b.get("kind") == "text")).strip()
        # a transformation («превратиться … на 5 минут. Макс. HP +15600») is not food: it has no «Время действия»
        try:
            buff = parse_card(text)
        except UnknownStat as error:
            unknown.append((row["id"], row["name"], str(error)))
            continue
        if buff:
            crawled = site.get(str(row["id"]))
            found.append({"id": row["id"], "name": row["name"], "kind": kind_of(row["icon"] or ""), "grade": row["grade"] or "",
                          "icon": row["icon"] or "", "item_level": row["level"] or 0,
                          "use_level": use_level(json.loads(crawled) if isinstance(crawled, str) else crawled), **buff})
    db.close()
    if unknown:
        raise UnknownStat(f"{len(unknown)} cards with a bonus of an unknown name, e.g. {unknown[:3]}")
    return sorted(merge_same(found), key=lambda x: (x["kind"], x["name"], x["id"]))


def main() -> None:
    items = collect(ROOT / "data" / "pulse.db", ROOT / "data" / "item_specs.json.gz")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "data/pulse.db item cards; use_level: data/item_specs.json.gz (tools/build_consumables.py)",
                               "items": items}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    print(f"{len(items)} buffs {counts}, with use_level {sum(1 for i in items if i['use_level'])}, "
          f"with an unknown bonus {sum(1 for i in items if i['unknown'])} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
