"""The card of a piece of equipment (``item.spec``) made from the game client's own numbers.

The crawl of the third-party site has a card with stats for a few thousand items; the client has the numbers of every weapon,
armour piece, jewel and wing. This module turns such a record into the same JSON shape the crawl's cards have, with the site's
wording (checked against its cards: «Атака», «Скор. атаки», «Точн. маг.», «Физ. защита», «Маг. сопр.» …), so the launcher
draws it with the code it already has.

    spec = gear_spec(name="Орихалковый меч", grade="common", fields={<the client's item fields>}, description="")
    # -> {"name": …, "grade": "common", "blocks": [{"kind": "pairs", "rows": [["Тип", "Меч"]]},
    #     {"kind": "warning", "text": "Можно использовать с 45-го уровня."}, {"kind": "hr"},
    #     {"kind": "grid", "pairs": [["Атака", "115-141"], ["Скор. атаки", "1.4"], …], "dim": False}, {"kind": "hr"},
    #     {"kind": "grid", "pairs": [["Физ. крит", "+19"]], "dim": False}]}
    # -> None for an item that is not worn or has no numbers

Base stats come from the client's own fields (min_damage … dodge), bonus stats from ``bonus_attrN`` («critical 19»,
«flyspeed 10%»). A bonus key the site's wording does not cover is left out, never shown raw. Pure.
"""

from __future__ import annotations

import re

from core.pulse_db.client_spec import FLAG_LINES
from core.pulse_db.gear import stat_line

WEAPON_TYPES = {"1h_sword": "Меч", "1h_dagger": "Кинжал", "1h_mace": "Булава", "2h_sword": "Двуручный меч",
                "2h_polearm": "Копье", "2h_staff": "Посох", "bow": "Лук", "2h_book": "Гримуар", "2h_orb": "Орб"}
ARMOUR_TYPES = {"robe": "Тканая броня", "leather": "Кожаная броня", "chain": "Кольчужная броня", "plate": "Латная броня"}

# the client's field -> the site's line, in the site's order. «Атака» is min_damage-max_damage, «Скор. атаки» seconds.
BASE = (("magical_skill_boost", "Сила магии"), ("attack_delay", "Скор. атаки"), ("magical_hit_accuracy", "Точн. маг."),
        ("hit_accuracy", "Точность"), ("critical", "Ф. крит."), ("parry", "Парир."), ("physical_defend", "Физ. защита"),
        ("magical_resist", "Маг. сопр."), ("dodge", "Уклонение"), ("block", "Блок щитом"))

# the client's bonus stat key (lower case) -> the site's line in the bonus block
BONUS = {
    "maxhp": "Макс. HP", "maxmp": "Макс. MP", "concentration": "Концентрация", "phyattack": "Физ. атака",
    "magicalskillboost": "Сила магии", "critical": "Физ. крит", "pvpdefendratio": "Защита в ПвП", "hitaccuracy": "Точность",
    "physicaldefend": "Физ. защита", "magicalresist": "Маг. защита", "pvpattackratio": "Урон в ПвП", "dodge": "Уклонение",
    "maxfp": "Время полета", "attackdelay": "Скорость атаки", "magicalhitaccuracy": "Маг. точность", "flyspeed": "Скор. полёта",
    "boosthate": "Агрессия", "block": "Блок щитом", "speed": "Скорость", "magicalcritical": "Маг. крит.",
    "elementaldefendfire": "Защ. от огня", "elementaldefendearth": "Защ. от земли", "elementaldefendwater": "Защ. от воды",
    "elementaldefendair": "Защ. от воздуха", "healskillboost": "Сила исцеления", "boostcastingtime": "Скор. магии",
    "physicalcriticalreducerate": "Блок ф.крит.", "magicalcriticalreducerate": "Блок м.крит.",
    "physicalcriticaldamagereduce": "Защ. от ф.крит.", "parry": "Парир.",
}


_BONUS_KEY = re.compile(r"bonus_attr(?:_([a-z]))?(\d+)")


def _int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _base(fields: dict) -> list[list[str]]:
    pairs = []
    low, high = _int(fields.get("min_damage")), _int(fields.get("max_damage"))
    if high:
        pairs.append(["Атака", f"{low}-{high}"])
    for key, label in BASE:
        value = _int(fields.get(key))
        if not value:
            continue
        pairs.append([label, f"{value / 1000:.1f}" if key == "attack_delay" else str(value)])
    return pairs


def _bonus(fields: dict) -> list[list[str]]:
    # bonus_attrN first, then bonus_attr_aN, bonus_attr_bN …: the site prints them all in one block, in this order
    keys = sorted((k for k in fields if _BONUS_KEY.fullmatch(k)),
                  key=lambda k: (_BONUS_KEY.fullmatch(k).group(1) or "", int(_BONUS_KEY.fullmatch(k).group(2))))
    pairs = []
    for key in keys:
        line = stat_line(fields[key])
        if not line or line[0] not in BONUS or not line[1]:
            continue
        sign = "" if str(line[1]).startswith("-") else "+"
        pairs.append([BONUS[line[0]], f"{sign}{_number(line[1])}{'%' if line[2] else ''}"])
    return pairs


def gear_spec(*, name: str, grade: str | None, fields: dict, description: str | None) -> dict | None:
    """The card of an item one wears, from the client's record; None when it is not worn or has no numbers."""
    if str(fields.get("equipment_slots") or "none") == "none":
        return None
    base, bonus = _base(fields), _bonus(fields)
    if not base and not bonus:
        return None
    blocks: list[dict] = []
    kind = WEAPON_TYPES.get(str(fields.get("weapon_type") or "")) or ARMOUR_TYPES.get(str(fields.get("armor_type") or ""))
    if kind:
        blocks.append({"kind": "pairs", "rows": [["Тип", kind]]})
    lines = [line for flag, line in FLAG_LINES if str(fields.get(flag, "TRUE")).upper() == "FALSE"]
    if lines:
        blocks.append({"kind": "props", "lines": lines})
    level = _int(fields.get("level"))
    if level:
        blocks.append({"kind": "warning", "text": f"Можно использовать с {level}-го уровня."})
    blocks.append({"kind": "hr"})
    text = str(description or "").strip()
    if text:
        blocks.append({"kind": "text", "text": text, "style": "normal"})
    for pairs in (base, bonus):
        if pairs:
            if blocks[-1]["kind"] == "grid":
                blocks.append({"kind": "hr"})
            blocks.append({"kind": "grid", "pairs": pairs, "dim": False})
    return {"name": name, "grade": grade or "common", "blocks": blocks}
