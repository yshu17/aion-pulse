"""An item's card (``item.spec``) made from the game client's own record.

The older cards come from a crawl of a third-party site and cover 28 000 of the client's 62 000 items. The client itself has a
description for 8 800 more (emotes, costumes, models, event boxes, food, sweets, potions). This module turns such a record into
the same JSON shape the crawl's cards have, so the launcher draws it with the code it already has.

    spec = client_spec(name="Бешевый коктейль", grade="rare", description="[%e1.StatUp.StatName]% +[%e1.StatUp.Value] …",
                       fields={"can_exchange": "FALSE", …}, skill={"name": "…", "effects": {"effect1_type": "StatUp", …}})
    # -> {"name": …, "grade": "rare", "blocks": [{"kind": "props", …}, {"kind": "hr"}, {"kind": "text", "text": "Восст. HP +2. …"}]}
    # -> None when the client has no description for the item

The client's descriptions of food, scrolls and potions hold placeholders («[%e1.StatUp.StatName]», «[%e1.Heal.CheckTimeHeal]»)
that the game fills from the skill the item activates. «eN» is the skill's effect N; what each placeholder reads (checked against
the crawl's cards, which print the same text the game does):

    StatUp.StatName / .Value        effectN_reserved13 (the stat's key) / effectN_reserved1
    *.RemainTime                    effectN_remain2, milliseconds
    Heal.CheckTimeHeal, MpHeal …    effectN_reserved9 (points per tick); .CheckTime = effectN_checktime, milliseconds
    ProcHeal_Instant.Heal …         effectN_reserved2
    Shield.CoverValue               effectN_reserved2

A sentence with a placeholder we cannot fill (an unknown stat key, a field the effect does not have) is left out, never shown
raw. The stat names are the game's own (the crawl's wording), not a guess. Pure.

The same text also repairs the crawl's own cards where the site left a text half-filled («hpRegen% +2», «Макс. HP% +40»,
«allresist +0»): ``repaired_spec`` swaps that one text block, every other block of the card stays.
"""

from __future__ import annotations

import re

# the client's stat key (lower case) -> the game's name and whether its value is a percent. The wording is the game's: taken from
# the crawl's cards of the same items. A key that is not here is not shown raw: its sentence is left out.
STAT_NAMES: dict[str, tuple[str, bool]] = {
    "speed": ("Скорость", True), "flyspeed": ("Скор. полёта", True), "boostcastingtime": ("Скор. магии", True),
    "attackdelay": ("Скорость атаки", True), "maxhp": ("Макс. HP", False), "maxmp": ("Макс. MP", False),
    "maxfp": ("Макс. время полёта", False), "magicalskillboost": ("Сила магии", False), "magicalhitaccuracy": ("Маг. точность", False),
    "phyattack": ("Физ. атака", False), "critical": ("Физ. крит.", False), "magicalcritical": ("Маг. крит.", False),
    "magicalresist": ("Маг. защита", False), "physicaldefend": ("Физ. защита", False), "dodge": ("Уклонение", False),
    "hitaccuracy": ("Точность", False), "hpregen": ("Восст. HP", False), "mpregen": ("Восст. MP", False),
    "elementaldefendfire": ("Защ. от огня", False), "elementaldefendearth": ("Защ. от земли", False),
    "elementaldefendwater": ("Защ. от воды", False), "elementaldefendair": ("Защ. от воздуха", False),
    "magicalcriticalreducerate": ("Блок м.крит.", False), "physicalcriticalreducerate": ("Блок ф.крит.", False),
    "elementaldefendall": ("Защ. от стихий", False), "kno": ("Знание", False), "wil": ("Воля", False),
}

# the client's trade flag -> the line the card prints when it is FALSE, in the game's order
FLAG_LINES = (
    ("can_exchange", "[Нельзя обменять]"),
    ("can_sell_to_npc", "[Нельзя продать торговцу]"),
    ("can_deposit_to_account_warehouse", "[Нельзя положить на склад аккаунта]"),
    ("can_deposit_to_character_warehouse", "[Нельзя положить на склад]"),
    ("can_deposit_to_guild_warehouse", "[Нельзя положить на склад легиона]"),
)

_STAT_PAIR = re.compile(r"\[%e(\d+)\.StatUp\.StatName\]%?\s*\+\[%e\1\.StatUp\.Value\](%%)?", re.IGNORECASE)  # «%%»: the value is a percent
_TOKEN = re.compile(r"\[%e(\d+)\.(\w+)\.(\w+)\]")
_LEFT = re.compile(r"\[%[^\]]*\]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z\[])")  # a capital must follow: «ед. урона» is no sentence end


def stat_text(key: str, value: str) -> str | None:
    """«hpRegen», «2» -> «Восст. HP +2»; a percent stat gets «%»; None for a key the game's names do not cover."""
    known = STAT_NAMES.get(str(key).strip().lower())
    if not known or not str(value).strip():
        return None
    label, percent = known
    sign = value if value[:1] in "+-" else f"+{value}"
    return f"{label} {sign}%" if percent and not sign.endswith("%") else f"{label} {sign}"


