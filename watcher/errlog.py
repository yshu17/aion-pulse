"""errors.log next to config.json: the traceback of an error the window only shows as one line."""

import traceback
from datetime import datetime
from pathlib import Path

MAX_BYTES = 256 * 1024  # over this, the older half is cut away


def log_exception(path: Path, where: str, previous: str = "") -> str:
    """Append the current exception with its traceback. Returns its one-line text (for `previous`).

    An error identical to the previous one is not written again, so a failure on every poll
    fills the file once, not every 500 ms.
    """
    text = traceback.format_exc().rstrip()
    summary = text.splitlines()[-1] if text else where
    if summary == previous:
        return summary
    try:
        if path.exists() and path.stat().st_size > MAX_BYTES:
            keep = path.read_bytes()[-MAX_BYTES // 2:]
            path.write_bytes(keep[keep.find(b"\n") + 1:] if b"\n" in keep else keep)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} {where}\n{text}\n")
    except OSError:
        pass  # a log that cannot be written must not stop the watcher
    return summary
