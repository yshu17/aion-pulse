"""SN-4: the old alerts go through the notification center — chat matches and «the game is not running».

Tk-free core (PAIR.md rule 17). The app feeds it plain data and acts on what it returns:

* ``chat_match(alert_ids, entries, nag)`` — one toast per batch of matches; ``entries`` are ``(nick, text, hits)``.
  Standard mode: the center plays the beep (its per-source sound rule applies). Nag mode: the toast offers «Принять»
  and stays silent — the nag alarm loops its own sound until the user reacts.
* ``toast_accepted(event)`` — «Принять» on the toast: the tracker alert ids to accept (once).
* ``alerts_done(alert_ids)`` — alerts accepted in the feed or missed: a toast whose alerts are all done is closed.
* ``game_running(running)`` — a toast with «Проверить снова» when the game stops; closed when it is back.

Sources: ``chat`` (kind ``chat``), ``status`` (kind ``warning``). Action ids: ``accept``, ``retry``.
"""

from __future__ import annotations

from core.notify.notify_center import Notification, NotificationAction, NotificationCenter

CHAT = "chat"
STATUS = "status"
GAME_OFF_TITLE = "Игра не запущена"
GAME_OFF_TEXT = "После запуска Aion нажми «Проверить снова»."


class AlertBridge:
    def __init__(self, center: NotificationCenter) -> None:
        self.center = center
        self._alerts: dict[int, set[int]] = {}  # notification id -> tracker alert ids still waiting
        self._game_off: Notification | None = None

    def chat_match(self, alert_ids: list[int], entries: list[tuple[str, str, list[str]]], nag: bool) -> Notification | None:
        if not entries:
            return None
        nick, text, hits = entries[0]
        words = ", ".join(dict.fromkeys(hit for _nick, _text, entry_hits in entries for hit in entry_hits))
        more = f" (и ещё {len(entries) - 1})" if len(entries) > 1 else ""
        actions = (NotificationAction("accept", "Принять"),) if nag else ()
        note = self.center.notify(CHAT, "chat", f"Найдено в чате: {words}", f"{nick}: {text}{more}", actions, sound=not nag)
        if note is not None and nag and alert_ids:
            self._alerts[note.id] = set(alert_ids)
        return note

    def toast_accepted(self, event: Notification | None) -> list[int]:
        if event is None:
            return []
        return sorted(self._alerts.pop(event.repeat_key or event.id, set()))

    def alerts_done(self, alert_ids: list[int]) -> None:
        done = set(alert_ids)
        for note_id, waiting in list(self._alerts.items()):
            waiting -= done
            if not waiting:
                del self._alerts[note_id]
                self.center.acknowledge(note_id)

    def game_running(self, running: bool) -> Notification | None:
        if running:
            if self._game_off is not None:
                self.center.acknowledge(self._game_off.id)
                self._game_off = None
            return None
        if self._game_off is not None:
            return None
        self._game_off = self.center.notify(STATUS, "warning", GAME_OFF_TITLE, GAME_OFF_TEXT,
                                            (NotificationAction("retry", "Проверить снова"),))
        return self._game_off
