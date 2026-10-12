"""Window-free notification center core.

UI adapters can pull queued events with :meth:`pop_next` and acknowledge them
when the user reacts. Sources, sound, counters, DND, retries and snoozes live
here so future toast and schedule views share the same rules.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Callable


@dataclass(frozen=True)
class NotificationAction:
    """An action offered by a future toast or notification list."""

    id: str
    label: str


@dataclass(frozen=True)
class Notification:
    """A normalized notification ready for presentation."""

    id: int
    source: str
    kind: str
    title: str
    text: str
    actions: tuple[NotificationAction, ...]
    created_at: datetime
    repeat_after: float | None = None
    repeat_key: int | None = None
    sound: bool = True


@dataclass
class SourceRule:
    enabled: bool = True
    sound: bool = True


class NotificationCenter:
    """Pure notification lifecycle and policy manager; it creates no windows.

    DND suppresses presentation only. Events still enter history, update source
    counters and play their configured sound. Disabled sources are ignored.
    """

    def __init__(
        self,
        *,
        sound: Callable[[Notification], None] | None = None,
        clock: Callable[[], float] | None = None,
        max_history: int = 500,
        max_queue: int = 100,
    ) -> None:
        if max_history < 1 or max_queue < 1:
            raise ValueError("history and queue limits must be positive")
        self._sound = sound or (lambda _event: None)
        self._clock = clock or monotonic
        self.max_history = max_history
        self.max_queue = max_queue
        self.rules: dict[str, SourceRule] = {}
        self.do_not_disturb = False
        self.history: deque[Notification] = deque(maxlen=max_history)
        self._queue: deque[Notification] = deque()
        self._counts: Counter[str] = Counter()
        self._next_id = 1
        self._acknowledged: set[int] = set()
        self._scheduled: dict[int, tuple[float, str]] = {}
        self._repeat_templates: dict[int, Notification] = {}

    @property
    def queued(self) -> int:
        return len(self._queue)

    @property
    def unread(self) -> int:
        return sum(1 for event in self.history if (event.repeat_key or event.id) not in self._acknowledged)

    def count(self, source: str | None = None) -> int:
        """Return the total accepted event count, optionally for one source."""
        return self._counts[source] if source is not None else sum(self._counts.values())

    def set_source(self, source: str, *, enabled: bool | None = None, sound: bool | None = None) -> None:
        rule = self.rules.setdefault(source, SourceRule())
        if enabled is not None:
            rule.enabled = enabled
        if sound is not None:
            rule.sound = sound

    def notify(
        self,
        source: str,
        kind: str,
        title: str,
        text: str = "",
        actions: tuple[NotificationAction, ...] | list[NotificationAction] = (),
        *,
        sound: bool = True,
        repeat_after: float | None = None,
    ) -> Notification | None:
        """Record and queue a notification, or ignore it if its source is off."""
        if not source or not kind or not title:
            raise ValueError("source, kind and title are required")
        if repeat_after is not None and repeat_after <= 0:
            raise ValueError("repeat_after must be positive")
        rule = self.rules.setdefault(source, SourceRule())
        if not rule.enabled:
            return None
        event = self._make(source, kind, title, text, tuple(actions), repeat_after, sound=sound)
        self._record(event, play_sound=sound and rule.sound)
        if not self.do_not_disturb:
            self._enqueue(event)
        if repeat_after is not None:
            self._repeat_templates[event.id] = event
            self._scheduled[event.id] = (self._clock() + repeat_after, "repeat")
        return event

    def pop_next(self) -> Notification | None:
        """Take the next event for a presenter (e.g. the toast window)."""
        if self.do_not_disturb:
            self._queue.clear()
            return None
        while self._queue:
            event = self._queue.popleft()
            if self.is_active(event):
                return event
        return None

    def is_active(self, event: Notification) -> bool:
        """A presenter must hide a series accepted elsewhere or disabled later."""
        return ((event.repeat_key or event.id) not in self._acknowledged
                and self.rules.get(event.source, SourceRule()).enabled)

    def acknowledge(self, event_id: int) -> bool:
        """Mark an event handled and cancel its pending repeat/snooze."""
        event = next((entry for entry in reversed(self.history) if entry.id == event_id), None)
        if event is None:
            return False
        self._acknowledged.add(event_id)
        repeat_key = event.repeat_key or event.id
        self._acknowledged.add(repeat_key)
        self._scheduled.pop(repeat_key, None)
        self._repeat_templates.pop(repeat_key, None)
        self._queue = deque((entry for entry in self._queue if (entry.repeat_key or entry.id) != repeat_key))
        return True

    def snooze(self, event_id: int, seconds: float) -> bool:
        """Schedule one more presentation after ``seconds``; returns if found."""
        if seconds <= 0:
            raise ValueError("snooze duration must be positive")
        event = next((entry for entry in reversed(self.history) if entry.id == event_id), None)
        if event is None or not self.is_active(event):
            return False
        repeat_key = event.repeat_key or event.id
        self._repeat_templates[repeat_key] = event
        self._scheduled[repeat_key] = (self._clock() + seconds, "snooze")
        self._queue = deque((entry for entry in self._queue if (entry.repeat_key or entry.id) != repeat_key))
        return True

    def tick(self) -> int:
        """Emit due repeats and snoozes; call from the app's existing timer."""
        now = self._clock()
        due = [(event_id, mode) for event_id, (deadline, mode) in self._scheduled.items() if deadline <= now]
        emitted = 0
        for event_id, mode in due:
            self._scheduled.pop(event_id, None)
            if event_id in self._acknowledged:
                continue
            template = self._repeat_templates.get(event_id)
            if template is None:
                template = next((entry for entry in reversed(self.history) if entry.id == event_id), None)
            if template is None:
                continue
            rule = self.rules.setdefault(template.source, SourceRule())
            if not rule.enabled:
                continue
            repeated = self._make(
                template.source, template.kind, template.title, template.text,
                template.actions, template.repeat_after, repeat_key=event_id, sound=template.sound,
            )
            self._record(repeated, play_sound=rule.sound and template.sound)
            if not self.do_not_disturb:
                self._enqueue(repeated)
            if template.repeat_after is not None:
                self._scheduled[event_id] = (now + template.repeat_after, "repeat")
            else:
                self._repeat_templates.pop(event_id, None)
            emitted += 1
        return emitted

    def _make(self, source: str, kind: str, title: str, text: str,
              actions: tuple[NotificationAction, ...], repeat_after: float | None,
              *, repeat_key: int | None = None, sound: bool = True) -> Notification:
        event = Notification(
            self._next_id, source, kind, title, text, actions,
            datetime.now(timezone.utc), repeat_after, repeat_key or self._next_id, sound,
        )
        self._next_id += 1
        return event

    def _record(self, event: Notification, *, play_sound: bool) -> None:
        self.history.append(event)
        self._counts[event.source] += 1
        # Keep acknowledgement bookkeeping bounded alongside history.
        retained_ids = {entry.repeat_key or entry.id for entry in self.history}
        retained_ids.update(entry.repeat_key or entry.id for entry in self._queue)
        self._acknowledged.intersection_update(retained_ids)
        if play_sound:
            self._sound(event)

    def _enqueue(self, event: Notification) -> None:
        if len(self._queue) >= self.max_queue:
            self._queue.popleft()
        self._queue.append(event)
