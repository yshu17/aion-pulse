"""ADR-001 step 1: the core modules stay free of Tk, of the screens and of Windows-only shell code.

Core = modules that the future launcher needs (see docs/ADR-001-core-package.md, section 11 for the groups). They may
import the standard library and each other; `parser` may read bundled data through `watcher.catalog` for now
(ADR-001 moves that to parameters at step 2, then `catalog` leaves the allowed list).
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_GROUPS = {
    "chat": ["tailer", "parser", "matcher", "series", "alerts"],
    "notify": ["notify_center", "alert_bridge", "notify_settings"],
    "schedule": ["reminders", "schedule_view", "schedule_custom", "schedule_update"],
    "bestiary": ["bestiary_labels", "bestiary_classify", "bestiary_store", "search_worker"],
    "map": ["poi"],
    "items": ["specs", "recipes"],
    "telegram": ["tgbatch"],
}
CORE = [module for group in CORE_GROUPS.values() for module in group]
ALLOWED_WATCHER = set(CORE) | {"catalog"}  # catalog: parser's data loader, removed at ADR-001 step 2
FORBIDDEN_TOP = {"tkinter", "PIL", "ctypes", "winsound", "winreg"}  # screens and Windows-only shell stay outside


def imported_modules(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def test_core_modules_do_not_import_tk_or_windows_shell():
    for module in CORE:
        names = imported_modules(ROOT / "watcher" / f"{module}.py")
        assert not [n for n in names if n.split(".")[0] in FORBIDDEN_TOP], module


def test_core_modules_import_only_core_or_stdlib():
    for module in CORE:
        names = imported_modules(ROOT / "watcher" / f"{module}.py")
        local = [n.split(".")[1] for n in names if n.startswith("watcher.") and len(n.split(".")) > 1]
        extra = [name for name in local if name not in ALLOWED_WATCHER]
        assert not extra, f"{module} imports screen or shell code: {extra}"
        third = {n.split(".")[0] for n in names if not n.startswith("watcher")} - set(sys.stdlib_module_names)
        assert not third, f"{module} needs packages outside the standard library: {third}"
