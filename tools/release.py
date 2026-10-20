"""Publish a Pulse release in one command: version, build, checksum, tag, GitHub release.

    python tools/release.py 1.2.0 --notes tmp/release_notes_1.2.0.md

What it does, in order (stops at the first failure, nothing is pushed before the build works):
  1. sets VERSION in watcher/version.py (commit «release X»), refuses if the tree has other changes;
  2. runs the stable PyInstaller build into build/release-X/Pulse.exe (the same options as build_exe.bat);
  3. adds the line «SHA256: <hex>» to the notes, so the self-update can check the download;
  4. pushes the branch, creates the tag vX and the GitHub release with Pulse.exe attached.
Needs git, gh (logged in) and PyInstaller. Run from the project folder.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "yshu17/aion-pulse"
VERSION_FILE = ROOT / "watcher" / "version.py"
ICON = ROOT / "client_extract" / "raw" / "aion_client_icon.ico"
EXCLUDES = ("numpy", "PIL.ImageQt", "PyQt5", "PyQt6", "PySide6", "matplotlib", "IPython")


def run(*args: str, **kwargs) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)}\n{result.stderr or result.stdout}")
    return result.stdout


def set_version(version: str) -> bool:
    text = VERSION_FILE.read_text(encoding="utf-8")
    new, count = re.subn(r'^VERSION = "[^"]*"', f'VERSION = "{version}"', text, flags=re.M)
    if count != 1:
        raise SystemExit("VERSION line not found in watcher/version.py")
    if new == text:
        return False
    VERSION_FILE.write_text(new, encoding="utf-8")
    return True


def build(version: str) -> Path:
    out = ROOT / "build" / f"release-{version}"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
               "--name", "Pulse", "--icon", str(ICON), "--distpath", str(out),
               "--workpath", str(ROOT / "build" / "release-work"), "--specpath", str(ROOT / "build" / "release-work"),
               "--add-data", f"{ROOT / 'data'};data"]
    for module in EXCLUDES:
        command += ["--exclude-module", module]
    run(*command, str(ROOT / "main.py"))
    exe = out / "Pulse.exe"
    if not exe.is_file():
        raise SystemExit(f"build produced no {exe}")
    return exe


def notes_with_checksum(notes: str, digest: str) -> str:
    notes = re.sub(r"^SHA256:.*\n?", "", notes, flags=re.M).rstrip()
    return f"{notes}\n\nSHA256: {digest}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", help="for example 1.2.0")
    parser.add_argument("--notes", required=True, type=Path, help="release description (markdown)")
    parser.add_argument("--skip-push", action="store_true", help="build and tag locally only")
    args = parser.parse_args()
    version = args.version.lstrip("vV")
    tag = f"v{version}"

    dirty = [line for line in run("git", "status", "--porcelain").splitlines()
             if line and not line.startswith("??") and "watcher/version.py" not in line]
    if dirty:
        raise SystemExit("commit or stash other changes first:\n" + "\n".join(dirty))
    if set_version(version):
        run("git", "add", "watcher/version.py")
        run("git", "commit", "-q", "-m", f"release {version}\n\nCo-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>")

    exe = build(version)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    notes = notes_with_checksum(args.notes.read_text(encoding="utf-8"), digest)
    notes_path = ROOT / "build" / f"release-{version}" / "notes.md"
    notes_path.write_text(notes, encoding="utf-8")
    print(f"built {exe} ({exe.stat().st_size:,} bytes)\nSHA256: {digest}")

    if args.skip_push:
        return 0
    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD").strip()
    run("git", "push", "origin", branch)
    run("git", "tag", "-a", tag, "-m", f"Pulse {version}")
    run("git", "push", "origin", tag)
    url = run("gh", "release", "create", tag, str(exe), "--repo", REPO, "--target", branch,
              "--title", f"Пульс {version}", "--notes-file", str(notes_path)).strip()
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
