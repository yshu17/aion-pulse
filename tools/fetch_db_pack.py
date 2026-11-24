"""Put the published game database into data/: for a build on a device that has no game client files.

    python tools/fetch_db_pack.py [--tag db-latest] [--repo yshu17/aion-pulse]

tools/build_pulse_db.py needs client_extract/ and downloads/, which only the machine with the game client has; a build there
without them gives a poorer pulse.db. This script takes the pack that is on the release instead (db_pack.json and the zip it
names), checks the size, the sha256 of the zip, the sha256 of pulse.db and the schema, then writes data/pulse.db and
data/db_pack.json (the record of the pack the bundled pulse.db is). Used by tools/build_pulse_plus.ps1 -FetchDb. Nothing is
uploaded and nothing is published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pulse_db.pack import schema_of  # noqa: E402

SUPPORTED_SCHEMA = 9  # the schema the program reads (DB_SCHEMA_SUPPORTED of launcher/src-tauri/src/lib.rs)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_pack(record: dict, zip_path: Path, data_dir: Path, supported: int = SUPPORTED_SCHEMA) -> Path:
    """Check `zip_path` against `record` and write data_dir/pulse.db + data_dir/db_pack.json. Raises ValueError when anything differs."""
    if record.get("schema") != supported:
        raise ValueError(f"the pack has schema {record.get('schema')}, this program reads {supported}: build the database on the machine with the game client")
    if zip_path.stat().st_size != record["size"]:
        raise ValueError(f"the zip is {zip_path.stat().st_size} bytes, the record says {record['size']}: a half-updated release? try again in a few minutes")
    if _sha256(zip_path) != record["sha256"]:
        raise ValueError("the zip does not match the sha256 of the record: a half-updated release? try again in a few minutes")
    data_dir.mkdir(parents=True, exist_ok=True)
    fresh = data_dir / "pulse.db.new"
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != ["pulse.db"]:
            raise ValueError(f"the zip holds {archive.namelist()}, expected only pulse.db")
        with archive.open("pulse.db") as source, fresh.open("wb") as out:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                out.write(chunk)
    try:
        if _sha256(fresh) != record["content"]:
            raise ValueError("pulse.db does not match the content sha256 of the record")
        if schema_of(fresh) != record["schema"]:
            raise ValueError("pulse.db has another schema than the record says")
    except ValueError:
        fresh.unlink(missing_ok=True)
        raise
    target = data_dir / "pulse.db"
    fresh.replace(target)  # fails with PermissionError while a running Pulse+ holds the file: nothing is half written
    (data_dir / "db_pack.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _get(url: str, to: Path | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "pulse-fetch-db"})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read()
    if to is not None:
        to.write_bytes(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", default="db-latest")
    parser.add_argument("--repo", default="yshu17/aion-pulse")
    args = parser.parse_args()
    base = f"https://github.com/{args.repo}/releases/download/{args.tag}"
    record = json.loads(_get(f"{base}/db_pack.json").decode("utf-8"))
    temp = ROOT / "local" / "PulseDbFetched"
    temp.mkdir(parents=True, exist_ok=True)
    zip_path = temp / record["name"]
    _get(f"{base}/{record['name']}", zip_path)
    try:
        target = install_pack(record, zip_path, ROOT / "data")
    except ValueError as error:
        print(f"fetch_db_pack: {error}", file=sys.stderr)
        return 1
    print(f"pulse.db from {record['name']} schema {record['schema']} built {record['built']} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
