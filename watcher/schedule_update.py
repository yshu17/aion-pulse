"""SN-9: has the schedule on the knowledge base changed? Tk-free core (PAIR.md rule 17).

No parsing of the picture: the article's grid picture name plus its ETag and Last-Modified (one HEAD request) form a
fingerprint; data/schedule.json keeps the fingerprint of the grid it was typed from (``image``, ``image_etag``,
``image_modified``). The user updates data/schedule.json by hand.

* ``site_fingerprint(fetch)`` — ``fetch(url, method) -> (text, headers)``; raises on a page without the picture;
* ``decide(known, current, seen, manual)`` — ``"changed"``, ``"same"`` or ``None`` (say nothing): at start only a new,
  not yet acknowledged version is reported; a manual check always answers.
"""

from __future__ import annotations

import re
import urllib.request

ARTICLE = "https://kb.aionempire.com/article/rasapisanie"
_PICTURE = re.compile(r"https://[^\"'\s<>]*/schedule[^\"'\s<>/]*\.(?:jpg|jpeg|png|webp)", re.I)


def image_url(html: str) -> str | None:
    match = _PICTURE.search(html)
    return match.group(0) if match else None


def fingerprint(name: str, etag: str, modified: str) -> str:
    return f"{name.rsplit('/', 1)[-1]}|{etag}|{modified}"


def known_fingerprint(data: dict) -> str:
    return fingerprint(data.get("image", ""), data.get("image_etag", ""), data.get("image_modified", ""))


def site_fingerprint(fetch) -> str:
    page, _headers = fetch(ARTICLE, "GET")
    url = image_url(page)
    if url is None:
        raise ValueError("на странице нет картинки расписания")
    _body, headers = fetch(url, "HEAD")
    return fingerprint(url, headers.get("ETag", ""), headers.get("Last-Modified", ""))


def decide(known: str, current: str, seen: str, manual: bool) -> str | None:
    if current == known:
        return "same" if manual else None
    if current == seen and not manual:
        return None
    return "changed"


def http_fetch(url: str, method: str, timeout: float = 10) -> tuple[str, dict]:
    """The real fetch: HTTPS only, a short timeout, nothing sent but the request itself; Russian page version."""
    if not url.startswith("https://"):
        raise ValueError("only https")
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "AionChatWatcher", "Accept-Language": "ru"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(2_000_000).decode("utf-8", "replace") if method == "GET" else ""
        return body, dict(response.headers)
