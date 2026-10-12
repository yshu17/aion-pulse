"""Verification of finished tasks, kept apart from the task status (docs/plan-verification.json).

The status says what the task is (planned, doing, done ...). The verification says how sure we are that "done" is true:

  verified  confirmed by checks: at least one piece of evidence (a commit that exists in git, a test run, a report)
  legacy    marked done earlier; no confirmation under the current rules was found
  pending   waiting for a check (every task in status "review", or an entry set by hand)

Rules:
  * Nothing is verified without evidence. `set ... verified` refuses an empty evidence list and checks that a commit exists.
  * A done task with no entry is legacy. The default is never verified.
  * Only done and review tasks carry a state; other tasks show none.
  * The status and the verification are stored in different places and never overwrite each other.

Commands (read-only unless noted):
  python tools/plan_verification.py list                     counts and the verified tasks
  python tools/plan_verification.py candidates               done tasks whose plan note names a real commit and a check:
                                                              proposals only, nothing is assigned
  python tools/plan_verification.py set KEY STATE [--evidence kind:ref ...] [--by NAME]   writes the file
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "plan-verification.json"

STATES = [
    ("verified", "Подтверждено проверками", "#5fd38d", "✓"),
    ("legacy", "Ранее отмечено, без нового подтверждения", "#8c919c", "ранее"),
    ("pending", "Ожидает проверки", "#f5b544", "ждёт"),
]
STATE_KEYS = [key for key, *_ in STATES]
EVIDENCE_KINDS = {"commit", "test", "snapshot", "report"}


def load(path: Path = PATH) -> dict:
    if not path.is_file():
        return {"schema_version": 1, "tasks": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("tasks"), dict):
        raise ValueError(f"Invalid verification file {path}")
    return data


def save(data: dict, path: Path = PATH) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve(status: str, entry: dict | None) -> tuple[str, list[dict]]:
    """The verification state shown for a task, and its evidence. Not applicable states are empty strings."""
    if status == "review":
        return "pending", (entry or {}).get("evidence", [])
    if status != "done":
        return "", []
    state = (entry or {}).get("state")
    if state in STATE_KEYS:
        return state, (entry or {}).get("evidence", [])
    return "legacy", []


def summary(items: list[dict]) -> dict:
    """Counts for done tasks, apart from the progress of the work itself."""
    done = [i for i in items if i.get("status") == "done"]
    return {
        "done": len(done),
        "verified": sum(1 for i in done if i.get("verification") == "verified"),
        "legacy": sum(1 for i in done if i.get("verification") == "legacy"),
        "pending": sum(1 for i in done if i.get("verification") == "pending"),
        "waiting": sum(1 for i in items if i.get("status") == "review"),
    }


def commit_exists(sha: str) -> bool:
    try:
        return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT,
                              capture_output=True).returncode == 0
    except OSError:
        return False


def validate_entry(key: str, entry: dict, status: str | None, commit_check=commit_exists) -> list[str]:
    errors = []
    state = entry.get("state")
    if state not in STATE_KEYS:
        return [f"{key}: unknown verification state {state!r}"]
    if state == "verified":
        if status != "done":
            errors.append(f"{key}: verified but the task is not done")
        evidence = entry.get("evidence") or []
        if not evidence:
            errors.append(f"{key}: verified without evidence")
        for item in evidence:
            if item.get("kind") not in EVIDENCE_KINDS or not item.get("ref"):
                errors.append(f"{key}: bad evidence {item!r}")
            elif item["kind"] == "commit" and not commit_check(item["ref"]):
                errors.append(f"{key}: commit {item['ref']} not found in git")
    return errors


SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
CHECK_WORDS = re.compile(r"тест|снимк|проверен|проверк|pytest", re.I)


def candidates(items: list[dict], commit_check=commit_exists) -> list[dict]:
    """Done tasks whose plan note names a commit that exists and a check. A proposal for a person to review."""
    found = []
    for item in items:
        if item.get("status") != "done" or item.get("verification") == "verified":
            continue
        note = f"{item.get('note', '')} {item.get('text', '')}"
        shas = [s for s in dict.fromkeys(SHA.findall(note)) if any(c.isalpha() for c in s) and commit_check(s)]
        if shas and CHECK_WORDS.search(note):
            found.append({"key": item["key"], "title": item["title"], "commits": shas})
    return found


def set_state(key: str, state: str, evidence: list[str], by: str, path: Path = PATH) -> dict:
    if state not in STATE_KEYS:
        raise SystemExit(f"state must be one of {STATE_KEYS}")
    parsed = []
    for raw in evidence:
        kind, _sep, ref = raw.partition(":")
        parsed.append({"kind": kind, "ref": ref})
    entry = {"state": state, "evidence": parsed, "at": date.today().strftime("%d.%m.%Y"), "by": by}
    errors = validate_entry(key, entry, "done" if state == "verified" else None)
    errors = [e for e in errors if "not done" not in e]  # the task status is checked by check_plans
    if errors:
        raise SystemExit("; ".join(errors))
    data = load(path)
    data["tasks"][key] = entry
    save(data, path)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("candidates")
    setter = sub.add_parser("set")
    setter.add_argument("key")
    setter.add_argument("state", choices=STATE_KEYS)
    setter.add_argument("--evidence", action="append", default=[], help="kind:ref, e.g. commit:abc1234")
    setter.add_argument("--by", default="Claude Code")
    args = parser.parse_args(argv)
    if args.command == "set":
        print(json.dumps(set_state(args.key, args.state, args.evidence, args.by), ensure_ascii=False, indent=2))
        return 0
    model = json.loads((ROOT / "docs" / "plan-model.json").read_text(encoding="utf-8"))
    if args.command == "list":
        print(summary(model["items"]))
        for item in model["items"]:
            if item.get("verification") == "verified":
                print(" verified:", item["key"], [e["ref"] for e in item.get("verification_evidence", [])])
        return 0
    for row in candidates(model["items"]):
        print(f"{row['key']}: {row['title'][:60]} | commits {', '.join(row['commits'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
