"""Shared bits of the interactive plan pages in docs/: the list of plans and the navigation bar.

Every plan page carries the same bar (links to the master plan and to each plan). Generated pages get it from their
generator; the hand-written ones (map, schedule) keep it between <!--NAV--> and <!--/NAV--> marks, refreshed by
tools/build_master_plan.py.
"""

from __future__ import annotations

import html
import re

# key, short title for the bar, page in docs/, where the plan stands as a whole
PLANS = [
    ("map", "Карта", "map-poi-plan.html", "в работе"),
    ("sn", "Расписание и уведомления", "schedule-notify-plan.html", "ждёт решений и «делаем»"),
    ("ui", "UI/UX", "ui-ux-improvement-plan.html", "ждёт «делаем»"),
    ("tg", "Telegram", "telegram-bridge-plan.html", "ждёт «делаем»"),
]
MASTER = "index.html"

NAV_CSS = (
    ".pn{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 18px;padding:8px;"
    "background:#1c1e24;border:1px solid #363a45;border-radius:10px;font:13px/1.4 'Segoe UI',system-ui,sans-serif}"
    ".pn a{color:#e9e7e4;text-decoration:none;padding:4px 10px;border-radius:7px;border:1px solid transparent}"
    ".pn a:hover{border-color:#ff8c1a}.pn a.on{background:#3a2a12;border-color:#ff8c1a;color:#ff8c1a}"
    ".pn .pn-sep{width:1px;height:18px;background:#363a45;margin:0 2px}.pn .pn-x{margin-left:auto;color:#8c919c}"
)


def nav_html(current: str) -> str:
    """The bar for the page `current` (a key of PLANS or "master"): a <nav> with its own <style>."""
    links = [f'<a href="{MASTER}"{" class=\"on\"" if current == "master" else ""}>★ Мастер-план</a>',
             '<span class="pn-sep"></span>']
    for key, title, page, _gate in PLANS:
        links.append(f'<a href="{page}"{" class=\"on\"" if key == current else ""}>{html.escape(title)}</a>')
    links.append('<a class="pn-x" href="../PAIR.md">PAIR.md</a>')
    return f'<style>{NAV_CSS}</style><nav class="pn" aria-label="Планы">{"".join(links)}</nav>'


def set_nav(page_html: str, current: str) -> str:
    """Put the bar between <!--NAV--> marks; the first time, right after the page's first wrapper element."""
    bar = f"<!--NAV-->{nav_html(current)}<!--/NAV-->"
    if "<!--NAV-->" in page_html:
        return re.sub(r"<!--NAV-->.*?<!--/NAV-->", lambda _m: bar, page_html, count=1, flags=re.S)
    return re.sub(r'(<(?:div|main) class="wrap">)', lambda m: m.group(1) + "\n" + bar, page_html, count=1)


def owners(who: str) -> list[str]:
    """«Кодекс → Claude», «ты + Claude» … -> ["Claude", "Кодекс", "Ты"] in a fixed order."""
    text = who.lower()
    out = []
    if "claude" in text:
        out.append("Claude")
    if "кодекс" in text:
        out.append("Кодекс")
    if re.search(r"\bты\b|пользовател", text):
        out.append("Ты")
    return out
