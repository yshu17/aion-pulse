"""Parse Aion Chat.log lines: any channel (ChatLine) and the «Поиск группы» search view (ChatMessage)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

CHANNEL = "[3.Поиск группы]"
LFG_PREFIX = "3."  # channel 3 is «Поиск группы»; some lines carry it with a broken encoding («3.????? ??????»)

_TIME_RE = re.compile(r"^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) : (.*)$")
_CHANNEL_RE = re.compile(r"^\[(?!charname:|item|cmd:|where:)([^\]]+)\] ?(.*)$")
_CHARNAME_RE = re.compile(r"^\[charname:([^;\]]+);([^\]]*)\](?: ([^:\[]{1,20}))?: ?(.*)$")
_PLAIN_NICK_RE = re.compile(r"^([^\s:\[\]]{2,24}): (.*)$")
_CMD_RE = re.compile(r"\[cmd:[^\]]*\]")
_ITEM_RE = re.compile(r"\[item:(\d*)[^\]]*\]")


@dataclass(frozen=True)
class ChatMessage:
    time: str
    nick: str
    text: str
    raw: str
    item_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChatLine:
    time: str
    channel: str | None
    nick: str | None
    text: str
    raw: str
    item_ids: tuple[str, ...] = ()
    color: str | None = None  # name colour «r g b» from [charname:…]; tells group/legion/whisper apart
    verb: str = ""  # «шепчет», «кричит» … between the name and the colon

    @property
    def is_player(self) -> bool:
        return self.nick is not None


def clean_text(text: str, names: Mapping[str, str] | None = None) -> str:
    """Drop [cmd:...] markup, show item links as [name] (or [item] if unknown), trim spaces."""
    names = names or {}
    text = _CMD_RE.sub("", text)
    text = _ITEM_RE.sub(lambda m: f"[{names.get(m.group(1), 'item')}]", text)
    return text.strip()


def parse_any_line(line: str, names: Mapping[str, str] | None = None) -> ChatLine | None:
    """Split a timestamped log line into channel, nick and text. None for lines without a time."""
    line = line.rstrip("\r\n")
    match = _TIME_RE.match(line)
    if match is None:
        return None
    time, rest = match.groups()
    channel = None
    channel_match = _CHANNEL_RE.match(rest)
    if channel_match is not None:
        channel, rest = channel_match.groups()
    nick = color = None
    verb = ""
    nick_match = _CHARNAME_RE.match(rest)
    if nick_match is not None:
        nick, color, verb, rest = nick_match.groups()
        verb = (verb or "").strip()
    elif channel is not None and channel.startswith(LFG_PREFIX):
        plain = _PLAIN_NICK_RE.match(rest)
        if plain is not None:
            nick, rest = plain.groups()
    item_ids = tuple(item_id for item_id in _ITEM_RE.findall(rest) if item_id)
    return ChatLine(
        time=time,
        channel=channel,
        nick=nick,
        text=clean_text(rest, names),
        raw=line,
        item_ids=item_ids,
        color=color,
        verb=verb,
    )


def parse_line(line: str, names: Mapping[str, str] | None = None) -> ChatMessage | None:
    """Return the message for a player line in «Поиск группы», else None."""
    parsed = parse_any_line(line, names)
    if parsed is None or parsed.nick is None or not (parsed.channel or "").startswith(LFG_PREFIX):
        return None
    return ChatMessage(
        time=parsed.time, nick=parsed.nick, text=parsed.text, raw=parsed.raw, item_ids=parsed.item_ids
    )
