"""The names of the files in a game data folder (shared by the builder and the reader)."""

from __future__ import annotations

SCHEMA = 1

MANIFEST = "manifest.json"
REPORT = "report.json"

# section -> file; a section is a JSON object {"schema", "section", ...} (see build.py for each shape)
SECTION_FILES = {
    "items": "items.json.gz",
    "recipes": "recipes.json.gz",
    "npcs": "npcs.json.gz",
    "maps": "maps.json",
    "labels": "labels.json.gz",
    "npc_points": "npc_points.json.gz",
    "vendors": "vendors.json.gz",
    "quests": "quests.json.gz",
    "skills": "skills.json.gz",
    "stigmas": "stigmas.json",
    "classes": "classes.json",
}
DROPS_FILE = "drops.sqlite"  # SQLite: too many rows for a JSON file (see build.write_drops)
DROPS_VERSION = 1  # PRAGMA user_version of drops.sqlite
