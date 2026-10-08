"""Parse Aion Chat.log lines of the «Поиск группы» channel."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

CHANNEL = "[3.Поиск группы]"

_LINE_RE = re.compile(
    r"^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) : "
    + re.escape(CHANNEL)
    + r" \[charname:([^;\]]+);[^\]]*\]: (.*)$"
)
_CMD_RE = re.compile(r"\[cmd:[^\]]*\]")
_ITEM_RE = re.compile(r"\[item:(\d*)[^\]]*\]")


@dataclass(frozen=True)
class ChatMessage:
    time: str
    nick: str
    text: str
    raw: str
    item_ids: tuple[str, ...] = ()


def clean_text(text: str, names: Mapping[str, str] | None = None) -> str:
    """Drop [cmd:...] markup, show item links as [name] (or [item] if unknown), trim spaces."""
    names = names or {}
    text = _CMD_RE.sub("", text)
    text = _ITEM_RE.sub(lambda m: f"[{names.get(m.group(1), 'item')}]", text)
    return text.strip()


def parse_line(line: str, names: Mapping[str, str] | None = None) -> ChatMessage | None:
    """Return the message for a «Поиск группы» line, else None."""
    line = line.rstrip("\r\n")
    match = _LINE_RE.match(line)
    if match is None:
        return None
    time, nick, body = match.groups()
    item_ids = tuple(item_id for item_id in _ITEM_RE.findall(body) if item_id)
    return ChatMessage(
        time=time, nick=nick, text=clean_text(body, names), raw=line, item_ids=item_ids
    )
