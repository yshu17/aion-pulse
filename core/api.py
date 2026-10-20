"""One JSON entry point to the core, for a launcher or any other program that is not Python.

    api = CoreApi()
    api.call("data.open", {"data_dir": ".../data"})          -> {"items": 61000, "zones": 20, ...}
    api.call("session.configure", {"keywords": ["wts"]})       -> {"ok": true}
    api.call("session.process", {"lines": [...], "now": 12.5}) -> {"entries": [...], "places": [...], ...}

`python -m core` runs the same API over stdin / stdout, one JSON object per line:
    request  {"id": 1, "method": "chat.parse", "params": {"line": "..."}}
    answer   {"id": 1, "result": {...}}   or   {"id": 1, "error": {"type": "KeyError", "message": "..."}}

Every method takes and returns plain JSON (dataclasses become objects, datetimes ISO strings, paths strings).
`now` of the session methods is a monotonic clock in seconds that the caller owns; schedule times are MSK wall-clock
ISO strings. The method list with its parameters is in core/API.md and in `core.version`.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core import __version__
from core.chat.parser import parse_any_line, parse_line
from core.chat.session import LogFeed, WatchSession
from core.items.browser import ItemBrowser, ItemFilter
from core.items.catalog import load_item_names, load_link_names, load_watch_items
from core.map.poi import PoiStore
from core.map.zones import SHOWN_TYPES, load_zones
from core.schedule.reminder_flow import ReminderPlanner, missed_events
from core.schedule.schedule_view import events_for_day, next_events
from core.schedule.timing import end_of, load_events, msk_now, until_text
from core.update.updater import latest_release, newer


def to_json(value):
    """Plain JSON data of a core value."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value) if isinstance(value, (set, frozenset)) else value
        return [to_json(v) for v in items]
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, Path):
        return str(value)
    return value


def _time(text: str | None) -> datetime:
    return datetime.fromisoformat(text) if text else msk_now()


