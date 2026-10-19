"""Bestiary data hygiene without Tk or files: which records are technical, and where a record without spawn
points can take them from.

    technical_name(name) -> bool                 test/internal names: «Test_…», «BAb1_…_lv50», English only, 3+ digits glued to letters
    plan(rows) -> (donors, service)              rows are dicts: id, name, level, category, points, drops, profile, sig
                                                 (sig: hashable content of the record: spawn points, goods, drops)
        donors:  {npc id: donor npc id}          a record with no points takes them from a same-named record, or from the
                                                 base of «Новые характеристики …» (compared by word stems: Валона = Валон)
        service: set of npc ids                  technical names and duplicates (same name, level and category as a better
                                                 record with identical content, so no spawn place, drop or ware is lost)
"""

from __future__ import annotations

import re

_LATIN = re.compile(r"[A-Za-z]")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_DIGIT_RUN = re.compile(r"[^\W\d_]\d{3,}|\d{3,}[^\W\d_]")  # digits glued to letters: «NPC123», «Страж123»
NEW_STATS = "новые характеристики "


def technical_name(name: str) -> bool:
    text = name.strip()
    if not text or not any(ch.isalpha() for ch in text):
        return True  # empty or digits and punctuation only
    if "_" in text or "test" in text.casefold() or _DIGIT_RUN.search(text):
        return True
    return bool(_LATIN.search(text)) and not _CYRILLIC.search(text)  # English names


def stem_key(name: str) -> tuple[str, ...]:
    """Word stems of a name, order-free, so «хранителя Валона» and «Хранитель Валон» agree."""
    words = re.findall(r"[а-яёa-z0-9]+", name.casefold())
    return tuple(sorted(word[:-1] if len(word) > 3 and word[-1] in "аяуюыиеоьй" else word for word in words))


def plan(rows: list[dict]) -> tuple[dict[str, str], set[str]]:
    with_points = [row for row in rows if row["points"] and not technical_name(row["name"])]
    by_name: dict[str, dict] = {}
    by_stem: dict[tuple[str, ...], dict] = {}
    for row in sorted(with_points, key=lambda item: item["points"]):  # the richest record wins
        by_name[row["name"].casefold()] = row
        by_stem[stem_key(row["name"])] = row
    donors: dict[str, str] = {}
    points = {row["id"]: row["points"] for row in rows}
    sigs = {row["id"]: row["sig"] for row in rows}
    for row in rows:
        if row["points"] or technical_name(row["name"]):
            continue
        key = row["name"].casefold()
        donor = by_name.get(key)
        if donor is None and key.startswith(NEW_STATS):
            donor = by_stem.get(stem_key(row["name"][len(NEW_STATS):]))
        if donor and donor["id"] != row["id"]:
            donors[row["id"]] = donor["id"]
            points[row["id"]] = donor["points"]
            sigs[row["id"]] = (donor["sig"][0], *row["sig"][1:])  # own wares and drops, the donor's places
    service = {row["id"] for row in rows if technical_name(row["name"])}
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        if row["id"] not in service:
            groups.setdefault((row["name"].casefold(), str(row["level"]), row["category"], sigs[row["id"]]), []).append(row)
    for group in groups.values():
        group.sort(key=lambda row: (row["profile"], points[row["id"]], row["drops"]), reverse=True)
        best = group[0]
        for row in group[1:]:
            service.add(row["id"])
    return donors, service
