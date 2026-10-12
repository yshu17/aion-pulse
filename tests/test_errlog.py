from watcher import errlog
from watcher.errlog import log_exception


def fail(path, previous=""):
    """Raise a ValueError inside a handler and log it, as _tick does."""
    try:
        raise ValueError("сбой чтения")
    except ValueError:
        return log_exception(path, "_tick", previous)


def test_traceback_is_written_once_per_distinct_error(tmp_path):
    path = tmp_path / "errors.log"
    first = fail(path)
    second = fail(path, previous=first)  # the same error again: not written
    assert first == second == "ValueError: сбой чтения"
    text = path.read_text(encoding="utf-8")
    assert text.count("Traceback") == 1 and "_tick" in text


def test_same_error_after_a_different_one_is_written_again(tmp_path):
    path = tmp_path / "errors.log"
    fail(path, previous="KeyError: other")
    assert path.read_text(encoding="utf-8").count("Traceback") == 1


def test_log_is_cut_back_when_it_grows_past_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(errlog, "MAX_BYTES", 2000)
    path = tmp_path / "errors.log"
    path.write_text("\n".join(f"line {i}" for i in range(2000)), encoding="utf-8")
    fail(path)
    text = path.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 2000 + 400
    assert "line 1999" in text and "line 0\n" not in text


def test_unwritable_log_does_not_raise(tmp_path):
    path = tmp_path / "missing-dir" / "errors.log"
    assert fail(path) == "ValueError: сбой чтения"
