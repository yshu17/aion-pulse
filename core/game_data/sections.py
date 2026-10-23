"""One function per section: rows of the exported tables in, the records of the section out.

Every function is a pure transformation (no files, no globals), sorted by ID, so the result is the same every time.
IDs are strings; numbers are numbers; unknown is ``None``. Records have ``source``: ``client`` or ``site``.

Shapes (a section file is ``{"schema", "section", <key>: ...}``):

    items       records: id, name, type, weapon, armor, level, price, icon, category, grade, source [, name_source]
    recipes     records: id, name, product, count, profession, level, race, ingredients [[item, count]], combo [item]|None
    npcs        records: id, name, function, ui, tribe, race, source
    maps        records: id, name, file, size, side
    labels      columns [map, key, level, x, y, z, name], rows
    npc_points  columns [map, npc, x, y, z, zone], rows
    vendors     columns [npc, item, price, currency, limit, kind], rows
    quests      records: id, name, min_level, max_level, race [..], category, repeatable, giver, ender, rewards [{type, group, item, amount}]
    skills      skills: id, name, classes [..], level, kind, mp, cooldown_ms, cast_ms, range, requires; learns: id, skill, class, race, level, stigma
    stigmas     records: type («skill» / «slot»), skill, class, level, slot, rank, rank_max, requires
    classes     records: id, class, race, name, base_stats, per_level  (stats are None until the client table is found)
"""

from __future__ import annotations

import json

from .tables import to_float, to_int

Rows = list[dict[str, str | None]]


def _id_key(value: str) -> tuple[int, int | str]:
    """Sort numbers as numbers, anything else after them as text."""
    return (0, int(value)) if value.isdigit() else (1, value)


def _names(rows: Rows, key: str, name: str) -> dict[str, str]:
    return {row[key]: row[name] for row in rows if row.get(key) and row.get(name)}  # type: ignore[misc]


def _json_list(value: str | None) -> list | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, list) else None


def items(rows: Rows, names: Rows, legacy_names: dict[str, str], legacy_meta: Rows) -> list[dict]:
    """Client items. The name comes from the client strings; where they have none, from the older names file
    (``name_source: "legacy"``). ``category`` and ``grade`` come from the older watch list where it knows the item."""
    client_names = _names(names, "item_id", "name_ru")
    meta = {row["id"]: row for row in legacy_meta if row.get("id")}
    out = []
    for row in rows:
        item_id = row.get("item_id")
        if not item_id:
            continue
        name = client_names.get(item_id)
        record: dict = {
            "id": item_id,
            "name": name or legacy_names.get(item_id),
            "type": row.get("item_type"),
            "weapon": row.get("weapon_type"),
            "armor": row.get("armor_type"),
            "level": to_int(row.get("item_level")),
            "price": to_int(row.get("client_price")),
            "icon": row.get("icon_name"),
            "category": (meta.get(item_id) or {}).get("category"),
            "grade": (meta.get(item_id) or {}).get("grade"),
            "source": row.get("source") or "client",
        }
        if name is None and record["name"] is not None:
            record["name_source"] = "legacy"
        out.append(record)
    out.sort(key=lambda r: _id_key(r["id"]))
    return out


def recipes(rows: Rows, ingredients: Rows, combinations: Rows, names: Rows) -> list[dict]:
    recipe_names = _names(names, "recipe_id", "name_ru")
    parts: dict[str, list[tuple[int, str, int]]] = {}
    for row in ingredients:
        if row.get("recipe_id") and row.get("item_id"):
            parts.setdefault(row["recipe_id"], []).append((to_int(row.get("position")) or 0, row["item_id"], to_int(row.get("count")) or 1))  # type: ignore[arg-type]
    combos: dict[str, list[tuple[int, str]]] = {}
    for row in combinations:
        if row.get("recipe_id") and row.get("item_id"):
            combos.setdefault(row["recipe_id"], []).append((to_int(row.get("position")) or 0, row["item_id"]))  # type: ignore[arg-type]
    out = []
    for row in rows:
        recipe_id = row.get("recipe_id")
        if not recipe_id:
            continue
        out.append({
            "id": recipe_id,
            "name": recipe_names.get(recipe_id),
            "product": row.get("product_item_id"),
            "count": to_int(row.get("product_count")),
            "profession": row.get("profession"),
            "level": to_int(row.get("level")),
            "race": row.get("race"),
            "ingredients": [[item, count] for _, item, count in sorted(parts.get(recipe_id, []))],
            "combo": [item for _, item in sorted(combos[recipe_id])] if recipe_id in combos else None,
            "source": row.get("source") or "client",
        })
    out.sort(key=lambda r: _id_key(r["id"]))
    return out


def npcs(rows: Rows, names: Rows) -> list[dict]:
    npc_names = _names(names, "npc_id", "name_ru")
    out = [{
        "id": row["npc_id"], "name": npc_names.get(row["npc_id"]),  # type: ignore[index]
        "function": row.get("function_type"), "ui": row.get("ui_type"), "tribe": row.get("tribe"), "race": row.get("race_type"),
        "source": row.get("source") or "client",
    } for row in rows if row.get("npc_id")]
    out.sort(key=lambda r: _id_key(r["id"]))
    return out


def maps(rows: Rows, names: Rows) -> list[dict]:
    map_names = _names(names, "map_id", "name_ru")
    out = [{"id": row["map_id"], "name": map_names.get(row["map_id"]), "file": row.get("file"),  # type: ignore[index]
            "size": to_int(row.get("size")), "side": row.get("side")} for row in rows if row.get("map_id")]
    out.sort(key=lambda r: _id_key(r["id"]))
    return out


