"""Equipment for the gear calculator (docs/GEAR_CALC_PLAN.md, stage 1): every item one can wear, its base and bonus stats, its
manastone slots, its set; the manastones; the item sets. Pure: the client's export in, rows out.

    rows = gear_rows(catalog_path, raw_dir, stones_by_item)   # {"item": [...], "set": [...], "stone": [...]}

Stat names are the calculator's (lower case, as aiongear.fun and the client's bonus_attr name them: maxhp, phyattack,
physicaldefend …). ``basic`` holds the item's own numbers (damage, attack delay, defence …), ``bonus`` the «bonus_attr» list
as [stat, value, percent]. A group tells how the item counts: sword … orb, shield, rb_torso … pl_shoes, head, earring, ring,
necklace, belt, wing. ``stones`` / ``stones_bonus`` come from the item card («stones» block: count, of them the last ``bonus``
may or may not be there); no card, no slots (None).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

WEAPON = {"1h_sword": "sword", "1h_dagger": "dagger", "1h_mace": "mace", "2h_sword": "greatsword", "2h_polearm": "polearm",
          "2h_staff": "staff", "bow": "bow", "2h_book": "spellbook", "2h_orb": "orb"}
ARMOUR = {"robe": "rb", "leather": "lt", "chain": "ch", "plate": "pl"}
PART = {"torso": "torso", "leg": "pants", "shoulder": "shoulder", "glove": "glove", "foot": "shoes"}
SLOT = {"right_or_left_ear": "earring", "right_or_left_finger": "ring", "neck": "necklace", "waist": "belt", "wing": "wing",
        "head": "head"}
# the client's own number fields -> the calculator's stat
BASIC = {"min_damage": "mindamage", "max_damage": "maxdamage", "attack_delay": "attackdelay", "hit_accuracy": "hitaccuracy",
         "critical": "critical", "magical_hit_accuracy": "magicalaccuracy", "magical_skill_boost": "magicalskillboost",
         "parry": "parry", "hit_count": "hitcount", "physical_defend": "physicaldefend", "magical_resist": "magicalresist",
         "dodge": "dodge", "block": "block", "damage_reduce": "damagereduce", "reduce_max": "reducemax"}
CLASSES = ["fighter", "knight", "assassin", "ranger", "wizard", "elementalist", "chanter", "cleric"]


def group_of(f: dict) -> str | None:
    slots = str(f.get("equipment_slots") or "")
    weapon = WEAPON.get(str(f.get("weapon_type") or ""))
    if weapon:
        return weapon
    if slots == "sub" and "shield" in str(f.get("name") or "").lower():
        return "shield"
    armour = ARMOUR.get(str(f.get("armor_type") or ""))
    if armour and slots in PART:
        return f"{armour}_{PART[slots]}"
    return SLOT.get(slots)


def slot_of(f: dict, group: str) -> str:
    slots = str(f.get("equipment_slots") or "")
    if group in WEAPON.values():
        return "main_or_sub" if slots == "main_or_sub" else "main"
    if group == "shield":
        return "sub"
    if "_" in group:
        return group.split("_", 1)[1]  # torso, pants, shoulder, glove, shoes
    return group


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def stat_line(text: str) -> list | None:
    """«maxHp 407» -> ["maxhp", 407, False]; «flyspeed 10%» -> ["flyspeed", 10, True]."""
    found = re.match(r"\s*\[?'?([A-Za-z_]+)'?\s+(-?[\d.]+)\s*(%?)", str(text))
    if not found:
        return None
    value = float(found.group(2))
    return [found.group(1).lower(), int(value) if value.is_integer() else value, bool(found.group(3))]


def _values(value) -> list:
    return value if isinstance(value, list) else [value]


def item_row(item_id: int, name: str, icon: str | None, f: dict, stones: dict | None) -> tuple | None:
    group = group_of(f)
    if not group or str(f.get("armor_type") or "") == "clothes":
        return None
    basic = {}
    for key, stat in BASIC.items():
        value = _num(f.get(key))
        if value:
            basic[stat] = int(value) if value.is_integer() else value
    if f.get("attack_range") and _num(f["attack_range"]):
        basic["attackrange"] = int(round(_num(f["attack_range"]) * 1000))
    bonus = []
    for key in sorted((k for k in f if k.startswith("bonus_attr")), key=lambda k: int(re.sub(r"\D", "", k) or 0)):
        for part in _values(f[key]):
            line = stat_line(part)
            if line:
                bonus.append(line)
    classes = [c for c in CLASSES if _num(f.get(c))]
    races = str(f.get("race_permitted") or "").split()
    return (item_id, name, icon, str(f.get("quality") or "").lower(), int(_num(f.get("level"))), slot_of(f, group), group,
            ",".join(races), json.dumps(classes), json.dumps(basic, separators=(",", ":")), json.dumps(bonus, separators=(",", ":")),
            stones.get("count") if stones else None, stones.get("bonus") if stones else None,
            0 if str(f.get("no_enchant") or "").upper() == "TRUE" else 1)


def _strings(raw_dir: Path) -> dict[str, str]:
    """STR_… -> Russian, from the client's string files the export kept."""
    out = {}
    for path in raw_dir.glob("client_strings_item*.xml"):
        raw = path.read_bytes()
        text = raw.decode("utf-16" if raw[:2] in (bytes([255, 254]), bytes([254, 255])) else "utf-8", errors="replace")
        for key, body in re.findall(r"<name>([^<]+)</name>\s*<body>(.*?)</body>", text, re.S):
            out.setdefault(key.upper(), body.strip())
    return out


