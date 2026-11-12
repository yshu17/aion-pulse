"""Download the skill pages of aidb.ru that carry the damage of a skill (the skill books and the stigmas).

    python tools/fetch_aidb_skills.py [--limit N] [--delay 0.5] [--workers 2]

Source: https://aidb.ru/sitemap-skills.xml (2 474 pages). Only the skills that a skill book or a stigma gives are fetched
(skill ids of data/pulse.db, the client's ids equal aidb's). Pages go to downloads/aidb_skills/pages/<id>.html, kept as they
came; a page that is there is not fetched again, so the run can be stopped and started. A polite pace as in
tools/fetch_aidb_quests.py. The text is read by core/pulse_db/aidb_skills.py. Registry: downloads/README.md.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "downloads" / "aidb_skills"
SITEMAP = ROOT / "downloads" / "aidb_quests" / "sitemap-skills.xml"
UA = "PulsePlus-research/1.0 (personal project, polite crawl)"


def wanted() -> list[tuple[int, str]]:
    """(skill id, url) of the sitemap's skills that a skill book or a stigma gives."""
    db = sqlite3.connect(f"file:{(ROOT / 'data' / 'pulse.db').as_posix()}?mode=ro", uri=True)
    ours = {r[0] for r in db.execute("SELECT skill_id FROM skill_book WHERE skill_id IS NOT NULL")}
    ours |= {r[0] for r in db.execute("SELECT skill_id FROM stigma WHERE skill_id IS NOT NULL")}
    out = []
    for url in re.findall(r"<loc>([^<]+)</loc>", SITEMAP.read_text(encoding="utf-8")):
        found = re.search(r"/skills/skill/(\d+)-", url)
        if found and int(found.group(1)) in ours:
            out.append((int(found.group(1)), url))
    return sorted(out)


class Pace:
    """One request every `delay` seconds across all threads."""

    def __init__(self, delay: float) -> None:
        self.delay, self.next, self.lock = delay, 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next)
            self.next = at + self.delay
        if at > now:
            time.sleep(at - now)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    pages = OUT / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    todo = [(sid, url) for sid, url in wanted() if not (pages / f"{sid}.html").is_file()
            and not (pages / f"{sid}.404").is_file()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} pages to fetch", flush=True)
    pace, stats = Pace(args.delay), {"ok": 0, "missing": 0, "error": 0, "streak": 0}
    lock = threading.Lock()

    def fetch(job: tuple[int, str]) -> None:
        sid, url = job
        if stats["streak"] >= 8:
            return  # repeated errors: stop asking
        for attempt in (1, 2):
            pace.wait()
            try:
                request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru"})
                with urllib.request.urlopen(request, timeout=30) as answer:
                    body = answer.read()
                (pages / f"{sid}.html").write_bytes(body)
                with lock:
                    stats["ok"] += 1
                    stats["streak"] = 0
                return
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    (pages / f"{sid}.404").write_text(url, encoding="utf-8")
                    with lock:
                        stats["missing"] += 1
                    return
                time.sleep(3 * attempt)
            except Exception:  # noqa: BLE001 - a timeout or a reset: one more try
                time.sleep(3 * attempt)
        with lock:
            stats["error"] += 1
            stats["streak"] += 1

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, _ in enumerate(pool.map(fetch, todo), 1):
            if n % 100 == 0:
                print(f"{n}/{len(todo)} {stats} {time.monotonic() - started:.0f}s", flush=True)
    print(f"done {stats} {time.monotonic() - started:.0f}s", flush=True)
    return 1 if stats["streak"] >= 8 else 0


if __name__ == "__main__":
    sys.exit(main())
