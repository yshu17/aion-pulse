"""Where the program lives: its data folder, the folder of config.json, the local bestiary data.

Shell code (PyInstaller, sys.frozen): the portable core never computes these paths, it receives them.
"""

import sys
from pathlib import Path


def app_root() -> Path:
    """Folder of config.json. A one-folder build keeps it next to its folder, so a rebuild (which replaces the
    folder) never deletes the settings."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir.parent if (exe_dir / "_internal").is_dir() else exe_dir
    return Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """Folder holding data/: inside the PyInstaller bundle when frozen, else the project."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def local_bestiary_dir() -> Path | None:
    """Folder with the NPC / Bestiary data, which is not part of the program: `bestiary/` next to the exe
    (or next to the build folder, or `local/bestiary/` in the project). None when it is not there, so the tab is simply not shown."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        candidates = [base / "bestiary", base.parent / "bestiary", base / "local" / "bestiary"]  # parent: onedir build
    else:
        candidates = [Path(__file__).resolve().parent.parent / "local" / "bestiary"]
    return next((folder for folder in candidates if (folder / "npcs.sqlite").is_file()), None)
