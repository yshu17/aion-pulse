"""Before / after screenshots of the app for a task, taken from two commits (Windows, PrintWindow via ui_snapshots).

    python tools/evidence_shots.py KEY BEFORE_COMMIT AFTER_COMMIT SCENARIO WIDTHxHEIGHT [x0,y0,x1,y1]

Each commit is checked out into a detached worktree under tmp/evidence-wt; the current tools/ui_snapshots.py is copied
in and its worker renders SCENARIO at that size (the app code is the commit's own). The pictures land in
docs/evidence/<KEY with ':' as '-'>/before.png and after.png, cut to the given box when one is given.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WT = ROOT / "tmp" / "evidence-wt"
OUT = ROOT / "docs" / "evidence"


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def checkout(commit: str) -> None:
    if not WT.exists():
        git("worktree", "add", "--detach", str(WT), commit)
    else:
        git("checkout", "--detach", "--force", commit, cwd=WT)
    shutil.copy2(ROOT / "tools" / "ui_snapshots.py", WT / "tools" / "ui_snapshots.py")


def shot(commit: str, scenario: str, width: int, height: int, box: tuple[int, int, int, int] | None, dest: Path) -> None:
    checkout(commit)
    run_dir = ROOT / "tmp" / "evidence-run"
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    result = subprocess.run([sys.executable, "tools/ui_snapshots.py", "_worker", str(run_dir), scenario, str(width), str(height)],
                            cwd=WT, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise SystemExit(f"{commit} {scenario}: {result.stderr[-800:]}")
    image = Image.open(run_dir / "shots" / f"{width}x{height}_{scenario}.png")
    if box:
        image = image.crop(box)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, optimize=True)


def main(argv: list[str]) -> int:
    key, before, after, scenario, size = argv[:5]
    width, height = map(int, size.split("x"))
    box = tuple(map(int, argv[5].split(","))) if len(argv) > 5 else None
    folder = OUT / key.replace(":", "-")
    shot(before, scenario, width, height, box, folder / "before.png")
    shot(after, scenario, width, height, box, folder / "after.png")
    print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
