"""Which «Весь чат» category a log line belongs to, and which system lines are notices.

Portable core. `category(line)` -> "Поиск группы" / "Общий" / "Личное" / "Группа" / "Легион" or None (not shown);
channel-less player lines are told apart by the name colour the game writes into [charname:Name;r g b].
`is_notice(line)` is true for system «information» (loot, kinah, can't-do-that…), not for combat lines.
"""

import re

from core.chat.parser import ChatLine

_NAME_COLORS = {
    "1.0000 1.0000 1.0000": "Общий",
    "0.6275 1.0000 0.6275": "Личное",
    "0.0196 0.7843 0.8431": "Группа",
    "0.6118 0.9059 0.8627": "Легион",
}
_WHISPER_VERBS = {"шепчет", "шепчете"}
_NOTICE = re.compile(
    r"^(Получено|Получен[аы]?|Вы получили|Использовано|Невозможно|Нельзя|Недостаточно|Вы не можете|"
    r"Цель находится|Кто-то уже|Не удалось|Задание|Вы вошли|Вы покинули)"
    r"|получает: \[|присоединил|покинул[аи]? (группу|легион)|кинар",
)


def category(line: ChatLine) -> str | None:
    """Which «Весь чат» category a player line belongs to; None = not shown."""
    channel = line.channel or ""
    if channel.startswith("3."):
        return "Поиск группы"
    if channel.startswith("1."):
        return "Общий"
    if channel:
        return None  # trade and other numbered channels
    if line.verb in _WHISPER_VERBS:
        return "Личное"
    return _NAME_COLORS.get(line.color or "")


def is_notice(line: ChatLine) -> bool:
    """System «information» and «errors/notifications» (loot, kinah, can't-do-that…), not combat."""
    if line.is_player:
        return False
    if line.channel is not None:
        return not line.channel.startswith("?")  # [Event], [Ежедневно] …; unreadable ones are skipped
    return "??" not in line.text and bool(_NOTICE.search(line.text))
