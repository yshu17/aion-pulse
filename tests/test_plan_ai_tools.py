"""AI tools & skills of plan tasks: recommendations are Claude's data, availability is checked on disk."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_feature_drafts  # noqa: E402
import build_master_plan  # noqa: E402
import plan_ai_tools  # noqa: E402


def skill_file(base: Path, rel: str) -> None:
    path = base / rel / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")


def test_availability_is_read_from_disk_not_assumed(tmp_path):
    root, home = tmp_path / "repo", tmp_path / "home"
    skill_file(root, ".claude/skills/planner")
    skill_file(home, "skills/ui-ux-pro-max")
    skill_file(home, "plugins/cache/official/superpowers/6.4.1/skills/brainstorming")
    (root / "tools").mkdir()
    (root / "tools" / "check_project.py").write_text("", encoding="utf-8")
    av = lambda source: plan_ai_tools.availability(source, root, home)  # noqa: E731
    assert av("project:.claude/skills/planner") == "project"
    assert av("project:.claude/skills/absent") == "missing"
    assert av("user:ui-ux-pro-max") == "user"
    assert av("plugin:superpowers:brainstorming") == "plugin"
    assert av("plugin:superpowers:writing-plans") == "missing"
    assert av("tool:tools/check_project.py") == "tool"
    assert av("tool:tools/ui_snapshots.py") == "missing"
    assert av("builtin:code-review") == "builtin"


def test_every_open_task_and_draft_stage_has_a_valid_recommendation():
    data = plan_ai_tools.load()
    items = build_master_plan.collect()
    stages = {f"draft:{st['id']}" for plan in build_feature_drafts.load()["plans"] for st in plan["stages"]}
    keys = {i["key"] for i in items} | stages
    open_keys = {i["key"] for i in items if i["status"] != "done"} | stages
    errors, warnings = plan_ai_tools.validate(data, keys, open_keys)
    assert errors == []
    assert warnings == []


def test_validate_rejects_unknown_skill_agent_and_codex_handoff_to_claude():
    data = {"skills": {"a": {"source": "builtin:a", "codex": "none"}},
            "tasks": {"map:1": {"agent": "robot", "reviewer": "claude", "handoff": "ready", "arch_review": "not-needed",
                                "skills": [{"name": "nope", "role": "primary", "purpose": "x"}], "done": ["ok"]},
                      "map:2": {"agent": "claude", "reviewer": "claude", "handoff": "ready", "arch_review": "not-needed",
                                "skills": [{"name": "a", "role": "primary", "purpose": "x"}], "done": ["ok"]}}}
    errors, warnings = plan_ai_tools.validate(data, {"map:1", "map:2"}, {"map:1", "map:2", "map:3"})
    assert "map:1: unknown agent" in errors
    assert "map:1: skill not in registry: nope" in errors
    assert "map:2: ready for Codex but agent is claude" in errors
    assert warnings == ["open task without AI recommendation: map:3"]


def test_new_open_task_is_flagged_not_guessed():
    data = plan_ai_tools.load()
    items = [{"key": "map:999", "status": "todo"}, {"key": "map:1", "status": "done"}]
    plan_ai_tools.annotate(items, data, plan_ai_tools.resolve_skills(data))
    assert items[0]["ai"] == {"state": "missing"}
    assert items[1]["ai"] == {"state": "retro"}


def test_codex_task_text_has_handoff_sections():
    data = plan_ai_tools.load()
    items = [i for i in build_master_plan.collect() if i["key"] == "map:29"]
    plan_ai_tools.annotate(items, data, plan_ai_tools.resolve_skills(data))
    text = items[0]["ai"]["codex_text"]
    for part in ("ЗАДАНИЕ ДЛЯ CODEX · map:29", "критерии готовности", "Разрешённые файлы", "Запрещено", "Тесты:",
                 "Проверяет и принимает: Claude Code", "Отчёт:"):
        assert part in text


def test_built_model_carries_ai_without_changing_ids_or_statuses():
    model = json.loads((ROOT / "docs" / "plan-model.json").read_text(encoding="utf-8"))
    source = {i["key"]: i for i in build_master_plan.collect()}
    assert {i["key"] for i in model["items"]} == source.keys()
    assert all(i["status"] == source[i["key"]]["status"] for i in model["items"])
    assert all(i["ai"]["state"] in {"recommended", "retro"} for i in model["items"])
    assert len(model["ai"]["drafts"]) == 24


def test_handoff_states_for_review_and_integration_are_known_and_filterable():
    import plan_ai_view

    assert "review" in plan_ai_tools.HANDOFF and "integrate" in plan_ai_tools.HANDOFF
    assert 'value="review"' in plan_ai_view.SHARED_CONTROLS and 'value="integrate"' in plan_ai_view.SHARED_CONTROLS
    assert "ai.handoff!=='review'" in plan_ai_view.SHARED_JS and "ai.handoff!=='integrate'" in plan_ai_view.SHARED_JS


def test_pilot_task_ui_42_is_in_progress_on_its_own_branch():
    import json
    from pathlib import Path

    data = json.loads((Path(plan_ai_tools.__file__).resolve().parent.parent / "docs" / "plan-ai-tools.json")
                      .read_text(encoding="utf-8"))
    task = data["tasks"]["ui:42"]
    assert task["agent"] == "codex" and task["handoff"] == "in-progress"
    assert task["branch"] == "codex/ui-42-tabs"
