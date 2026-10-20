"""Repeat series for the nag mode: one player re-posting the same thing (e.g. «1/12 … 11/12»).

A series is keyed by (nick, match) — the match is a watched item name or a keyword. Every message
of a series rings the alarm until the user accepts one of them; after that the rest of the series
comes in silently. A series ends after SERIES_LIMIT messages, after SERIES_IDLE_SEC without a new
message, or on reset(). A message with several matches belongs to several series and is silent only
if all of them are already accepted.
"""

from dataclasses import dataclass, field

from core.chat.matcher import normalize
from core.chat.parser import ChatMessage

SERIES_LIMIT = 12  # «1/12 … 12/12»: the 13th message starts a new series
SERIES_IDLE_SEC = 15 * 60


@dataclass
class Series:
    count: int = 0
    last: float = 0.0
    accepted: bool = False
    alert_ids: set[int] = field(default_factory=set)


class SeriesTracker:
    def __init__(self, limit: int = SERIES_LIMIT, idle_sec: float = SERIES_IDLE_SEC) -> None:
        self.limit = limit
        self.idle_sec = idle_sec
        self._series: dict[tuple[str, str], Series] = {}

    @staticmethod
    def keys(msg: ChatMessage, hits: list[str]) -> list[tuple[str, str]]:
        nick = msg.nick.strip().lower()
        return list(dict.fromkeys((nick, normalize(hit.strip())) for hit in hits if hit.strip()))

    def is_silent(self, msg: ChatMessage, hits: list[str], now: float) -> bool:
        """True when every match of the message continues a series the user already accepted."""
        series = [self._live(key, now) for key in self.keys(msg, hits)]
        return bool(series) and all(s is not None and s.accepted for s in series)

    def record(self, msg: ChatMessage, hits: list[str], now: float, alert_id: int | None = None) -> None:
        """Add the message to its series (starting new ones where needed)."""
        for key in self.keys(msg, hits):
            series = self._live(key, now)
            if series is None:
                series = self._series[key] = Series()
            series.count += 1
            series.last = now
            if alert_id is not None:
                series.alert_ids.add(alert_id)

    def accept(self, alert_id: int) -> set[int]:
        """Mark the series of an accepted alert as accepted. Returns the other alerts in them."""
        others: set[int] = set()
        for series in self._series.values():
            if alert_id in series.alert_ids:
                series.accepted = True
                others |= series.alert_ids
        others.discard(alert_id)
        return others

    def reset(self) -> None:
        self._series.clear()

    def _live(self, key: tuple[str, str], now: float) -> Series | None:
        series = self._series.get(key)
        if series is None or series.count >= self.limit or now - series.last >= self.idle_sec:
            return None
        return series
