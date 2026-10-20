"""Which notification to raise for a program event, and what a button on a notification means.

    release_notice(found, can_install, current, seen) -> Notice | None   a newer release on GitHub
    schedule_check_notice(status, value, known, seen, manual) -> Notice | None   the KB schedule check
    route_action(action, key, release_key, schedule_key) -> what to do          a button press on a notification

A Notice is (source, kind, title, text, actions) with actions as (id, label) pairs; the caller hands it to the
notification center. Portable core: no window, no network.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.schedule.schedule_update import decide
from core.update.updater import newer


@dataclass(frozen=True)
class Notice:
    source: str
    kind: str
    title: str
    text: str
    actions: tuple[tuple[str, str], ...] = ()


def release_notice(found: tuple[str, str] | None, can_install: bool, current: str, seen: str) -> Notice | None:
    """A newer release that the user has not dismissed yet. `found` = (tag, page url) of the latest release."""
    if found is None or not newer(found[0], current) or found[0] == seen:
        return None
    if can_install:  # the stable exe can install it: the user decides, the program only asks
        actions = (("install", "Обновить сейчас"), ("release", "Открыть релиз"), ("accept", "Позже"))
        text = "Pulse скачает Pulse.exe с GitHub, проверит контрольную сумму и перезапустится. Ничего без твоего «да»."
    else:
        actions = (("release", "Открыть релиз"), ("accept", "Понятно"))
        text = "Открой страницу релиза и скачай новый Pulse.exe. Программа сама ничего не скачивает."
    return Notice("app", "event", f"Доступна новая версия {found[0]}", text, actions)


def schedule_check_notice(status: str, value: str, known: str, seen: str, manual: bool) -> Notice | None:
    """status «ok» with the site fingerprint in `value`, or «err» with the error text."""
    if status == "err":
        return Notice("schedule", "warning", "Не удалось проверить расписание", value[:120]) if manual else None
    verdict = decide(known, value, seen, manual)
    if verdict == "same":
        return Notice("schedule", "event", "Расписание актуально",
                      "Картинка в базе знаний та же, по которой составлена сетка программы.")
    if verdict == "changed":
        return Notice("schedule", "event", "Расписание на сайте обновилось",
                      "Картинка в базе знаний новая — сверь сетку; data/schedule.json правится вручную.",
                      (("site", "Открыть статью"), ("accept", "Понятно")))
    return None


def route_action(action: str, key: int | None, release_key: int | None, schedule_key: int | None) -> str:
    """What a button press means. `key` is the notification id (or its repeat key); the other two are the ids of the
    release and schedule-check notifications currently shown.

    Results: open_site, install, open_release, release_seen, schedule_seen, accept_alerts, retry, open.
    """
    is_release = release_key is not None and key == release_key
    if action == "site":
        return "open_site"
    if action == "install" and is_release:
        return "install"
    if action == "release" and is_release:
        return "open_release"
    if action == "accept" and is_release:
        return "release_seen"
    if action == "accept" and schedule_key is not None and key == schedule_key:
        return "schedule_seen"
    if action == "accept":
        return "accept_alerts"
    if action == "retry":
        return "retry"
    return "open"
