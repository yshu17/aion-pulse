"""Portable core of Pulse (ADR-001): the logic the launcher needs, without Tk and without Windows API.

Rules (checked by tests/test_core_boundary.py):
  * only the standard library and other `core` modules are imported;
  * no file is read by a path computed inside the core: paths, names and settings come in as parameters;
  * no timers owned by the program: the caller ticks (`search_worker` runs its own worker thread).

Groups: chat, notify, schedule, bestiary, map, items, settings, update, telegram. One JSON entry point for other
programs: `core.api.CoreApi` and `python -m core` (stdin / stdout, one JSON object per line; see core/API.md).
"""

__version__ = "2.0.0"  # the API contract version: major = an incompatible change of a method or its data
