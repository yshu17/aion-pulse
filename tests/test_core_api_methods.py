"""Every method of the JSON entry point answers with plain JSON, and core/API.md lists exactly these methods."""

import gzip
import json
import re
from pathlib import Path

import pytest

from core.api import CoreApi
from tools.build_bestiary_index import build

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LINE = "2026.10.20 18:00:00 : [3.Поиск группы] [charname:A;1 1 1]: wts [Кираса Рудры] {}"


def _bestiary(tmp_path) -> Path:
    source, areas, database = tmp_path / "npcs.json.gz", tmp_path / "areas.json.gz", tmp_path / "npcs.sqlite"
    record = {"id": "210065", "name": "Когтистая рефисма", "site_name": "Когтистая рефисма", "local_name": "",
              "internal_name": "lepisma", "category": "npc", "role": "", "race": "beast", "site_level": 15,
              "icon_asset": "", "kb_url": "", "kb_status": "loaded",
              "points": [{"map_id": "210010000", "x": 100, "y": 200, "gx": 11, "gy": 22}],
              "kb": {"badges": {"type": "Монстр", "race": "Зверь", "rank": "Обычный"}, "stats": {"Макс. ХП": "282"},
                     "drops": [{"item_id": "1", "name": "Прах рефисмы", "rarity": "junk"}], "locations": []}}
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump({"zones": {"210010000": "Фоэта"}, "records": [record]}, stream, ensure_ascii=False)
    with gzip.open(areas, "wt", encoding="utf-8") as stream:
        json.dump({"areas": [{"npc_id": "210065", "map_id": "210010000", "area_id": "a", "point_count": 1,
                              "center": [100, 200], "area_names": ["Пастбище"],
                              "polygon": [[90, 190], [110, 190], [100, 210]]}]}, stream, ensure_ascii=False)
    build(source, areas, database)
    return database


@pytest.fixture
def api(tmp_path):
    api = CoreApi()
    api.call("data.open", {"data_dir": str(DATA)})
    return api


