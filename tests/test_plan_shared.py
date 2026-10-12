"""The shared Task Card is one component on every page, the old lists are hidden but not removed, stages match the tasks."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "tools"))

import plan_shared  # noqa: E402

PLAN_PAGES = ["index.html", "map-poi-plan.html", "schedule-notify-plan.html", "ui-ux-improvement-plan.html",
              "telegram-bridge-plan.html"]
DRAFT_PAGES = sorted(p.name for p in DOCS.glob("feature-*.html") if p.name != "feature-drafts.html")


def script_of(page: str) -> str:
    html = (DOCS / page).read_text(encoding="utf-8")
    match = re.search(r'<script id="shared-plan-script">(.*?)</script>', html, re.S)
    assert match, f"{page}: no shared card script"
    return re.sub(r"const PAGE='[a-z]+'", "const PAGE='*'", match.group(1))


def test_one_component_the_same_script_and_style_on_every_page():
    """Changing the card in tools/plan_shared.py changes every page: they all carry the same script and style."""
    pages = PLAN_PAGES + DRAFT_PAGES
    assert len(DRAFT_PAGES) == 6
    scripts = {page: script_of(page) for page in pages}
    assert len(set(scripts.values())) == 1, "the card script differs between pages"
    styles = {re.search(r'<style id="shared-plan-style">(.*?)</style>', (DOCS / p).read_text(encoding="utf-8"), re.S).group(1)
              for p in pages}
    assert len(styles) == 1


def test_old_lists_are_marked_not_removed():
    """Stage 3 hides the old lists; their code and markup stay (stage 4, the deletion, is not approved)."""
    for page, markers in {"ui-ux-improvement-plan.html": ['id="tasks"', "function renderTasks"],
                          "telegram-bridge-plan.html": ['id="tasks"', "function renderTasks"],
                          "index.html": ['id="list"', "function list"]}.items():
        html = (DOCS / page).read_text(encoding="utf-8")
        assert "native-list" in html, page
        for marker in markers:
            assert marker in html, f"{page}: the old list lost {marker}"


def test_hide_switch_and_pages_agree():
    flag = "true" if plan_shared.HIDE_NATIVE_LISTS else "false"
    for page in PLAN_PAGES + DRAFT_PAGES:
        assert f"const HIDE_NATIVE={flag}," in script_of(page), page
    assert ".native-hidden .native-list" in plan_shared.STYLE


def test_stages_match_the_tasks():
    model = json.loads((DOCS / "plan-model.json").read_text(encoding="utf-8"))
    assert {k: len(v) for k, v in model["stages"].items()} == {"ui": 9, "tg": 3}
    for plan in ("ui", "tg"):
        ids = {stage["id"] for stage in model["stages"][plan]}
        for item in model["items"]:
            if item["plan"] == plan:
                assert item["stage"] == "" or item["stage"] in ids, item["key"]
    assert all(item["stage"] == "" for item in model["items"] if item["plan"] not in ("ui", "tg"))
    tg = [item for item in model["items"] if item["plan"] == "tg"]
    assert tg and all(item["stage"] for item in tg)  # every Telegram task belongs to a stage


def test_migration_and_safety_controls_exist_in_the_card():
    script = plan_shared.SCRIPT
    for needle in ("shared-migrate", "nativeMarks", "aion-backup-last-v1", "shared-restore", "shared-reset",
                   "aion-shared-plan-filters-v1", "перенос из старого списка"):
        assert needle in script or needle in plan_shared.PANEL, needle
    # a conflict never overwrites silently: «оставить как в общем журнале» is the checked default
    assert 'value="keep" checked' in script
    # old storage keys are read, never deleted by the transfer
    assert "removeItem(NATIVE_KEYS" not in script


def test_qa_regressions_from_the_browser_audit():
    """ui:44 findings: the newest-plan order uses the normalized status, the open cards survive a redraw, ?native needs =1."""
    script = plan_shared.SCRIPT
    assert "status(i)==='planned');const order" in script and "status(i)==='todo');const order" not in script  # QA-01
    assert "const OPEN=new Set()" in script and "OPEN.has(" in script  # QA-02
    assert ".get('native')==='1'" in script and ".has('native')" not in script  # QA-03
