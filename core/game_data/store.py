"""Read a game data folder built by `build.build_all`.

    data = GameData(Path("data/game"))
    data.manifest["built"]
    data.by_id("items")["100000001"]["name"]        # a section is loaded on the first use and kept
    data.table("vendors")                           # (columns, rows) for the big tables
    data.drops_of_npc("210065")                     # [{"item_id", "chance_min", "chance_max", "count_min", "count_max"}]
    data.droppers_of("100000133")                   # [{"npc_id", ...}]

A missing or broken file gives empty data, never a crash (core/DATA.md). The folder is a parameter.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

from .layout import DROPS_FILE, MANIFEST, SCHEMA, SECTION_FILES


class GameData:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._sections: dict[str, dict] = {}
        self._by_id: dict[str, dict[str, dict]] = {}
        self._drops: sqlite3.Connection | None = None
        self.manifest = self._read_json(self.folder / MANIFEST)

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            raw = path.read_bytes()
            if path.name.endswith(".gz"):
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, EOFError):
            return {}
        return data if isinstance(data, dict) else {}

    @property
    def usable(self) -> bool:
        """The folder has a manifest of a schema this reader knows."""
        return self.manifest.get("schema") == SCHEMA

    def section(self, name: str) -> dict:
        """The whole section object (``{"schema", "section", ...}``); ``{}`` when it is not built."""
        if name not in self._sections:
            self._sections[name] = self._read_json(self.folder / SECTION_FILES[name]) if name in SECTION_FILES else {}
        return self._sections[name]

    def records(self, name: str) -> list[dict]:
        return self.section(name).get("records", [])

    def by_id(self, name: str) -> dict[str, dict]:
        """The records of a section by ID (built once)."""
        if name not in self._by_id:
            self._by_id[name] = {record["id"]: record for record in self.records(name)}
        return self._by_id[name]

    def table(self, name: str) -> tuple[list[str], list[list]]:
        section = self.section(name)
        return section.get("columns", []), section.get("rows", [])

    # ---- drops (SQLite) -------------------------------------------------------------------------------------------

    def _drops_db(self) -> sqlite3.Connection | None:
        if self._drops is None:
            path = self.folder / DROPS_FILE
            if not path.is_file():
                return None
            try:
                self._drops = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
                self._drops.row_factory = sqlite3.Row
            except sqlite3.Error:
                return None
        return self._drops

    def _drop_rows(self, column: str, value: str) -> list[dict]:
        db = self._drops_db()
        if db is None or not value.isdigit():
            return []
        order = "item_id" if column == "npc_id" else "npc_id"
        try:
            return [dict(row) for row in db.execute(f"SELECT * FROM drops WHERE {column}=? ORDER BY {order}", (int(value),))]
        except sqlite3.Error:
            return []

    def drops_of_npc(self, npc_id: str) -> list[dict]:
        """What an NPC drops. ``[]`` also when the NPC was not checked: the drops are not a complete list."""
        return [{key: row[key] for key in ("item_id", "chance_min", "chance_max", "count_min", "count_max")} for row in self._drop_rows("npc_id", npc_id)]

    def droppers_of(self, item_id: str) -> list[dict]:
        return [{key: row[key] for key in ("npc_id", "chance_min", "chance_max", "count_min", "count_max")} for row in self._drop_rows("item_id", item_id)]

    def close(self) -> None:
        if self._drops is not None:
            self._drops.close()
            self._drops = None
