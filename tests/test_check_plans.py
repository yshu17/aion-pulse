"""Plan integrity catches data drift before publishing generated pages."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_plans  # noqa: E402


def sample():
    item = dict(key="map:1", plan="map", title="First", text="", status="todo",
                who="Claude", parent="", depends_on=[], added_at="", changed_at="")
    return {"items": [item], "latest": "map:1"}, [item.copy()], {"latest": "map:1", "known_keys": ["map:1"]}


def test_valid_model():
    model, source, metadata = sample()
    assert check_plans.validate_model(model, source, metadata) == []


def test_duplicate_missing_dependency_and_stale_status():
    model, source, metadata = sample()
    model["items"].append(model["items"][0].copy())
    model["items"][0]["depends_on"] = ["map:999"]
    model["items"][1]["status"] = "done"
    errors = check_plans.validate_model(model, source, metadata)
    assert any("duplicate ID" in e for e in errors)
    assert any("missing dependency" in e for e in errors)
    assert any("stale MASTER" in e for e in errors)


def test_invalid_date_and_missing_metadata():
    model, source, metadata = sample()
    model["items"][0]["added_at"] = "tomorrow"
    metadata["known_keys"] = []
    errors = check_plans.validate_model(model, source, metadata)
    assert any("invalid added_at" in e for e in errors)
    assert any("not registered" in e for e in errors)


def test_removed_id_and_dependency_cycle():
    model, source, metadata = sample()
    metadata["known_keys"].append("map:2")
    model["items"][0]["depends_on"] = ["map:1"]
    errors = check_plans.validate_model(model, source, metadata)
    assert any("disappeared" in e for e in errors)
    assert any("cycle" in e for e in errors)


def test_embedded_model_and_links(tmp_path):
    model, _, _ = sample()
    for name in check_plans.PAGES:
        (tmp_path / name).write_text(
            '<a href="gone.html">broken</a><script type="application/json" '
            'id="shared-plan-data">' + json.dumps(model) + '</script>', encoding="utf-8")
    assert any("broken local link" in e for e in check_plans.validate_pages(model, tmp_path))
    (tmp_path / "gone.html").write_text("ok", encoding="utf-8")
    assert check_plans.validate_pages(model, tmp_path) == []
