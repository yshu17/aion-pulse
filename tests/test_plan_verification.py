"""Verification is a state apart from the status: verified needs evidence, a done task defaults to legacy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_plans  # noqa: E402
import plan_verification as pv  # noqa: E402


def test_status_decides_where_a_state_applies_and_done_defaults_to_legacy():
    assert pv.resolve("done", None) == ("legacy", [])  # never verified by default
    assert pv.resolve("done", {"state": "verified", "evidence": [{"kind": "test", "ref": "x"}]})[0] == "verified"
    assert pv.resolve("done", {"state": "bogus"}) == ("legacy", [])
    assert pv.resolve("review", None)[0] == "pending"
    for status in ("planned", "research", "doing", "blocked", "deferred", "cancelled"):
        assert pv.resolve(status, {"state": "verified", "evidence": [{"kind": "test", "ref": "x"}]}) == ("", [])


def test_verified_needs_evidence_a_done_task_and_a_real_commit():
    def exists(sha):
        return sha == "abc1234"

    assert pv.validate_entry("ui:1", {"state": "verified", "evidence": []}, "done", exists) == ["ui:1: verified without evidence"]
    assert "not done" in pv.validate_entry("ui:1", {"state": "verified", "evidence": [{"kind": "test", "ref": "t"}]}, "doing", exists)[0]
    ghost = {"state": "verified", "evidence": [{"kind": "commit", "ref": "deadbee"}]}
    assert "not found in git" in pv.validate_entry("ui:1", ghost, "done", exists)[0]
    good = {"state": "verified", "evidence": [{"kind": "commit", "ref": "abc1234"}]}
    assert pv.validate_entry("ui:1", good, "done", exists) == []
    assert pv.validate_entry("ui:1", {"state": "legacy"}, "done", exists) == []
    assert "unknown verification state" in pv.validate_entry("ui:1", {"state": "ok"}, "done", exists)[0]


def test_summary_keeps_progress_and_verification_apart():
    items = [{"status": "done", "verification": "verified"}, {"status": "done", "verification": "legacy"},
             {"status": "done", "verification": "legacy"}, {"status": "review", "verification": "pending"},
             {"status": "planned", "verification": ""}]
    assert pv.summary(items) == {"done": 3, "verified": 1, "legacy": 2, "pending": 0, "waiting": 1}


def test_set_refuses_without_evidence_and_writes_with_it(tmp_path):
    path = tmp_path / "plan-verification.json"
    with pytest.raises(SystemExit, match="without evidence"):
        pv.set_state("ui:5", "verified", [], "tester", path)
    assert not path.exists()
    entry = pv.set_state("ui:5", "verified", ["test:pytest 1 passed"], "tester", path)
    assert entry["evidence"] == [{"kind": "test", "ref": "pytest 1 passed"}]
    assert json.loads(path.read_text(encoding="utf-8"))["tasks"]["ui:5"]["state"] == "verified"
    pv.set_state("ui:6", "legacy", [], "tester", path)  # legacy and pending need no evidence
    assert set(pv.load(path)["tasks"]) == {"ui:5", "ui:6"}


def test_candidates_are_proposals_from_a_real_commit_and_a_check_word():
    items = [
        {"key": "ui:1", "status": "done", "verification": "legacy", "title": "a", "note": "готово (`abc1234`), проверено снимками"},
        {"key": "ui:2", "status": "done", "verification": "legacy", "title": "b", "note": "готово (`abc1234`)"},  # no check word
        {"key": "ui:3", "status": "done", "verification": "legacy", "title": "c", "note": "тест, коммит `deadbee`"},  # no such commit
        {"key": "ui:4", "status": "done", "verification": "verified", "title": "d", "note": "тест `abc1234`"},  # already verified
        {"key": "ui:5", "status": "doing", "verification": "", "title": "e", "note": "тест `abc1234`"},
    ]
    found = pv.candidates(items, commit_check=lambda sha: sha == "abc1234")
    assert [row["key"] for row in found] == ["ui:1"]


def test_integrity_check_flags_orphans_stale_states_and_missing_states():
    model = {"items": [
        {"key": "ui:1", "status": "done", "verification": "legacy"},
        {"key": "ui:2", "status": "done", "verification": ""},  # done without a state
        {"key": "ui:3", "status": "doing", "verification": "verified"},  # a state on an open task
        {"key": "ui:4", "status": "planned", "verification": ""},
    ]}
    entries = {"ui:9": {"state": "legacy"}}
    errors = check_plans.validate_verification(model, entries, commit_check=lambda _s: True)
    assert "verification for a missing task: ui:9" in errors
    assert "done/review task without a verification state: ui:2" in errors
    assert "verification state on a task that is not done or in review: ui:3" in errors
    assert not any("ui:1" in e or "ui:4" in e for e in errors)


def test_recorded_data_is_consistent_with_the_rules():
    """The real file: every verified task is done, carries evidence, and its commits exist."""
    model = json.loads((ROOT / "docs" / "plan-model.json").read_text(encoding="utf-8"))
    assert check_plans.validate_verification(model) == []
    states = {item["key"]: item["verification"] for item in model["items"] if item["status"] == "done"}
    assert states["ui:42"] == "verified" and states["ui:43"] == "verified"
    assert all(state in pv.STATE_KEYS for state in states.values())
