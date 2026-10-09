"""Parse Aion Chat.log lines: any channel (ChatLine) and the «Поиск группы» search view (ChatMessage)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

CHANNEL = "[3.Поиск группы]"
LFG_PREFIX = "3."  # channel 3 is «Поиск группы»; some lines carry it with a broken encoding («3.????? ??????»)

_TIME_RE = re.compile(r"^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) : (.*)$")
_CHANNEL_RE = re.compile(r"^\[(?!charname:|item|cmd:|where:|pos:|quest:|recipe:)([^\]]+)\] ?(.*)$")
_CHARNAME_RE = re.compile(r"^\[charname:([^;\]]+);([^\]]*)\](?: ([^:\[]{1,20}))?: ?(.*)$")
_PLAIN_NICK_RE = re.compile(r"^([^\s:\[\]]{2,24}): (.*)$")
_CMD_RE = re.compile(r"\[cmd:[^\]]*\]")
_ITEM_RE = re.compile(r"\[(?:item|item_ex|recipe):(\d*)[^\]]*\]")
_POS_RE = re.compile(r"\[pos:([^;\]]*);(\d+)[^\]]*\]")
_QUEST_RE = re.compile(r"\[quest:(\d+)[^\]]*\]")
_WHERE_RE = re.compile(r"\[where:([^\]]*)\]")
# the game cuts long messages; a link left open at the end of the line is shown with «…»
_CUT_LINK_RE = re.compile(r"\[(?:where|pos|quest|item|item_ex|recipe|cmd):([^\]]*)$")
_EMOTES_RE = re.compile(r"\?{3,}")  # the client writes each chat smiley as «?» (no smileys in cp1251)

# Links that are not items are wrapped in these marks; the chat views draw them as <…> links.
LINK_OPEN, LINK_CLOSE = "⟪", "⟫"
EMOTE = "✦"  # stands for a run of smileys


def _load_map_names() -> dict[str, str]:
    """Map id -> official Russian zone name (data/map_names.tsv, from aidb.ru)."""
    from watcher.catalog import load_item_names, resource_root

    return load_item_names(resource_root() / "data" / "map_names.tsv")  # same «id<TAB>name» format


MAP_NAMES = _load_map_names()


def _load_quest_names() -> dict[str, str]:
    """Quest id -> name (data/quest_names.tsv, from kb.aionempire.com/quests)."""
    from watcher.catalog import load_item_names, resource_root

    return load_item_names(resource_root() / "data" / "quest_names.tsv")


QUEST_NAMES = _load_quest_names()


def _quest(match: re.Match) -> str:
    name = QUEST_NAMES.get(match.group(1))
    return f"{LINK_OPEN}Задание: {name}{LINK_CLOSE}" if name else f"{LINK_OPEN}Задание {match.group(1)}{LINK_CLOSE}"


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


def _place(match: re.Match) -> str:
    label = match.group(1) or "Место"
    region = MAP_NAMES.get(match.group(2))
    return f"{LINK_OPEN}{label} · {region}{LINK_CLOSE}" if region else f"{LINK_OPEN}{label}{LINK_CLOSE}"


def _cut_link(match: re.Match) -> str:
    """An unclosed link at the end of a cut message: keep the readable part of «where» text."""
    if match.group(0).startswith("[where:") and match.group(1).strip():
        return f"{LINK_OPEN}{match.group(1).strip()}…{LINK_CLOSE}"
    return "…"


def clean_text(text: str, names: Mapping[str, str] | None = None) -> str:
    """Drop [cmd:...] markup and make links readable.

    Item / recipe links become [name] ([item] if unknown); place, quest and «where» links become
    ⟪Место · Келькмарос⟫, ⟪Задание 2058⟫, ⟪text⟫; runs of «???» (smileys) become ✦.
    """
    names = names or {}
    text = _CUT_LINK_RE.sub(_cut_link, text.rstrip())
    text = _CMD_RE.sub("", text)
    text = _ITEM_RE.sub(lambda m: f"[{names.get(m.group(1), 'item')}]", text)
    text = _POS_RE.sub(_place, text)
    text = _QUEST_RE.sub(_quest, text)
    text = _WHERE_RE.sub(lambda m: f"{LINK_OPEN}{m.group(1).strip()}{LINK_CLOSE}", text)
    text = _EMOTES_RE.sub(EMOTE, text)
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
