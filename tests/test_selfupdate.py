import hashlib
import io
import json
import sys

import pytest

from watcher import selfupdate
from watcher.selfupdate import can_install, download, install, pick_asset, remove_old

DATA = b"new exe bytes"
SHA = hashlib.sha256(DATA).hexdigest()


def _release(body="Changes\n\nSHA256: " + SHA, assets=None):
    return json.dumps({"tag_name": "v1.2.0", "body": body, "assets": assets if assets is not None else [
        {"name": "Pulse.exe", "size": len(DATA), "browser_download_url": "https://github.com/x/y/releases/download/v1.2.0/Pulse.exe"},
        {"name": "notes.txt", "size": 3, "browser_download_url": "https://github.com/x/y/notes.txt"},
    ]})


def test_asset_and_checksum_come_from_the_release():
    asset = pick_asset(_release())
    assert asset == {"url": "https://github.com/x/y/releases/download/v1.2.0/Pulse.exe", "size": len(DATA), "sha256": SHA}
    assert pick_asset(_release(body="no checksum here"))["sha256"] == ""  # then download refuses
    assert pick_asset(_release(assets=[])) is None
    assert pick_asset(_release(assets=[{"name": "Pulse-Local.exe", "size": 1,
                                        "browser_download_url": "https://github.com/x"}])) is None


def test_only_the_stable_exe_of_a_frozen_program_can_install(tmp_path, monkeypatch):
    assert can_install(tmp_path / "Pulse.exe") is False  # not frozen: the source tree is never replaced
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert can_install(tmp_path / "Pulse.exe") is True
    assert can_install(tmp_path / "Pulse-Local.exe") is False


class _Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _asset(**changes):
    asset = {"url": "https://github.com/x/y/Pulse.exe", "size": len(DATA), "sha256": SHA}
    asset.update(changes)
    return asset


def test_download_checks_the_checksum_and_the_address(tmp_path, monkeypatch):
    monkeypatch.setattr(selfupdate.urllib.request, "urlopen", lambda request, timeout: _Response(DATA))
    dest = download(_asset(), tmp_path / "Pulse.update")
    assert dest.read_bytes() == DATA and not (tmp_path / "Pulse.update.part").exists()


def test_download_refuses_a_wrong_hash_size_or_address_and_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(selfupdate.urllib.request, "urlopen", lambda request, timeout: _Response(b"tampered bytes"))
    with pytest.raises(ValueError, match="SHA-256"):
        download(_asset(size=0), tmp_path / "Pulse.update")
    assert not (tmp_path / "Pulse.update").exists() and not (tmp_path / "Pulse.update.part").exists()
    with pytest.raises(ValueError, match="untrusted"):
        download(_asset(url="http://github.com/x/Pulse.exe"), tmp_path / "a")
    with pytest.raises(ValueError, match="untrusted"):
        download(_asset(url="https://example.com/Pulse.exe"), tmp_path / "a")
    with pytest.raises(ValueError, match="no SHA256"):
        download(_asset(sha256=""), tmp_path / "a")


def test_install_swaps_the_files_and_starts_the_new_copy(tmp_path):
    current, new = tmp_path / "Pulse.exe", tmp_path / "Pulse.update"
    current.write_bytes(b"old")
    new.write_bytes(DATA)
    started = []
    install(current, new, launch=lambda cmd, cwd: started.append((cmd, cwd)))
    assert current.read_bytes() == DATA and (tmp_path / "Pulse.exe.old").read_bytes() == b"old"
    assert not new.exists()
    assert started == [([str(current)], str(tmp_path))]


def test_install_puts_the_working_copy_back_when_the_new_one_is_missing(tmp_path):
    current = tmp_path / "Pulse.exe"
    current.write_bytes(b"old")
    with pytest.raises(OSError):
        install(current, tmp_path / "missing.update", launch=lambda cmd, cwd: None)
    assert current.read_bytes() == b"old" and not (tmp_path / "Pulse.exe.old").exists()


def test_the_old_copy_is_removed_at_the_next_start(tmp_path):
    current = tmp_path / "Pulse.exe"
    (tmp_path / "Pulse.exe.old").write_bytes(b"old")
    remove_old(current)
    assert not (tmp_path / "Pulse.exe.old").exists()
    remove_old(current)  # nothing to remove: no error
