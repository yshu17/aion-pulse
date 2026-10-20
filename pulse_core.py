"""Entry point of pulse-core.exe: the portable core alone, JSON over stdin / stdout (core/API.md).

Built by build_core.bat. The launcher starts it once and keeps it; Pulse itself does not use it.
"""

import sys

from core.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
