"""Background search for the Bestiary: a UI that types faster than the database answers never waits for it. No Tk.

    worker = SearchWorker(path)          # nothing starts until the first submit
    worker.submit(seq, text, "monster", min_level=10)   # same arguments as BestiaryStore.search
    worker.latest() -> SearchResult | None              # newest finished answer, older ones are dropped

One thread with its own database connection (a SQLite connection belongs to the thread that made it). Requests that
queue up while a search runs are collapsed to the newest one: of ten keystrokes only the last is searched.
"""

from __future__ import annotations

import queue
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from core.bestiary.bestiary_store import BestiaryStore


@dataclass
class SearchResult:
    seq: int
    rows: list[dict] = field(default_factory=list)
    total: int = 0
    error: str = ""


class SearchWorker:
    def __init__(self, path: Path, store_factory=BestiaryStore):
        self.path = Path(path)
        self._factory = store_factory
        self._jobs: queue.Queue = queue.Queue()
        self._done: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    def submit(self, seq: int, *args, **kwargs) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="bestiary-search", daemon=True)
            self._thread.start()
        self._jobs.put((seq, args, kwargs))

    def latest(self) -> SearchResult | None:
        """The newest finished result, or None. Anything older that was waiting is discarded."""
        result = None
        while True:
            try:
                result = self._done.get_nowait()
            except queue.Empty:
                return result

    def close(self) -> None:
        if self._thread is not None:
            self._jobs.put(None)
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        try:
            store = self._factory(self.path)
        except (OSError, ValueError, sqlite3.Error) as exc:
            store, failure = None, str(exc)
        else:
            failure = ""
        try:
            while True:
                job = self._jobs.get()
                if job is None:
                    return
                while True:  # collapse a burst of requests to the newest
                    try:
                        newer = self._jobs.get_nowait()
                    except queue.Empty:
                        break
                    if newer is None:
                        return
                    job = newer
                seq, args, kwargs = job
                if store is None:
                    self._done.put(SearchResult(seq, error=failure))
                    continue
                try:
                    rows, total = store.search(*args, **kwargs)
                except (sqlite3.Error, ValueError) as exc:
                    self._done.put(SearchResult(seq, error=str(exc)))
                else:
                    self._done.put(SearchResult(seq, rows, total))
        finally:
            if store is not None:
                store.close()
