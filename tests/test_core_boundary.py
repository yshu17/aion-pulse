"""ADR-001: the core package stays free of Tk, of the program and of Windows-only shell code.

Core = `core/<group>/<module>.py`, the logic the future launcher needs (docs/ADR-001-core-package.md, section 11).
It imports the standard library and other `core` modules only; names and paths come in as parameters. The program
imports it as `core.<group>.<module>`; the old `watcher.<module>` names are gone, and `core/` works copied alone.
"""

import ast
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_GROUPS = {
    "chat": ["tailer", "parser", "matcher", "series", "alerts", "categories"],
    "notify": ["notify_center", "alert_bridge", "notify_settings"],
    "schedule": ["reminders", "schedule_view", "schedule_custom", "schedule_update"],
    "bestiary": ["bestiary_labels", "bestiary_classify", "bestiary_store", "search_worker"],
    "map": ["poi", "zones"],
    "items": ["specs", "recipes", "catalog", "browser"],
    "settings": ["config"],
    "update": ["updater", "selfupdate"],
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


def test_the_program_keeps_no_copy_or_alias_of_a_core_module():
    left = [m for modules in CORE_GROUPS.values() for m in modules if (ROOT / "watcher" / f"{m}.py").exists()]
    assert not left


def test_core_works_copied_alone(tmp_path):
    """The launcher gets core/ only: every module imports in an isolated interpreter that sees just that copy."""
    shutil.copytree(ROOT / "core", tmp_path / "core", ignore=shutil.ignore_patterns("__pycache__"))
    modules = [f"core.{group}.{module}" for group, names in CORE_GROUPS.items() for module in names]
    code = "import importlib, sys\nsys.path.insert(0, '.')\n"  # -I: no project folder, no user site-packages
    code += "".join(f"importlib.import_module({name!r})\n" for name in modules)
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
