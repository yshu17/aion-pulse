"""Collect the master plan and every page it links to into build/plans_site/ for publishing.

The plans (docs/index.html — the master plan by tools/build_master_plan.py, and the plan pages it links to) are
published as one private claude.ai artifact so they open on a phone. This tool:
- copies the plan pages, with a phone layer (PHONE_CSS) added to each and storage writes made safe;
- renders the Markdown they link to (PAIR.md, UI_UX_IMPROVEMENT_PLAN.md, docs/telegram-bridge-plan.md) as pages;
- rewrites links so every page points inside the site (no «../»);
- writes main.html: the master plan without its document skeleton — the artifact's own page (the publish adds one).
- writes Планы_Aion_Chat_Watcher_Telegram.html: all plan pages embedded in one offline-friendly mobile reader.
Publish: Artifact tool, file_path build/plans_site/main.html, files = every other file in the folder.
Dev tool (needs the markdown package). Usage: python tools/build_plans_site.py
"""

import base64
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "build" / "plans_site"
VENDOR = ROOT / "downloads" / "phosphor_icons_2.1.1" / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

import markdown  # noqa: E402
from build_feature_drafts import HUB, filename, load  # noqa: E402

MAIN_TITLE = "Планы Aion Chat Watcher"
PAGES = ["index.html", "map-poi-plan.html", "ui-ux-improvement-plan.html", "telegram-bridge-plan.html",
         "schedule-notify-plan.html", HUB] + [filename(plan) for plan in load()["plans"]]
# Markdown the pages link to -> (source, page name, title)
SOURCES = {
    "../REPORT_SN23.md": (ROOT / "REPORT_SN23.md", "notifications-report.html", "Уведомления: отчёт SN-2/SN-3"),
    "../PAIR.md": (ROOT / "PAIR.md", "pair.html", "Задачи и журнал"),
    "../UI_UX_IMPROVEMENT_PLAN.md": (ROOT / "UI_UX_IMPROVEMENT_PLAN.md", "ui-ux-source.html", "UI/UX: полный план"),
    "telegram-bridge-plan.md": (DOCS / "telegram-bridge-plan.md", "telegram-source.html", "Telegram: исходный план"),
}

# Phone layer on top of each page's own styles: nothing wider than the screen, tables and code scroll inside
# their own box, tap targets of at least 40 px, a 16 px side gutter.
PHONE_CSS = """<style id="phone">
:root{color-scheme:dark}
html{-webkit-text-size-adjust:100%}
body{overflow-wrap:anywhere}
@media(max-width:620px){.pn{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}.pn::-webkit-scrollbar{display:none}.pn a{white-space:nowrap;flex:none}.pn .pn-x{display:none}}
p,li,td,th,a,dd,dt{overflow-wrap:anywhere}
table{display:block;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
img,svg,video,canvas{max-width:100%;height:auto}
pre,code{white-space:pre-wrap;word-break:break-word}
.table-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
@media (max-width:640px){
  body{font-size:15px}
  .wrap,main,.container,.page{padding-left:16px!important;padding-right:16px!important;max-width:100%!important}
  h1{font-size:22px!important}h2{font-size:18px!important}
  table{display:block;overflow-x:auto;max-width:100%}
  td,th{min-width:0}
  button,select,input,.chip,summary,a.btn{min-height:40px}
  [style*="min-width"]{min-width:0!important}
}
</style>"""

