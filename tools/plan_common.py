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
    ("draft", "Черновики функций", "feature-drafts.html", "черновики, не утверждено"),
    ("sn", "Расписание и уведомления", "schedule-notify-plan.html", "в работе · SN-1–3 готовы"),
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


# «Файлы и ресурсы» block of each plan: what is provided, what is needed from the user, what Claude / Codex get
# themselves. Kinds: "have" — есть, "need" — нужно от тебя, "self" — достанем сами. link: relative to docs/ or a URL.
RESOURCES: dict[str, list[tuple[str, str, str, str]]] = {
    "map": [
        ("have", "Клиент игры", "папка игры — только чтение; из неё всё распаковано", "../client_extract/README.md"),
        ("have", "Распаковка клиента", "карты newmap и радар, NPC, подписи, задания, значки — client_extract/",
         "../client_extract/README.md"),
        ("have", "Бездна и элийские зоны", "склейки слоёв ab1_1–3 и карт lf1, lf1a, lf2, lf2a, lf3, lc1, NPC и подписи "
         "(Кодекс, шаги 23 и 25)", "../client_extract/raw/REPORT_V4.md"),
        ("have", "Скачанное с aiondb", "кто выдаёт задания (2 458 связей), запасные карты, значки", "../downloads/README.md"),
        ("have", "Твои скриншоты", "игровая карта Келькмароса, крепость «Запечатанная башня» — в чате", ""),
        ("need", "Ссылки «Место» из чата", "2–3 зоны, в т. ч. Пандемониум — для сверки привязки (шаги 20 и 27)", ""),
        ("need", "Скриншоты Бездны", "игровая карта каждого слоя с несколькими значками — сверить слои и кадр", ""),
        ("self", "Значки ×4", "Waifu2x локально — downloads/icon_upscale, tools/upscale_icons.py (Кодекс)",
         "../downloads/README.md"),
    ],
    "sn": [
        ("have", "Текущие оповещения", "звук, «назойливый» режим, мигание кнопки — watcher/alarm.py, watcher/notifier.py", ""),
        ("have", "Звуки Windows", "системные .wav — выбор в программе уже есть", ""),
        ("have", "Расписание сервера", "статья базы знаний Aion Empire и картинка «Расписание активностей» → data/schedule.json", "https://kb.aionempire.com/article/rasapisanie"),
        ("have", "Часовой пояс сервера", "МСК (UTC+3, без летнего времени); время показывает компьютер", ""),
        ("need", "Режим игры", "«оконный без рамки» или «полный экран» — от этого зависит, видны ли тосты", ""),
        ("have", "Шаблон расписания", "data/schedule.json: 79 записей по дням, откаты квестов, арена, команды (из статьи)", "../data/schedule.json"),
        ("self", "Картинки тоста", "фон 9-slice и значки видов из клиента, Waifu2x (Кодекс, SN-3)", ""),
        ("self", "Свой звук уведомления", "по желанию: пришли .wav, иначе — системный", ""),
    ],
    "ui": [
        ("have", "Аудит интерфейса", "31 задача, этапы, критерии — UI_UX_IMPROVEMENT_PLAN.md", "../UI_UX_IMPROVEMENT_PLAN.md"),
        ("have", "Навыки дизайна", "ui-ux-pro-max, high-end-visual-design, design-theme-guide, ui-visual-validator — "
         ".claude/skills", ""),
        ("have", "Картинки 9-slice", "data/ui, генератор tools/build_ui.py", ""),
        ("need", "«Делаем»", "старт плана; по желанию — образец программы, чей вид нравится", ""),
        ("self", "Иконки Phosphor", "открытый набор (MIT) → PNG, tools/build_ui_icons.py (Кодекс)", "https://phosphoricons.com"),
        ("self", "Снимки до / после", "tools/ui_snapshots.py через PrintWindow, работает даже под игрой (Кодекс)", ""),
    ],
    "tg": [
        ("have", "Пачки сообщений", "watcher/tgbatch.py с тестами — готово", ""),
        ("need", "Токен бота", "создать бота у @BotFather; токен — как пароль, только в config.json, не в чат",
         "https://t.me/BotFather"),
        ("need", "Закрытая группа", "создать, добавить бота, написать туда сообщение", ""),
        ("need", "/start боту в личке", "чтобы бот мог писать тебе уведомления", ""),
        ("self", "Отправка и тесты", "telegram.py на urllib, без новых зависимостей (Кодекс)", ""),
        ("self", "Поиск чатов", "кнопка «Найти чаты» — getUpdates, выбор группы и лички (Claude)", ""),
    ],
}
RES_KINDS = [("have", "Есть", "#5fd38d", "✓"), ("need", "Нужно от тебя", "#ff8c1a", "!"), ("self", "Достанем сами", "#4aa3ff", "↻")]
RES_CSS = (
    ".rs{margin:0 0 18px;background:#1c1e24;border:1px solid #363a45;border-radius:10px;padding:10px 12px;"
    "font:13px/1.45 'Segoe UI',system-ui,sans-serif;color:#e9e7e4}"
    ".rs summary{cursor:pointer;font-weight:600;font-size:14px;list-style:none}.rs summary::-webkit-details-marker{display:none}"
    ".rs summary:before{content:'▾ ';color:#ff8c1a}.rs:not([open]) summary:before{content:'▸ '}"
    ".rs summary span{font-weight:400;color:#8c919c}"
    ".rs .rg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}"
    "@media(max-width:820px){.rs .rg{grid-template-columns:1fr}}"
    ".rs h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.04em}"
    ".rs .ri{display:flex;gap:8px;padding:5px 0;border-top:1px solid #2c2f37}.rs .ri:first-of-type{border-top:0}"
    ".rs .rm{width:16px;flex:none;text-align:center;font-weight:700}.rs .rd{color:#8c919c;overflow-wrap:anywhere}"
    ".rs a{color:#ffb05c}"
)


