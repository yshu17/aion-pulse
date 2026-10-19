import threading
import time

from watcher.search_worker import SearchWorker


class SlowStore:
    """Stand-in for BestiaryStore: records the thread, takes a moment per search."""
    thread_ids: list = []
    closed = False

    def __init__(self, path):
        self.opened_in = threading.get_ident()

    def search(self, text="", *args, **kwargs):
        SlowStore.thread_ids.append((self.opened_in, threading.get_ident()))
        time.sleep(0.05)
        if text == "boom":
            raise ValueError("bad")
        return [{"id": text}], 1

    def close(self):
        SlowStore.closed = True


def _wait(worker, seq, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = worker.latest()
        if result is not None and result.seq == seq:
            return result
        time.sleep(0.01)
    raise AssertionError("no result")


def test_search_runs_in_its_own_thread_with_its_own_connection(tmp_path):
    SlowStore.thread_ids = []
    worker = SearchWorker(tmp_path / "x.sqlite", store_factory=SlowStore)
    worker.submit(1, "a")
    assert _wait(worker, 1).rows == [{"id": "a"}]
    opened, searched = SlowStore.thread_ids[0]
    assert opened == searched != threading.get_ident()
    worker.close()
    assert SlowStore.closed


def test_a_burst_of_requests_is_collapsed_to_the_newest(tmp_path):
    SlowStore.thread_ids = []
    worker = SearchWorker(tmp_path / "x.sqlite", store_factory=SlowStore)
    for seq, text in enumerate("abcdefghij", start=1):
        worker.submit(seq, text)
    assert _wait(worker, 10).rows == [{"id": "j"}]
    assert len(SlowStore.thread_ids) < 10  # not every keystroke was searched
    worker.close()


def test_errors_come_back_as_results_and_the_worker_keeps_working(tmp_path):
    worker = SearchWorker(tmp_path / "x.sqlite", store_factory=SlowStore)
    worker.submit(1, "boom")
    assert _wait(worker, 1).error == "bad"
    worker.submit(2, "ok")
    assert _wait(worker, 2).rows == [{"id": "ok"}]
    worker.close()


def test_unopenable_database_is_reported_not_raised(tmp_path):
    worker = SearchWorker(tmp_path / "missing.sqlite")
    worker.submit(1, "x")
    assert _wait(worker, 1).error
    worker.close()