NAV = ('<nav class="site-nav"><a href="index.html">← Мастер-план</a></nav>')
MD_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<style>
:root{{--bg:#141519;--surface:#1c1e24;--surface2:#262931;--border:#363a45;--text:#e9e7e4;--muted:#8c919c;
--accent:#ff8c1a;--link:#ffb05c;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 "Segoe UI",system-ui,sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding-inline:16px;padding-block:16px 48px}}
.site-nav{{position:sticky;top:env(safe-area-inset-top,0px);background:var(--bg);padding-block:10px;
border-bottom:1px solid var(--border);margin-bottom:12px;z-index:1}}
.site-nav a{{color:var(--link);text-decoration:none;display:inline-block;min-height:40px;line-height:40px}}
a{{color:var(--link)}}
h1{{font-size:24px;text-wrap:balance}}h2{{font-size:19px;margin-top:28px;text-wrap:balance}}h3{{font-size:16px}}
p,li{{max-width:70ch}}
code{{background:var(--surface2);padding:1px 5px;border-radius:5px;font-size:13px;overflow-wrap:anywhere}}
pre{{background:var(--surface);border:1px solid var(--border);padding:12px;border-radius:8px;overflow-x:auto}}
pre code{{background:none;padding:0}}
.table-scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:12px 0}}
table{{border-collapse:collapse;font-size:14px;min-width:100%}}
th,td{{border:1px solid var(--border);padding:6px 8px;vertical-align:top;text-align:left}}
th{{background:var(--surface2)}}
blockquote{{border-left:3px solid var(--accent);margin:12px 0;padding:4px 12px;color:var(--muted)}}
@media (max-width:640px){{h1{{font-size:21px}}table{{font-size:13px}}th,td{{min-width:140px}}}}
</style>
</head>
<body>
<div class="wrap">
{nav}
{body}
</div>
</body>
</html>
"""


def rewrite_links(html: str) -> str:
    for href, (_src, page, _title) in SOURCES.items():
        html = html.replace(f'href="{href}', f'href="{page}')
    return html


def site_links_only(html: str) -> str:
    """Markdown links: «docs/x.html» -> «x.html»; links to files that are not on the site become plain text."""
    html = rewrite_links(html.replace('href="docs/', 'href="'))
    pages = set(PAGES) | {page for _src, page, _title in SOURCES.values()}

    def keep(m: re.Match) -> str:
        href = m.group(1)
        return m.group(0) if href.split("#")[0] in pages or href.startswith(("http://", "https://")) else m.group(2)
    return re.sub(r'<a href="([^"]*)"[^>]*>(.*?)</a>', keep, html, flags=re.S)


# confirm() never shows inside the artifact frame (it returns false): a reset button asks for a second tap instead
TWICE = """<script>function __twice(b){if(b.dataset.armed){delete b.dataset.armed;b.textContent=b.dataset.label;return true}
b.dataset.label=b.textContent;b.dataset.armed="1";b.textContent="Нажми ещё раз";
setTimeout(()=>{if(b.dataset.armed){delete b.dataset.armed;b.textContent=b.dataset.label}},3000);return false}</script>"""


def no_confirm(html: str) -> str:
    if "confirm(" not in html:
        return html
    html = re.sub(r'confirm\("[^"]*"\)', 'window.__twice(document.getElementById("reset"))', html)
    return html.replace("</head>", TWICE + "\n</head>", 1)


def safe_storage(html: str) -> str:
    """localStorage can throw inside the artifact frame (blocked site data): wrap the bare writes."""
    return re.sub(r"(?<!try\{)localStorage\.setItem\(([^;\n{}]*?)\);",
                  r"(()=>{try{localStorage.setItem(\1)}catch(e){}})();", html)  # an expression: valid even right before else


def drop_export(html: str) -> str:
    """The phone page cannot save a file for the viewer: no export button, no download script.
    Import (read a file the viewer picks) still works."""
    html = re.sub(r'<button[^>]*id="shared-export"[^>]*>.*?</button>', "", html, flags=re.S)
    return re.sub(r"\$\('shared-export'\)\.onclick=[^\n]*\n", "", html, count=1)


def phone_page(html: str) -> str:
    html = rewrite_links(drop_export(no_confirm(safe_storage(html))))
    html = re.sub(r'<meta name="viewport"[^>]*>',
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">', html, count=1)
    return html.replace("</head>", PHONE_CSS + "\n</head>", 1)


def markdown_page(source: Path, title: str) -> str:
    body = markdown.markdown(source.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "sane_lists"])
    body = body.replace("<table>", '<div class="table-scroll"><table>').replace("</table>", "</table></div>")
    page = MD_PAGE.format(title=title, nav=NAV, body=site_links_only(body))
    return page.replace("</head>", PHONE_CSS + "\n</head>", 1)  # the same phone rules as the plan pages


def main_page(html: str) -> str:
    """The master plan as the artifact's page: the publish adds <!doctype>, <html>, <head> and <body> itself."""
    title = f"<title>{MAIN_TITLE}</title>"  # the artifact's name in the claude.ai gallery
    styles = "\n".join(re.findall(r"<style[^>]*>.*?</style>", html, re.S))
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
    return f"{title}\n{styles}\n{body.strip()}\n"


