"""ADR-001: the core package stays free of Tk, of the program and of Windows-only shell code.

Core = `core/<group>/<module>.py`, the logic the future launcher needs (docs/ADR-001-core-package.md, section 11).
It imports the standard library and other `core` modules only; names and paths come in as parameters. The old names
`watcher.<module>` are aliases of the same module objects, so existing imports and monkeypatching keep working.
"""

import ast
import importlib
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
FORBIDDEN_TOP = {"tkinter", "PIL", "ctypes", "winsound", "winreg", "watcher"}


def imported_modules(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def core_files() -> list[Path]:
    return sorted((ROOT / "core").rglob("*.py"))


def test_every_core_module_is_in_its_group():
    found = {(p.parent.name, p.stem) for p in core_files() if p.stem != "__init__"}
    assert found == {(group, module) for group, modules in CORE_GROUPS.items() for module in modules}


def test_core_imports_only_the_standard_library_and_core():
    for path in core_files():
        names = imported_modules(path)
        assert not [n for n in names if n.split(".")[0] in FORBIDDEN_TOP], path
        third = {n.split(".")[0] for n in names} - set(sys.stdlib_module_names) - {"core", "__future__"}
        assert not third, f"{path} needs packages outside the standard library: {third}"


def test_old_watcher_names_are_the_same_module_objects():
    for group, modules in CORE_GROUPS.items():
        for module in modules:
            assert importlib.import_module(f"watcher.{module}") is importlib.import_module(f"core.{group}.{module}")
