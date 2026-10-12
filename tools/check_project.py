"""Run the project's plan integrity check and complete existing pytest suite."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    temp = ROOT / "tmp"
    temp.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(TMP=str(temp), TEMP=str(temp), TMPDIR=str(temp))
    vendor = ROOT / "downloads" / "notifications_build" / "vendor"
    if vendor.is_dir():
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(vendor), env.get("PYTHONPATH", ""))))
    commands = ([sys.executable, str(ROOT / "tools" / "check_plans.py")],
                [sys.executable, "-m", "pytest", "-q", "--tb=short"])
    failed = False
    for command in commands:
        print("\n> " + " ".join(command), flush=True)
        failed |= subprocess.run(command, cwd=ROOT, env=env, check=False).returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
