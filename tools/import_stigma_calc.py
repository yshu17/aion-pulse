"""Take the stigma calculator's data of github.com/Persepha/Aion-classic-stigma-calculator into data/stigma/classic24.json.

    git clone https://github.com/Persepha/Aion-classic-stigma-calculator downloads/stigma_calc
    python tools/import_stigma_calc.py

Source: downloads/stigma_calc (commit df22667, 08.05.2023; Aion NA Classic 2.4). The repository has no licence file: the data are
the game's own (skill ids, levels, costs), the pictures are not taken (Pulse+ has the client's icons). Read from it:
public/data/<class>.json — the class's stigmas with their levels; utils/aionClasses/<class>/index.ts — the two advanced trees
(getFirstStigmaTree, getSecondStigmaTree) and the dependencies (graph.addDependency(stigma, needs)). The TypeScript is read as
text with patterns, never run.

Out: data/stigma/classic24.json — {source, classes: {fighter: {stigmas: [...], trees: {elyos: [[10 ids], [10 ids]], asmodian: ...},
needs: {elyos: [[a, b], ...], asmodian: ...}}}} (some classes' trees and dependencies name a stigma of the faction).
A stigma: id, faction (daeva = both, elyos, asmodian), advanced, kind, target, info, levels: [{level, skill, name, text, mp, cast,
cooldown, shards, ap}]. «skill» is the client's skill id: pulse.db's skill.id (the program takes the Russian name, text and icon
from there, launcher/src/core/stigma/merge.ts).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "downloads" / "stigma_calc"
OUT = ROOT / "data" / "stigma" / "classic24.json"
# the repository's class names -> Pulse+'s (core/gear/labels.ts CLASSES)
CLASSES = {"gladiator": "fighter", "templar": "knight", "assassin": "assassin", "ranger": "ranger", "sorcerer": "wizard",
           "spiritmaster": "elementalist", "chanter": "chanter", "cleric": "cleric"}
# the tree's ten places in the order the screen draws them (launcher/src/core/stigma/tree.ts PLACES)
TERNARY = re.compile(r'this\.faction\s*===\s*"elyos"\s*\?\s*("[^"]+")\s*:\s*("[^"]+")')
FACTIONS = {"elyos": 1, "asmodian": 2}
TIERS = ["tier4_1", "tier4_2", "tier4_3", "tier3_1", "tier3_2", "tier4_4", "tier4_5", "tier2_1", "tier2_2", "tier1"]


def tree(text: str, method: str) -> list[str]:
    body = re.search(method + r"\(\)[^{]*\{\s*return\s*\{(.*?)\};", text, re.S)
    if not body:
        raise SystemExit(f"no {method}")
    slots = dict(re.findall(r"(tier\d(?:_\d)?)\s*:\s*\"([^\"]+)\"", body.group(1)))
    return [slots[t] for t in TIERS]


def level(row: dict, at: int) -> dict:
    d = row[str(at)]
    return {"level": at, "skill": d["id"], "name": d["name"], "text": d.get("Description") or "", "mp": d.get("Usage Cost") or "",
            "cast": d.get("Cast time") or "", "cooldown": d.get("Cooldown") or "", "shards": d.get("Shards cost"), "ap": d.get("Abyss point") or 0}


def main() -> int:
    if not (SRC / "public" / "data").is_dir():
        print(f"no {SRC}: clone the repository there first (see the docstring)", file=sys.stderr)
        return 1
    commit = subprocess.run(["git", "-C", str(SRC), "log", "-1", "--format=%h %ad", "--date=short"], capture_output=True, text=True).stdout.split()
    out: dict = {"source": {"repo": "https://github.com/Persepha/Aion-classic-stigma-calculator", "commit": commit[0] if commit else "",
                            "date": commit[1] if len(commit) > 1 else "", "game": "Aion NA Classic 2.4"}, "classes": {}}
    for name, cls in CLASSES.items():
        rows = json.loads((SRC / "public" / "data" / f"{name}.json").read_text(encoding="utf-8"))
        code = (SRC / "utils" / "aionClasses" / name / "index.ts").read_text(encoding="utf-8")
        stigmas = [{"id": r["id"], "faction": r["faction"], "advanced": r["type"] == 1, "kind": r.get("Skill type") or "",
                    "target": r.get("Target") or "", "info": [" ".join(x.split()) for x in r.get("Additional info") or []],
                    "levels": [level(r, at) for at in sorted(r["lvls"])]} for r in rows]
        known = {s["id"] for s in stigmas}
        trees, needs = {}, {}
        for faction, group in FACTIONS.items():
            # the class file picks some stigmas by the faction (`this.faction === "elyos" ? a : b`): one text per faction
            text = TERNARY.sub(lambda m, g=group: m.group(g), code)
            needs[faction] = [list(p) for p in re.findall(r"addDependency\(\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"\s*\)", text)]
            trees[faction] = [tree(text, "getFirstStigmaTree"), tree(text, "getSecondStigmaTree")]
            missing = {x for p in needs[faction] for x in p} | {x for t in trees[faction] for x in t}
            missing -= known
            if missing:
                raise SystemExit(f"{name}/{faction}: unknown stigmas {sorted(missing)}")
        out["classes"][cls] = {"stigmas": stigmas, "trees": trees, "needs": needs}
        print(f"{cls}: {len(stigmas)} stigmas, {len(needs['elyos'])} dependencies")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
