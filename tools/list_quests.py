"""Download quest names from kb.aionempire.com/quests into data/quest_names.tsv (id<TAB>name).

Chat links [quest:2058] are then shown as <Задание: name>. Dev tool. Usage: python tools/list_quests.py
"""

import concurrent.futures as cf
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://kb.aionempire.com"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": "PLAY_LANG=ru"}
ROW = re.compile(r'href="/quest/(\d+)">\s*(?:\[\d+\])?\s*([^<]*)</a>')
BATCH = 8


def fetch(page: int) -> list[tuple[str, str]]:
    for attempt in range(4):
        try:
            url = f"{SITE}/quests?p={page}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
            return [(i, html.unescape(n).strip()) for i, n in ROW.findall(text)]
        except Exception as exc:  # retry transient errors
            error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"page {page}: {error}")


def main() -> int:
    names: dict[str, str] = {}
    page = 1
    with cf.ThreadPoolExecutor(BATCH) as pool:
        while True:
            pages = list(pool.map(fetch, range(page, page + BATCH)))
            for rows in pages:
                for quest_id, name in rows:
                    if name:
                        names.setdefault(quest_id, name)
            if any(not rows for rows in pages):
                break
            page += BATCH
    out = ROOT / "data" / "quest_names.tsv"
    with open(out, "w", encoding="utf-8") as f:
        for quest_id in sorted(names, key=int):
            f.write(f"{quest_id}\t{names[quest_id]}\n")
    print(f"{len(names)} quests -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
