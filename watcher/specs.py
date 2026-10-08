"""Item spec (tooltip) data: parsed from kb.aionempire.com item pages, stored as JSON.

A spec is {"name", "grade", "blocks": [...]}. Block kinds:
  pairs   {"rows": [[name, value], ...]}            one pair per line (rank, type)
  props   {"lines": [...]}                          yellow trade restrictions
  warning {"text"}                                  red level requirement
  hr      {}                                        separator
  grid    {"pairs": [[name, value], ...], "dim"}    stats, two pairs per line
  text    {"text", "style": normal|epic|muted}
  stones  {"count", "bonus"}                        manastone slots
  set     {"items": [name, ...]}                    set pieces
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

_VOID = {"img", "br", "hr", "input", "meta", "link"}
_SPACES = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACES.sub(" ", text).replace("%%", "%").strip()


class _SpecParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.name = ""
        self.grade = ""
        self.blocks: list[dict] = []
        self._stack: list[tuple[str, set[str]]] = []
        self._active = False  # from item-base-wrapper to the end of item-info-tabs-wrapper
        self._grid: dict | None = None
        self._pending_name: str | None = None
        self._field: str | None = None  # "name" | "value" while inside attr-name / attr-value
        self._buf: list[str] = []
        self._in_title = False

    # --- helpers -------------------------------------------------------------
    def _classes_in_stack(self) -> set[str]:
        out: set[str] = set()
        for _tag, classes in self._stack:
            out |= classes
        return out

    def _start_grid(self, single: bool) -> None:
        self._grid = {"single": single, "pairs": [], "dim": False, "stones": 0, "bonus": 0, "set": []}

    def _end_grid(self) -> None:
        grid, self._grid = self._grid, None
        if grid is None:
            return
        if grid["set"]:
            self.blocks.append({"kind": "set", "items": grid["set"]})
        elif grid["stones"]:
            self.blocks.append({"kind": "stones", "count": grid["stones"], "bonus": grid["bonus"]})
        elif grid["pairs"]:
            if grid["single"]:
                last = self.blocks[-1] if self.blocks else None
                if last and last["kind"] == "pairs":
                    last["rows"].extend(grid["pairs"])
                else:
                    self.blocks.append({"kind": "pairs", "rows": grid["pairs"]})
            else:
                self.blocks.append({"kind": "grid", "pairs": grid["pairs"], "dim": grid["dim"]})

    def _text(self, text: str, style: str) -> None:
        text = _clean(text)
        if text:
            self.blocks.append({"kind": "text", "text": text, "style": style})

    # --- HTMLParser ----------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        if tag == "h1" and "item-desc" in classes:
            self._in_title = True
            self.grade = next((c for c in classes if c != "item-desc"), "")
        if "item-base-wrapper" in classes:
            self._active = True
        if tag == "hr" and self._active and self._grid is None:
            self.blocks.append({"kind": "hr"})
        if tag in _VOID:
            return
        self._stack.append((tag, classes))
        if not self._active:
            return
        if tag == "div" and {"attributes-info", "table"} <= classes:
            self._start_grid(single="type-info" in self._classes_in_stack())
        elif "attr-name" in classes or "attr-value" in classes:
            self._field = "name" if "attr-name" in classes else "value"
            self._buf = []
            if "disabled" in classes and self._grid is not None:
                self._grid["dim"] = True
        elif "stone-slot" in classes and self._grid is not None:
            self._grid["stones"] += 1
            if "slot-bonus" in classes:
                self._grid["bonus"] += 1
        elif tag == "a" and "setitem-piece" in classes:
            self._buf = []
            self._field = "set"
        elif tag == "div" and ({"properties", "warning", "attributes-desc"} & classes):
            self._buf = []
        elif tag == "span" and self._grid is None and "properties" not in self._classes_in_stack():
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID or not self._stack:
            return
        _tag, classes = self._stack.pop()
        if tag == "h1":
            self._in_title = False
        if not self._active:
            return
        if self._field in ("name", "value") and ("attr-name" in classes or "attr-value" in classes):
            value = _clean("".join(self._buf))
            if self._field == "name":
                self._pending_name = value
            elif self._grid is not None and (self._pending_name or value):
                self._grid["pairs"].append([self._pending_name or "", value])
                self._pending_name = None
            self._field = None
        elif self._field == "set" and tag == "a":
            if self._grid is not None:
                self._grid["set"].append(_clean("".join(self._buf)))
            self._field = None
        elif tag == "div" and {"attributes-info", "table"} <= classes:
            self._end_grid()
        elif tag == "span" and "properties" in self._classes_in_stack():
            line = _clean("".join(self._buf))
            if line:
                last = self.blocks[-1] if self.blocks else None
                if last and last["kind"] == "props":
                    last["lines"].append(line)
                else:
                    self.blocks.append({"kind": "props", "lines": [line]})
            self._buf = []
        elif tag == "div" and "warning" in classes:
            text = _clean("".join(self._buf))
            if text:
                self.blocks.append({"kind": "warning", "text": text})
        elif tag == "div" and "attributes-desc" in classes:
            self._text("".join(self._buf), "epic" if "epic" in classes else "normal")
        elif tag == "span" and self._grid is None and self._field is None:
            self._text("".join(self._buf), "muted")
            self._buf = []
        if tag == "div" and "item-info-tabs-wrapper" in classes:
            self._active = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.name += data
            return
        if not self._active:
            return
        in_text_div = any(
            {"properties", "warning", "attributes-desc"} & classes for _t, classes in self._stack
        )
        if self._field is not None or in_text_div or self._stack and self._stack[-1][0] == "span":
            self._buf.append(data)
        elif self._grid is None and _clean(data):
            # loose text between blocks, e.g. «Надев все предметы комплекта…»
            self._text(data, "normal")


def parse_spec(page_html: str) -> dict:
    """Parse the tooltip block of a kb.aionempire.com item page."""
    parser = _SpecParser()
    parser.feed(page_html)
    parser.close()
    return {"name": _clean(parser.name), "grade": parser.grade, "blocks": parser.blocks}


def load_specs(path: Path) -> dict[str, dict]:
    """Item id -> spec. A missing or broken file gives {}."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
