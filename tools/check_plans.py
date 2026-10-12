"""Read-only integrity check for the five generated plan pages and their sources.

Run after rebuilding plans: ``python tools/check_plans.py``.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "tools"))
import plan_states  # noqa: E402

import build_master_plan  # noqa: E402
import build_feature_drafts  # noqa: E402
import plan_ai_tools  # noqa: E402
from plan_task_meta import load_task_meta  # noqa: E402

PAGES = ("index.html", "map-poi-plan.html", "schedule-notify-plan.html",
         "ui-ux-improvement-plan.html", "telegram-bridge-plan.html")
PAYLOAD = re.compile(r'<script type="application/json" id="shared-plan-data">(.*?)</script>', re.S)
VALID_STATUSES = set(plan_states.STATE_KEYS)  # one vocabulary: tools/plan_states.py
DATE_FORMAT = "%d.%m.%Y %H:%M"
DATE_ONLY = "%d.%m.%Y"  # the agreed date for old tasks (08.10.2026) has no time


def parse_date(value: str) -> datetime:
    """Accept «ДД.ММ.ГГГГ ЧЧ:ММ» and «ДД.ММ.ГГГГ» (the date only, for old tasks)."""
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        return datetime.strptime(value, DATE_ONLY)


def validate_model(model: dict, source: list[dict], metadata: dict) -> list[str]:
    """Return actionable errors; never alter a plan or infer completion from text."""
    errors: list[str] = []
    items = model.get("items", [])
    if not isinstance(items, list):
        return ["items is not a list"]
    keys = [item.get("key") for item in items]
    counts = Counter(keys)
    errors.extend(f"duplicate ID: {key}" for key, count in counts.items() if count > 1)
    source_by_key = {item["key"]: item for item in source}
    model_by_key = {item["key"]: item for item in items if item.get("key")}
    errors.extend(f"missing from MASTER: {key}" for key in source_by_key.keys() - model_by_key.keys())
    errors.extend(f"orphan in MASTER: {key}" for key in model_by_key.keys() - source_by_key.keys())
    for key in source_by_key.keys() & model_by_key.keys():
        a, b = source_by_key[key], model_by_key[key]
        for field in ("title", "text", "status", "who", "depends_on", "parent"):
            if a.get(field) != b.get(field):
                errors.append(f"stale MASTER {key}: {field}")
    known = set(keys)
    for item in items:
        key = item.get("key", "<missing>")
        if item.get("status") not in VALID_STATUSES:
            errors.append(f"invalid status: {key}")
        if not item.get("title", "").strip():
            errors.append(f"empty title: {key}")
        parent = item.get("parent")
        if parent and parent not in known:
            errors.append(f"missing parent: {key} -> {parent}")
        for dep in item.get("depends_on", []):
            if dep not in known:
                errors.append(f"missing dependency: {key} -> {dep}")
            if dep == key:
                errors.append(f"self dependency: {key}")
        dates = {}
        for field in ("added_at", "changed_at"):
            value = item.get(field)
            if value:
                try:
                    dates[field] = parse_date(value)
                except ValueError:
                    errors.append(f"invalid {field}: {key}: {value}")
        for field, value in dates.items():
            if value > datetime.now():
                errors.append(f"future {field}: {key}")
        if len(dates) == 2 and dates["changed_at"] < dates["added_at"]:
            errors.append(f"change predates addition: {key}")
    latest = model.get("latest")
    if latest and latest not in known:
        errors.append(f"latest points to missing task: {latest}")
    if latest != metadata.get("latest"):
        errors.append("latest differs from metadata")
    missing_metadata = known - set(metadata.get("known_keys", []))
    errors.extend(f"ID not registered in metadata: {key}" for key in sorted(missing_metadata))
    removed = set(metadata.get("known_keys", [])) - known
    errors.extend(f"registered ID disappeared from sources: {key}" for key in sorted(removed))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            errors.append(f"dependency cycle at {key}")
            return
        if key in visited or key not in model_by_key:
            return
        visiting.add(key)
        for dep in model_by_key[key].get("depends_on", []):
            visit(dep)
        visiting.remove(key)
        visited.add(key)

    for key in known:
        visit(key)
    titles = Counter((item.get("plan"), re.sub(r"\s+", " ", item.get("title", "").casefold()).strip())
                     for item in items)
    errors.extend(f"repeated title in {plan}: {title}" for (plan, title), count in titles.items() if count > 1)
    return errors


def validate_pages(model: dict, docs: Path = DOCS) -> list[str]:
    errors: list[str] = []
    for name in PAGES:
        path = docs / name
        if not path.is_file():
            errors.append(f"missing page: {name}")
            continue
        html = path.read_text(encoding="utf-8")
        payloads = PAYLOAD.findall(html)
        if len(payloads) != 1:
            errors.append(f"{name}: expected one embedded model, found {len(payloads)}")
        else:
            try:
                if json.loads(payloads[0]) != model:
                    errors.append(f"{name}: embedded model is stale")
            except json.JSONDecodeError:
                errors.append(f"{name}: invalid embedded model")
        # The five navigation targets must resolve within docs/. Dynamic task
        # anchors are checked by the browser; task cards are created at runtime.
        for href in re.findall(r'href="([^"]+\.html)(?:#[^"]*)?"', html):
            if "${" not in href and not (docs / href).is_file():
                errors.append(f"{name}: broken local link {href}")
    return errors


def main() -> int:
    model = json.loads((DOCS / "plan-model.json").read_text(encoding="utf-8"))
    source = build_master_plan.collect()
    # the same normalisation as the master build: the model holds the vocabulary values, the sources hold the legacy ones
    for item in source:
        item["status"] = plan_states.normalize_status(item["status"])
        item["priority"] = plan_states.normalize_priority(item["priority"])
    errors = validate_model(model, source, load_task_meta()) + validate_pages(model)
    draft = build_feature_drafts.load()
    all_stage_ids = [stage["id"] for plan in draft["plans"] for stage in plan["stages"]]
    stage_ids = set(all_stage_ids)
    if len(stage_ids) != len(all_stage_ids):
        errors.append("duplicate DRAFT stage ID")
    numbers = [plan["number"] for plan in draft["plans"]]
    if sorted(numbers) != list(range(1, 7)):
        errors.append("DRAFT plan numbers must be 1–6")
    try:
        datetime.strptime(draft["added_at"], DATE_FORMAT)
    except ValueError:
        errors.append("invalid DRAFT added_at")
    ids = {plan["id"] for plan in draft["plans"]} | stage_ids
    for plan in draft["plans"]:
        if not all(stage["id"].startswith(plan["id"] + ".") for stage in plan["stages"]):
            errors.append(f"draft {plan['id']}: stage ID prefix mismatch")
        if plan.get("parent") and plan["parent"] not in ids:
            errors.append(f"draft {plan['id']}: missing parent")
        for dependency in plan.get("depends_on", []):
            if dependency not in ids:
                errors.append(f"draft {plan['id']}: missing dependency {dependency}")
        for stage in plan["stages"]:
            for dependency in stage["depends_on"]:
                if dependency not in ids:
                    errors.append(f"draft {stage['id']}: missing dependency {dependency}")
        page = DOCS / build_feature_drafts.filename(plan)
        if not page.is_file() or 'Для дальнейшей проработки Claude Code' not in page.read_text(encoding="utf-8"):
            errors.append(f"missing draft page or Claude section: {page.name}")
    hub = DOCS / build_feature_drafts.HUB
    if not hub.is_file():
        errors.append("missing draft hub")
    for page in [hub, *(DOCS / build_feature_drafts.filename(plan) for plan in draft["plans"])]:
        if not page.is_file():
            continue
        for href in re.findall(r'href="([^"]+\.html)(?:#[^"]*)?"', page.read_text(encoding="utf-8")):
            if not (DOCS / href).is_file():
                errors.append(f"{page.name}: broken local link {href}")
    ai_data = plan_ai_tools.load()
    stage_keys = {f"draft:{sid}" for sid in stage_ids}
    open_keys = {item["key"] for item in source if item["status"] != "done"} | stage_keys
    ai_errors, ai_warnings = plan_ai_tools.validate(ai_data, {item["key"] for item in source} | stage_keys, open_keys)
    errors.extend(ai_errors)
    if any(not item.get("ai") for item in model["items"]):
        errors.append("MASTER items without ai block — rebuild plans")
    for warning in ai_warnings:
        print("WARNING:", warning)
    master = (DOCS / "index.html").read_text(encoding="utf-8")
    for plan in draft["plans"]:
        if build_feature_drafts.filename(plan) not in master:
            errors.append(f"MASTER missing draft link: {plan['id']}")
    if errors:
        for error in errors:
            print("ERROR:", error)
        print(f"Plan integrity: {len(errors)} error(s)")
        return 1
    recommended = sum(1 for key in ai_data["tasks"])
    print(f"Plan integrity: OK, {len(model['items'])} tasks, {len(PAGES)} core pages, {len(draft['plans'])} DRAFT plans, "
          f"{recommended} AI recommendations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
