"""The watching session without a window: Chat.log lines in, matches, alerts and place pins out.

    session = WatchSession(item_names, map_names, quest_names, keywords=[...], watch_items={id: name},
                           mode="or", cooldown_sec=60, alert_mode="standard", react_sec=30)
    feed = LogFeed(path, history_min)          # reads the file: history once, then the new lines
    history, lines = feed.poll()               # FileNotFoundError / OSError go to the caller
    batch = session.history(history, now)      # matches from before Start: listed, no alert, not counted
    batch = session.process(lines, now)        # live matches: counted; in «nag» mode they wait for «Принять»
    session.accept(alert_id) -> ids            # accepts the alert and the rest of its repeat series
    session.accept_all() / session.expire(now) -> ids, session.remaining(now) -> {id: seconds}

A Batch lists Entry(msg, hits, kind, alert_id) in log order — kind «history», «loud» (signal) or «quiet» (a repeat of a
series the user already accepted) — plus the place pins of every message and `announce`: alert ids not yet shown in a
notification. `now` is a monotonic clock in seconds; the session owns no timer and no thread.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.chat.alerts import AlertTracker
from core.chat.matcher import Matcher
from core.chat.parser import ChatMessage, display_text, parse_line, places_in
from core.chat.series import SeriesTracker
from core.chat.tailer import LogTailer
from core.map.zones import Place

HISTORY, LOUD, QUIET = "history", "loud", "quiet"
ALERT_MODES = ("standard", "nag")


@dataclass(frozen=True)
class Entry:
    msg: ChatMessage
    hits: list[str]
    kind: str  # HISTORY, LOUD or QUIET
    alert_id: int | None = None  # nag mode: the pending alert of a LOUD entry


@dataclass
class Batch:
    entries: list[Entry] = field(default_factory=list)
    places: list[Place] = field(default_factory=list)
    announce: list[int] = field(default_factory=list)  # pending alert ids not announced in a notification yet

    @property
    def loud(self) -> list[tuple[ChatMessage, list[str]]]:
        return [(entry.msg, entry.hits) for entry in self.entries if entry.kind == LOUD]


class WatchSession:
    def __init__(self, item_names: Mapping[str, str] | None = None, map_names: Mapping[str, str] | None = None,
                 quest_names: Mapping[str, str] | None = None, *, keywords: list[str] | None = None,
                 watch_items: Mapping[str, str] | None = None, mode: str = "or", cooldown_sec: float = 60,
                 alert_mode: str = "standard", react_sec: float = 30) -> None:
        self.item_names = item_names or {}
        self.map_names = map_names or {}
        self.quest_names = quest_names or {}
        self.matcher = Matcher(keywords or [], cooldown_sec, watch_items=dict(watch_items or {}), mode=mode)
        self.tracker = AlertTracker(react_sec)
        self.series = SeriesTracker()
        self.alert_mode = alert_mode if alert_mode in ALERT_MODES else "standard"
        self._announced: set[int] = set()

    # --- settings ----------------------------------------------------------------------
    def set_keywords(self, keywords: list[str]) -> None:
        self.matcher.set_keywords(keywords)

    def set_watch_items(self, watch_items: Mapping[str, str]) -> None:
        self.matcher.set_watch_items(dict(watch_items))

    def set_mode(self, mode: str) -> None:
        self.matcher.set_mode(mode)

    def set_alert_mode(self, alert_mode: str) -> None:
        self.alert_mode = alert_mode if alert_mode in ALERT_MODES else "standard"

    # --- lines -------------------------------------------------------------------------
    def parse(self, line: str) -> ChatMessage | None:
        return parse_line(line, self.item_names, maps=self.map_names, quests=self.quest_names)

    def history(self, lines: list[str], now: float) -> Batch:
        """Lines from before Start: matches are listed, nothing rings and nothing is counted."""
        batch = Batch()
        for msg in self._messages(lines, batch):
            hits = self.matcher.check(msg, now)
            if hits:
                batch.entries.append(Entry(msg, hits, HISTORY))
        return batch

    def process(self, lines: list[str], now: float) -> Batch:
        """New lines: count the matches; in nag mode each waits for «Принять» unless its series is accepted."""
        batch = Batch()
        nag = self.alert_mode == "nag"
        for msg in self._messages(lines, batch):
            hits = self.matcher.check(msg, now)
            if not hits:
                continue
            if not nag:
                self.tracker.add(msg, hits, now, nag=False)
                batch.entries.append(Entry(msg, hits, LOUD))
            elif self.series.is_silent(msg, hits, now):
                self.tracker.add(msg, hits, now, nag=False)
                self.series.record(msg, hits, now)
                batch.entries.append(Entry(msg, hits, QUIET))
            else:
                alert_id = self.tracker.add(msg, hits, now, nag=True)
                self.series.record(msg, hits, now, alert_id)
                batch.entries.append(Entry(msg, hits, LOUD, alert_id))
        if batch.loud:
            batch.announce = [a for a in self.tracker.pending_ids if a not in self._announced]
            self._announced.update(batch.announce)
        return batch

    def _messages(self, lines: list[str], batch: Batch):
        for line in lines:
            msg = self.parse(line)
            if msg is None:
                continue
            note = f"{msg.time[11:16]}  {msg.nick}: {display_text(msg.text)}"
            batch.places.extend(Place(map_id, x, y, label, note) for label, (map_id, x, y) in places_in(msg.text))
            yield msg

    # --- alerts ------------------------------------------------------------------------
    def accept(self, alert_id: int) -> list[int]:
        """Accept an alert and every other waiting alert of the same series. Returns the ids really accepted."""
        return [a for a in (alert_id, *sorted(self.series.accept(alert_id))) if self.tracker.accept(a)]

    def accept_all(self) -> list[int]:
        accepted = self.tracker.accept_all()
        for alert_id in accepted:
            self.series.accept(alert_id)
        return accepted

    def expire(self, now: float) -> list[int]:
        """Alerts nobody accepted within react_sec become «missed»."""
        return self.tracker.expire(now)

    def remaining(self, now: float) -> dict[int, float]:
        return self.tracker.remaining(now)

    @property
    def pending_ids(self) -> list[int]:
        return self.tracker.pending_ids

    @property
    def counters(self) -> tuple[int, int, int]:
        """(found, reacted, missed) of this run."""
        return self.tracker.found, self.tracker.reacted, self.tracker.missed

    def reset_counters(self) -> None:
        self.tracker.reset()

    def stop(self) -> None:
        """Stop: the repeat series start anew at the next Start."""
        self.series.reset()


class LogFeed:
    """Chat.log reading for a session: at the first poll the history of the last `history_min` minutes, then only the
    lines appended since the previous poll. A missing file raises FileNotFoundError and the next poll starts over."""

    def __init__(self, path: str, history_min: int = 0, clock: Callable[[], datetime] = datetime.now) -> None:
        self.path = str(path)
        self.history_min = history_min
        self.clock = clock
        self._tailer: LogTailer | None = None
        self._history_pending = history_min > 0

    def poll(self) -> tuple[list[str] | None, list[str]]:
        """(history lines or None, new lines)."""
        history = None
        try:
            if self._tailer is None:
                tailer = LogTailer(self.path)
                tailer.start_at_end()
                self._tailer = tailer
                if self._history_pending:
                    history = tailer.read_backlog(self.clock() - timedelta(minutes=self.history_min))
                    self._history_pending = False
            return history, self._tailer.read_new_lines()
        except FileNotFoundError:
            self._tailer = None
            raise
