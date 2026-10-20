"""Alert bookkeeping: found / reacted / missed counters and pending (unaccepted) alerts."""

from dataclasses import dataclass

from core.chat.parser import ChatMessage


@dataclass
class Alert:
    id: int
    msg: ChatMessage
    hits: list[str]
    created: float


class AlertTracker:
    def __init__(self, react_sec: float = 30) -> None:
        self.react_sec = react_sec  # 0 = wait for the user forever
        self.found = 0
        self.reacted = 0
        self.missed = 0
        self._pending: dict[int, Alert] = {}
        self._next_id = 1

    @property
    def pending_ids(self) -> list[int]:
        return list(self._pending)

    def add(self, msg: ChatMessage, hits: list[str], now: float, nag: bool) -> int:
        """Count a match. In nag mode it stays pending until accepted or expired."""
        alert_id = self._next_id
        self._next_id += 1
        self.found += 1
        if nag:
            self._pending[alert_id] = Alert(alert_id, msg, hits, now)
        return alert_id

    def accept(self, alert_id: int) -> bool:
        if self._pending.pop(alert_id, None) is None:
            return False
        self.reacted += 1
        return True

    def accept_all(self) -> list[int]:
        ids = self.pending_ids
        for alert_id in ids:
            self.accept(alert_id)
        return ids

    def expire(self, now: float) -> list[int]:
        """Move alerts older than react_sec to «missed». Returns their ids."""
        if self.react_sec <= 0:
            return []
        overdue = [a.id for a in self._pending.values() if now - a.created >= self.react_sec]
        for alert_id in overdue:
            del self._pending[alert_id]
            self.missed += 1
        return overdue

    def remaining(self, now: float) -> dict[int, float]:
        """Seconds left before each pending alert expires ({} when there is no timeout)."""
        if self.react_sec <= 0:
            return {}
        return {a.id: self.react_sec - (now - a.created) for a in self._pending.values()}

    def reset(self) -> None:
        """Zero the counters. Pending alerts stay pending."""
        self.found = self.reacted = self.missed = 0
