"""The golden files (tests/golden/*.json) still match the Python core: the reference for the TypeScript port."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import golden_gen  # noqa: E402


def _stored(name: str):
    return json.loads((ROOT / "tests" / "golden" / f"{name}.json").read_text(encoding="utf-8"))["case"]


def test_settings_golden_matches_core():
    assert json.loads(json.dumps(golden_gen.settings_cases(), ensure_ascii=False)) == _stored("settings")


def test_loader_golden_matches_core():
    assert json.loads(json.dumps(golden_gen.loader_cases(), ensure_ascii=False)) == _stored("loaders")


def test_items_golden_matches_core():
    for name, build in (("browser", golden_gen.browser_cases), ("recipes", golden_gen.recipe_cases),
                        ("specs", golden_gen.spec_cases)):
        assert json.loads(json.dumps(build(), ensure_ascii=False)) == _stored(name), name


def test_chat_golden_matches_core():
    import golden_chat
    import golden_notify

    for name, case in {**golden_chat.all_cases(), **golden_notify.all_cases()}.items():
        assert json.loads(json.dumps(case, ensure_ascii=False)) == _stored(name), name


def test_schedule_golden_matches_core():
    import golden_schedule

    for name, case in golden_schedule.all_cases().items():
        assert json.loads(json.dumps(case, ensure_ascii=False)) == _stored(name), name
