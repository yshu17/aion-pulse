"""Check a built pulse-core.exe (or `python -m core`) with real JSON requests, the way the launcher talks to it.

    python tools/check_core_exe.py build/core/pulse-core.exe data
    python tools/check_core_exe.py --python data          # the same checks against `python -m core`

Exit code 0 when every answer is right; the failing request is printed otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE = "2026.10.20 18:00:00 : [3.Поиск группы] [charname:A;1 1 1]: wts [Кираса Рудры] у [pos:Место;220070000 2010.1 1315.8 0.0 0]"


def requests(data_dir: str) -> list[tuple[str, dict, object]]:
    """(method, params, check of the result)."""
    return [
        ("core.version", {}, lambda r: r["version"] and "session.process" in r["methods"]),
        ("data.open", {"data_dir": data_dir}, lambda r: r["zones"] > 0 and r["items"] > 0),
        ("chat.parse", {"line": LINE}, lambda r: r["nick"] == "A" and "Келькмарос" in r["text"]),
        ("session.configure", {"keywords": ["wts"], "alert_mode": "nag", "cooldown_sec": 0}, lambda r: r["ok"]),
        ("session.process", {"lines": [LINE], "now": 1}, lambda r: r["entries"][0]["alert_id"] == 1 and r["places"]),
        ("session.accept", {"alert_id": 1}, lambda r: r["accepted"] == [1]),
        ("map.search", {"map_id": "220070000", "query": "торговец"}, lambda r: r and r[0]["x"] > 0),
        ("schedule.next", {"now": "2026-10-14T20:30:00", "limit": 2}, lambda r: len(r) == 2),
        ("items.list", {"query": "кираса рудры"}, lambda r: r["matches"]),
        ("nope", {}, None),  # an unknown method is an error answer, the process keeps running
        ("core.version", {}, lambda r: r["version"]),
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    command = [sys.executable, "-m", "core"] if argv[1] == "--python" else [argv[1]]
    checks = requests(str(Path(argv[2]).resolve()))
    payload = "".join(json.dumps({"id": i, "method": m, "params": p}, ensure_ascii=False) + "\n"
                      for i, (m, p, _c) in enumerate(checks)) + "\n"
    done = subprocess.run(command, input=payload, capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          timeout=120)
    answers = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    if done.returncode != 0 or len(answers) != len(checks):
        print(f"exit {done.returncode}, {len(answers)} answers of {len(checks)}\n{done.stderr[-2000:]}")
        return 1
    for (method, _params, check), answer in zip(checks, answers):
        ok = "error" in answer if check is None else "result" in answer and check(answer["result"])
        if not ok:
            print(f"FAIL {method}: {json.dumps(answer, ensure_ascii=False)[:400]}")
            return 1
    print(f"ok: {len(checks)} requests answered by {' '.join(command)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
