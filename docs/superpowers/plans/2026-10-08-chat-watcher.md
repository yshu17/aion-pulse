# Aion Chat Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Small Windows app that tails Aion's `Chat.log`, picks «[3.Поиск группы]» messages, and beeps when a message text contains a user keyword.

**Architecture:** Pure modules (`parser`, `matcher`, `tailer`, `config`, `notifier`) with unit tests, plus a thin tkinter `app` that polls the tailer with `root.after()` every 500 ms. The tailer starts at the end of the file and only reads appended bytes.

**Tech Stack:** Python 3.11+ (dev machine has 3.14), tkinter, winsound, stdlib only at runtime; pytest; PyInstaller for the exe.

**Spec:** `docs/superpowers/specs/2026-10-08-chat-watcher-design.md`

## Global Constraints

- Project root: `C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_chat_watcher` (git repo already initialised). All commands run from this folder.
- Runtime: standard library only. Dev deps: `pytest>=8.0`, `pyinstaller>=6.0`.
- Chat log encoding `cp1251`, line endings CRLF. Decode with `errors="replace"`.
- Default game dir: `C:\aMain\Games\AION Imperia\Aion Empire`; log path `<game_dir>\classic\Chat.log` unless `chat_log` is set.
- Channel prefix exactly `[3.Поиск группы]`. Keywords are searched only in cleaned text, never in the nick.
- Normalisation: `lower()` + `ё`→`е`.
- Anti-spam: same `(nick, normalised text)` does not alert again within `cooldown_sec` (default 60).
- Start always begins at the end of the file; old messages never alert.
- Program only reads the log. Never write to the real game `Chat.log` (manual tests use a temp file).
- UI text in Russian. Code, comments, commit messages in English.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: Scaffold + parser

**Files:**
- Create: `.gitignore`, `pytest.ini`, `requirements.txt`, `watcher/__init__.py`, `tests/__init__.py`
- Create: `watcher/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Produces: `watcher.parser.CHANNEL: str`, `watcher.parser.ChatMessage(time: str, nick: str, text: str, raw: str)` (frozen dataclass), `watcher.parser.clean_text(text: str) -> str`, `watcher.parser.parse_line(line: str) -> ChatMessage | None`

- [ ] **Step 1: Create scaffold files**

`.gitignore`:
```
__pycache__/
.pytest_cache/
build/
config.json
AionChatWatcher.exe
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
```

`requirements.txt`:
```
pytest>=8.0
pyinstaller>=6.0
```

`watcher/__init__.py` and `tests/__init__.py`: empty files.

- [ ] **Step 2: Write the failing test**

`tests/test_parser.py`:
```python
from watcher.parser import ChatMessage, clean_text, parse_line

CMD_LINE = (
    "2026.10.08 18:43:17 : [3.Поиск группы] [charname:Tiyamate;1.0000 0.6941 0.6941]: "
    "[cmd:Tiyamate;sxFsA1JTuwlRMeXXcsGOGIhtgp+mUuuHulz+ZUdiohM=]WTB MMK 2.2KK SM++++++++++++++ "
)
ITEM_LINE = (
    "2026.10.08 18:42:00 : [3.Поиск группы] [charname:Roflokabanchik;1.0000 0.6941 0.6941]: "
    "wts [item:168000066;ver2;;;][item:168000067;ver2;;;] вставка "
)
PLAIN_LINE = (
    "2026.10.08 18:42:08 : [3.Поиск группы] [charname:Flomaster;1.0000 0.6941 0.6941]: "
    "А ангир будут исправлять? "
)
SYSTEM_LINE = "2026.10.08 18:42:29 : Бешеный ветер I: Скор. движ. цели Mockoco увеличивается. "
OTHER_CHANNEL_LINE = (
    "2026.10.08 18:42:29 : [1.Общий] [charname:Someone;1.0000 1.0000 1.0000]: хил нужен"
)


