"""The typed contract of core/api.py: JSON Schema (core/api.schema.json) and TypeScript types (core/api.d.ts).

Both files are generated from METHODS and the core dataclasses by `python tools/build_core_schema.py`; a test fails
when they are out of date or when a method of CoreApi has no entry here.

Type expressions: string, integer, number, boolean, object, any, null, a named type (a dataclass of the core or an
entry of SHAPES), `T[]` for a list and `A|B` for either. A parameter name ending in «?» is optional.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from datetime import datetime
from pathlib import Path

from core.chat.parser import ChatLine, ChatMessage
from core.chat.segments import Segment
from core.chat.session import Batch, Entry
from core.map.poi import Poi
from core.map.zones import Place
from core.notify.notices import Notice
from core.notify.notify_center import Notification, NotificationAction
from core.schedule.reminder_flow import Reminder

DATACLASSES = (ChatMessage, ChatLine, Entry, Batch, Place, Segment, Poi, Notice, Notification, NotificationAction,
               Reminder)

# shapes of plain dict results (field -> type expression; a field name ending in «?» may be absent)
SHAPES: dict[str, dict[str, str]] = {
    "Ok": {"ok": "boolean"},
    "VersionInfo": {"version": "string", "methods": "string[]"},
    "DataCounts": {"items": "integer", "watch_items": "integer", "zones": "integer", "points": "integer",
                   "events": "integer"},
    "Accepted": {"accepted": "integer[]"},
    "Missed": {"missed": "integer[]"},
    "SessionState": {"found": "integer", "reacted": "integer", "missed": "integer", "pending": "integer[]",
                     "remaining": "object"},
    "PollResult": {"history": "Batch|null", "batch": "Batch"},
    "ItemsList": {"sections": "object", "matches": "string[]", "types": "string[]", "grades": "string[]"},
    "ZoneInfo": {"map_id": "string", "name": "string", "side": "string", "size": "integer"},
    "Nearest": {"point": "Poi", "metres": "number"},
    "ClusterIcon": {"x": "number", "y": "number", "type": "string", "count": "integer", "points": "Poi[]"},
    "ScheduleEvent": {"day": "string", "start": "string", "end": "string", "name": "string", "group?": "string",
                      "color?": "string", "kind?": "string", "maps?": "object"},
    "Upcoming": {"event": "ScheduleEvent", "start": "string", "end": "string", "until": "string"},
    "MissedEvent": {"event": "ScheduleEvent", "start": "string"},
    "EventCount": {"events": "integer"},
    "ParsedSchedule": {"events": "ScheduleEvent[]", "errors": "string[]"},
    "SiteCheck": {"status": "string", "value": "string", "notice": "Notice|null"},
    "BestiaryInfo": {"version": "integer", "coverage": "integer[]"},
    "BestiaryPage": {"rows": "object[]", "total": "integer"},
    "BestiaryFilters": {"races": "string[]", "ranks": "string[]", "zones": "any[]"},
    "Release": {"tag": "string|null", "url": "string|null", "newer": "boolean"},
    "Chip": {"short": "string", "kind": "string"},
    "EmptyFeed": {"title": "string", "hint": "string"},
    "Acknowledged": {"ok": "boolean"},
    "NotifyState": {"queued": "integer", "unread": "integer", "dnd": "boolean", "sources": "string[]"},
    "Settings": {"config": "object", "notice": "string"},
    "Queued": {"queued": "integer"},
    "TelegramPoll": {"messages": "string[]", "queued": "integer", "dropped": "integer"},
}

_SESSION = {"keywords?": "string[]", "watch_items?": "string[]", "mode?": "string", "alert_mode?": "string",
            "cooldown_sec?": "number", "react_sec?": "number"}
_FILTER_TYPES = {"types?": "string[]", "side?": "string", "layer?": "integer|null"}

# method -> (params, result)
METHODS: dict[str, tuple[dict[str, str], str]] = {
    "core.version": ({}, "VersionInfo"),
    "data.open": ({"data_dir": "string"}, "DataCounts"),
    "chat.parse": ({"line": "string", "any?": "boolean"}, "ChatMessage|ChatLine|null"),
    "chat.segments": ({"text": "string", "hits?": "string[]"}, "Segment[]"),
    "chat.status_chip": ({"text": "string"}, "Chip"),
    "chat.empty_feed": ({"running?": "boolean", "mode?": "string", "keywords?": "string[]",
                         "watch_items?": "string[]"}, "EmptyFeed"),
    "chat.search_hint": ({"mode?": "string", "keywords?": "string[]", "watch_items?": "string[]"}, "string"),
    "session.configure": (_SESSION, "Ok"),
    "session.process": ({"lines": "string[]", "now": "number"}, "Batch"),
    "session.history": ({"lines": "string[]", "now": "number"}, "Batch"),
    "session.open_log": ({"path": "string", "history_min?": "integer"}, "Ok"),
    "session.poll": ({"now": "number"}, "PollResult"),
    "session.accept": ({"alert_id": "integer"}, "Accepted"),
    "session.accept_all": ({}, "Accepted"),
    "session.expire": ({"now": "number"}, "Missed"),
    "session.state": ({"now?": "number"}, "SessionState"),
    "session.stop": ({}, "Ok"),
    "items.list": ({"query?": "string", "filter?": "object", "checked?": "string[]"}, "ItemsList"),
    "items.spec": ({"item_id": "string"}, "object|null"),
    "map.zones": ({}, "ZoneInfo[]"),
    "map.search": ({"map_id": "string", "query?": "string", **_FILTER_TYPES}, "Poi[]"),
    "map.nearest": ({"map_id": "string", "x": "number", "y": "number", "type": "string"}, "Nearest|null"),
    "map.cluster": ({"map_id": "string", "scale?": "number", "dx?": "number", "dy?": "number", "radius?": "number",
                     **_FILTER_TYPES}, "ClusterIcon[]"),
    "schedule.day": ({"day": "string"}, "ScheduleEvent[]"),
    "schedule.next": ({"now?": "string", "limit?": "integer"}, "Upcoming[]"),
    "schedule.reminders": ({"belled?": "ScheduleEvent[]", "lead_min?": "integer", "now?": "string"}, "Reminder[]"),
    "schedule.missed": ({"belled?": "ScheduleEvent[]", "last?": "string", "now?": "string"}, "MissedEvent[]"),
    "schedule.custom_open": ({"path": "string"}, "EventCount"),
    "schedule.custom_add": ({"event": "ScheduleEvent"}, "EventCount"),
    "schedule.custom_add_days": ({"event": "ScheduleEvent", "days": "string[]"}, "EventCount"),
    "schedule.custom_edit": ({"old": "ScheduleEvent", "new": "ScheduleEvent"}, "EventCount"),
    "schedule.custom_remove": ({"event": "ScheduleEvent"}, "EventCount"),
    "schedule.to_text": ({"events?": "ScheduleEvent[]"}, "string"),
    "schedule.parse_text": ({"text": "string"}, "ParsedSchedule"),
    "schedule.site_check": ({"seen?": "string", "manual?": "boolean"}, "SiteCheck"),
    "notify.post": ({"source": "string", "kind": "string", "title": "string", "text?": "string", "actions?": "any[]",
                     "sound?": "boolean", "repeat_after?": "number|null", "now?": "number"}, "Notification|null"),
    "notify.next": ({"now?": "number"}, "Notification[]"),
    "notify.acknowledge": ({"id": "integer"}, "Acknowledged"),
    "notify.snooze": ({"id": "integer", "seconds": "number", "now?": "number"}, "Acknowledged"),
    "notify.settings": ({"off?": "string[]", "mute?": "string[]", "dnd?": "boolean"}, "Ok"),
    "notify.state": ({}, "NotifyState"),
    "notice.release": ({"found": "string[]|null", "can_install?": "boolean", "current": "string", "seen?": "string"},
                       "Notice|null"),
    "notice.schedule_check": ({"status": "string", "value": "string", "known?": "string", "seen?": "string",
                               "manual?": "boolean"}, "Notice|null"),
    "notice.route": ({"action": "string", "key?": "integer|null", "release_key?": "integer|null",
                      "schedule_key?": "integer|null"}, "string"),
    "settings.read": ({"path": "string"}, "Settings"),
    "settings.save": ({"path": "string", "values": "object"}, "Ok"),
    "bestiary.open": ({"path": "string"}, "BestiaryInfo"),
    "bestiary.search": ({"text?": "string", "category?": "string", "race?": "string", "rank?": "string",
                         "map_id?": "string", "offset?": "integer", "limit?": "integer", "min_level?": "integer|null",
                         "max_level?": "integer|null", "region?": "string", "order?": "string",
                         "hide_low?": "boolean"}, "BestiaryPage"),
    "bestiary.detail": ({"npc_id": "string"}, "object|null"),
    "bestiary.filters": ({}, "BestiaryFilters"),
    "bestiary.regions": ({"map_id?": "string"}, "string[]"),
    "bestiary.areas": ({"npc_id": "string"}, "object[]"),
    "update.check": ({"body": "string", "current?": "string"}, "Release"),
    "telegram.add": ({"lines": "string[]", "now?": "number"}, "Queued"),
    "telegram.poll": ({"now?": "number"}, "TelegramPoll"),
}

_BASIC = {"string", "integer", "number", "boolean", "object", "any", "null"}


# --- type expressions -------------------------------------------------------------------------------------------------
def _python_type(hint) -> str:
    """A type expression for a dataclass field annotation."""
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if hint in (str, Path) or hint is datetime:
        return "string"
    if hint is bool:
        return "boolean"
    if hint is int:
        return "integer"
    if hint is float:
        return "number"
    if dataclasses.is_dataclass(hint):
        return hint.__name__
    if origin in (typing.Union, getattr(__import__("types"), "UnionType")):
        return "|".join(_python_type(a) for a in args)
    if hint is type(None):
        return "null"
    if origin in (list, tuple, set, frozenset):
        inner = [a for a in args if a is not Ellipsis]
        if origin is tuple and len(inner) > 1 and len(set(inner)) > 1:
            return "any[]"
        return (_python_type(inner[0]) + "[]") if inner else "any[]"
    if origin is dict or hint is dict:
        return "object"
    return "any"


def dataclass_shape(cls) -> dict[str, str]:
    hints = typing.get_type_hints(cls)
    return {f.name: _python_type(hints[f.name]) for f in dataclasses.fields(cls)}


def all_shapes() -> dict[str, dict[str, str]]:
    shapes = {cls.__name__: dataclass_shape(cls) for cls in DATACLASSES}
    shapes.update(SHAPES)
    return shapes


def _split(expr: str) -> list[str]:
    return [part.strip() for part in expr.split("|")]


def to_json_schema(expr: str) -> dict:
    options = []
    for part in _split(expr):
        if part.endswith("[]"):
            options.append({"type": "array", "items": to_json_schema(part[:-2])})
        elif part == "any":
            options.append({})
        elif part in _BASIC:
            options.append({"type": part})
        else:
            options.append({"$ref": f"#/$defs/{part}"})
    return options[0] if len(options) == 1 else {"anyOf": options}


def to_typescript(expr: str) -> str:
    names = {"string": "string", "integer": "number", "number": "number", "boolean": "boolean",
             "object": "Record<string, unknown>", "any": "unknown", "null": "null"}
    out = []
    for part in _split(expr):
        if part.endswith("[]"):
            inner = to_typescript(part[:-2])
            out.append(f"({inner})[]" if "|" in inner else f"{inner}[]")
        else:
            out.append(names.get(part, part))
    return " | ".join(out)


def _object_schema(fields: dict[str, str], all_required: bool = False) -> dict:
    props, required = {}, []
    for name, expr in fields.items():
        key = name.rstrip("?")
        props[key] = to_json_schema(expr)
        if all_required or not name.endswith("?"):
            required.append(key)
    return {"type": "object", "properties": props, "required": required}


# --- documents --------------------------------------------------------------------------------------------------------
def json_schema(version: str) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Pulse core API {version}",
        "$defs": {name: _object_schema(fields, False) for name, fields in all_shapes().items()},
        "methods": {name: {"params": _object_schema(params, False), "result": to_json_schema(result)}
                    for name, (params, result) in sorted(METHODS.items())},
    }


def typescript(version: str) -> str:
    lines = [f"// Pulse core API {version}: generated by tools/build_core_schema.py from core/schema.py, do not edit.",
             "// Requests go to `python -m core` / pulse-core.exe as JSON lines: {id, method, params}.", ""]
    for name, fields in all_shapes().items():
        lines.append(f"export interface {name} {{")
        lines += [f"  {field}: {to_typescript(expr)};" for field, expr in fields.items()]
        lines += ["}", ""]
    lines.append("export interface CoreMethods {")
    for name, (params, result) in sorted(METHODS.items()):
        args = "; ".join(f"{p}: {to_typescript(e)}" for p, e in params.items())
        lines.append(f"  \"{name}\": {{ params: {{ {args} }}; result: {to_typescript(result)} }};")
    lines += ["}", "", "export interface CoreRequest<M extends keyof CoreMethods> {",
              "  id: number;", "  method: M;", "  params: CoreMethods[M][\"params\"];", "}", "",
              "export type CoreAnswer<M extends keyof CoreMethods> =",
              "  | { id: number; result: CoreMethods[M][\"result\"] }",
              "  | { id: number | null; error: { type: string; message: string } };", ""]
    return "\n".join(lines)


def check_params(method: str, params: dict) -> list[str]:
    """Problems of a request against the schema: unknown or missing parameters (types are not checked)."""
    declared = METHODS[method][0]
    names = {name.rstrip("?") for name in declared}
    required = {name for name in declared if not name.endswith("?")}
    return [f"unknown parameter {key}" for key in params if key not in names] + \
           [f"missing parameter {key}" for key in required if key not in params]


def write(folder: Path, version: str) -> tuple[Path, Path]:
    """Write api.schema.json and api.d.ts into `folder` (the core folder)."""
    schema, types = Path(folder) / "api.schema.json", Path(folder) / "api.d.ts"
    schema.write_text(json.dumps(json_schema(version), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    types.write_text(typescript(version), encoding="utf-8")
    return schema, types
