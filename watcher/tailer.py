"""Read lines appended to a growing log file."""

import os


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