LABEL_COLUMNS = ["map", "key", "level", "x", "y", "z", "name"]


def labels(rows: Rows, names: Rows) -> list[list]:
    label_names = _names(names, "string_key", "name_ru")
    out = [[row["map_id"], row.get("string_key"), row.get("display_level"), to_float(row.get("game_x")), to_float(row.get("game_y")),
            to_float(row.get("game_z")), label_names.get(row.get("string_key") or "")] for row in rows if row.get("map_id")]
    out.sort(key=lambda r: (_id_key(r[0]), r[1] or ""))
    return out


NPC_POINT_COLUMNS = ["map", "npc", "x", "y", "z", "zone"]


def npc_points(rows: Rows) -> list[list]:
    out = [[row["map_id"], row["npc_id"], to_float(row.get("game_x")), to_float(row.get("game_y")), to_float(row.get("game_z")), row.get("zone")]
           for row in rows if row.get("map_id") and row.get("npc_id")]
    out.sort(key=lambda r: (_id_key(r[0]), _id_key(r[1]), r[2] or 0.0, r[3] or 0.0))
    return out


VENDOR_COLUMNS = ["npc", "item", "price", "currency", "limit", "kind"]


def vendors(rows: Rows) -> list[list]:
    out = [[row["npc_id"], row["item_id"], to_int(row.get("price")), row.get("currency"), to_int(row.get("limit")), row.get("trade_kind")]
           for row in rows if row.get("npc_id") and row.get("item_id")]
    out.sort(key=lambda r: (_id_key(r[0]), _id_key(r[1]), r[5] or ""))
    return out


def quests(info: Rows, npc_rows: Rows, reward_rows: Rows, names: Rows) -> list[dict]:
    """Quests: the level, race and category from the quest table, the giver and ender from the NPC table (the giver
    falls back to the quest table), the rewards grouped by quest."""
    quest_names = _names(names, "quest_id", "name_ru")
    ends = {row["quest_id"]: row for row in npc_rows if row.get("quest_id")}
    rewards: dict[str, list[dict]] = {}
    for row in reward_rows:
        if row.get("quest_id"):
            rewards.setdefault(row["quest_id"], []).append({"type": row.get("reward_type"), "group": row.get("group"),
                                                            "item": row.get("item_id"), "amount": to_int(row.get("amount"))})
    ids = {row["quest_id"] for row in info if row.get("quest_id")} | set(ends) | set(rewards)
    by_info = {row["quest_id"]: row for row in info if row.get("quest_id")}
    out = []
    for quest_id in ids:
        base = by_info.get(quest_id, {})
        npc = ends.get(quest_id, {})
        race = base.get("race")
        out.append({
            "id": quest_id,
            "name": quest_names.get(quest_id) or base.get("name_ru"),
            "min_level": to_int(base.get("min_level")),
            "max_level": to_int(base.get("max_level")),
            "race": race.split() if race else None,
            "category": base.get("category"),
            "repeatable": None if base.get("repeatable") is None else base["repeatable"] == "yes",
            "giver": npc.get("giver_npc_id") or base.get("start_npc_id"),
            "ender": npc.get("ender_npc_id") or base.get("end_npc_id"),
            "rewards": rewards.get(quest_id, []),
        })
    out.sort(key=lambda r: _id_key(r["id"]))
    return out


def skills(rows: Rows, names: Rows, learn_rows: Rows) -> dict:
    skill_names = _names(names, "id", "name_ru")
    skill_list = [{
        "id": row["id"], "name": skill_names.get(row["id"]),  # type: ignore[index]
        "classes": _json_list(row.get("class")), "level": to_int(row.get("level")), "kind": row.get("kind"),
        "mp": to_int(row.get("mp")), "cooldown_ms": to_int(row.get("cooldown_ms")), "cast_ms": to_int(row.get("cast_ms")),
        "range": to_float(row.get("range")), "requires": row.get("requires"), "source": row.get("source") or "client",
    } for row in rows if row.get("id")]
    skill_list.sort(key=lambda r: _id_key(r["id"]))
    learns = [{"id": row["learn_id"], "skill": row.get("skill_name"), "class": row.get("class"), "race": row.get("race"),
               "level": to_int(row.get("level")), "stigma": to_int(row.get("stigma_display"))} for row in learn_rows if row.get("learn_id")]
    learns.sort(key=lambda r: _id_key(r["id"]))
    return {"skills": skill_list, "learns": learns}


def stigmas(rows: Rows) -> list[dict]:
    out = [{"type": row.get("record_type"), "skill": row.get("skill_id"), "class": row.get("class"), "level": to_int(row.get("level")),
            "slot": to_int(row.get("slot_number")), "rank": to_int(row.get("active_rank")), "rank_max": to_int(row.get("rank_max")),
            "requires": row.get("requires")} for row in rows]
    out.sort(key=lambda r: (r["type"] or "", r["class"] or "", r["slot"] or 0, _id_key(r["skill"] or "0")))
    return out


def classes(rows: Rows, names: Rows) -> list[dict]:
    class_names = _names(names, "class", "name_ru")
    out = []
    for row in rows:
        if not row.get("class"):
            continue
        base = row.get("base_stats")
        per_level = row.get("per_level")
        out.append({
            "id": f"{row['class']}.{row.get('race') or ''}", "class": row["class"], "race": row.get("race"),
            "name": class_names.get(row["class"]),
            "base_stats": json.loads(base) if base else None, "per_level": json.loads(per_level) if per_level else None,
            "source": row.get("source") or "client",
        })
    out.sort(key=lambda r: r["id"])
    return out
