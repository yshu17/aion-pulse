"""The database pack (core/pulse_db/pack.py): the record, the same bytes for the same database, a kept pack."""

import hashlib
import sqlite3
import zipfile

from core.pulse_db.pack import make_pack, schema_of


def _db(path, version=9, rows=3):
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE npc (id TEXT)")
    connection.executemany("INSERT INTO npc VALUES (?)", [(str(i),) for i in range(rows)])
    connection.execute(f"PRAGMA user_version = {version}")
    connection.commit()
    connection.close()


def test_record_describes_the_zip_and_the_database(tmp_path):
    db = tmp_path / "pulse.db"
    _db(db)
    pack = make_pack(db, tmp_path / "out", "db-latest", "owner/repo", None, "2026-11-11T00:00:00Z")
    zip_path = tmp_path / "out" / pack["name"]
    assert pack["schema"] == schema_of(db) == 9
    assert pack["content"] == hashlib.sha256(db.read_bytes()).hexdigest()
    assert pack["sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest() and pack["size"] == zip_path.stat().st_size
    assert pack["name"] == f"pulse-db-{pack['sha256'][:12]}.zip"
    assert pack["url"] == f"https://github.com/owner/repo/releases/download/db-latest/{pack['name']}"
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["pulse.db"] and archive.read("pulse.db") == db.read_bytes()


def test_the_same_database_keeps_its_pack_and_its_time_and_a_new_one_replaces_it(tmp_path):
    db = tmp_path / "pulse.db"
    _db(db)
    first = make_pack(db, tmp_path / "out", "t", "o/r", None, "2026-11-11T00:00:00Z")
    again = make_pack(db, tmp_path / "out", "t", "o/r", first, "2027-01-01T00:00:00Z")
    assert again["built"] == "2026-11-11T00:00:00Z" and again["sha256"] == first["sha256"]
    db.unlink()
    _db(db, rows=5)
    second = make_pack(db, tmp_path / "out", "t", "o/r", first, "2027-01-01T00:00:00Z")
    assert second["built"] == "2027-01-01T00:00:00Z" and second["content"] != first["content"]
    assert sorted(p.name for p in (tmp_path / "out").glob("pulse-db-*.zip")) == [second["name"]]  # only the current pack is left to upload


def test_the_zip_is_the_same_bytes_for_the_same_database(tmp_path):
    db = tmp_path / "pulse.db"
    _db(db)
    a = make_pack(db, tmp_path / "a", "t", "o/r", None, "2026-11-11T00:00:00Z")
    b = make_pack(db, tmp_path / "b", "t", "o/r", None, "2030-01-01T00:00:00Z")
    assert a["sha256"] == b["sha256"]