def test_parses_player_message_and_strips_cmd():
    msg = parse_line(CMD_LINE)
    assert msg == ChatMessage(
        time="2026.10.08 18:43:17",
        nick="Tiyamate",
        text="WTB MMK 2.2KK SM++++++++++++++",
        raw=CMD_LINE,
    )


def test_replaces_item_links():
    msg = parse_line(ITEM_LINE)
    assert msg is not None
    assert msg.nick == "Roflokabanchik"
    assert msg.text == "wts [item][item] вставка"


def test_parses_plain_message():
    msg = parse_line(PLAIN_LINE)
    assert msg is not None
    assert msg.nick == "Flomaster"
    assert msg.text == "А ангир будут исправлять?"


def test_strips_line_ending():
    msg = parse_line(PLAIN_LINE + "\r\n")
    assert msg is not None
    assert msg.raw == PLAIN_LINE


def test_ignores_system_line():
    assert parse_line(SYSTEM_LINE) is None


def test_ignores_other_channel():
    assert parse_line(OTHER_CHANNEL_LINE) is None


def test_ignores_garbage():
    assert parse_line("") is None
    assert parse_line("[3.Поиск группы] без даты") is None


def test_clean_text():
    assert clean_text("  [cmd:X;abc=]Хил [item:1;ver2;;;] ") == "Хил [item]"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'watcher.parser'`

- [ ] **Step 4: Write minimal implementation**

`watcher/parser.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_parser.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add .gitignore pytest.ini requirements.txt watcher tests
git commit -m "feat: parse Поиск группы chat lines

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Matcher

**Files:**
- Create: `watcher/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `watcher.parser.ChatMessage` (fields `nick`, `text`)
- Produces: `watcher.matcher.normalize(text: str) -> str`, `watcher.matcher.Matcher(keywords: list[str], cooldown_sec: float = 60.0)` with `.keywords -> list[str]`, `.set_keywords(keywords: list[str]) -> None`, `.check(msg: ChatMessage, now: float) -> list[str]`; `watcher.matcher.highlight_segments(text: str, keywords: list[str]) -> list[tuple[str, bool]]`

- [ ] **Step 1: Write the failing test**

`tests/test_matcher.py`:
```python
from watcher.matcher import Matcher, highlight_segments, normalize
from watcher.parser import ChatMessage


def msg(text, nick="Nick"):
    return ChatMessage(time="2026.10.08 18:00:00", nick=nick, text=text, raw="")


def test_normalize():
    assert normalize("ЕщЁ MMK") == "еще mmk"


def test_case_insensitive_cyrillic():
    assert Matcher(["ммк"]).check(msg("WTB ММК 2.2кк"), 0) == ["ммк"]


def test_yo_equals_e_both_ways():
    assert Matcher(["ещё"]).check(msg("нужен ЕЩЕ хил"), 0) == ["ещё"]
    assert Matcher(["еще"]).check(msg("нужен ещё хил"), 0) == ["еще"]


def test_returns_all_matched_keywords():
    assert Matcher(["хил", "чант", "глад"]).check(msg("Хил чант кожа"), 0) == ["хил", "чант"]


def test_no_match():
    assert Matcher(["хил"]).check(msg("WTB MMK"), 0) == []


def test_blank_and_duplicate_keywords_dropped():
    assert Matcher(["", "  ", " Хил ", "хил"]).keywords == ["Хил"]


def test_nick_is_not_searched():
    assert Matcher(["zdravie"]).check(msg("Удасы по всем рб", nick="Zdravie"), 0) == []


def test_cooldown_blocks_repeat_then_allows():
    m = Matcher(["хил"], cooldown_sec=60)
    assert m.check(msg("Хил нужен"), 0) == ["хил"]
    assert m.check(msg("Хил нужен"), 30) == []
    assert m.check(msg("ХИЛ нужен"), 59.9) == []
    assert m.check(msg("Хил нужен"), 61) == ["хил"]