def _seconds(ms) -> str | None:
    try:
        seconds = int(ms) // 1000
    except (TypeError, ValueError):
        return None
    return f"{seconds} сек." if seconds > 0 else None


def _duration(ms) -> str | None:
    """5 мин., 24 сек., 1 ч.: the crawl's (and so the game's) way to write a time of action."""
    try:
        seconds = int(ms) // 1000
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    if seconds < 60:
        return f"{seconds} сек."
    minutes = seconds // 60
    return f"{minutes // 60} ч." if minutes >= 60 and minutes % 60 == 0 and minutes < 24 * 60 else f"{minutes} мин."


def _points(effects: dict, index: str, key: str) -> str | None:
    value = str(effects.get(f"effect{index}_{key}") or "").strip()
    return value if value and value != "0" else None


def _token(effects: dict, index: str, kind: str, field: str) -> str | None:
    """What the placeholder «[%e<index>.<kind>.<field>]» stands for, or None when this database cannot tell."""
    kind, field = kind.lower(), field.lower()
    effect_type = str(effects.get(f"effect{index}_type") or "").lower()
    if field == "remaintime":
        return _duration(effects.get(f"effect{index}_remain2"))
    if effect_type != kind:
        return None
    if kind in ("heal", "mpheal"):
        if field == "checktimeheal":
            return _points(effects, index, "reserved9")
        if field == "checktime":
            return _seconds(effects.get(f"effect{index}_checktime"))
    if kind in ("procheal_instant", "procmpheal_instant", "procfpheal_instant") and field == "heal":
        return _points(effects, index, "reserved2")
    if kind == "shield" and field == "covervalue":
        return _points(effects, index, "reserved2")
    return None


def resolve_text(text: str, skill: dict | None) -> tuple[str, bool]:
    """The description with the placeholders filled from `skill` (``{"effects": <the skill's client fields>}``).

    Returns (text, complete). A sentence that still holds a placeholder is dropped and `complete` is False."""
    effects = (skill or {}).get("effects") or {}

    def stat(match: re.Match) -> str:
        index = match.group(1)
        if str(effects.get(f"effect{index}_type") or "") != "StatUp":
            return match.group(0)
        line = stat_text(str(effects.get(f"effect{index}_reserved13") or ""), _points(effects, index, "reserved1") or "")
        if not line:
            return match.group(0)
        return line + "%" if match.group(2) and not line.endswith("%") else line

    def other(match: re.Match) -> str:
        return _token(effects, match.group(1), match.group(2), match.group(3)) or match.group(0)

    text = _TOKEN.sub(other, _STAT_PAIR.sub(stat, str(text or "")))
    text = text.replace("%%", "%")
    text = re.sub(r"(?:\\n|\r?\n)+", " ", text).strip()
    if not _LEFT.search(text):
        return re.sub(r"\s{2,}", " ", text), True
    kept = [s for s in _SENTENCE_END.split(text) if s.strip() and not _LEFT.search(s)]
    return " ".join(kept).strip(), False


_GLITCH = re.compile(r"\[%|\b[a-z]+[A-Z][A-Za-z]*%? \+|%\s\+|\ballresist\b")


def has_glitch(text: str) -> bool:
    """True when a crawl card's text still holds what the site failed to fill: a placeholder («[%e1.StatUp.Value]»), a raw stat key
    («hpRegen% +2», «ElementalDefendAll% +10», «allresist +0») or the client's stray percent sign («Макс. HP% +40»)."""
    return bool(_GLITCH.search(str(text or "")))


def repaired_spec(spec: dict, description: str | None, skill: dict | None) -> dict | None:
    """The crawl's card `spec` with its glitchy text block replaced by the client's text, filled from the skill; every other block
    stays. None when nothing needs repair or the client's text cannot be filled completely (the crawl's card is then kept)."""
    if not str(description or "").strip():
        return None
    blocks = spec.get("blocks") or []
    at = next((i for i, b in enumerate(blocks) if b.get("kind") == "text" and has_glitch(b.get("text"))), None)
    if at is None:
        return None
    text, complete = resolve_text(description, skill)
    if not complete or not text:
        return None
    fixed = list(blocks)
    fixed[at] = {**blocks[at], "text": text}
    return {**spec, "blocks": fixed}


def client_spec(*, name: str, grade: str | None, description: str | None, fields: dict, skill: dict | None) -> dict | None:
    """The card of an item the crawl never had, from the client's record; None when the client has no description for it."""
    if not str(description or "").strip():
        return None
    text, complete = resolve_text(description, skill)
    if not text:
        effect_name = str((skill or {}).get("name") or "").strip()
        if not effect_name:
            return None
        text = f"Эффект: {effect_name}."
    blocks: list[dict] = []
    lines = [line for flag, line in FLAG_LINES if str(fields.get(flag, "TRUE")).upper() == "FALSE"]
    if lines:
        blocks.append({"kind": "props", "lines": lines})
    blocks.append({"kind": "hr"})
    blocks.append({"kind": "text", "text": text, "style": "normal"})
    return {"name": name, "grade": grade or "common", "blocks": blocks}