def resources_html(key: str) -> str:
    """The «Файлы и ресурсы» block of a plan (empty when the plan has no list)."""
    items = RESOURCES.get(key, [])
    if not items:
        return ""
    need = sum(1 for kind, *_ in items if kind == "need")
    cols = []
    for kind, label, color, mark in RES_KINDS:
        rows = []
        for item_kind, title, detail, link in items:
            if item_kind != kind:
                continue
            name = html.escape(title)
            if link:
                name = f'<a href="{html.escape(link)}">{name}</a>'
            rows.append(f'<div class="ri"><span class="rm" style="color:{color}">{mark}</span><div><b>{name}</b>'
                        f'<div class="rd">{html.escape(detail)}</div></div></div>')
        cols.append(f'<div><h4 style="color:{color}">{label}</h4>{"".join(rows) or "<div class=rd>—</div>"}</div>')
    return (f'<style>{RES_CSS}</style><details class="rs" open><summary>Файлы и ресурсы '
            f'<span>· нужно от тебя: {need}</span></summary><div class="rg">{"".join(cols)}</div></details>')


def set_nav(page_html: str, current: str) -> str:
    """Put the bar between <!--NAV--> marks (the first time right after the page's first wrapper element) and the
    plan's «Файлы и ресурсы» block between <!--RES--> marks right after the bar."""
    bar = f"<!--NAV-->{nav_html(current)}<!--/NAV-->"
    if "<!--NAV-->" in page_html:
        page_html = re.sub(r"<!--NAV-->.*?<!--/NAV-->", lambda _m: bar, page_html, count=1, flags=re.S)
    else:
        page_html = re.sub(r'(<(?:div|main) class="wrap">)', lambda m: m.group(1) + "\n" + bar, page_html, count=1)
    res = f"<!--RES-->{resources_html(current)}<!--/RES-->"
    if "<!--RES-->" in page_html:
        return re.sub(r"<!--RES-->.*?<!--/RES-->", lambda _m: res, page_html, count=1, flags=re.S)
    # the first time: under the page's title — after its <header>, or after the subtitle line under <h1>
    if "</header>" in page_html:
        return page_html.replace("</header>", "</header>\n" + res, 1)
    return re.sub(r'(<h1>.*?</h1>\s*<div class="sub"[^>]*>.*?</div>)', lambda m: m.group(1) + "\n  " + res, page_html,
                  count=1, flags=re.S)


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
