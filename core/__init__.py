"""Portable core of Pulse (ADR-001): the logic the launcher needs, without Tk and without Windows API.

Rules (checked by tests/test_core_boundary.py):
  * only the standard library and other `core` modules are imported;
  * no file is read by a path computed inside the core: paths, names and settings come in as parameters;
  * no timers and no threads owned by the program: the caller ticks (`search_worker` runs its own worker thread).

Groups: chat, notify, schedule, bestiary, map, items, telegram. The old names `watcher.<module>` stay as aliases.
"""
