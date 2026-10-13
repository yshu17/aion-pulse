"""ADR-001 step 1: the core modules stay free of Tk and of the screens.

Core = modules that the future launcher needs. They may import the standard library and each other; `parser` may
read bundled data through `watcher.catalog` for now (ADR-001 moves that to parameters at step 2, the list below
shrinks then).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ["notify_center", "alert_bridge", "notify_settings", "tailer", "parser", "matcher", "series", "alerts"]
ALLOWED_WATCHER = {"notify_center", "alert_bridge", "notify_settings", "tailer", "parser", "matcher", "series",
                   "alerts", "catalog"}  # catalog: parser's data loader, removed at ADR-001 step 2


def imported_modules(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def test_core_modules_do_not_import_tkinter():
    for module in CORE:
        names = imported_modules(ROOT / "watcher" / f"{module}.py")
        assert not [n for n in names if n.split(".")[0] == "tkinter"], module


def test_core_modules_import_only_core_or_stdlib_from_watcher():
    for module in CORE:
        names = imported_modules(ROOT / "watcher" / f"{module}.py")
        local = [n.split(".")[1] for n in names if n.startswith("watcher.") and len(n.split(".")) > 1]
        extra = [name for name in local if name not in ALLOWED_WATCHER]
        assert not extra, f"{module} imports screen code: {extra}"
