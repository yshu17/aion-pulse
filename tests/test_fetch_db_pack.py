"""tools/fetch_db_pack.py: the pack of the release is checked before it replaces data/pulse.db."""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from core.pulse_db.pack import make_pack  # noqa: E402
from fetch_db_pack import install_pack  # noqa: E402


def _db(path: Path, schema: int = 9) -> Path:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE t (x INTEGER)")
    connection.execute("INSERT INTO t VALUES (1)")
    connection.execute(f"PRAGMA user_version = {schema}")
    connection.commit()
    connection.close()
    return path


def _pack(tmp_path: Path, schema: int = 9) -> tuple[dict, Path]:
    source = _db(tmp_path / "source.db", schema)
    out = tmp_path / "out"
    record = make_pack(source, out, "db-latest", "yshu17/aion-pulse", None, "2026-11-20T00:00:00Z")
    return record, out / record["name"]


def test_a_good_pack_becomes_data_pulse_db_and_its_record(tmp_path):
    record, zip_path = _pack(tmp_path)
    data = tmp_path / "data"
    target = install_pack(record, zip_path, data)
    assert target == data / "pulse.db"
    assert sqlite3.connect(target).execute("SELECT x FROM t").fetchone() == (1,)
    assert '"name": "%s"' % record["name"] in (data / "db_pack.json").read_text(encoding="utf-8")
    assert not (data / "pulse.db.new").exists()


def test_a_pack_of_another_schema_is_refused_and_data_stays_untouched(tmp_path):
    record, zip_path = _pack(tmp_path, schema=10)
    data = tmp_path / "data"
    data.mkdir()
    (data / "pulse.db").write_bytes(b"old")
    with pytest.raises(ValueError, match="schema 10"):
        install_pack(record, zip_path, data)
    assert (data / "pulse.db").read_bytes() == b"old"


def test_a_zip_that_differs_from_its_record_is_refused(tmp_path):
    record, zip_path = _pack(tmp_path)
    with pytest.raises(ValueError, match="sha256|bytes"):
        install_pack({**record, "sha256": "0" * 64}, zip_path, tmp_path / "data")
    with pytest.raises(ValueError, match="bytes"):
        install_pack({**record, "size": record["size"] + 1}, zip_path, tmp_path / "data")
    assert not (tmp_path / "data" / "pulse.db").exists()


def test_a_database_that_differs_from_the_content_hash_is_refused(tmp_path):
    record, zip_path = _pack(tmp_path)
    with pytest.raises(ValueError, match="content"):
        install_pack({**record, "content": "f" * 64}, zip_path, tmp_path / "data")
    assert not (tmp_path / "data" / "pulse.db").exists()
    assert not (tmp_path / "data" / "pulse.db.new").exists()
