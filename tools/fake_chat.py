"""Append a fake «Поиск группы» line to a log file for manual testing.

Never point it at the real game Chat.log.
Usage: python tools/fake_chat.py <log path> <text> [nick]
"""

import sys
import time


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path, text = sys.argv[1], sys.argv[2]
    nick = sys.argv[3] if len(sys.argv) > 3 else "Tester"
    stamp = time.strftime("%Y.%m.%d %H:%M:%S")
    line = f"{stamp} : [3.Поиск группы] [charname:{nick};1.0000 0.6941 0.6941]: {text} \r\n"
    with open(path, "ab") as f:
        f.write(line.encode("cp1251", errors="replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
