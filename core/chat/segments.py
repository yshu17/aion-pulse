"""How a cleaned chat message is drawn: plain text, item links, place links and the matched words.

    message_segments(text, hits, spec_items, grades) -> [Segment]

`text` is the cleaned message of core.chat.parser: item links are «[Name]», place / quest / «where» links are
«⟪shown¦map x y⟫». A Segment is one run of text with its kind:
    text   plain text; `hit` marks a matched keyword
    item   «<Name>» of an item link; `item_id` and `grade` when the item has a tooltip, `hit` when it matched
    place  «<Место · Келькмарос>»; `place` = (map id, game x, game y) when the link carries coordinates
An item link without a tooltip stays plain text, except names with «Рудр» (worth spotting in the chat).
Portable core: a window turns the kinds into colours, a launcher into HTML.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from core.chat.matcher import highlight_segments, normalize
from core.chat.parser import LINK_CLOSE, LINK_OPEN, split_place

# item link | place / quest / «where» link (see parser.clean_text)
LINKS = re.compile(rf"\[([^\[\]]+)\]|{LINK_OPEN}([^{LINK_OPEN}{LINK_CLOSE}]+){LINK_CLOSE}")
HIGHLIGHT_NAMES = re.compile(r"рудр", re.IGNORECASE)  # item links worth spotting even without a tooltip


@dataclass(frozen=True)
class Segment:
    text: str
    kind: str = "text"  # "text", "item" or "place"
    hit: bool = False
    item_id: str | None = None
    grade: str | None = None
    place: tuple[str, float, float] | None = None


def message_segments(message: str, hits: list[str] | None = None, spec_items: Mapping[str, str] | None = None,
                     grades: Mapping[str, str] | None = None) -> list[Segment]:
    """Segments of a message in order. spec_items: item name -> id (items with a tooltip); grades: id -> grade."""
    hits = hits or []
    spec_items = spec_items or {}
    grades = grades or {}
    out: list[Segment] = []
    pos = 0
    for match in LINKS.finditer(message):
        if match.group(1) is None:  # place / quest / «where» link
            out += _plain(message[pos:match.start()], hits)
            shown, place = split_place(match.group(2))
            out.append(Segment(f"<{shown}>", "place", place=place))
            pos = match.end()
            continue
        name = match.group(1)
        item_id = spec_items.get(name)
        if item_id is None and not HIGHLIGHT_NAMES.search(name):
            continue  # stays in the plain text around it
        out += _plain(message[pos:match.start()], hits)
        hit = any(normalize(h) in normalize(name) for h in hits if h.strip())
        out.append(Segment(f"<{name}>", "item", hit, item_id, grades.get(item_id) if item_id is not None else None))
        pos = match.end()
    out += _plain(message[pos:], hits)
    return out


def _plain(chunk: str, hits: list[str]) -> list[Segment]:
    if not hits:
        return [Segment(chunk)]
    return [Segment(piece, hit=is_hit) for piece, is_hit in highlight_segments(chunk, hits)] or [Segment("")]