def test_other_nick_is_new_alert():
    m = Matcher(["хил"], cooldown_sec=60)
    assert m.check(msg("Хил нужен", nick="A"), 0) == ["хил"]
    assert m.check(msg("Хил нужен", nick="B"), 1) == ["хил"]


def test_set_keywords_live():
    m = Matcher(["хил"])
    m.set_keywords(["чант"])
    assert m.keywords == ["чант"]
    assert m.check(msg("хил чант"), 0) == ["чант"]


def test_highlight_segments():
    assert highlight_segments("WTB MMK sm", ["mmk"]) == [
        ("WTB ", False),
        ("MMK", True),
        (" sm", False),
    ]


def test_highlight_overlap_and_repeats():
    assert highlight_segments("abcd ab", ["ab", "bc"]) == [
        ("abc", True),
        ("d ", False),
        ("ab", True),
    ]


def test_highlight_empty():
    assert highlight_segments("", ["x"]) == []
    assert highlight_segments("текст", []) == [("текст", False)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'watcher.matcher'`

- [ ] **Step 3: Write minimal implementation**

`watcher/matcher.py`:
```python
"""Keyword search over chat messages, with anti-spam cooldown."""

from watcher.parser import ChatMessage

_PURGE_THRESHOLD = 1000


def normalize(text: str) -> str:
    """Lowercase and treat «ё» as «е». Keeps string length."""
    return text.lower().replace("ё", "е")


class Matcher:
    def __init__(self, keywords: list[str], cooldown_sec: float = 60.0) -> None:
        self.cooldown_sec = cooldown_sec
        self._keywords: list[tuple[str, str]] = []
        self._seen: dict[tuple[str, str], float] = {}
        self.set_keywords(keywords)

    @property
    def keywords(self) -> list[str]:
        return [original for original, _ in self._keywords]

    def set_keywords(self, keywords: list[str]) -> None:
        result: list[tuple[str, str]] = []
        seen: set[str] = set()
        for keyword in keywords:
            original = keyword.strip()
            norm = normalize(original)
            if norm and norm not in seen:
                seen.add(norm)
                result.append((original, norm))
        self._keywords = result

    def check(self, msg: ChatMessage, now: float) -> list[str]:
        """Return matched keywords, or [] if none matched or the message is a recent repeat."""
        text = normalize(msg.text)
        hits = [original for original, norm in self._keywords if norm in text]
        if not hits:
            return []
        key = (msg.nick, text)
        last = self._seen.get(key)
        if last is not None and now - last < self.cooldown_sec:
            return []
        if len(self._seen) >= _PURGE_THRESHOLD:
            self._seen = {k: t for k, t in self._seen.items() if now - t < self.cooldown_sec}
        self._seen[key] = now
        return hits


def highlight_segments(text: str, keywords: list[str]) -> list[tuple[str, bool]]:
    """Split text into (chunk, is_match) pieces for highlighting."""
    norm = normalize(text)
    marks = [False] * len(text)
    for keyword in keywords:
        needle = normalize(keyword.strip())
        if not needle:
            continue
        start = norm.find(needle)
        while start != -1:
            for i in range(start, min(start + len(needle), len(text))):
                marks[i] = True
            start = norm.find(needle, start + 1)
    segments: list[tuple[str, bool]] = []
    for char, mark in zip(text, marks):
        if segments and segments[-1][1] == mark:
            segments[-1] = (segments[-1][0] + char, mark)
        else:
            segments.append((char, mark))
    return segments
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add watcher/matcher.py tests/test_matcher.py
git commit -m "feat: keyword matcher with cooldown and highlight segments

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Log tailer

**Files:**
- Create: `watcher/tailer.py`
- Test: `tests/test_tailer.py`

**Interfaces:**
- Produces: `watcher.tailer.LogTailer(path: str, encoding: str = "cp1251")` with `.start_at_end() -> None` and `.read_new_lines() -> list[str]`. Both raise `FileNotFoundError` when the file is missing; other read errors surface as `OSError`.

- [ ] **Step 1: Write the failing test**

`tests/test_tailer.py`:
```python
import pytest

from watcher.tailer import LogTailer


def write(path, text, mode="ab"):
    with open(path, mode) as f:
        f.write(text.encode("cp1251"))


def test_start_at_end_skips_old_content(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "old line\r\n", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    assert tailer.read_new_lines() == []
    write(path, "new line\r\n")
    assert tailer.read_new_lines() == ["new line"]
    assert tailer.read_new_lines() == []


def test_partial_line_waits_for_newline(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "half")
    assert tailer.read_new_lines() == []
    write(path, " done\r\nnext\r\n")
    assert tailer.read_new_lines() == ["half done", "next"]


def test_decodes_cp1251(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "[3.Поиск группы] ищу хила\r\n")
    assert tailer.read_new_lines() == ["[3.Поиск группы] ищу хила"]


def test_lf_only_lines(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "a\nb\n")
    assert tailer.read_new_lines() == ["a", "b"]


def test_recreated_shorter_file_is_read_from_start(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "a long old line that will vanish\r\n" * 3, "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "fresh\r\n", "wb")
    assert tailer.read_new_lines() == ["fresh"]


def test_missing_file_raises(tmp_path):
    tailer = LogTailer(str(tmp_path / "nope.log"))
    with pytest.raises(FileNotFoundError):
        tailer.start_at_end()
    with pytest.raises(FileNotFoundError):
        tailer.read_new_lines()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tailer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'watcher.tailer'`

- [ ] **Step 3: Write minimal implementation**

`watcher/tailer.py`:
```python
"""Read lines appended to a growing log file."""

import os


class LogTailer:
    def __init__(self, path: str, encoding: str = "cp1251") -> None:
        self.path = path
        self.encoding = encoding
        self._pos = 0
        self._buf = b""

    def start_at_end(self) -> None:
        """Skip everything already in the file."""
        self._pos = os.path.getsize(self.path)
        self._buf = b""

    def read_new_lines(self) -> list[str]:
        """Return complete lines appended since the last call.

        The file is opened per call so the game keeps full access to it.
        A file shorter than our position was recreated: read it from the start.
        """
        size = os.path.getsize(self.path)
        if size < self._pos:
            self._pos = 0
            self._buf = b""
        if size == self._pos:
            return []
        with open(self.path, "rb") as f:
            f.seek(self._pos)
            data = f.read(size - self._pos)
        self._pos += len(data)
        *lines, self._buf = (self._buf + data).split(b"\n")
        return [line.rstrip(b"\r").decode(self.encoding, errors="replace") for line in lines]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tailer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add watcher/tailer.py tests/test_tailer.py
git commit -m "feat: tail new lines from Chat.log

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Config

**Files:**
- Create: `watcher/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `watcher.config.DEFAULT_GAME_DIR: str`, `watcher.config.app_root() -> Path`, `watcher.config.Config` dataclass (`game_dir: str`, `chat_log: str`, `keywords: list[str]`, `poll_interval_ms: int`, `cooldown_sec: float`, `sound_path: str`, method `chat_log_path() -> Path`), `watcher.config.load_config(path: Path) -> Config`, `watcher.config.save_config(path: Path, cfg: Config) -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import json
from pathlib import Path

from watcher.config import DEFAULT_GAME_DIR, Config, load_config, save_config


def test_missing_file_gives_defaults_and_creates_it(tmp_path):
    path = tmp_path / "config.json"
    cfg = load_config(path)
    assert cfg == Config()
    assert cfg.game_dir == DEFAULT_GAME_DIR
    assert json.loads(path.read_text(encoding="utf-8"))["poll_interval_ms"] == 500


def test_broken_json_gives_defaults_and_rewrites(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_config(path) == Config()
    assert json.loads(path.read_text(encoding="utf-8"))["keywords"] == []


def test_non_object_json_gives_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2]", encoding="utf-8")
    assert load_config(path) == Config()


def test_roundtrip_keeps_cyrillic(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(keywords=["хил", "ММК"], cooldown_sec=30)
    save_config(path, cfg)
    assert "хил" in path.read_text(encoding="utf-8")
    assert load_config(path) == cfg


def test_unknown_keys_ignored_missing_keys_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"keywords": ["чант"], "extra": 1}), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.keywords == ["чант"]
    assert cfg.poll_interval_ms == 500


def test_chat_log_path_default_and_override():
    assert Config(game_dir=r"D:\Aion").chat_log_path() == Path(r"D:\Aion") / "classic" / "Chat.log"
    assert Config(chat_log=r"E:\x\Chat.log").chat_log_path() == Path(r"E:\x\Chat.log")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'watcher.config'`

- [ ] **Step 3: Write minimal implementation**

`watcher/config.py`:
```python
"""config.json next to the exe (or the project folder when run from source)."""

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_GAME_DIR = r"C:\aMain\Games\AION Imperia\Aion Empire"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@dataclass
class Config:
    game_dir: str = DEFAULT_GAME_DIR
    chat_log: str = ""
    keywords: list[str] = field(default_factory=list)
    poll_interval_ms: int = 500
    cooldown_sec: float = 60
    sound_path: str = ""

    def chat_log_path(self) -> Path:
        if self.chat_log:
            return Path(self.chat_log)
        return Path(self.game_dir) / "classic" / "Chat.log"


def save_config(path: Path, cfg: Config) -> None:
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")


def load_config(path: Path) -> Config:
    """Load config; a missing or broken file is replaced with defaults."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
    except (OSError, ValueError):
        cfg = Config()
        save_config(path, cfg)
        return cfg
    names = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in names})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add watcher/config.py tests/test_config.py
git commit -m "feat: load and save config.json

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Notifier

**Files:**
- Create: `watcher/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Produces: `watcher.notifier.Notifier(sound_path: str | None = None)` with `.play() -> None` (non-blocking)

- [ ] **Step 1: Write the failing test**

`tests/test_notifier.py`:
```python
import winsound

from watcher import notifier
from watcher.notifier import Notifier


def record_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(notifier.winsound, "MessageBeep", lambda kind: calls.append(("beep", kind)))
    monkeypatch.setattr(
        notifier.winsound, "PlaySound", lambda path, flags: calls.append(("play", path, flags))
    )
    return calls


def test_beeps_without_sound_file(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    Notifier("").play()
    Notifier(None).play()
    Notifier(str(tmp_path / "missing.wav")).play()
    assert calls == [("beep", winsound.MB_ICONEXCLAMATION)] * 3


def test_plays_existing_file_async(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    wav = tmp_path / "alert.wav"
    wav.write_bytes(b"RIFF")
    Notifier(str(wav)).play()
    assert calls == [("play", str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: FAIL with `ImportError: cannot import name 'notifier' from 'watcher'`

- [ ] **Step 3: Write minimal implementation**

`watcher/notifier.py`:
```python
"""Alert sound."""

import os
import winsound


class Notifier:
    def __init__(self, sound_path: str | None = None) -> None:
        self.sound_path = sound_path or ""

    def play(self) -> None:
        """Play the WAV file if it exists, else the Windows exclamation sound. Never blocks."""
        if self.sound_path and os.path.isfile(self.sound_path):
            winsound.PlaySound(self.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add watcher/notifier.py tests/test_notifier.py
git commit -m "feat: alert sound notifier

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Window, entry point, fake chat tool

**Files:**
- Create: `watcher/app.py`, `main.py`, `tools/fake_chat.py`

**Interfaces:**
- Consumes: `LogTailer(path).start_at_end()/.read_new_lines()`, `parse_line(line) -> ChatMessage | None`, `Matcher(keywords, cooldown_sec)` with `.keywords`, `.set_keywords()`, `.check(msg, now)`, `highlight_segments(text, keywords)`, `Notifier(sound_path).play()`, `Config`, `load_config(path)`, `save_config(path, cfg)`, `app_root()`
- Produces: `watcher.app.App(root: tk.Tk, config_path: Path)`, `watcher.app.split_keywords(text: str) -> list[str]`

No unit tests for tkinter; `split_keywords` gets a small test. GUI is verified manually in Step 6.

- [ ] **Step 1: Write the failing test**

`tests/test_app.py`:
```python
from watcher.app import split_keywords


def test_split_keywords():
    assert split_keywords(" хил,  ММК ,,чант , ") == ["хил", "ММК", "чант"]
    assert split_keywords("") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'watcher.app'`

- [ ] **Step 3: Write the app**

`watcher/app.py`:
```python
"""tkinter window: keywords, start/stop, list of matched messages."""

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from watcher.config import load_config, save_config
from watcher.matcher import Matcher, highlight_segments
from watcher.notifier import Notifier
from watcher.parser import ChatMessage, parse_line
from watcher.tailer import LogTailer

MAX_ROWS = 500
RETRY_MS = 2000


def split_keywords(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


class App:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.cfg = load_config(config_path)
        self.matcher = Matcher(self.cfg.keywords, self.cfg.cooldown_sec)
        self.notifier = Notifier(self.cfg.sound_path)
        self.tailer: LogTailer | None = None
        self.running = False
        self._after_id: str | None = None
        self._rows = 0
        self._build_ui()
        self._set_status("Остановлен")

    def _build_ui(self) -> None:
        root = self.root
        root.title("Aion Chat Watcher")
        root.geometry("760x480")

        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Папка игры:").grid(row=0, column=0, sticky="w")
        self.game_dir_var = tk.StringVar(value=self.cfg.game_dir)
        dir_entry = ttk.Entry(top, textvariable=self.game_dir_var)
        dir_entry.grid(row=0, column=1, sticky="ew", padx=4)
        dir_entry.bind("<Return>", lambda _e: self._apply_game_dir())
        dir_entry.bind("<FocusOut>", lambda _e: self._apply_game_dir())
        ttk.Button(top, text="…", width=3, command=self._pick_dir).grid(row=0, column=2)

        ttk.Label(top, text="Ключевые слова:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.kw_var = tk.StringVar(value=", ".join(self.cfg.keywords))
        kw_entry = ttk.Entry(top, textvariable=self.kw_var)
        kw_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=4, pady=(6, 0))
        kw_entry.bind("<Return>", lambda _e: self._apply_keywords())
        kw_entry.bind("<FocusOut>", lambda _e: self._apply_keywords())
        top.columnconfigure(1, weight=1)

        bar = ttk.Frame(root, padding=(8, 0))
        bar.pack(fill="x")
        self.start_btn = ttk.Button(bar, text="Start", command=self.toggle)
        self.start_btn.pack(side="left")
        ttk.Button(bar, text="Тест звука", command=self.notifier.play).pack(side="left", padx=6)
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=10)

        frame = ttk.Frame(root, padding=8)
        frame.pack(fill="both", expand=True)
        self.text = tk.Text(frame, wrap="word", state="disabled", font=("Segoe UI", 10))
        scroll = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("meta", foreground="#888888")
        self.text.tag_configure("nick", font=("Segoe UI", 10, "bold"))
        self.text.tag_configure("hit", background="#ffe066", foreground="#000000")

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _pick_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.game_dir_var.get() or None)
        if chosen:
            self.game_dir_var.set(str(Path(chosen)))
            self._apply_game_dir()

    def _apply_game_dir(self) -> None:
        new_dir = self.game_dir_var.get().strip()
        if new_dir == self.cfg.game_dir:
            return
        self.cfg.game_dir = new_dir
        save_config(self.config_path, self.cfg)
        if self.running:
            self.stop()
            self.start()

    def _apply_keywords(self) -> None:
        keywords = split_keywords(self.kw_var.get())
        if keywords == self.cfg.keywords:
            return
        self.cfg.keywords = keywords
        self.matcher.set_keywords(keywords)
        save_config(self.config_path, self.cfg)

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        self._apply_keywords()
        self.running = True
        self.tailer = None
        self.start_btn.configure(text="Stop")
        self._tick()

    def stop(self) -> None:
        self.running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.tailer = None
        self.start_btn.configure(text="Start")
        self._set_status("Остановлен")

    def _schedule(self, delay_ms: int) -> None:
        self._after_id = self.root.after(delay_ms, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
            return
        path = self.cfg.chat_log_path()
        try:
            if self.tailer is None:
                tailer = LogTailer(str(path))
                tailer.start_at_end()
                self.tailer = tailer
            lines = self.tailer.read_new_lines()
        except FileNotFoundError:
            self.tailer = None
            self._set_status(f"Chat.log не найден: {path}")
            self._schedule(RETRY_MS)
            return
        except OSError as exc:
            self._set_status(f"Ошибка чтения: {exc}")
            self._schedule(self.cfg.poll_interval_ms)
            return
        self._set_status(f"Слежу за {path}")
        self._process(lines)
        self._schedule(self.cfg.poll_interval_ms)

    def _process(self, lines: list[str]) -> None:
        now = time.monotonic()
        matched = False
        for line in lines:
            msg = parse_line(line)
            if msg is None:
                continue
            if self.matcher.check(msg, now):
                self._add_row(msg)
                matched = True
        if matched:
            self.notifier.play()

    def _add_row(self, msg: ChatMessage) -> None:
        parts: list = [f"{msg.time[11:]}  ", ("meta",), f"{msg.nick}: ", ("nick",)]
        for chunk, is_hit in highlight_segments(msg.text, self.matcher.keywords):
            parts += [chunk, ("hit",) if is_hit else ()]
        parts += ["\n", ()]
        self.text.configure(state="normal")
        self.text.insert("1.0", *parts)
        self._rows += 1
        if self._rows > MAX_ROWS:
            self.text.delete(f"{MAX_ROWS + 1}.0", "end")
            self._rows = MAX_ROWS
        self.text.configure(state="disabled")

    def _on_close(self) -> None:
        self._apply_keywords()
        self._apply_game_dir()
        self.stop()
        self.root.destroy()
```

`main.py`:
```python
"""Aion Chat Watcher: beep when «Поиск группы» chat contains a keyword."""

import tkinter as tk

from watcher.app import App
from watcher.config import app_root


def main() -> None:
    root = tk.Tk()
    App(root, app_root() / "config.json")
    root.mainloop()


if __name__ == "__main__":
    main()
```

`tools/fake_chat.py`:
```python
"""Append a fake «Поиск группы» line to a log file for manual testing.

Never point it at the real game Chat.log.
Usage: python tools/fake_chat.py <log path> <text> [nick]
"""

import sys
import time


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path, text = sys.argv[1], sys.argv[2]
    nick = sys.argv[3] if len(sys.argv) > 3 else "Tester"
    stamp = time.strftime("%Y.%m.%d %H:%M:%S")
    line = f"{stamp} : [3.Поиск группы] [charname:{nick};1.0000 0.6941 0.6941]: {text} \r\n"
    with open(path, "ab") as f:
        f.write(line.encode("cp1251", errors="replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -v`
Expected: 36 passed (8 parser + 13 matcher + 6 tailer + 6 config + 2 notifier + 1 app)

- [ ] **Step 5: Commit**

```bash
git add watcher/app.py main.py tools/fake_chat.py tests/test_app.py
git commit -m "feat: chat watcher window and fake chat tool

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Manual check with a fake log**

1. Create the fake log: `python -c "open(r'C:\Users\F88B~1\AppData\Local\Temp\fake_chat.log','wb').close()"` (any temp path works).
2. Run `python main.py` once and close it, so `config.json` is created. Set `"chat_log"` in `config.json` to the fake log path.
3. Run `python main.py`. Expected: status «Остановлен».
4. Click «Тест звука». Expected: Windows exclamation sound.
5. Type `ммк, хил` in «Ключевые слова», press Enter. Expected: `config.json` now has `"keywords": ["ммк", "хил"]`.
6. Click Start. Expected: status «Слежу за …fake_chat.log».
7. Run `python tools/fake_chat.py <fake log> "[cmd:X;abc=]WTB ММК 2.2кк" Tiyamate`. Expected within 1 s: sound, new row `HH:MM:SS  Tiyamate: WTB ММК 2.2кк` with «ММК» highlighted.
8. Run the same command again. Expected: no sound, no row (cooldown).
9. Run `python tools/fake_chat.py <fake log> "просто текст"`. Expected: nothing.
10. Delete the fake log file. Expected: status «Chat.log не найден: …». Recreate it, add a matching line. Expected: status «Слежу за …», then sound and row on the next matching line.
11. Clear `"chat_log"` in `config.json`, restart, Start with the game running. Expected: status «Слежу за C:\aMain\Games\AION Imperia\Aion Empire\classic\Chat.log», real messages with keywords appear.

---

### Task 7: Build exe + README

**Files:**
- Create: `build_exe.bat`, `README.md`

- [ ] **Step 1: Write build script**

`build_exe.bat`:
```bat
@echo off
rem Build AionChatWatcher.exe into this folder (next to config.json).
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AionChatWatcher ^
  --distpath . --workpath build --specpath build ^
  main.py || goto :error
echo.
echo Done: %~dp0AionChatWatcher.exe
exit /b 0
:error
echo Build failed.
exit /b 1
```

- [ ] **Step 2: Write README**

`README.md`:
````markdown
# Aion Chat Watcher

Следит за чатом Aion в реальном времени и подаёт звуковой сигнал, когда в канале
«Поиск группы» появляется сообщение с одним из ключевых слов.

Программа только читает файл `Chat.log`. Клиент, память игры и ввод не трогаются.

## Как работает

Клиент пишет чат в `<папка игры>\classic\Chat.log` (в `system.cfg` должно быть `g_chatlog = "1"`).
Программа читает только новые строки, берёт строки `[3.Поиск группы]`, отбрасывает ник и служебную
разметку и ищет ключевые слова в тексте (без учёта регистра, «ё» = «е»).
Один и тот же текст от того же игрока не звенит чаще раза в `cooldown_sec` секунд.

## Запуск

- `AionChatWatcher.exe` — или из исходников: `python main.py`.
- «Папка игры» — папка `Aion Empire`. Кнопка «…» открывает выбор папки.
- «Ключевые слова» — через запятую, применяются по Enter.
- Start / Stop. Сигналы только для новых сообщений после Start.
- «Тест звука» — проверить звук.

## config.json

Создаётся рядом с exe / `main.py` при первом запуске.

| Ключ | По умолчанию | Смысл |
|------|--------------|-------|
| `game_dir` | `C:\aMain\Games\AION Imperia\Aion Empire` | папка игры |
| `chat_log` | `""` | полный путь к логу, если он не в `game_dir\classic\Chat.log` |
| `keywords` | `[]` | ключевые слова |
| `poll_interval_ms` | `500` | как часто читать лог |
| `cooldown_sec` | `60` | анти-спам для повторов |
| `sound_path` | `""` | свой WAV; пусто — системный звук |

## Разработка

```
pip install -r requirements.txt
python -m pytest
python tools/fake_chat.py <тестовый лог> "текст" [ник]   # ручная проверка; не на настоящий Chat.log
build_exe.bat                                            # сборка exe
```
````

- [ ] **Step 3: Build and smoke-test the exe**

Run: `build_exe.bat`
Expected: ends with `Done: ...\AionChatWatcher.exe`. Start `AionChatWatcher.exe`: window opens, `config.json` next to it is loaded (keywords from Task 6 visible), «Тест звука» beeps.

- [ ] **Step 4: Commit**

```bash
git add build_exe.bat README.md
git commit -m "build: PyInstaller script and README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
