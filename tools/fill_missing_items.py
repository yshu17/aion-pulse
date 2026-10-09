"""Find item links in a Chat.log whose ids are not in data/item_names.tsv and add their names.

Names come from kb.aionempire.com item pages (name, grade, level), else from aioncodex.com (Russian
name). Found names are appended to data/item_names.tsv; a TSV for tools/crawl_items.py is written so the
kb ones can also get specs and grade colours (crawl, then rerun tools/build_catalog.py with that cache).
Dev tool. Usage: python tools/fill_missing_items.py <Chat.log> <out.tsv>
"""

import concurrent.futures as cf
import html
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ROOT / "data" / "item_names.tsv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Cookie": "PLAY_LANG=ru"}
EQUIPMENT = ("100", "101", "110", "111", "112", "113", "114", "115", "187")
LINK_RE = re.compile(r"\[(?:item|item_ex|recipe):(\d{6,})")


def page(url: str) -> str | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except OSError:
        return None


def lookup(item_id: str) -> tuple[str, str, str] | None:
    """(name, grade, level) or None."""
    text = page(f"https://kb.aionempire.com/items/{item_id}")
    if text:
        title = html.unescape(re.search(r"<title>([^<]*)</title>", text).group(1))
        match = re.match(r"(.*?) \(Lv\.(\d+)\) \|", title)
        grade = re.search(r'<h1 class="item-desc ([a-z]+)', text)
        if match and match.group(1) != "null":
            return match.group(1), grade.group(1) if grade else "common", match.group(2)
    text = page(f"https://aioncodex.com/ru/item/{item_id}/")
    if text:
        title = html.unescape(re.search(r"<title>([^<]*)</title>", text).group(1)).rsplit(" - Aion Codex", 1)[0]
        if title.strip() and title.strip() != "Aion Codex":
            return title.strip(), "common", "1"
    return None


def main() -> int:
    log, out = Path(sys.argv[1]), Path(sys.argv[2])
    names = dict(line.rstrip("\n").split("\t", 1) for line in open(NAMES, encoding="utf-8") if "\t" in line)
    ids = sorted({i for i in LINK_RE.findall(log.read_bytes().decode("cp1251", "replace")) if i not in names})
    found, missing = [], []
    with cf.ThreadPoolExecutor(6) as pool:
        for item_id, result in zip(ids, pool.map(lookup, ids)):
            (found.append((item_id, *result)) if result else missing.append(item_id))
    for item_id, name, _grade, _level in found:
        names[item_id] = name
    NAMES.write_text("".join(f"{k}\t{v}\n" for k, v in sorted(names.items(), key=lambda kv: int(kv[0]))),
                     encoding="utf-8")
    out.write_text("".join(
        f"{i}\t{g}\t{lv}\t{n}\t{'equip' if i[:3] in EQUIPMENT else 'other'}\n" for i, n, g, lv in found
    ), encoding="utf-8")
    print(f"{len(ids)} unknown ids, {len(found)} named, not found anywhere: {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
