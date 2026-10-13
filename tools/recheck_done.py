"""Close one UI/UX task after the skill-based re-check of 13.10.2026 (user decision).

    python tools/recheck_done.py N "verdict" BEFORE AFTER skill1,skill2 [--result "short result"] [--no-shots "why"]

Section 9 of UI_UX_IMPROVEMENT_PLAN.md: «- [?] **N** …» becomes «- [x] **N** … Повторная проверка 13.10: verdict.»;
docs/plan-evidence.json gets the task with the pictures from docs/evidence/ui-N/ and the skills really invoked.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "UI_UX_IMPROVEMENT_PLAN.md"
EVIDENCE = ROOT / "docs" / "plan-evidence.json"


def close_in_plan(text: str, number: int, verdict: str) -> str:
    pattern = re.compile(rf"^- \[\?\] \*\*{number}\*\* — (.*?) \*\*Повторная проверка скиллами \(13\.10\): [^*]+\.\*\*$", re.M)
    match = pattern.search(text)
    if not match:
        raise SystemExit(f"ui:{number}: no reopened line in section 9")
    return text[:match.start()] + f"- [x] **{number}** — {match.group(1)} **Повторная проверка 13.10: {verdict}**" + text[match.end():]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("number", type=int)
    parser.add_argument("verdict")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("skills")
    parser.add_argument("--result", default="")
    parser.add_argument("--no-shots", default="")
    args = parser.parse_args()
    PLAN.write_text(close_in_plan(PLAN.read_text(encoding="utf-8"), args.number, args.verdict), encoding="utf-8")
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    entry = {"result": args.result or args.verdict, "skills_used": args.skills.split(","),
             "skills_note": "повторная проверка 13.10 скиллами — " + args.verdict}
    if args.no_shots:
        entry.update({"shots": False, "no_shots": args.no_shots})
    else:
        entry.update({"before": args.before, "after": args.after})
    data["tasks"][f"ui:{args.number}"] = entry
    EVIDENCE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ui:{args.number} closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
