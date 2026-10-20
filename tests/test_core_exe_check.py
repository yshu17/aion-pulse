import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_exe_self_check_passes_against_python_m_core():
    """build_core.bat runs the same check against pulse-core.exe; here it runs against `python -m core`."""
    done = subprocess.run([sys.executable, "tools/check_core_exe.py", "--python", "data"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.startswith("ok: 11 requests")
