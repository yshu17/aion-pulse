"""The game data core: one build from the client exports, one reader for the program.

    from core.game_data.build import Sources, build_all
    from core.game_data.store import GameData

* `build.build_all(sources, out_dir, built=..., client_build=...)` reads the exported TSV tables (``client_extract/*``,
  ``downloads/kb_drops``) and writes ``manifest.json``, ``report.json`` and one file per section into ``out_dir``;
* `store.GameData(folder)` reads that folder: ``records("items")``, ``by_id("npcs")``, ``drops_of_npc(id)`` …

Rules of the data (docs: GAME_DATA.md, core/DATA.md):

* the key of every record is the client ID, written as a string; links between sections are IDs only;
* the client wins over the site; every record has ``source`` (``client`` or ``site``);
* an unknown value is ``None``; a missing record means «not checked», an empty list «checked, nothing there»;
* sections are separate files, so a screen loads only what it shows; big tables are ``columns`` + ``rows``;
* the files are sorted and gzipped without a time stamp: the same input gives the same bytes.
"""
