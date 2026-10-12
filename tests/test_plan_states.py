"""The one vocabulary of statuses and priorities: legacy values, the checkbox rule, progress, contrast."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import plan_states as ps  # noqa: E402
import plan_verification as pv  # noqa: E402


def test_legacy_and_unknown_values_never_become_done():
    assert ps.normalize_status("todo") == "planned"
    assert ps.normalize_status("") == "planned" and ps.normalize_status(None) == "planned"
    assert ps.normalize_status("whatever") == "planned"
    assert ps.normalize_status("done") == "done" and ps.normalize_status("doing") == "doing"
    assert ps.native_status("review") == "todo" and ps.native_status("done") == "done"  # the old pages know three values


def test_priorities_map_and_empty_stays_empty():
    assert [ps.normalize_priority(p) for p in ("P0", "P1", "P2", "P3")] == ["Critical", "High", "Medium", "Low"]
    assert ps.normalize_priority("") == "" and ps.normalize_priority(None) == "" and ps.normalize_priority("P9") == ""
    assert ps.normalize_priority("High") == "High"
    assert ps.priority_label("") == "Не определён" and ps.priority_label("Low") == "Low"


def test_checkbox_rule_done_by_tick_review_by_untick():
    assert ps.status_after_checkbox("planned", True) == "done"
    assert ps.status_after_checkbox("doing", True) == "done"
    assert ps.status_after_checkbox("done", False) == "review"  # unticking is not «not started»
    assert ps.status_after_checkbox("doing", False) == "doing"  # unticking an open task changes nothing
    assert ps.status_after_checkbox("review", False) == "review"


def test_progress_excludes_cancelled_and_counts_each_task_once():
    statuses = ["done", "done", "doing", "planned", "blocked", "review", "cancelled", "research", "todo"]
    p = ps.progress(statuses)
    assert p["total"] == 8 and p["done"] == 2 and p["percent"] == 25  # cancelled leaves the total
    assert p["active"] == 3 and p["blocked"] == 1  # doing + research + review
    assert p["by_status"]["cancelled"] == 1 and p["by_status"]["planned"] == 2  # legacy todo counted as planned
    assert ps.progress([])["percent"] == 0
    assert ps.progress(["cancelled"])["total"] == 0


def test_the_vocabulary_has_the_eight_statuses_in_the_agreed_order():
    assert ps.STATE_KEYS == ["planned", "research", "doing", "blocked", "review", "done", "deferred", "cancelled"]
    assert ps.PRIORITIES == ["Critical", "High", "Medium", "Low"]


def luminance(hex_color: str) -> float:
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


CARD = "#1c1e24"  # the card ground in tools/plan_shared.py
SELECT = "#262931"  # the status list ground
COLOURS = [(k, c) for k, _l, c in ps.STATES] + [(f"verification {k}", c) for k, _l, c, _m in pv.STATES]


@pytest.mark.parametrize("name,colour", COLOURS, ids=[n for n, _ in COLOURS])
def test_status_and_verification_text_colours_meet_aa_on_both_grounds(name, colour):
    for ground in (CARD, SELECT):
        assert contrast(colour, ground) >= 4.5, f"{name} {colour} on {ground}: {contrast(colour, ground):.2f}"
