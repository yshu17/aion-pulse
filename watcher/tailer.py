"""Read lines appended to a growing log file."""

import os
import re
from datetime import datetime

_TIME = re.compile(rb"^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})")


def _line_time(line: bytes) -> datetime | None:
    match = _TIME.match(line)
    if match is None:
        return None
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return None


class LogTailer:
    def __init__(self, path: str, encoding: str = "cp1251") -> None:
        self.path = path
        self.encoding = encoding
        self._pos = 0
        self._buf = b""

    def start_at_end(self) -> None:
        """Skip everything already in the file."""
        self._pos = os.path.getsize(self.path)
        self._buf = b""

    def read_new_lines(self) -> list[str]:
        """Return complete lines appended since the last call.

        The file is opened per call so the game keeps full access to it.
        A file shorter than our position was recreated: read it from the start.
        """
        size = os.path.getsize(self.path)
        if size < self._pos:
            self._pos = 0
            self._buf = b""
        if size == self._pos:
            return []
        with open(self.path, "rb") as f:
            f.seek(self._pos)
            data = f.read(size - self._pos)
        self._pos += len(data)
        *lines, self._buf = (self._buf + data).split(b"\n")
        return [line.rstrip(b"\r").decode(self.encoding, errors="replace") for line in lines]

    def read_backlog(self, since: datetime, chunk_size: int = 256 * 1024) -> list[str]:
        """Return complete lines before the current position whose time is >= since.

        Reads backwards in chunks until a line older than `since` (or the file start)
        is reached, so a huge log costs only the bytes of the requested period.
        """
        end = self._pos
        start = end
        with open(self.path, "rb") as f:
            while start > 0:
                start = max(0, start - chunk_size)
                f.seek(start)
                lines = f.read(end - start).split(b"\n")
                if start > 0:
                    lines = lines[1:]  # first piece may be a partial line
                first = next((t for t in map(_line_time, lines) if t is not None), None)
                if first is not None and first < since:
                    break
            f.seek(start)
            lines = f.read(end - start).split(b"\n")
        if start > 0:
            lines = lines[1:]
        result = []
        for line in lines[:-1]:  # the piece after the last newline is not a complete line
            line = line.rstrip(b"\r")
            time = _line_time(line)
            if time is not None and time >= since:
                result.append(line.decode(self.encoding, errors="replace"))
        return result

