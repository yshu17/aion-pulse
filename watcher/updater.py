"""Update check against the latest GitHub release. Tk-free core: it only reads a release and says if it is newer.

The program never downloads or runs anything: it offers the release page, the user decides.
"""

from __future__ import annotations

import json

from watcher.version import REPO

API = f"https://api.github.com/repos/{REPO}/releases/latest"


def parse_version(text: str) -> tuple[int, ...]:
    """«v1.2.10» → (1, 2, 10); unreadable parts count as 0."""
    parts = text.strip().lstrip("vV").split(".")
    return tuple(int(part) if part.isdigit() else 0 for part in parts)


def latest_release(body: str) -> tuple[str, str] | None:
    """(tag, page url) of a GitHub release JSON, or None when the answer has no tag."""
    data = json.loads(body)
    tag, url = data.get("tag_name", ""), data.get("html_url", "")
    return (tag, url) if tag and url else None


def newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)
