import winsound

from watcher import notifier
from watcher.notifier import Notifier


def record_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(notifier.winsound, "MessageBeep", lambda kind: calls.append(("beep", kind)))
    monkeypatch.setattr(
        notifier.winsound, "PlaySound", lambda path, flags: calls.append(("play", path, flags))
    )
    return calls


def test_beeps_without_sound_file(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    Notifier("").play()
    Notifier(None).play()
    Notifier(str(tmp_path / "missing.wav")).play()
    assert calls == [("beep", winsound.MB_ICONEXCLAMATION)] * 3


def test_plays_existing_file_async(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    wav = tmp_path / "alert.wav"
    wav.write_bytes(b"RIFF")
    Notifier(str(wav)).play()
    assert calls == [("play", str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)]


def test_falls_back_to_beep_when_play_fails(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    wav = tmp_path / "broken.wav"
    wav.write_bytes(b"not a wav")

    def failing_play(path, flags):
        raise RuntimeError("Failed to play sound")

    monkeypatch.setattr(notifier.winsound, "PlaySound", failing_play)
    Notifier(str(wav)).play()
    assert calls == [("beep", winsound.MB_ICONEXCLAMATION)]
