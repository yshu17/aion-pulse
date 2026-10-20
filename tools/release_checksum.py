"""Print the SHA256 line for the release notes of a Pulse.exe (the self-update installs only with it).

    python tools/release_checksum.py build/release-1.2/Pulse.exe

Paste the printed line into the release description; watcher/selfupdate.py reads «SHA256: <hex>» from there.
"""

import hashlib
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
