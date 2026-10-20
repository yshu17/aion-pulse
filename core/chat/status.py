"""What the watching says about itself: the status line, its short chip, and the empty feed.

    search_hint(mode, keywords, watch_items) -> "нет ключевых слов" / "" ...   what the search mode is missing
    empty_feed(running, mode, keywords, watch_items) -> (title, hint)        the text of an empty «Поиск» feed
    watching_status(path, hint) / NOT_FOUND / GAME_OFF / STOPPED              the status line
    status_chip(text) -> (short text, kind)   kind: "live", "warn", "error", "idle" (a window maps it to a style)
Portable core: plain text in, plain text out.
"""

from __future__ import annotations

from core.text import plural

STOPPED = "Остановлен"
GAME_OFF = "Игра не запущена — слежение остановлено"
STATUS_CHARS = 20  # the chip keeps one width; the full text goes to its hint
HINT_SEP = "  ·  "


def watching_status(path: str, hint: str = "") -> str:
    return f"Слежу за {path}" + (f"{HINT_SEP}{hint}" if hint else "")


def not_found_status(path: str) -> str:
    return f"Chat.log не найден: {path}"


def error_status(error: object) -> str:
    return f"Ошибка: {error}"


def read_error_status(error: object) -> str:
    return f"Ошибка чтения: {error}"


def game_off_note(clock_hm: str) -> str:
    """The feed line when the game is closed, «— 18:05 Игра не запущена …: запусти игру и нажми Start —»."""
    return f"— {clock_hm} {GAME_OFF}: запусти игру и нажми Start —"


def search_hint(mode: str, keywords: list[str], watch_items: list[str]) -> str:
    """What the chosen search mode is missing, e.g. «нет ключевых слов»; "" when it can find something."""
    no_words = not keywords and mode in ("words", "and", "or")
    no_items = not watch_items and mode in ("items", "and", "or")
    if mode == "or" and not (no_words and no_items):
        return ""
    missing = [text for flag, text in ((no_words, "нет ключевых слов"), (no_items, "не отмечены предметы")) if flag]
    return ", ".join(missing)


def empty_feed(running: bool, mode: str, keywords: list[str], watch_items: list[str]) -> tuple[str, str]:
    """(title, hint) of the empty feed: what will appear there and what is being looked for."""
    missing = search_hint(mode, keywords, watch_items)
    hint = (f"Сейчас {missing}" if missing else
            f"Ищу: {plural(len(keywords), 'слово', 'слова', 'слов')}, "
            f"{plural(len(watch_items), 'предмет', 'предмета', 'предметов')}")
    title = "Слежу — совпадений пока нет" if running else "Нажми Start — здесь появятся совпадения"
    return title, hint


def status_chip(text: str) -> tuple[str, str]:
    """The compact status of the chip and its kind: live, warn, error or idle."""
    if text.startswith("Слежу"):
        hint = text.split(HINT_SEP, 1)[1] if HINT_SEP in text else ""
        return "Слежу" + (f"{HINT_SEP}{hint}" if hint else ""), "live"
    if text.startswith("Игра не запущена"):
        return "Игра не запущена", "warn"
    if text.startswith("Chat.log не найден"):
        return "Chat.log не найден", "warn"
    if text.startswith("Ошибка"):
        return (text if len(text) <= STATUS_CHARS else text[:STATUS_CHARS - 1] + "…"), "error"
    return "Не слежу", "idle"
