"""Parse Aion Chat.log lines of the «Поиск группы» channel."""

import re
from dataclasses import dataclass

CHANNEL = "[3.Поиск группы]"

_LINE_RE = re.compile(
    r"^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) : "
    + re.escape(CHANNEL)
    + r" \[charname:([^;\]]+);[^\]]*\]: (.*)$"
)
_CMD_RE = re.compile(r"\[cmd:[^\]]*\]")
_ITEM_RE = re.compile(r"\[item:[^\]]*\]")


@dataclass(frozen=True)
class ChatMessage:
    time: str
    nick: str
    text: str
    raw: str


def clean_text(text: str) -> str:
    """Drop [cmd:...] markup, shorten item links, trim spaces."""
    text = _CMD_RE.sub("", text)
    text = _ITEM_RE.sub("[item]", text)
    return text.strip()


def parse_line(line: str) -> ChatMessage | None:
    """Return the message for a «Поиск группы» line, else None."""
    line = line.rstrip("\r\n")
    match = _LINE_RE.match(line)
    if match is None:
        return None
    time, nick, body = match.groups()
    return ChatMessage(time=time, nick=nick, text=clean_text(body), raw=line)
