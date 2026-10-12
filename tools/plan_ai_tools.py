"""AI tools & skills for plan tasks: Claude's recommendations + a deterministic availability check.

Source: docs/plan-ai-tools.json. Claude Code writes the recommendations there by hand (skills, executor, split of
responsibility, readiness criteria); this module never guesses them. It only

* checks on disk whether each skill/tool really exists (``resolve_skills``),
* attaches the recommendation to the task items of the plan model (``annotate``),
* validates the file (``validate``) and
* renders a ready-to-paste task text for Codex (``codex_task``).

CLI:  python tools/plan_ai_tools.py codex map:29     — print the Codex task for a key
      python tools/plan_ai_tools.py missing          — open tasks without a recommendation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "plan-ai-tools.json"
HOME_CLAUDE = Path.home() / ".claude"

AGENTS = {"claude": "Claude Code", "codex": "Codex", "joint": "Совместно", "user": "Пользователь"}
ROLES = {"primary": "основной", "supporting": "дополнительный"}
HANDOFF = {"ready": "готово к передаче Codex", "needs-architecture": "ждёт архитектурного решения Claude",
           "in-progress": "в работе", "gated": "план ждёт «делаем»", "blocked": "ждёт предыдущих этапов",
           "user": "нужен пользователь", "n/a": "передача не нужна",
           "review": "ждёт проверки Claude", "integrate": "проверено, готово к интеграции"}
ARCH = {"pending": "ожидает архитектурной проверки Claude", "approved": "архитектура утверждена", "not-needed": "не требуется"}
REVIEWERS = {"claude", "codex", "user"}
CODEX_ACCESS = {"native": "у Codex есть свой экземпляр", "read-file": "Codex читает SKILL.md по AGENTS.md",
                "analogue": "у Codex свой аналог", "none": "только у Claude"}
AVAILABILITY = {"project": "установлен в проекте", "user": "установлен глобально", "plugin": "плагин",
                "synced": "из claude.ai", "builtin": "встроен в Claude Code", "tool": "скрипт проекта",
                "missing": "не найден — рекомендуется создать или установить"}
AVAILABLE = {"project", "user", "plugin", "synced", "builtin", "tool"}


def load(path: Path = SOURCE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def availability(source: str, root: Path = ROOT, home: Path = HOME_CLAUDE) -> str:
    """Look the skill up where Claude Code / the project really keep it; 'missing' when it is not there."""
    kind, _sep, ref = source.partition(":")
    if kind == "project":
        found = (root / ref / "SKILL.md").is_file()
    elif kind == "user":
        found = (home / "skills" / ref / "SKILL.md").is_file()
    elif kind == "plugin":
        plugin, _sep, skill = ref.partition(":")
        found = any(home.glob(f"plugins/cache/*/{plugin}/*/skills/{skill}/SKILL.md"))
    elif kind == "synced":
        found = any(home.glob(f"skills/synced/*/{ref}/SKILL.md"))
    elif kind == "tool":
        found = (root / ref).is_file()
    elif kind == "builtin":
        return "builtin"  # part of Claude Code itself; no file to look for
    else:
        return "missing"
    return kind if found else "missing"


def resolve_skills(data: dict, root: Path = ROOT, home: Path = HOME_CLAUDE) -> dict:
    out = {}
    for name, info in data.get("skills", {}).items():
        state = availability(info["source"], root, home)
        out[name] = {**info, "name": name, "availability": state, "available": state in AVAILABLE,
                     "availability_label": AVAILABILITY[state], "codex_label": CODEX_ACCESS.get(info.get("codex", ""), "")}
    return out


def annotate(items: list[dict], data: dict, skills: dict) -> list[dict]:
    """Attach ``ai`` to every task item. Done tasks without a recommendation get the factual executor only."""
    tasks = data.get("tasks", {})
    for item in items:
        rec = tasks.get(item["key"])
        if rec is None:
            item["ai"] = {"state": "retro" if item["status"] == "done" else "missing"}
            continue
        item["ai"] = attach(rec, skills)
        if rec["agent"] in {"codex", "joint"}:
            item["ai"]["codex_text"] = codex_task(item)
    return items


def attach(rec: dict, skills: dict) -> dict:
    rows = [{**row, "role_label": ROLES.get(row["role"], row["role"]), **{k: skills[row["name"]][k] for k in
            ("title", "area", "availability", "available", "availability_label", "codex", "codex_label")}}
            for row in rec.get("skills", []) if row["name"] in skills]
    return {**rec, "state": "recommended", "skills": rows, "agent_label": AGENTS[rec["agent"]],
            "handoff_label": HANDOFF[rec["handoff"]], "arch_label": ARCH[rec["arch_review"]],
            "missing_tools": [row["name"] for row in rows if not row["available"]]}


def draft_items(drafts: dict, data: dict, skills: dict) -> list[dict]:
    """Stages of the six DRAFT plans with their recommendation (they are not core plan tasks)."""
    rows = []
    for plan in drafts["plans"]:
        for stage in plan["stages"]:
            rec = data.get("tasks", {}).get(f"draft:{stage['id']}")
            rows.append({"key": f"draft:{stage['id']}", "id": stage["id"], "plan_id": plan["id"], "plan_title": plan["title"],
                         "title": stage["title"], "depends_on": [f"draft:{d}" for d in stage["depends_on"] if "." in d],
                         "ai": attach(rec, skills) if rec else {"state": "missing"}})
    return rows


def validate(data: dict, keys: set[str], open_keys: set[str]) -> tuple[list[str], list[str]]:
    """Errors for broken recommendations; warnings for open tasks that still wait for one."""
    errors: list[str] = []
    skills = data.get("skills", {})
    for name, info in skills.items():
        if info.get("source", "").partition(":")[0] not in {"project", "user", "plugin", "synced", "builtin", "tool"}:
            errors.append(f"skill {name}: unknown source kind")
        if info.get("codex") not in CODEX_ACCESS:
            errors.append(f"skill {name}: unknown codex access")
    for key, rec in data.get("tasks", {}).items():
        if key not in keys:
            errors.append(f"recommendation for unknown task: {key}")
        if rec.get("agent") not in AGENTS:
            errors.append(f"{key}: unknown agent")
        if rec.get("reviewer") not in REVIEWERS:
            errors.append(f"{key}: unknown reviewer")
        if rec.get("handoff") not in HANDOFF:
            errors.append(f"{key}: unknown handoff state")
        if rec.get("arch_review") not in ARCH:
            errors.append(f"{key}: unknown arch_review")
        roles = [row.get("role") for row in rec.get("skills", [])]
        if "primary" not in roles:
            errors.append(f"{key}: no primary skill")
        for row in rec.get("skills", []):
            if row.get("name") not in skills:
                errors.append(f"{key}: skill not in registry: {row.get('name')}")
            if row.get("role") not in ROLES:
                errors.append(f"{key}: unknown role {row.get('role')}")
            if not row.get("purpose"):
                errors.append(f"{key}: skill {row.get('name')} has no purpose")
        if not rec.get("done"):
            errors.append(f"{key}: no readiness criteria")
        if rec.get("handoff") == "ready" and rec.get("agent") not in {"codex", "joint"}:
            errors.append(f"{key}: ready for Codex but agent is {rec.get('agent')}")
    warnings = [f"open task without AI recommendation: {key}" for key in sorted(open_keys - data.get("tasks", {}).keys())]
    return errors, warnings


def mapping_markdown(items: list[dict], skills: dict, drafts: list[dict]) -> str:
    """docs/AI_SKILLS_TASK_MAPPING.md — generated from the same data, never edited by hand."""
    open_items = [i for i in items if i["status"] != "done"]
    rows = ["# Сопоставление задач и навыков", "",
            "Сгенерировано `python tools/build_master_plan.py` из `docs/plan-ai-tools.json` — не править вручную. "
            "Учтены открытые задачи пяти планов и этапы черновиков; доступность проверена по файлам при сборке.", "",
            "## Реестр инструментов", "", "| Скилл / инструмент | Направление | Доступность | Codex | Открытых задач |", "|---|---|---|---|---|"]
    for name, info in skills.items():
        n = sum(1 for i in open_items + drafts if any(r["name"] == name for r in i["ai"].get("skills", [])))
        rows.append(f"| `{name}` | {info['area']} | {info['availability_label']} | {info['codex_label']} | {n} |")
    count = {a: sum(1 for i in open_items if i["ai"].get("agent") == a) for a in AGENTS}
    rows += ["", "## Распределение открытых задач", "",
             " · ".join(f"{AGENTS[a]}: **{n}**" for a, n in count.items()), "",
             "## Задачи", "", "| Ключ | Задача | Исполнитель | Основной скилл | Дополнительные | Передача |", "|---|---|---|---|---|---|"]
    for i in open_items + drafts:
        ai = i["ai"]
        if ai.get("state") != "recommended":
            rows.append(f"| `{i['key']}` | {i['title']} | — | **нет рекомендации** | | |")
            continue
        main = ", ".join(f"`{r['name']}`" for r in ai["skills"] if r["role"] == "primary")
        extra = ", ".join(f"`{r['name']}`" for r in ai["skills"] if r["role"] != "primary")
        rows.append(f"| `{i['key']}` | {i['title'].replace('|', '/')} | {ai['agent_label']} | {main} | {extra} | {ai['handoff_label']} |")
    return "\n".join(rows) + "\n"


FORBIDDEN = ["Игровая папка (только чтение)", "config.json пользователя", "docs/plan-ai-tools.json и статусы планов — меняет Claude",
             "Чужие незавершённые файлы из `git status`"]


def codex_task(item: dict) -> str:
    """Plain-text task for manual hand-off to Codex (it has no access to Claude's Skill tool)."""
    ai = item.get("ai", {})
    if ai.get("state") != "recommended":
        return ""
    files = ai.get("files", {})
    allowed = files.get("Codex", []) or ["— уточнить у Claude до начала —"]
    skills = [f"- {r['name']} ({r['role_label']}): {r['purpose']}. "
              + (f"{r['codex_label']}." if r["available"] else f"НЕТ: {r['availability_label']}, сделать вручную.") for r in ai["skills"]]
    deps = ", ".join(item.get("depends_on", [])) or item.get("dependencies_text") or "нет"
    lines = [f"ЗАДАНИЕ ДЛЯ CODEX · {item['key']} · {item['title']}",
             f"Цель: {item['title']}.",
             f"Контекст: {item.get('text') or 'см. план'}",
             f"План: {item.get('plan', '')} · статус: {item.get('status', '')} · передача: {ai['handoff_label']}",
             f"Зависимости: {deps}",
             "Требования и критерии готовности:", *[f"- {d}" for d in ai["done"]],
             "Разрешённые файлы:", *[f"- {f}" for f in allowed],
             "Запрещено:", *[f"- {f}" for f in FORBIDDEN],
             "Инструменты (читай SKILL.md и references/ из .claude/skills или ~/.claude/skills):", *skills]
    if ai.get("contract"):
        lines.append(f"Контракт: {ai['contract']}")
    if ai.get("note"):
        lines.append(f"Примечание: {ai['note']}")
    lines += ["Тесты:", *[f"- {t}" for t in ai.get("tests", [])], "- python tools/check_project.py",
              f"Проверяет и принимает: {AGENTS.get(ai['reviewer'], ai['reviewer'])}.",
              "Отчёт: строка в журнал PAIR.md (что сделано, файлы, результат тестов, открытые вопросы); своя ветка codex/<задача>."]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_master_plan  # noqa: PLC0415
    data = load()
    items = annotate(build_master_plan.collect(), data, resolve_skills(data))
    if len(argv) == 2 and argv[0] == "codex":
        item = next((i for i in items if i["key"] == argv[1]), None)
        text = codex_task(item) if item else ""
        print(text or f"Нет рекомендации для {argv[1]}")
        return 0 if text else 1
    if argv == ["missing"]:
        missing = [i["key"] for i in items if i["ai"]["state"] == "missing"]
        print("\n".join(missing) or "Все открытые задачи имеют рекомендацию")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
