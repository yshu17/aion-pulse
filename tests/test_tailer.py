import pytest

from core.chat.tailer import LogTailer


def write(path, text, mode="ab"):
    with open(path, mode) as f:
        f.write(text.encode("cp1251"))


def test_start_at_end_skips_old_content(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "old line\r\n", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    assert tailer.read_new_lines() == []
    write(path, "new line\r\n")
    assert tailer.read_new_lines() == ["new line"]
    assert tailer.read_new_lines() == []


def test_partial_line_waits_for_newline(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "half")
    assert tailer.read_new_lines() == []
    write(path, " done\r\nnext\r\n")
    assert tailer.read_new_lines() == ["half done", "next"]


def test_decodes_cp1251(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "[3.Поиск группы] ищу хила\r\n")
    assert tailer.read_new_lines() == ["[3.Поиск группы] ищу хила"]


def test_lf_only_lines(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "a\nb\n")
    assert tailer.read_new_lines() == ["a", "b"]


def test_recreated_shorter_file_is_read_from_start(tmp_path):
    path = tmp_path / "Chat.log"
    write(path, "a long old line that will vanish\r\n" * 3, "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "fresh\r\n", "wb")
    assert tailer.read_new_lines() == ["fresh"]


def test_missing_file_raises(tmp_path):
    tailer = LogTailer(str(tmp_path / "nope.log"))
    with pytest.raises(FileNotFoundError):
        tailer.start_at_end()
    with pytest.raises(FileNotFoundError):
        tailer.read_new_lines()


def stamp(dt):
    return dt.strftime("%Y.%m.%d %H:%M:%S")


def test_read_backlog_returns_lines_since_cutoff(tmp_path):
    from datetime import datetime, timedelta

    now = datetime(2026, 10, 8, 19, 0, 0)
    lines = [f"{stamp(now - timedelta(seconds=s))} : line {s}" for s in (400, 200, 90, 30, 5)]
    path = tmp_path / "Chat.log"
    write(path, "".join(line + "\r\n" for line in lines), "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    got = tailer.read_backlog(now - timedelta(minutes=2), chunk_size=40)
    assert got == lines[2:]
    assert tailer.read_new_lines() == []


def test_read_backlog_whole_file_when_cutoff_is_older(tmp_path):
    from datetime import datetime, timedelta

    now = datetime(2026, 10, 8, 19, 0, 0)
    lines = [f"{stamp(now - timedelta(seconds=s))} : Привет {s}" for s in (50, 20)]
    path = tmp_path / "Chat.log"
    write(path, "".join(line + "\r\n" for line in lines), "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    assert tailer.read_backlog(now - timedelta(minutes=3)) == lines


def test_read_backlog_skips_lines_without_time_and_empty_file(tmp_path):
    from datetime import datetime

    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    assert tailer.read_backlog(datetime(2026, 1, 1)) == []
    write(path, "no time here\r\n2026.10.08 18:59:00 : ok\r\n", "wb")
    tailer.start_at_end()
    assert tailer.read_backlog(datetime(2026, 10, 8, 18, 58)) == ["2026.10.08 18:59:00 : ok"]


def test_over_long_line_is_dropped_and_reading_resumes_at_next_newline(tmp_path, monkeypatch):
    import core.chat.tailer as tailer_module

    monkeypatch.setattr(tailer_module, "MAX_LINE_BYTES", 100)
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "x" * 150)  # no newline yet: too long, dropped
    assert tailer.read_new_lines() == []
    assert tailer.dropped_lines == 1
    write(path, "y" * 500)  # still the same broken line
    assert tailer.read_new_lines() == []
    write(path, "end of it\r\nafter\r\n")
    assert tailer.read_new_lines() == ["after"]
    assert tailer.dropped_lines == 1


def test_short_lines_never_count_as_dropped(tmp_path, monkeypatch):
    import core.chat.tailer as tailer_module

    monkeypatch.setattr(tailer_module, "MAX_LINE_BYTES", 100)
    path = tmp_path / "Chat.log"
    write(path, "", "wb")
    tailer = LogTailer(str(path))
    tailer.start_at_end()
    write(path, "a" * 90 + "\r\n")
    assert tailer.read_new_lines() == ["a" * 90]
    assert tailer.dropped_lines == 0