def gear_rows(catalog: Path | None, raw_dir: Path | None, stones: dict[int, dict]) -> dict:
    out = {"item": [], "set": [], "stone": []}
    if not catalog or not catalog.is_file():
        return out
    db = sqlite3.connect(f"file:{catalog.as_posix()}?mode=ro", uri=True)
    by_internal: dict[str, int] = {}
    columns = {row[1] for row in db.execute("PRAGMA table_info(entries)")}
    if not {"internal_name", "name_ru", "icon_path", "fields_json"} <= columns:  # not an export of tools/export_fresh_catalog.py
        db.close()
        return out
    try:
        for eid, internal, name, icon_path, fields in db.execute(
                "SELECT id, internal_name, name_ru, icon_path, fields_json FROM entries WHERE section = 'items'"):
            f = json.loads(fields)
            iid = int(eid)
            icon = Path(icon_path).stem.lower() if icon_path else None
            if internal:
                by_internal[internal.lower()] = iid
            if str(internal or "").lower().startswith("matter_option") and f.get("stat_enchant_type"):
                line = stat_line(f"{f['stat_enchant_type']} {f.get('stat_enchant_value', 0)}")
                if line:
                    out["stone"].append((iid, name or "", icon, str(f.get("quality") or "").lower(), int(_num(f.get("level"))),
                                         line[0], line[1]))
                continue
            row = item_row(iid, name or "", icon, f, stones.get(iid))
            if row:
                out["item"].append(row)
    finally:
        db.close()
    path = raw_dir / "client_setitem.xml" if raw_dir else None
    if path and path.is_file():
        strings = _strings(raw_dir)
        text = path.read_text(encoding="utf-16", errors="replace")
        for block in re.findall(r"<client_setitem>(.*?)</client_setitem>", text, re.S):
            tags = dict(re.findall(r"<(\w+)>(.*?)</\1>", block, re.S))
            items = [by_internal[v.strip().lower()] for k, v in sorted(tags.items()) if re.fullmatch(r"item\d+", k)
                     and v.strip().lower() in by_internal]
            bonuses = []
            for k, v in tags.items():
                need = 0 if k == "fullset_bonus" else int(k.removeprefix("piece_bonus")) if k.startswith("piece_bonus") else None
                if need is None:
                    continue
                stats = [s for s in (stat_line(p) for p in v.split(";")) if s]
                if stats:
                    bonuses.append({"need": need, "stats": stats})
            bonuses.sort(key=lambda b: (b["need"] == 0, b["need"]))
            name = strings.get(str(tags.get("desc", "")).upper(), tags.get("name", ""))
            if items:
                out["set"].append((int(tags["id"]), name, json.dumps(items), json.dumps(bonuses, ensure_ascii=False, separators=(",", ":"))))
    out["item"].sort()
    out["stone"].sort()
    out["set"].sort()
    return out
