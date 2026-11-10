"""Take the class tables of aiongear.fun for Aion Classic 2.0 (eu20) into data/gear/eu20 (docs/GEAR_CALC_PLAN.md, stage 1).

    python tools/import_aiongear.py

Source: downloads/aiongear/ (fetched from https://aiongear.fun, robots.txt «Allow: /», user's decision 09.11.2026):
chunk-Bf6HBxlh.js — static/stats/eu20/class_stats.json, chunk-BSN2daZN.js — static/skills/eu20/passive_skills.json.
The files are JavaScript object literals (unquoted keys, `strings`, !0/!1); they are read as data here, never run.

Out: data/gear/eu20/class_stats.json — class -> one row per level 1… (the base class's rows for the first levels, then the
class's own, by HP as the site orders them); data/gear/eu20/passive_skills.json — the passive skills and which ones a class
has at a level. Each file names its source.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "downloads" / "aiongear"
OUT = ROOT / "data" / "gear" / "eu20"
# the site's class order (function Vc): the index is the key of its tables
ORDER = ["all", "warrior", "scout", "mage", "priest", "artist", "engineer", "monk", "striker", "orchestrator", "knight", "fighter",
         "ranger", "assassin", "wizard", "elementalist", "chanter", "cleric", "bard", "rider", "gunner", "thunderer", "battlemaster",
         "lumines", "runewarrior", "runeblade"]
BASE = {"knight": "warrior", "fighter": "warrior", "assassin": "scout", "ranger": "scout", "wizard": "mage", "elementalist": "mage",
        "cleric": "priest", "chanter": "priest"}
CLASSES_20 = ["knight", "fighter", "ranger", "assassin", "wizard", "elementalist", "chanter", "cleric"]
ROW = ["power", "health", "agility", "accuracy", "knowledge", "will", "hp", "mp", "evasion", "physicalAccuracy", "magicalAccuracy"]


class Literal:
    """A reader of a JavaScript object literal as data: objects, arrays, strings, numbers, !0/!1, true/false/null."""

    def __init__(self, text: str) -> None:
        self.s, self.i = text, 0

    def ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t\r\n":
            self.i += 1

    def value(self):
        self.ws()
        ch = self.s[self.i]
        if ch == "{":
            return self.obj()
        if ch == "[":
            return self.arr()
        if ch in "`'\"":
            return self.string()
        if ch == "!":
            self.i += 2
            return self.s[self.i - 1] == "0"
        found = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?", re.I).match(self.s, self.i)
        if found:
            self.i = found.end()
            text = found.group(0)
            number = float(text)
            return int(number) if number.is_integer() and not re.search(r"[.e]", text, re.I) else number
        word = re.compile(r"[A-Za-z_$][\w$]*").match(self.s, self.i)
        if word:
            self.i = word.end()
            return {"true": True, "false": False, "null": None, "void": None}.get(word.group(0), word.group(0))
        raise ValueError(f"unexpected {self.s[self.i:self.i + 30]!r} at {self.i}")

    def string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        out = []
        while self.s[self.i] != quote:
            if self.s[self.i] == "\\":
                self.i += 1
                out.append({"n": "\n", "t": "\t"}.get(self.s[self.i], self.s[self.i]))
            else:
                out.append(self.s[self.i])
            self.i += 1
        self.i += 1
        return "".join(out)

    def key(self) -> str:
        self.ws()
        if self.s[self.i] in "`'\"":
            return self.string()
        found = re.compile(r"[\w$]+").match(self.s, self.i)
        self.i = found.end()
        return found.group(0)

    def obj(self) -> dict:
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            k = self.key()
            self.ws()
            assert self.s[self.i] == ":", self.s[self.i:self.i + 20]
            self.i += 1
            out[k] = self.value()
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1

    def arr(self) -> list:
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1


def variables(text: str) -> dict:
    """Every `var name=<literal>` of a chunk, read as data (references to other names stay their names)."""
    out = {}
    for found in re.finditer(r"(?:^|;)\s*var (\w+)=", text):
        reader = Literal(text)
        reader.i = found.end()
        try:
            out[found.group(1)] = reader.value()
        except (ValueError, AssertionError, IndexError):
            continue
    return out


def class_stats(raw: dict) -> dict:
    """class -> rows by level (the site's vq(): the base class's rows but its last, then the class's, sorted by HP)."""
    out = {}
    for name in CLASSES_20:
        own = raw.get(str(ORDER.index(name)), [])
        base = raw.get(str(ORDER.index(BASE[name])), [])
        rows = sorted([*base[:-1], *own], key=lambda r: r[6])
        out[name] = [dict(zip(ROW, r)) for r in rows]
    return out


FRESH = ROOT / "client_extract" / "fresh_catalog"
ICONS = ROOT / "data" / "icons"


def client_strings() -> dict[str, str]:
    """STR_… -> Russian, from the client's string files (UTF-16 or UTF-8)."""
    out = {}
    for path in (FRESH / "raw").glob("client_strings_*.xml"):
        raw = path.read_bytes()
        text = raw.decode("utf-16" if raw[:2] in (bytes([255, 254]), bytes([254, 255])) else "utf-8", errors="replace")
        for key, body in re.findall(r"<name>([^<]+)</name>\s*<body>(.*?)</body>", text, re.S):
            out.setdefault(key.strip().upper(), re.sub(r"\s+", " ", body).strip())
    return out


def copy_icon(name: str, folder: str) -> str | None:
    """A picture of the client export into data/icons/<folder>/ (once); its path for Icon, or None."""
    if not name:
        return None
    stem = name.lower()
    src = FRESH / "icons" / ("skills" if folder == "skills" else "items") / f"{stem}.png"
    target_dir = ICONS / folder if folder else ICONS
    target = target_dir / f"{stem}.png"
    if not target.is_file():
        if not src.is_file():
            return None
        target_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
    return f"{folder}/{stem}" if folder else stem


def active_skills(raw: dict, strings: dict[str, str]) -> dict:
    """class -> its active skills (the chain by character level: name, icon, effects); «share» skills can be cast on others."""
    out = {}
    for name in CLASSES_20:
        rows = []
        for skill in raw.get(str(ORDER.index(name)), []):
            chain = []
            for step in skill["chain"]:
                if all(e.get("f") for e in step["effects"]):
                    continue  # flying only
                chain.append({"level": step["char_lvl"], "name": strings.get(str(step["desc"]).upper(), step["desc"]),
                              "icon": copy_icon(step.get("icon", ""), "skills"), "effects": step["effects"]})
            if chain and any(e["type"] in ("statup", "statboost", "weaponstatup", "weaponstatboost", "aura", "boosthate")
                             for step in chain for e in step["effects"]):
                rows.append({"id": skill["id"], "share": bool(skill.get("share")), "chain": chain})
        out[name] = rows
    return out


def scrolls(raw: list, strings: dict[str, str]) -> list:
    return [{"type": s["type"], "effects": s["effects"],
             "levels": [{"level": l["level"], "minLevel": l["min_use_level"], "name": strings.get(str(l["desc"]).upper(), l["desc"]),
                         "icon": copy_icon(l.get("icon", ""), "")} for l in s["levels"]]} for s in raw]


def main() -> int:
    stats = variables((SRC / "chunk-Bf6HBxlh.js").read_text(encoding="utf-8"))
    passive = variables((SRC / "chunk-BSN2daZN.js").read_text(encoding="utf-8"))
    strings = client_strings()
    active = active_skills(variables((SRC / "chunk-KMjd5OzS.js").read_text(encoding="utf-8")).get("t", {}), strings)
    scroll_list = scrolls(variables((SRC / "chunk-DZ4lrw_22.js").read_text(encoding="utf-8")).get("l", []), strings)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "active_skills.json").write_text(json.dumps({
        "source": "aiongear.fun static/skills/eu20/active_skills.json (downloads/aiongear/chunk-KMjd5OzS.js), 09.11.2026; names and icons: the client",
        "classes": active}, ensure_ascii=False), encoding="utf-8")
    (OUT / "scrolls.json").write_text(json.dumps({
        "source": "aiongear.fun static/scrolls/eu20/scrolls.json (downloads/aiongear/chunk-DZ4lrw_22.js), 09.11.2026; names and icons: the client",
        "scrolls": scroll_list}, ensure_ascii=False), encoding="utf-8")
    print("active skills:", {k: len(v) for k, v in active.items()}, "scrolls:", len(scroll_list))
    OUT.mkdir(parents=True, exist_ok=True)
    table = class_stats(next(iter(stats.values())))
    (OUT / "class_stats.json").write_text(json.dumps({
        "source": "aiongear.fun static/stats/eu20/class_stats.json (downloads/aiongear/chunk-Bf6HBxlh.js), 09.11.2026",
        "row": "one row per level from 1; evasion is also block and parry", "classes": table}, ensure_ascii=False), encoding="utf-8")
    skills = passive.get("t", {})
    ids = passive.get("a", {})
    class_skills = {name: ids.get(str(ORDER.index(name)), {}) for name in CLASSES_20} if isinstance(ids, dict) else {}
    (OUT / "passive_skills.json").write_text(json.dumps({
        "source": "aiongear.fun static/skills/eu20/passive_skills.json (downloads/aiongear/chunk-BSN2daZN.js), 09.11.2026",
        "skills": skills, "class_skill_ids": class_skills}, ensure_ascii=False), encoding="utf-8")
    print({name: len(rows) for name, rows in table.items()}, "passive skills:", len(skills),
          "classes with skills:", {k: len(v) for k, v in class_skills.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
