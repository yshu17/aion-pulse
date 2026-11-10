"""What a quest asks, in short, from the client's own quest tables (map:45): who to kill, what to get and where, what to craft,
which quests come first. The client has no journal text, so the steps are made from its conditions, nothing guessed.

    steps = quest_steps(quest_dir, quest_fields, npc_by_internal, item_by_internal, quest_ids)
    steps[1001] -> [{"do": "loot", "item": 182200001, "count": 5, "from": [["700123", "Керубим"]], "more": 0}, …]

Inputs: ``quest_dir`` holds quest_monster.csv and quest_script_monster.csv (client Data/quest, client_extract/raw/Data/quest);
``quest_fields`` id -> the quest's XML fields (catalog.sqlite entries); ``npc_by_internal`` the lower-case internal name of
an NPC -> (id, name); ``item_by_internal`` the lower-case internal name of an item -> id; ``quest_ids`` «Q1001» -> 1001.

A step: {do: kill | loot | gather | buy | drop | craft | after, …}. NPCs are [id, name] pairs (the first ones), ``more`` counts
the others, the ones the client names but pulse.db does not know included. Steps keep the quest's progress order; the same
item from several groups of monsters is one step. ``count`` is how many items the quest wants (its collect_item / check_item
fields); the tables' own number is the size of their monster list, so a kill has no count.
"""

from __future__ import annotations

import csv
from pathlib import Path

NPCS_SHOWN = 4
# quest_monster.csv sourceType -> the step
SOURCE = {"questItemDropMonster": "loot", "dropMonster": "loot", "gatherSource": "gather", "goodsList": "buy", "commonDrop": "drop"}


def _rows(path: Path) -> list[list[str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return [row for row in list(csv.reader(stream))[1:] if len(row) >= 6 and row[0].strip().isdigit()]


def _progress(text: str) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _npcs(names: list[str], npc_by_internal: dict[str, tuple[str, str]]) -> tuple[list[list[str]], int]:
    known, seen = [], set()
    for raw in names:
        found = npc_by_internal.get(raw.strip().lower())
        if found and found[1] and found[1] not in seen:
            seen.add(found[1])
            known.append([found[0], found[1]])
    shown = known[:NPCS_SHOWN]
    return shown, len({n.strip().lower() for n in names if n.strip()}) - len(shown)


def _count(text) -> int:
    return int(text) if str(text).strip().isdigit() else 1


def _wanted(fields: dict) -> dict[str, int]:
    """item internal name (lower case) -> how many the quest wants («quest_1001a 5» of collect_item1, check_item1_1 …)."""
    out: dict[str, int] = {}
    for key, value in fields.items():
        if key.startswith(("collect_item", "check_item")):
            for part in _list(value):
                name, _, n = str(part).strip().partition(" ")
                if name:
                    out[name.lower()] = max(out.get(name.lower(), 0), _count(n.strip() or 1))
    return out


def quest_steps(quest_dir: Path | None, quest_fields: dict[int, dict], npc_by_internal: dict[str, tuple[str, str]],
                item_by_internal: dict[str, int], quest_ids: dict[str, int]) -> dict[int, list[dict]]:
    steps: dict[int, list[tuple[int, dict]]] = {}
    if quest_dir:
        for qid, progress, _item, _type, _source, num, *targets in _rows(quest_dir / "quest_script_monster.csv"):
            if _type != "killedByUser":
                continue
            npcs, more = _npcs(targets, npc_by_internal)
            if npcs or more:
                steps.setdefault(int(qid), []).append((_progress(progress), {"do": "kill", "from": npcs, "more": more}))
        for qid, progress, item, kind, source, num, *targets in _rows(quest_dir / "quest_monster.csv"):
            do = SOURCE.get(kind)
            if not do:
                continue  # «simpleQuest»: the quest itself gives the item
            npcs, more = _npcs(targets, npc_by_internal)
            wanted = _wanted(quest_fields.get(int(qid), {})).get(item.strip().lower())
            step = {"do": do, "item": item_by_internal.get(item.strip().lower()), "count": wanted, "from": npcs, "more": more}
            steps.setdefault(int(qid), []).append((_progress(progress), step))
    for qid, fields in quest_fields.items():
        extra = []
        if fields.get("combineskill"):
            extra.append((90, {"do": "craft", "skill": fields["combineskill"], "level": _count(fields.get("combine_skillpoint") or 0) or None}))
        after = [quest_ids[q.strip().upper()] for value in _list(fields.get("finished_quest_cond1"))
                 for q in str(value).split(",") if q.strip().upper() in quest_ids]
        if after:
            extra.append((-1, {"do": "after", "quests": after}))
        steps.setdefault(qid, []).extend(extra)
    out = {}
    for qid, rows in steps.items():
        unique: list[dict] = []
        by_item: dict[tuple, dict] = {}
        seen = set()
        for _, step in sorted(rows, key=lambda r: r[0]):
            if step.get("item") is not None:  # one item from several groups: one step, its monsters together
                key = (step["do"], step["item"])
                if key in by_item:
                    merged = by_item[key]
                    names = {n[1] for n in merged["from"]}
                    extra = [n for n in step["from"] if n[1] not in names]
                    room = NPCS_SHOWN - len(merged["from"])
                    merged["from"] += extra[:max(room, 0)]
                    merged["more"] += step["more"] + max(len(extra) - max(room, 0), 0)
                    continue
                by_item[key] = step = dict(step, **{"from": list(step["from"])})
            sig = (repr(("kill", [n[1] for n in step["from"]])) if step["do"] == "kill"  # two NPC ids of one name: one kill
                   else repr(sorted((k, repr(v)) for k, v in step.items())))
            if sig not in seen:
                seen.add(sig)
                unique.append(step)
        if unique:
            out[qid] = unique
    return out


def _list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
