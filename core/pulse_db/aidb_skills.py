"""The damage of a skill, read from the skill pages of aidb.ru (downloads/aidb_skills/pages, tools/fetch_aidb_skills.py).

    read_skill_damage(pages) -> {skill id: {"text": str, "min": int | None, "max": int | None}}

The client has no plain per-level damage numbers, so the text of the page's «Описание» block is the source: a line such as
«Физическая атака, наносит цели 661-665 ед. урона.». A page of an other version or one that does not parse is left out.
The text is kept as it is; min and max are the numbers of «N-M ед. урона» (or «N ед. урона», then min = max = N); None when
the page names no damage. Pure: no database, no paths but the folder given.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

DESCR = re.compile(r'id="descr">.*?<div class="rich">(.*?)</div>', re.S)
TAGS = re.compile(r"<[^>]+>")
DAMAGE = re.compile(r"(\d+)(?:\s*-\s*(\d+))?\s*ед\.\s*урона")


def parse_page(raw: str) -> dict | None:
    """The description and the damage of one skill page; None when the page has no description block."""
    found = DESCR.search(raw)
    if not found:
        return None
    text = " ".join(html.unescape(TAGS.sub(" ", found.group(1))).split())
    if not text:
        return None
    hit = DAMAGE.search(text)
    low = int(hit.group(1)) if hit else None
    high = (int(hit.group(2)) if hit.group(2) else low) if hit else None
    return {"text": text, "min": low, "max": high}


def read_skill_damage(pages: Path | None) -> dict[int, dict]:
    """Every page of the folder (<skill id>.html) read by parse_page, by skill id."""
    out: dict[int, dict] = {}
    if not pages or not pages.is_dir():
        return out
    for path in sorted(pages.glob("*.html")):
        if not path.stem.isdigit():
            continue
        parsed = parse_page(path.read_bytes().decode("utf-8", "replace"))
        if parsed:
            out[int(path.stem)] = parsed
    return out
