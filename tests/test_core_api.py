import json
from pathlib import Path

import pytest

from core.api import CoreApi

DATA = Path(__file__).resolve().parents[1] / "data"


def line(nick, text):
    return f"2026.10.20 18:00:00 : [3.Поиск группы] [charname:{nick};1 1 1]: {text} "


@pytest.fixture(scope="module")
def api():
    api = CoreApi()
    api.call("data.open", {"data_dir": str(DATA)})
    return api


def test_requests_and_errors_are_json_lines(api):
    answer = json.loads(api.handle('{"id": 7, "method": "core.version"}'))
    assert answer["id"] == 7 and "session.process" in answer["result"]["methods"]
    error = json.loads(api.handle('{"id": 8, "method": "nope"}'))
    assert error == {"id": 8, "error": {"type": "ValueError", "message": "unknown method: nope"}}
    assert json.loads(api.handle("not json"))["error"]["type"] == "JSONDecodeError"


def test_open_data_loads_the_bundled_folder(api):
    counts = api.call("data.open", {"data_dir": str(DATA)})
    assert counts["zones"] > 0 and counts["items"] > 0 and counts["events"] > 0


def test_session_over_the_api_counts_and_accepts(api):
    api.call("session.configure", {"keywords": ["wts"], "alert_mode": "nag", "cooldown_sec": 0})
    batch = api.call("session.process", {"lines": [line("A", "wts шлем")], "now": 1})
    entry = batch["entries"][0]
    assert entry["kind"] == "loud" and entry["msg"]["nick"] == "A" and batch["announce"] == [entry["alert_id"]]
    assert api.call("session.state", {"now": 2})["pending"] == [entry["alert_id"]]
    assert api.call("session.accept", {"alert_id": entry["alert_id"]}) == {"accepted": [entry["alert_id"]]}
    assert api.call("session.state", {})["reacted"] == 1
    api.call("session.stop", {})


def test_log_reading_over_the_api(api, tmp_path):
    log = tmp_path / "Chat.log"
    log.write_bytes(b"")
    api.call("session.configure", {"keywords": ["wts"], "alert_mode": "standard"})
    api.call("session.open_log", {"path": str(log)})
    assert api.call("session.poll", {"now": 1})["batch"]["entries"] == []
    log.write_bytes(line("B", "wts лук").encode("cp1251") + b"\r\n")
    assert api.call("session.poll", {"now": 2})["batch"]["entries"][0]["msg"]["nick"] == "B"


def test_items_map_schedule_and_update(api):
    items = api.call("items.list", {"query": "кираса рудры"})
    assert items["matches"] and items["types"][0] == "Все типы"
    points = api.call("map.search", {"map_id": "220070000", "query": "торговец"})
    assert points and points[0]["x"] > 0  # projected onto the zone picture
    near = api.call("map.nearest", {"map_id": "220070000", "x": points[0]["gx"], "y": points[0]["gy"],
                                    "type": "merchant"})
    assert near["metres"] == pytest.approx(0, abs=1)
    upcoming = api.call("schedule.next", {"now": "2026-10-14T20:30:00", "limit": 3})
    assert len(upcoming) == 3 and upcoming[0]["until"]
    release = api.call("update.check", {"body": '{"tag_name": "v9.0.0", "html_url": "u"}', "current": "1.2.0"})
    assert release == {"tag": "v9.0.0", "url": "u", "newer": True}
    with pytest.raises(RuntimeError):
        CoreApi().call("bestiary.search", {"text": "x"})
