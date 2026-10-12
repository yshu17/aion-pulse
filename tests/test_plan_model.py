"""The five published plans must agree on task IDs and source status."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_master_plan  # noqa: E402
import plan_shared  # noqa: E402
import plan_task_meta  # noqa: E402


def test_shared_model_has_all_five_views_and_unique_task_keys():
    items = build_master_plan.collect()
    registry = set(plan_task_meta.load_task_meta()["known_keys"])  # the registry of every task ID ever registered
    assert {item["key"] for item in items} == registry  # no task lost, none unregistered; no fixed number to bump
    assert len({item["key"] for item in items}) == len(items)
    assert {item["plan"] for item in items} == {"map", "sn", "ui", "tg", "draft"}
    import plan_states
    assert all(plan_states.normalize_status(item["status"]) in plan_states.STATE_KEYS for item in items)  # sources hold legacy values
    assert all(item["title"] for item in items)
    assert next(i for i in items if i["key"] == "ui:3")["depends_on"] == ["ui:5", "ui:6"]


def test_new_id_receives_date_only_after_initial_catalogue(tmp_path, monkeypatch):
    metadata = tmp_path / "plan-task-meta.json"
    metadata.write_text('{"latest":"ui:42","tasks":{"ui:42":{"added_at":"11.10.2026 02:46"}}}', encoding="utf-8")
    monkeypatch.setattr(plan_task_meta, "META_PATH", metadata)
    assert plan_task_meta.register_new_tasks(["ui:42", "map:39"])
    first = json.loads(metadata.read_text(encoding="utf-8"))
    assert first["latest"] == "ui:42"
    assert "map:39" not in first["tasks"]
    assert plan_task_meta.register_new_tasks(["ui:42", "map:39", "map:40"])
    second = json.loads(metadata.read_text(encoding="utf-8"))
    assert second["latest"] == "map:40"
    assert second["tasks"]["map:40"]["added_at"]
    assert plan_task_meta.register_new_tasks(["ui:42", "map:39", "map:40"]) is False


def test_source_change_history_starts_only_after_baseline(tmp_path, monkeypatch):
    metadata = tmp_path / "plan-task-meta.json"
    metadata.write_text('{"latest":"map:1","tasks":{},"known_keys":["map:1"]}', encoding="utf-8")
    monkeypatch.setattr(plan_task_meta, "META_PATH", metadata)
    item = {"key": "map:1", "title": "Карта", "text": "Начало", "status": "todo", "who": "Кодекс"}
    assert plan_task_meta.register_source_changes([item])
    baseline = json.loads(metadata.read_text(encoding="utf-8"))
    assert "map:1" not in baseline["tasks"]
    assert plan_task_meta.register_source_changes([item]) is False
    item["status"] = "doing"
    assert plan_task_meta.register_source_changes([item])
    changed = json.loads(metadata.read_text(encoding="utf-8"))["tasks"]["map:1"]
    assert changed["changed_at"]
    assert changed["history"][0]["event"] == "Изменено в исходном плане"


def test_all_five_pages_embed_one_model_and_injection_is_idempotent():
    model = json.loads((ROOT / "docs" / "plan-model.json").read_text(encoding="utf-8"))
    assert {item["key"] for item in model["items"]} == set(plan_task_meta.load_task_meta()["known_keys"])
    for page in ("index", "map-poi-plan", "schedule-notify-plan", "ui-ux-improvement-plan", "telegram-bridge-plan"):
        html = (ROOT / "docs" / f"{page}.html").read_text(encoding="utf-8")
        assert html.count('id="shared-plan-data"') == 1
        assert html.count('id="shared-plan-script"') == 1
        payload = re.search(r'<script type="application/json" id="shared-plan-data">(.*?)</script>', html, re.S)
        assert payload is not None
        assert json.loads(payload.group(1)) == model
        current = "all" if page == "index" else {"map-poi-plan": "map", "schedule-notify-plan": "sn",
                                                  "ui-ux-improvement-plan": "ui", "telegram-bridge-plan": "tg"}[page]
        assert plan_shared.inject_shared_explorer(html, model, current) == html
