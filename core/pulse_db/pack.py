"""The game database as a pack of its own (docs/ADR-003-pulse-db-replace.md, step 4): one zip with pulse.db, and the record
the program reads to know whether a newer pack exists and where it is.

    pack = make_pack(db, out_dir, tag="db-latest", repo="yshu17/aion-pulse", previous=None, now="2026-11-11T12:00:00Z")
    # -> {"schema": 9, "built": "...", "content": sha256 of pulse.db, "sha256": sha256 of the zip, "size": zip bytes, "url": ..., "name": ...}

The record (db_pack.json) goes beside the zip into the release the program asks (``DB_MANIFEST`` of launcher/src-tauri/src/lib.rs) and
into data/ (the program's own copy: which pack the bundled pulse.db is). The zip is the same bytes for the same pulse.db (fixed
timestamps), so a pack that is already built stays: ``previous`` with the same content keeps its built time and its zip.
Pure apart from the files it is given: no network, no clock of its own.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # zip entries carry no real time: the same database gives the same zip


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema_of(db: Path) -> int:
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        connection.close()


def _zip(db: Path, target: Path) -> None:
    info = zipfile.ZipInfo("pulse.db", FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive, db.open("rb") as source:
        with archive.open(info, "w") as out:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                out.write(chunk)


def make_pack(db: Path, out_dir: Path, tag: str, repo: str, previous: dict | None, now: str) -> dict:
    """The record of the pack of `db`; its zip is written to `out_dir` unless `previous` already describes the same content."""
    content = _sha256(db)
    out_dir.mkdir(parents=True, exist_ok=True)
    if previous and previous.get("content") == content and (out_dir / previous.get("name", "")).is_file():
        return {**previous, "url": f"https://github.com/{repo}/releases/download/{tag}/{previous['name']}"}
    temp = out_dir / "pulse-db-new.zip"
    _zip(db, temp)
    zip_sha = _sha256(temp)
    name = f"pulse-db-{zip_sha[:12]}.zip"
    temp.replace(out_dir / name)
    for old in out_dir.glob("pulse-db-*.zip"):  # an older pack is not kept: the folder holds what is to be uploaded
        if old.name != name:
            old.unlink()
    return {"schema": schema_of(db), "built": now, "content": content, "sha256": zip_sha, "size": (out_dir / name).stat().st_size,
            "name": name, "url": f"https://github.com/{repo}/releases/download/{tag}/{name}"}


def write_record(record: dict, *paths: Path) -> None:
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    for path in paths:
        path.write_text(text, encoding="utf-8")
