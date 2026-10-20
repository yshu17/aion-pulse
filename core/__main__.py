"""`python -m core`: the core API over stdin / stdout, one JSON request per line, one JSON answer per line.

An empty line or the end of input stops it. The launcher keeps one process and sends requests (core/API.md).
"""

import sys

from core.api import CoreApi


def main() -> int:
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")
    api = CoreApi()
    for line in sys.stdin:
        if not line.strip():
            break
        sys.stdout.write(api.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
