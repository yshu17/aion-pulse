"""Golden results of core/update/selfupdate.py for the TypeScript port (tests/golden/update_self.json).

The download runs against a stand-in for urllib's answer (chunks and a Content-Length), so the checks — trusted
address, checksum present, size, SHA-256 — and the progress calls are recorded without a network. The file swap
(install, remove_old) belongs to the program shell and is not part of the TypeScript core.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from unittest import mock

PAYLOAD = bytes(range(256)) * 700 + b"Pulse"  # 179 205 bytes: three 64 KiB chunks
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class _Answer:
    def __init__(self, data: bytes, length: str | None):
        self._data, self.headers = data, ({"Content-Length": length} if length is not None else {})

    def read(self, size):
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def download_cases() -> list:
    from core.update import selfupdate

    url = "https://github.com/yshu17/aion-pulse/releases/download/v1/Pulse.exe"
    assets = [
        {"url": url, "size": len(PAYLOAD), "sha256": ""},
        {"url": "http://github.com/x/Pulse.exe", "size": 1, "sha256": SHA},
        {"url": "https://evil.example/Pulse.exe", "size": 1, "sha256": SHA},
        {"url": "https://github.com.evil.example/Pulse.exe", "size": 1, "sha256": SHA},
        {"url": "https://evil@github.com/Pulse.exe", "size": len(PAYLOAD), "sha256": SHA},
        {"url": "HTTPS://GitHub.com:443/Pulse.exe", "size": len(PAYLOAD), "sha256": SHA},
        {"url": "https://objects.githubusercontent.com/a/b", "size": len(PAYLOAD), "sha256": SHA},
        {"url": "https://release-assets.githubusercontent.com/a", "size": len(PAYLOAD) + 1, "sha256": SHA},
        {"url": url, "size": len(PAYLOAD), "sha256": "0" * 64},
        {"url": url, "size": 0, "sha256": SHA},
        {"url": url, "size": len(PAYLOAD), "sha256": SHA},
        {"url": "ftp://github.com/Pulse.exe", "size": 1, "sha256": SHA},
        {"url": "https:///Pulse.exe", "size": 1, "sha256": SHA},
    ]
    out = []
    tmp = Path(tempfile.mkdtemp())
    for i, asset in enumerate(assets):
        for length in (str(len(PAYLOAD)), None):
            progress = []
            dest = tmp / f"Pulse{i}.exe"
            with mock.patch("urllib.request.urlopen", lambda request, timeout: _Answer(PAYLOAD, length)):
                try:
                    selfupdate.download(asset, dest, lambda done, total: progress.append([done, total]))
                    result = {"ok": dest.read_bytes() == PAYLOAD}
                except ValueError as error:
                    result = {"error": str(error)}
            left = sorted(p.name for p in tmp.iterdir() if p.name.startswith(f"Pulse{i}."))
            out.append([asset, length, result, progress, left])
            for p in tmp.iterdir():
                p.unlink()
    return out


def all_cases() -> dict[str, dict]:
    from core.update.selfupdate import ASSET, HOSTS, OLD_SUFFIX, pick_asset

    sha = "AB" * 32
    bodies = [
        {"assets": [{"name": "Pulse.exe", "browser_download_url": "https://github.com/x", "size": 10}],
         "body": f"Что нового\nSHA256: {sha}\n"},
        {"assets": [{"name": "Pulse.exe", "browser_download_url": "https://github.com/x", "size": "12"}],
         "body": "sha256 = " + "c" * 64},
        {"assets": [{"name": "Pulse.exe", "browser_download_url": "https://github.com/x"}], "body": "SHA256=" + "d" * 63},
        {"assets": [{"name": "Pulse.exe", "browser_download_url": "https://github.com/x", "size": None}],
         "body": "SHA256:" + "e" * 64 + "f"},
        {"assets": [{"name": "pulse.exe", "browser_download_url": "https://github.com/x"}], "body": ""},
        {"assets": [{"name": "Pulse.exe", "browser_download_url": ""}, {"name": "Pulse.exe", "browser_download_url": "u2",
                                                                          "size": 3}], "body": None},
        {"assets": None}, {}, {"assets": [{"name": "Other.zip", "browser_download_url": "z"}]},
        {"assets": [{"name": "Pulse.exe", "browser_download_url": "u"}], "body": "SHA256 : " + "1" * 64 + "\nSHA256: " + "2" * 64},
    ]
    return {"update_self": {
        "consts": [ASSET, list(HOSTS), OLD_SUFFIX],
        "pick": [[json.dumps(b, ensure_ascii=False), pick_asset(json.dumps(b, ensure_ascii=False))] for b in bodies],
        "download": download_cases(),
        "payload": {"sha256": SHA, "size": len(PAYLOAD)},
    }}
