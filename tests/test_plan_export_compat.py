"""Old exports (with the `native` field) must restore statuses and history without the old native lists.

Stage 4 (removing the old lists) waits for the owner's decision. These tests fix what an old export must keep working:
the journal part carries statuses and history; the `native` part restores the old keys; backup and rollback read only the journal and the old keys.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import plan_shared  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "old_export_with_native.json"
SCRIPT = plan_shared.SCRIPT
PANEL = plan_shared.PANEL


def test_fixture_is_a_valid_old_export():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert isinstance(data["statuses"], dict) and isinstance(data["history"], list)
    assert set(data["native"]) <= {"aion-ui-ux-plan-status-v1", "aion-telegram-plan-status-v1", "aion-master-plan-filters-v1"}


def test_import_keeps_statuses_and_history_in_the_journal():
    # the journal part of an export is applied first and does not read the native part
    assert "ledger.statuses[key]=norm(s)" in SCRIPT
    assert "ledger.history.push(x)" in SCRIPT


def test_backup_and_rollback_do_not_need_the_removed_components():
    # the backup is the journal plus a copy of the old keys; no rendering function is called on the backup path
    snap = SCRIPT[SCRIPT.index("function snapshot()"):].split("\n", 1)[0]
    assert "ledger:" in snap and "native:readNative()" in snap
    restore = SCRIPT[SCRIPT.index("$('shared-restore').onclick"):].split("\n", 1)[0]
    for needle in ("renderTasks", "renderStages", "renderProgress", "list()", "#reset"):
        assert needle not in restore, needle


def test_old_keys_are_kept_for_compatibility():
    assert "const KEYS=['aion-ui-ux-plan-status-v1','aion-telegram-plan-status-v1','aion-master-plan-filters-v1']" in SCRIPT
    assert "removeItem(NATIVE_KEYS" not in SCRIPT


def _browser_or_skip():
    pw = pytest.importorskip("playwright.sync_api")
    return pw


@pytest.mark.parametrize("page_name", ["ui-ux-improvement-plan.html", "telegram-bridge-plan.html"])
def test_old_export_restores_marks_in_a_fresh_browser(page_name, tmp_path):
    """Real browser, fresh isolated context, file:// origin. No user data is touched."""
    pw = _browser_or_skip()
    from playwright.sync_api import sync_playwright
    url = (ROOT / "docs" / page_name).as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_context().new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.evaluate("localStorage.clear()")
            page.reload()
            page.evaluate("document.getElementById('shared-plan').open=true")
            page.set_input_files("#shared-file", str(FIXTURE))
            page.wait_for_timeout(400)
            ledger = json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')"))
            assert ledger["statuses"].get("ui:41") == "done"
            assert ledger["statuses"].get("tg:2.2") == "review"
            assert len([h for h in ledger["history"] if h["key"] == "ui:41"]) == 1
            # the native part restores the old key again (compatibility)
            ui_old = json.loads(page.evaluate("localStorage.getItem('aion-ui-ux-plan-status-v1')") or "{}")
            assert ui_old.get("40") == "doing"
            # re-import is idempotent for history
            page.set_input_files("#shared-file", str(FIXTURE))
            page.wait_for_timeout(400)
            ledger2 = json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')"))
            assert len(ledger2["history"]) == len(ledger["history"])
            # rollback returns the state before the last import
            page.click("#shared-restore")
            page.wait_for_timeout(300)
            assert errors == []
            browser.close()
    except Exception as exc:  # browser missing or not installed: report, do not fail the suite silently
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("chromium for playwright not installed")
        raise


def test_native_only_marks_enter_the_journal_in_a_browser(tmp_path):
    """UI45 requirement: a mark that exists only in the old export's native part goes into the journal (with history);
    a journal value that differs from the old list is NOT overwritten. Fresh isolated browser, file:// origin."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    url = (ROOT / "docs" / "ui-ux-improvement-plan.html").as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_context().new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.evaluate("localStorage.clear()")
            page.reload()
            page.evaluate("document.getElementById('shared-plan').open=true")
            page.set_input_files("#shared-file", str(FIXTURE))
            page.wait_for_timeout(400)
            ledger = json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')"))
            # native-only: ui:40 exists only in the native part of the export
            assert ledger["statuses"].get("ui:40") == "doing"
            origins = [h["origin"] for h in ledger["history"] if h["key"] == "ui:40"]
            assert origins == ["импорт старого экспорта (native)"]
            # conflict: the journal says review for tg:2.2, the native part says done - the journal keeps its value
            assert ledger["statuses"].get("tg:2.2") == "review"
            # the old keys are still written (compatibility, nothing is deleted)
            assert json.loads(page.evaluate("localStorage.getItem('aion-ui-ux-plan-status-v1')"))["40"] == "doing"
            # a second import adds nothing
            n = len(ledger["history"])
            page.set_input_files("#shared-file", str(FIXTURE))
            page.wait_for_timeout(400)
            ledger2 = json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')"))
            assert len(ledger2["history"]) == n
            # reload keeps the journal
            page.reload()
            page.wait_for_timeout(200)
            after = json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')"))
            assert after["statuses"].get("ui:40") == "doing"
            # rollback returns the journal to the state before the last import: one import, one rollback
            page.evaluate("localStorage.clear()")
            page.reload()
            page.evaluate("document.getElementById('shared-plan').open=true")
            page.set_input_files("#shared-file", str(FIXTURE))
            page.wait_for_timeout(400)
            assert "ui:40" in json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')"))["statuses"]
            page.click("#shared-restore")
            page.wait_for_timeout(300)
            rolled = json.loads(page.evaluate("localStorage.getItem('aion-shared-plan-ledger-v1')") or "{}")
            assert "ui:40" not in rolled.get("statuses", {})
            assert errors == []
            browser.close()
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("chromium for playwright not installed")
        raise
