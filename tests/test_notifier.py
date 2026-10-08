import winsound

from watcher import notifier
from watcher.notifier import Notifier


def record_calls(monkeypatch):
    monkeypatch.setattr(notifier, "default_beep_path", lambda: None)
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


def test_start_loop_plays_file_in_loop_and_stop_silences(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    wav = tmp_path / "alarm.wav"
    wav.write_bytes(b"RIFF")
    n = Notifier(str(wav))
    assert n.start_loop() is True
    n.stop()
    assert calls == [
        ("play", str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP),
        ("play", None, 0),
    ]


def test_start_loop_without_file_reports_no_native_loop(monkeypatch):
    calls = record_calls(monkeypatch)
    assert Notifier("").start_loop() is False
    assert calls == []


def test_start_loop_failure_reports_no_native_loop(tmp_path, monkeypatch):
    record_calls(monkeypatch)
    wav = tmp_path / "broken.wav"
    wav.write_bytes(b"x")

    def failing_play(path, flags):
        raise RuntimeError("Failed to play sound")

    monkeypatch.setattr(notifier.winsound, "PlaySound", failing_play)
    assert Notifier(str(wav)).start_loop() is False


def test_system_sounds_lists_wav_files_sorted(tmp_path):
    from watcher.notifier import system_sounds

    for name in ("Ring01.wav", "Alarm01.wav", "readme.txt"):
        (tmp_path / name).write_bytes(b"RIFF")
    assert [p.name for p in system_sounds(tmp_path)] == ["Alarm01.wav", "Ring01.wav"]
    assert system_sounds(tmp_path / "missing") == []


def test_system_beep_plays_windows_wav_so_volume_applies(tmp_path, monkeypatch):
    calls = record_calls(monkeypatch)
    wav = tmp_path / "Windows Exclamation.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(notifier, "default_beep_path", lambda: str(wav))
    Notifier("").play()
    assert calls == [("play", str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)]


def test_default_beep_path_prefers_exclamation(tmp_path):
    from watcher.notifier import default_beep_path

    (tmp_path / "Windows Background.wav").write_bytes(b"RIFF")
    assert default_beep_path(tmp_path).endswith("Windows Background.wav")
    (tmp_path / "Windows Exclamation.wav").write_bytes(b"RIFF")
    assert default_beep_path(tmp_path).endswith("Windows Exclamation.wav")
    assert default_beep_path(tmp_path / "missing") is None


def test_set_volume_scales_both_channels(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier, "_wave_out_set_volume", lambda value: sent.append(value))
    n = Notifier("")
    sent.clear()
    n.set_volume(100)
    n.set_volume(50)
    n.set_volume(0)
    n.set_volume(250)  # clamped
    assert sent == [0xFFFFFFFF, 0x7FFF7FFF, 0, 0xFFFFFFFF]
    assert n.volume == 100