class CoreApi:
    def __init__(self) -> None:
        self.item_names: dict[str, str] = {}
        self.map_names: dict[str, str] = {}
        self.quest_names: dict[str, str] = {}
        self.watch_items = []
        self.zones = {}
        self.poi: PoiStore | None = None
        self.events: list[dict] = []
        self.bestiary = None
        self.session = WatchSession()
        self.feed: LogFeed | None = None
        self.planner = ReminderPlanner()
        self.methods: dict[str, Callable[[dict], object]] = {
            "core.version": self.version,
            "data.open": self.open_data,
            "chat.parse": self.parse,
            "session.configure": self.configure,
            "session.process": lambda p: self.session.process(p.get("lines", []), float(p.get("now", 0))),
            "session.history": lambda p: self.session.history(p.get("lines", []), float(p.get("now", 0))),
            "session.open_log": self.open_log,
            "session.poll": self.poll,
            "session.accept": lambda p: {"accepted": self.session.accept(int(p["alert_id"]))},
            "session.accept_all": lambda p: {"accepted": self.session.accept_all()},
            "session.expire": lambda p: {"missed": self.session.expire(float(p.get("now", 0)))},
            "session.state": self.state,
            "session.stop": self.stop,
            "items.list": self.items,
            "map.zones": lambda p: [{"map_id": z.map_id, "name": z.name, "side": z.side, "size": z.size}
                                    for z in self.zones.values()],
            "map.search": self.map_search,
            "map.nearest": self.map_nearest,
            "schedule.day": lambda p: events_for_day(self.events, p["day"]),
            "schedule.next": self.schedule_next,
            "schedule.reminders": self.reminders,
            "schedule.missed": lambda p: [{"event": e, "start": at} for e, at in missed_events(
                p.get("belled", self.events), datetime.fromisoformat(p["last"]) if p.get("last") else None,
                _time(p.get("now")))],
            "bestiary.open": self.open_bestiary,
            "bestiary.search": self.bestiary_search,
            "bestiary.detail": lambda p: self._bestiary().detail(str(p["npc_id"])),
            "update.check": lambda p: self._release(p),
        }

    # --- dispatch ----------------------------------------------------------------------
    def call(self, method: str, params: dict | None = None):
        handler = self.methods.get(method)
        if handler is None:
            raise ValueError(f"unknown method: {method}")
        return to_json(handler(params or {}))

    def handle(self, request_line: str) -> str:
        """One JSON request line -> one JSON answer line (errors are answers too, never exceptions)."""
        request_id = None
        try:
            request = json.loads(request_line)
            request_id = request.get("id")
            result = self.call(request["method"], request.get("params"))
            answer = {"id": request_id, "result": result}
        except Exception as exc:  # the caller gets the error as data and keeps the process
            answer = {"id": request_id, "error": {"type": type(exc).__name__, "message": str(exc)}}
        return json.dumps(answer, ensure_ascii=False)

    # --- methods -----------------------------------------------------------------------
    def version(self, _params: dict) -> dict:
        return {"version": __version__, "methods": sorted(self.methods)}

    def open_data(self, params: dict) -> dict:
        """Load the bundled data folder of Pulse (data/): names, watchable items, map zones, points, schedule."""
        data = Path(params["data_dir"])
        self.item_names = load_item_names(data / "item_names.tsv")
        self.map_names, self.quest_names = load_link_names(data)
        self.watch_items = load_watch_items(data / "watch_items.csv")
        self.zones = load_zones(data / "maps", self.map_names)
        self.poi = PoiStore.load(data / "maps" / "poi.json").projected(
            {map_id: zone.to_image for map_id, zone in self.zones.items()})  # x, y: pixels of the zone picture
        self.events = load_events(data / "schedule.json")
        self.session.item_names, self.session.map_names = self.item_names, self.map_names
        self.session.quest_names = self.quest_names
        return {"items": len(self.item_names), "watch_items": len(self.watch_items), "zones": len(self.zones),
                "points": sum(len(points) for points in self.poi._zones.values()), "events": len(self.events)}

    def parse(self, params: dict):
        args = (params["line"], self.item_names)
        names = {"maps": self.map_names, "quests": self.quest_names}
        return parse_any_line(*args, **names) if params.get("any") else parse_line(*args, **names)

    def configure(self, params: dict) -> dict:
        """Watching settings; `watch_items` are item ids (their names come from data.open)."""
        names = {item.id: item.name for item in self.watch_items}
        if "keywords" in params:
            self.session.set_keywords(list(params["keywords"]))
        if "watch_items" in params:
            self.session.set_watch_items({i: names.get(i, i) for i in params["watch_items"]})
        if "mode" in params:
            self.session.set_mode(params["mode"])
        if "alert_mode" in params:
            self.session.set_alert_mode(params["alert_mode"])
        if "cooldown_sec" in params:
            self.session.matcher.cooldown_sec = float(params["cooldown_sec"])
        if "react_sec" in params:
            self.session.tracker.react_sec = float(params["react_sec"])
        return {"ok": True}

    def open_log(self, params: dict) -> dict:
        self.feed = LogFeed(params["path"], int(params.get("history_min", 0)))
        return {"ok": True}

    def poll(self, params: dict) -> dict:
        """Read the log opened by session.open_log: the history batch (first poll only) and the live batch."""
        if self.feed is None:
            raise RuntimeError("session.open_log first")
        now = float(params.get("now", 0))
        history, lines = self.feed.poll()
        return {"history": self.session.history(history, now) if history is not None else None,
                "batch": self.session.process(lines, now)}

    def state(self, params: dict) -> dict:
        found, reacted, missed = self.session.counters
        return {"found": found, "reacted": reacted, "missed": missed, "pending": self.session.pending_ids,
                "remaining": self.session.remaining(float(params.get("now", 0)))}

    def stop(self, _params: dict) -> dict:
        self.session.stop()
        self.feed = None
        return {"ok": True}

    def items(self, params: dict) -> dict:
        """The «Что искать» list: sections after a filter, and the matches of a search."""
        f = params.get("filter") or {}
        browser = ItemBrowser(self.watch_items, params.get("checked", []), (),
                              ItemFilter(set(f.get("grades", [])), int(f.get("level_min", 0)),
                                         int(f.get("level_max", 0)), f.get("type", "")))
        found = browser.search(params.get("query", ""))
        return {"sections": {name: [item.id for item in items] for name, items in browser.shown.items()},
                "matches": browser.matches[:found], "types": browser.type_choices(), "grades": browser.grades}

    def _points(self):
        if self.poi is None:
            raise RuntimeError("data.open first")
        return self.poi

    def map_search(self, params: dict):
        types = set(params.get("types") or SHOWN_TYPES)
        return self._points().search(params["map_id"], params.get("query", ""), types, params.get("side", ""),
                                     params.get("layer"))

    def map_nearest(self, params: dict):
        found = self._points().nearest(params["map_id"], float(params["x"]), float(params["y"]), params["type"])
        return None if found is None else {"point": found[0], "metres": found[1]}

    def schedule_next(self, params: dict) -> list[dict]:
        now = _time(params.get("now"))
        return [{"event": event, "start": start, "end": end_of(event, start),
                 "until": until_text(start, end_of(event, start), now)}
                for event, start in next_events(self.events, now, int(params.get("limit", 8)))]

    def reminders(self, params: dict):
        """Reminders due now for the belled events (each occurrence once per API instance)."""
        belled = params.get("belled", self.events)
        return self.planner.due(belled, _time(params.get("now")), int(params.get("lead_min", 5)))

    def open_bestiary(self, params: dict) -> dict:
        from core.bestiary.bestiary_store import BestiaryStore

        if self.bestiary is not None:
            self.bestiary.close()
        self.bestiary = BestiaryStore(Path(params["path"]))
        return {"version": self.bestiary.version, "coverage": list(self.bestiary.coverage())}

    def _bestiary(self):
        if self.bestiary is None:
            raise RuntimeError("bestiary.open first")
        return self.bestiary

    def bestiary_search(self, params: dict) -> dict:
        rows, total = self._bestiary().search(**{k: v for k, v in params.items() if k in (
            "text", "category", "race", "rank", "map_id", "offset", "limit", "min_level", "max_level", "region",
            "order", "hide_low")})
        return {"rows": rows, "total": total}

    @staticmethod
    def _release(params: dict):
        found = latest_release(params["body"])
        if found is None:
            return {"tag": None, "url": None, "newer": False}
        return {"tag": found[0], "url": found[1], "newer": newer(found[0], params.get("current", "0"))}