def telegram_reader() -> str:
    """Pack every phone-ready plan page into one self-contained, tabbed HTML file."""
    titles = {
        "index.html": "Мастер-план",
        "map-poi-plan.html": "Карта",
        "schedule-notify-plan.html": "Расписание",
        "ui-ux-improvement-plan.html": "UI/UX",
        "telegram-bridge-plan.html": "Telegram",
        "pair.html": "Журнал PAIR",
        "ui-ux-source.html": "UI/UX — полный план",
        "telegram-source.html": "Telegram — полный план",
        "notifications-report.html": "Уведомления — отчёт",
    }
    titles[HUB] = "Новые планы"
    titles.update({filename(plan): plan["title"] for plan in load()["plans"]})
    encoded = {
        name: base64.b64encode((OUT / name).read_bytes()).decode("ascii")
        for name in titles
    }
    payload = json.dumps(encoded, ensure_ascii=True)
    nav = "".join(
        f'<button type="button" data-page="{name}">{title}</button>'
        for name, title in titles.items()
    )
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>Планы Aion Chat Watcher — Telegram</title>
<style>
:root{{color-scheme:dark;--bg:#141519;--surface:#1c1e24;--line:#363a45;--text:#e9e7e4;--muted:#a1a5ae;--accent:#ff8c1a}}
*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;background:var(--bg);color:var(--text);font:15px/1.45 "Segoe UI",system-ui,sans-serif}}
body{{display:flex;flex-direction:column;height:100vh;height:100dvh;overflow:hidden}}
header{{padding:9px 12px 7px;border-bottom:1px solid var(--line);background:var(--surface)}}
h1{{font-size:16px;line-height:1.25;margin:0 0 8px;font-weight:650}}
nav{{display:flex;gap:6px;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;padding-bottom:3px}}
button{{flex:none;min-height:40px;padding:7px 12px;border:1px solid var(--line);border-radius:9px;background:#262931;color:var(--text);font:inherit;white-space:nowrap}}
button.active{{border-color:var(--accent);color:#ffb05c;background:#30271d}}
main{{flex:1;min-height:0}}iframe{{display:block;width:100%;height:100%;border:0;background:var(--bg)}}
#hint{{padding:4px 12px;color:var(--muted);font-size:11px;border-top:1px solid var(--line)}}
</style>
</head>
<body>
<header><h1>Планы Aion Chat Watcher</h1><nav aria-label="Разделы планов">{nav}</nav></header>
<main><iframe id="viewer" title="Планы проекта"></iframe></main>
<div id="hint">Один файл · работает без интернета · разделы переключаются сверху</div>
<script>
const FILES={payload};
const frame=document.getElementById("viewer");
const buttons=[...document.querySelectorAll("[data-page]")];
function decodePage(value){{const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0));return new TextDecoder("utf-8").decode(bytes)}}
function showPage(name,hash=""){{
  if(!FILES[name])return;
  frame.srcdoc=decodePage(FILES[name]);
  buttons.forEach(b=>b.classList.toggle("active",b.dataset.page===name));
  if(hash)frame.addEventListener("load",()=>{{try{{frame.contentWindow.location.hash=hash}}catch(_e){{}}}},{{once:true}});
}}
buttons.forEach(b=>b.addEventListener("click",()=>showPage(b.dataset.page)));
frame.addEventListener("load",()=>{{
  try{{frame.contentDocument.addEventListener("click",event=>{{
    const link=event.target.closest("a[href]");if(!link)return;
    const href=link.getAttribute("href");if(!href||href.startsWith("http:")||href.startsWith("https:")||href.startsWith("#"))return;
    const parts=href.split("#");const file=parts[0].split("/").pop();
    if(FILES[file]){{event.preventDefault();showPage(file,parts[1]||"")}}
  }},true)}}catch(_e){{}}
}});
showPage("index.html");
</script>
</body>
</html>
'''


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for name in PAGES:
        page = phone_page((DOCS / name).read_text(encoding="utf-8"))
        (OUT / name).write_text(page, encoding="utf-8")
        if name == "index.html":
            (OUT / "main.html").write_text(main_page(page), encoding="utf-8")
    for _href, (source, page, title) in SOURCES.items():
        (OUT / page).write_text(markdown_page(source, title), encoding="utf-8")
    reader = OUT / "Планы_Aion_Chat_Watcher_Telegram.html"
    reader.write_text(telegram_reader(), encoding="utf-8")
    files = sorted(p.name for p in OUT.iterdir())
    print(f"{len(files)} files in {OUT}: {', '.join(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
