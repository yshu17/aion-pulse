"""The quest pages of aidb.ru as plain rows (map:46): the guide text the client does not hold.

    guide = parse_quest_page(html_text)        # one page -> dict, None when it is not a quest page
    guides = read_guides(Path("downloads/aidb_quests/pages"))   # quest id -> guide

Source: https://aidb.ru/quests/<id>-<slug>/ (the database of Aion 4.0.2); the quest id is the client's. Pure: text in, rows out, no
network. A guide is {name_en, icon, category, race, classes, level, rec_level, repeat, notes, zone: {id, name}, giver, ender,
needs, rewards, title, steps, start}: ``giver`` / ``ender`` are {id, name} of the NPC of the client (the page links /npcs/<id>-…),
``needs`` and ``rewards['items']`` are {id, name, count}, ``steps`` are the walk-through lines, each {text, links} with the
links {kind, id, name} of the page's own (npcs, items, zones, …); ``start`` is the map of the quest's start: {zone, x, y} in
percents of the picture. A field the page does not have is None / [].
"""

from __future__ import annotations

import html
import re
from pathlib import Path

TAG = re.compile(r"<[^>]+>")
LINK = re.compile(r'<a\s+[^>]*href="/(npcs|items|zones|quests|skills|titles|pets|sets)/(\d+)-[^"]*"[^>]*>(.*?)</a>', re.S)


def _text(fragment: str) -> str:
    return html.unescape(TAG.sub("", fragment)).replace("\xa0", " ").strip()


def _int(value) -> int | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _section(page: str, name: str) -> str:
    found = re.search(rf'<section class="card" id="{name}">(.*?)</section>', page, re.S)
    return found.group(1) if found else ""


def _rows(section: str) -> list[tuple[str, str]]:
    """(label, raw html of the value) of a «props» table; a row without a label has the label ''."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", section, re.S):
        head = re.search(r"<th>(.*?)</th>\s*<td>(.*?)</td>", row, re.S)
        if head:
            out.append((_text(head.group(1)).rstrip(":"), head.group(2)))
        else:
            cell = re.search(r"<td[^>]*>(.*?)</td>", row, re.S)
            if cell and _text(cell.group(1)):
                out.append(("", cell.group(1)))
    return out


def _items(raw: str) -> list[dict]:
    """The items of a value: «<a href="/items/<id>-…">Name</a>(3)»."""
    out = []
    for found in re.finditer(r'href="/items/(\d+)-[^"]*"[^>]*>(.*?)</a>\s*(?:\((\d+)\))?', raw, re.S):
        out.append({"id": int(found.group(1)), "name": _text(found.group(2)), "count": int(found.group(3) or 1)})
    return out


def _npc(raw: str) -> dict | None:
    found = re.search(r'href="/npcs/(\d+)-[^"]*"[^>]*>(.*?)</a>', raw, re.S)
    return {"id": int(found.group(1)), "name": re.sub(r"\s*\([^)]*\)\s*$", "", _text(found.group(2)))} if found else None


def _steps(section: str) -> list[dict]:
    rich = re.search(r'<div class="rich">(.*?)</div>', section, re.S)
    if not rich:
        return []
    steps = []
    for line in re.split(r"<br\s*/?>", rich.group(1)):
        text = re.sub(r"^\s*[-–•]\s*", "", _text(line))
        if text:
            links = [{"kind": kind, "id": int(ident), "name": _text(label)} for kind, ident, label in LINK.findall(line)]
            steps.append({"text": text, "links": links})
    return steps


def parse_quest_page(page: str) -> dict | None:
    head = re.search(r'<div class="obj-head">\s*<img src="/static/img/(\w+)\.[^"]*"[^>]*alt="([^"]*)"', page)
    if not head or 'id="info"' not in page:
        return None
    name_en = re.search(r'<span class="name-en">(.*?)</span>', page, re.S)
    guide: dict = {
        "name_en": _text(name_en.group(1)) if name_en else None, "icon": head.group(1), "category": html.unescape(head.group(2)),
        "race": None, "classes": [], "level": None, "rec_level": None, "repeat": None, "notes": [], "zone": None, "giver": None,
        "ender": None, "needs": [], "rewards": {"exp": None, "gold": None, "abyss": None, "items": [], "choice": []},
        "title": None, "steps": _steps(_section(page, "walkthrough")), "start": None,
    }
    for label, raw in _rows(_section(page, "info")):
        value = _text(raw)
        if label == "Раса":
            guide["race"] = value
        elif label == "Для классов":
            guide["classes"] = [c.strip() for c in value.split(",") if c.strip()]
        elif label == "Уровень":
            guide["level"] = _int(value)
        elif label == "Рек. уровень":
            guide["rec_level"] = _int(value)
        elif label == "Возможно повторить":
            guide["repeat"] = value
        elif label == "Локация":
            zone = re.search(r'href="/zones/(\d+)-[^"]*"[^>]*>(.*?)</a>', raw, re.S)
            guide["zone"] = {"id": zone.group(1), "name": _text(zone.group(2))} if zone else {"id": None, "name": value}
        elif label == "Квест начинает":
            guide["giver"] = _npc(raw)
        elif label == "Квест заканчивает":
            guide["ender"] = _npc(raw)
        elif label.startswith("Предметы необходимые"):
            guide["needs"] = _items(raw)
        elif label == "" and value:
            guide["notes"].append(value)
    rewards = guide["rewards"]
    for label, raw in _rows(_section(page, "rewards")):
        if label == "Опыт":
            rewards["exp"] = _int(raw)
        elif label == "Кинары":
            rewards["gold"] = _int(raw)
        elif label == "Очки Бездны":
            rewards["abyss"] = _int(raw)
        elif label == "Титул":
            guide["title"] = _text(raw)
        elif label == "Награда":
            rewards["items"] += _items(raw)
        elif "выбор" in label.lower():
            rewards["choice"] += _items(raw)
    marker = re.search(r'<figure class="loc-figure" id="map-(\d+)".*?class="marker" style="left:([\d.]+)%;top:([\d.]+)%', _section(page, "start"), re.S)
    if marker:
        guide["start"] = {"zone": marker.group(1), "x": float(marker.group(2)), "y": float(marker.group(3))}
    return guide


def read_guides(pages: Path | None) -> dict[int, dict]:
    """Every page of the folder (<quest id>.html) as a guide, by quest id; pages that do not parse are left out."""
    out: dict[int, dict] = {}
    if not pages or not pages.is_dir():
        return out
    for path in sorted(pages.glob("*.html"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        if not path.stem.isdigit():
            continue
        guide = parse_quest_page(path.read_text(encoding="utf-8", errors="replace"))
        if guide:
            out[int(path.stem)] = guide
    return out
