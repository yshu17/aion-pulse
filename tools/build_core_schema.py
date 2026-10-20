"""Regenerate core/api.schema.json and core/api.d.ts from core/schema.py (run after changing a method of core/api.py).

    python tools/build_core_schema.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import __version__  # noqa: E402
from core.schema import write  # noqa: E402

if __name__ == "__main__":
    for path in write(ROOT / "core", __version__):
        print("written", path.relative_to(ROOT))
