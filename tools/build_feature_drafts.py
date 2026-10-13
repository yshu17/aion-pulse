"""Render six preliminary feature plans from one source without changing the five core plan statuses."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_ai_tools  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SOURCE = DOCS / "feature-drafts.json"
HUB = "feature-drafts.html"
CLAUDE_FIELDS = (
    ("architecture", "Архитектурные вопросы"),
    ("game_data", "Недостающие игровые данные"),
    ("research", "Необходимые исследования"),
    ("ui", "Варианты пользовательского интерфейса"),
    ("motion", "Идеи анимаций и интерактивности"),
    ("diagrams", "Необходимые диаграммы"),
    ("risks", "Технические риски"),
    ("owner", "Вопросы, требующие решения владельца"),
    ("next", "Предлагаемые следующие этапы"),
)
STYLE = """<style>
:root{color-scheme:dark;--bg:#141519;--surface:#1c1e24;--surface2:#262931;--border:#363a45;--text:#e9e7e4;--muted:#a7abb5;--accent:#ff8c1a}
*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 'Segoe UI',system-ui,sans-serif}
.wrap{max-width:1000px;margin:auto;padding:22px 16px 50px}a{color:#ffb05c}nav{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}h1{font-size:26px;margin:0 0 6px}h2{font-size:19px;margin:28px 0 10px}h3{font-size:16px;margin:0}
.muted{color:var(--muted)}.banner{padding:12px;border:1px solid #785320;border-radius:10px;background:#30271d;margin:14px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}.card,details{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;margin:9px 0}
.card{display:block;text-decoration:none;color:var(--text)}.card:hover{border-color:var(--accent)}.card p{margin:6px 0;color:var(--muted)}
summary{cursor:pointer;font-weight:650}details[open]>summary{color:#ffb05c}details details{background:var(--surface2)}
ul,ol{padding-left:22px}li{margin:5px 0}.id{font:12px Consolas,monospace;color:#ffb05c}.badge{display:inline-block;padding:1px 7px;border-radius:6px;background:#493516;border:1px solid #846128;color:#ffd16b;font-size:11px;font-weight:750}
.stage{margin-top:8px}.ai{font-size:13px}.ai td,.ai th{border-bottom:1px solid var(--border);padding:3px 5px;text-align:left;vertical-align:top}.ai table{border-collapse:collapse;width:100%}.miss{color:#ff8f6b}.ok{color:#5fd38d}input[type=search]{width:100%;padding:9px;border-radius:8px;background:var(--surface2);color:var(--text);border:1px solid var(--border);font:inherit}
@media(max-width:600px){h1{font-size:22px}.wrap{padding:16px}.grid{display:block}}
</style>"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>{esc(title)}</title>{STYLE}</head>'
            f'<body><div class="wrap"><!--NAV--><!--/NAV-->{body}</div></body></html>')


def load() -> dict:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    if data.get("reviewStatus") != "DRAFT" or len(data.get("plans", [])) != 6:
        raise ValueError("Expected six DRAFT feature plans")
    ids = [plan["id"] for plan in data["plans"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate draft plan ID")
    if any(plan.get("reviewStatus") != "DRAFT" for plan in data["plans"]):
        raise ValueError("Only DRAFT reviewStatus is allowed for preliminary plans")
    if data.get("latest") not in ids:
        raise ValueError("Unknown latest draft plan")
    return data


def filename(plan: dict) -> str:
    return f'feature-{plan["slug"]}.html'


def master_section(data: dict) -> str:
    cards = []
    for plan in sorted(data["plans"], key=lambda row: row["number"], reverse=True):
        badge = '<span class="new-badge">НОВОЕ</span>' if is_new_draft(plan, data) else ""
        cards.append(f'<article class="plan"><h3><a href="{esc(filename(plan))}">{esc(plan["id"])} · {esc(plan["title"])}</a> {badge}</h3>'
                     f'<span class="gate">DRAFT · ожидает Claude</span><span class="tag">Добавлено: {esc(data["added_at"])}</span></article>')
    return (f'<h2>Новые планы · черновики для Claude Code</h2><p class="tag">'
            f'Шесть тем из <a href="{HUB}">единого реестра черновиков</a>; они не меняют статусы пяти основных планов.</p>'
            f'<div class="plans">{"".join(cards)}</div>')


def ai_block(rec: dict) -> str:
    """«AI Tools & Skills» of one DRAFT stage, from docs/plan-ai-tools.json."""
    if rec.get("state") != "recommended":
        return '<details class="ai"><summary>AI Tools &amp; Skills / Инструменты разработки</summary><p class="miss">Рекомендации ещё нет.</p></details>'
    rows = "".join(f'<tr><td><code>{esc(r["name"])}</code></td><td>{esc(r["role_label"])}</td><td>{esc(r["purpose"])}</td>'
                   f'<td class="{"ok" if r["available"] else "miss"}">{esc(r["availability_label"])}</td></tr>' for r in rec["skills"])
    split = rec.get("split", {})
    done = "".join(f"<li>{esc(d)}</li>" for d in rec["done"])
    return (f'<details class="ai"><summary>AI Tools &amp; Skills / Инструменты разработки · {esc(rec["agent_label"])}</summary>'
            f'<table><tr><th>Скилл</th><th>Роль</th><th>Зачем</th><th>Доступность</th></tr>{rows}</table>'
            f'<p>Проектирование: {esc(split.get("design", ""))} · реализация: {esc(split.get("build", ""))} · '
            f'тестирование: {esc(split.get("test", ""))} · утверждение: {esc(split.get("approve", ""))}</p>'
            f'<p>Передача: {esc(rec["handoff_label"])} · архитектура: {esc(rec["arch_label"])}</p><ul>{done}</ul>'
            + (f'<p class="muted">{esc(rec["note"])}</p>' if rec.get("note") else "") + '</details>')


def is_new_draft(plan: dict, data: dict) -> bool:
    """Drafts added on the day of the newest one are all new (one file added the six together)."""
    latest = next((p for p in data["plans"] if p["id"] == data["latest"]), {})
    day = (latest.get("added_at") or data.get("added_at", ""))[:10]
    return bool(day) and (plan.get("added_at") or data.get("added_at", ""))[:10] == day


def render_plan(plan: dict, data: dict, ai: dict | None = None) -> str:
    ai = ai or {}
    latest = is_new_draft(plan, data)
    badge = ' <span class="badge">НОВОЕ</span>' if latest else ""
    heading = (f'<h1>{esc(plan["id"])} · {esc(plan["title"])}{badge}</h1>'
               f'<div class="banner"><b>{esc(data["reviewLabel"])}</b><br>Добавлено: {esc(data["added_at"])}. '
               f'Это подготовительный план, разработка не утверждена.</div>'
               f'<p>{esc(plan["goal"])}</p>')
    if plan["parent"]:
        parent = next(p for p in data["plans"] if p["id"] == plan["parent"])
        heading += f'<p class="muted">Подплан: <a href="{esc(filename(parent))}">{esc(parent["id"])} · {esc(parent["title"])}</a></p>'
    sections = [("Пользовательские сценарии", plan["scenarios"]),
                ("Функциональные требования", plan["requirements"]),
                ("Неподтверждённые игровые механики и данные", plan["unconfirmed"])]
    blocks = "".join(f'<details open><summary>{esc(title)}</summary><ul>{"".join(f"<li>{esc(row)}</li>" for row in rows)}</ul></details>'
                     for title, rows in sections)
    stages = ""
    for stage in reversed(plan["stages"]):
        deps = ", ".join(stage["depends_on"]) or "нет"
        stages += (f'<details class="stage"><summary><span class="id">{esc(stage["id"])}</span> · {esc(stage["title"])}</summary>'
                   f'<p>Результат: {esc(stage["result"])}</p><p class="muted">Предварительные зависимости: {esc(deps)}. '
                   f'Добавлено: {esc(data["added_at"])}.</p>{ai_block(ai.get(stage["id"], {}))}</details>')
    claude = "".join(f'<li><b>{esc(label)}:</b> {esc(plan["claude"][key])}</li>' for key, label in CLAUDE_FIELDS)
    used = list(dict.fromkeys(r["name"] for st in plan["stages"] for r in ai.get(st["id"], {}).get("skills", [])))
    skills = ", ".join(f'<code>{esc(name)}</code>' for name in used or data["skills"])
    further = (f'<details><summary>Для дальнейшей проработки Claude Code</summary><ol>{claude}</ol>'
               f'<p>Скиллы этапов (подробно — «AI Tools &amp; Skills» у каждого этапа): {skills}. Claude Code проверяет и расширяет черновик как Lead Developer.</p></details>')
    return page(plan["title"], heading + blocks + '<h2>Предварительные этапы · новые сверху</h2>' + stages + further)


def render_hub(data: dict) -> str:
    cards = ""
    for plan in sorted(data["plans"], key=lambda row: row["number"], reverse=True):
        badge = ' <span class="badge">НОВОЕ</span>' if is_new_draft(plan, data) else ""
        cards += (f'<a class="card" data-plan href="{esc(filename(plan))}"><h3>{esc(plan["id"])} · {esc(plan["title"])}{badge}</h3>'
                  f'<p>{esc(plan["goal"])}</p><small>DRAFT · {esc(data["added_at"])}</small></a>')
    body = ('<h1>Новые планы для Claude Code</h1><p class="muted">Шесть первоначальных планов из одного файла '
            '<code>docs/feature-drafts.json</code>. Статус каждого: DRAFT — ожидает проверки Claude Code.</p>'
            '<input type="search" id="search" aria-label="Поиск по черновикам" placeholder="Найти план…">'
            f'<div class="grid" id="plans">{cards}</div>'
            '<script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase("ru");'
            'document.querySelectorAll("[data-plan]").forEach(x=>x.hidden=!x.textContent.toLocaleLowerCase("ru").includes(q))})</script>')
    return page("Черновики новых планов", body)


def main() -> int:
    data = load()
    (DOCS / HUB).write_text(render_hub(data), encoding="utf-8")
    ai_data = plan_ai_tools.load()
    rows = plan_ai_tools.draft_items(data, ai_data, plan_ai_tools.resolve_skills(ai_data))
    ai = {row["id"]: row["ai"] for row in rows}
    for plan in data["plans"]:
        (DOCS / filename(plan)).write_text(render_plan(plan, data, ai), encoding="utf-8")
    print(f"Generated {HUB} and {len(data['plans'])} DRAFT plans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
