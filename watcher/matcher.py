"""Keyword search over chat messages, with anti-spam cooldown."""

from watcher.parser import ChatMessage

_PURGE_THRESHOLD = 1000
# How keyword hits and watched-item hits combine.
MODES = ("or", "words", "items", "and")


def normalize(text: str) -> str:
    """Lowercase and treat «ё» as «е». Keeps string length."""
    return text.lower().replace("ё", "е")


class Matcher:
    def __init__(
        self,
        keywords: list[str],
        cooldown_sec: float = 60.0,
        watch_items: dict[str, str] | None = None,
        mode: str = "or",
    ) -> None:
        self.cooldown_sec = cooldown_sec
        self.mode = "or"
        self.set_mode(mode)
        self._keywords: list[tuple[str, str]] = []
        self._watch_items: dict[str, str] = {}
        self._seen: dict[tuple[str, str], float] = {}
        self.set_keywords(keywords)
        self.set_watch_items(watch_items or {})

    def set_mode(self, mode: str) -> None:
        """«or» word or item, «words» only words, «items» only items, «and» word and item."""
        self.mode = mode if mode in MODES else "or"

    def set_watch_items(self, watch_items: dict[str, str]) -> None:
        """Item id -> display name. A message linking any of these ids matches."""
        self._watch_items = dict(watch_items)

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
        """Return matched keywords and watched item names, combined according to the mode.

        [] if nothing matched or the message is a recent repeat.
        """
        text = normalize(msg.text)
        words = [original for original, norm in self._keywords if norm in text]
        items = []
        for item_id in dict.fromkeys(msg.item_ids):
            name = self._watch_items.get(item_id)
            if name is not None and name not in items:
                items.append(name)
        if self.mode == "words":
            hits = words
        elif self.mode == "items":
            hits = items
        elif self.mode == "and":
            hits = words + items if words and items else []
        else:
            hits = words + [name for name in items if name not in words]
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