def calls(tmp_path, api):
    """(method, params, check) for every method; check gets the JSON result."""
    log = tmp_path / "Chat.log"
    log.write_bytes(b"")
    custom = tmp_path / "schedule_custom.json"
    config = tmp_path / "config.json"
    event = {"day": "wed", "start": "21:30", "end": "22:00", "name": "Своё"}
    wed = "2026-10-14T20:30:00"
    return [
        ("core.version", {}, lambda r: r["version"]),
        ("data.open", {"data_dir": str(DATA)}, lambda r: r["zones"] > 0),
        ("chat.parse", {"line": LINE.format("")}, lambda r: r["nick"] == "A"),
        ("chat.segments", {"text": "wts [Кираса Рудры]", "hits": ["wts"]}, lambda r: r[0]["hit"] and r[-2]["kind"] == "item"),
        ("chat.status_chip", {"text": "Слежу за x"}, lambda r: r == {"short": "Слежу", "kind": "live"}),
        ("chat.empty_feed", {"running": True}, lambda r: r["title"].startswith("Слежу")),
        ("chat.search_hint", {"mode": "words"}, lambda r: r == "нет ключевых слов"),
        ("session.configure", {"keywords": ["wts"], "cooldown_sec": 0, "alert_mode": "nag"}, lambda r: r["ok"]),
        ("session.history", {"lines": [LINE.format(1)], "now": 1}, lambda r: r["entries"][0]["kind"] == "history"),
        ("session.process", {"lines": [LINE.format(2)], "now": 2}, lambda r: r["entries"][0]["alert_id"]),
        ("session.state", {"now": 3}, lambda r: r["found"] == 1 and len(r["pending"]) == 1),
        ("session.accept", {"alert_id": 1}, lambda r: r["accepted"] == [1]),
        ("session.accept_all", {}, lambda r: r["accepted"] == []),
        ("session.expire", {"now": 999}, lambda r: r["missed"] == []),
        ("session.open_log", {"path": str(log)}, lambda r: r["ok"]),
        ("session.poll", {"now": 4}, lambda r: r["batch"]["entries"] == [] and r["history"] is None),
        ("session.stop", {}, lambda r: r["ok"]),
        ("items.list", {"query": "кираса рудры"}, lambda r: r["matches"]),
        ("items.spec", {"item_id": next(iter(api.specs))}, lambda r: r["name"]),
        ("map.zones", {}, lambda r: any(z["map_id"] == "220070000" for z in r)),
        ("map.search", {"map_id": "220070000", "query": "торговец"}, lambda r: r[0]["type"] == "merchant"),
        ("map.nearest", {"map_id": "220070000", "x": 884.5, "y": 1726.4, "type": "merchant"}, lambda r: r["metres"] < 1),
        ("map.cluster", {"map_id": "220070000", "scale": 0.2, "radius": 40}, lambda r: sum(g["count"] for g in r) > len(r)),
        ("schedule.day", {"day": "wed"}, lambda r: r and all(e["day"] == "wed" for e in r)),
        ("schedule.next", {"now": wed, "limit": 2}, lambda r: len(r) == 2),
        ("schedule.reminders", {"belled": [event], "now": "2026-10-14T21:26:00", "lead_min": 5},
         lambda r: r[0]["title"] == "Через 5 мин: Своё"),
        ("schedule.missed", {"belled": [event], "last": "2026-10-14T00:00:00", "now": "2026-10-15T00:00:00"},
         lambda r: r[0]["start"] == "2026-10-14T21:30:00"),
        ("schedule.custom_open", {"path": str(custom)}, lambda r: r["events"] > 0),
        ("schedule.custom_add", {"event": event}, lambda r: custom.exists()),
        ("schedule.custom_add_days", {"event": event, "days": ["thu"]}, lambda r: r["events"] > 0),
        ("schedule.custom_edit", {"old": event, "new": {**event, "name": "Своё 2"}}, lambda r: "Своё 2" in custom.read_text(encoding="utf-8")),
        ("schedule.custom_remove", {"event": {**event, "name": "Своё 2"}}, lambda r: r["events"] > 0),
        ("schedule.to_text", {"events": [event]}, lambda r: "Своё" in r),
        ("schedule.site_check", {"manual": True}, lambda r: r["status"] == "ok" and r["notice"]["title"]),
        ("schedule.parse_text", {"text": "ср 21:30-22:00 Своё"}, lambda r: set(r) == {"events", "errors"}),
        ("notice.release", {"found": ["v9.0.0", "u"], "can_install": True, "current": "1.2.0"},
         lambda r: r["actions"][0] == ["install", "Обновить сейчас"]),
        ("notice.schedule_check", {"status": "err", "value": "timeout", "manual": True}, lambda r: r["kind"] == "warning"),
        ("notice.route", {"action": "retry"}, lambda r: r == "retry"),
        ("notify.settings", {"mute": ["chat"], "dnd": False}, lambda r: r["ok"]),
        ("notify.post", {"source": "chat", "kind": "chat", "title": "Найдено", "repeat_after": 10, "now": 0},
         lambda r: r["id"] == 1),
        ("notify.next", {"now": 1}, lambda r: [n["title"] for n in r] == ["Найдено"]),
        ("notify.snooze", {"id": 1, "seconds": 5, "now": 2}, lambda r: r["ok"] is True),
        ("notify.acknowledge", {"id": 1}, lambda r: r["ok"] is True),
        ("notify.state", {}, lambda r: r["queued"] == 0 and "chat" in r["sources"]),
        ("settings.save", {"path": str(config), "values": {"keywords": ["wts"], "unknown": 1}}, lambda r: r["ok"]),
        ("settings.read", {"path": str(config)}, lambda r: r["config"]["keywords"] == ["wts"] and r["notice"] == ""),
        ("update.check", {"body": '{"tag_name": "v1.0.0", "html_url": "u"}', "current": "1.2.0"},
         lambda r: r["newer"] is False),
        ("telegram.add", {"lines": ["a", "b"], "now": 0}, lambda r: r["queued"] == 2),
        ("telegram.poll", {"now": 0}, lambda r: r["messages"] and r["queued"] == 0),
        ("bestiary.open", {"path": str(_bestiary(tmp_path))}, lambda r: r["version"]),
        ("bestiary.search", {"text": "рефисма"}, lambda r: r["total"] == 1),
        ("bestiary.detail", {"npc_id": "210065"}, lambda r: r["name"] == "Когтистая рефисма"),
        ("bestiary.filters", {}, lambda r: set(r) == {"races", "ranks", "zones"}),
        ("bestiary.regions", {"map_id": "210010000"}, lambda r: isinstance(r, list)),
        ("bestiary.areas", {"npc_id": "210065"}, lambda r: r and r[0]["map_id"] == "210010000"),
    ]


def test_every_method_answers_with_json(tmp_path, api, monkeypatch):
    import core.api

    monkeypatch.setattr(core.api, "site_fingerprint", lambda fetch: "site-picture-v2")  # no network in tests
    table = calls(tmp_path, api)
    assert sorted({method for method, _p, _c in table}) == sorted(api.methods), "add the new method to this table"
    for method, params, check in table:
        result = json.loads(json.dumps(api.call(method, params), ensure_ascii=False))
        assert check(result), (method, result)


def test_the_api_document_lists_exactly_the_methods(api):
    documented = set(re.findall(r"^\| `([a-z_]+\.[a-z_]+)` \|", (ROOT / "core" / "API.md").read_text(encoding="utf-8"), re.M))
    assert documented == set(api.methods)
