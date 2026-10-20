"""Install a newer Pulse.exe from its GitHub release. Tk-free: the caller asks the user and shows the progress.

Steps: pick the Pulse.exe asset of the release, download it over HTTPS to a temporary file, check its size and its
SHA-256 against the value in the release notes (a line «SHA256: <64 hex>»), then swap the files. Windows lets a running
exe be renamed but not overwritten, so the running copy becomes Pulse.exe.old, the new one takes its name, and the
program starts again. The old copy is removed at the next start.

Nothing is installed without a checksum: a release without «SHA256:» in its notes is offered as a page, not an install.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

ASSET = "Pulse.exe"
HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
OLD_SUFFIX = ".old"
SHA_LINE = re.compile(r"SHA256\s*[:=]\s*([0-9a-fA-F]{64})")


def pick_asset(release_json: str) -> dict | None:
    """The Pulse.exe of a release: {url, size, sha256}; None when there is no such asset."""
    data = json.loads(release_json)
    for asset in data.get("assets") or []:
        if asset.get("name") == ASSET and asset.get("browser_download_url"):
            found = SHA_LINE.search(data.get("body") or "")
            return {"url": asset["browser_download_url"], "size": int(asset.get("size") or 0),
                    "sha256": found.group(1).lower() if found else ""}
    return None


def can_install(current: Path) -> bool:
    """Only the stable exe built from a frozen program: never the source tree or the local test build."""
    return bool(getattr(sys, "frozen", False)) and current.name.lower() == ASSET.lower()


def download(asset: dict, dest: Path, progress: Callable[[int, int], None] = lambda done, total: None,
             timeout: float = 30) -> Path:
    """Fetch the asset into dest. Raises ValueError (untrusted address, no checksum, wrong size or hash)."""
    if not asset.get("sha256"):
        raise ValueError("no SHA256 in the release notes")
    parts = urlparse(asset["url"])
    if parts.scheme != "https" or parts.hostname not in HOSTS:
        raise ValueError("update from an untrusted address")
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    request = urllib.request.Request(asset["url"], headers={"User-Agent": "Pulse"})
    with urllib.request.urlopen(request, timeout=timeout) as response, part.open("wb") as out:
        total = int(response.headers.get("Content-Length") or asset.get("size") or 0)
        done = 0
        while chunk := response.read(64 * 1024):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            progress(done, total)
    if asset.get("size") and part.stat().st_size != asset["size"]:
        part.unlink(missing_ok=True)
        raise ValueError("download is incomplete")
    if digest.hexdigest() != asset["sha256"]:
        part.unlink(missing_ok=True)
        raise ValueError("SHA-256 does not match the release notes")
    os.replace(part, dest)
    return dest


def install(current: Path, new: Path, launch: Callable[[list[str], str], object] | None = None) -> None:
    """Put new in place of current and start it. The running copy is kept as current.name + .old."""
    old = current.with_name(current.name + OLD_SUFFIX)
    old.unlink(missing_ok=True)
    os.replace(current, old)  # the running exe can be renamed on Windows, not overwritten
    try:
        os.replace(new, current)
    except OSError:
        os.replace(old, current)  # put the working copy back
        raise
    start = launch or (lambda cmd, cwd: subprocess.Popen(cmd, cwd=cwd))
    start([str(current)], str(current.parent))


def remove_old(current: Path) -> None:
    """At start: the copy the last update replaced is no longer needed (it may still be locked a moment)."""
    try:
        current.with_name(current.name + OLD_SUFFIX).unlink(missing_ok=True)
    except OSError:
        pass
