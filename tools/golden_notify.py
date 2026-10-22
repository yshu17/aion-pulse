"""Golden results of core/notify for the TypeScript port (written by tools/golden_gen.py into tests/golden/notify*.json).

The notification center keeps queue, history, repeats and snoozes between calls, so its scenario is a list of
operations with their results; the clock is a value the scenario sets. `created_at` (the wall clock) is left out.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace


def note(event):
    if event is None:
        return None
    data = {f.name: getattr(event, f.name) for f in dataclasses.fields(event) if f.name != "created_at"}
    data["actions"] = [[a.id, a.label] for a in event.actions]
    return data


def center_cases() -> dict:
    from core.notify.notify_center import NotificationAction, NotificationCenter

    clock = [0.0]
    sounds: list[int] = []
    c = NotificationCenter(sound=lambda e: sounds.append(e.id), clock=lambda: clock[0], max_history=6, max_queue=3)
    ops = [
        ["notify", "chat", "chat", "Найдено", "A: wts", [["accept", "Принять"]], True, None],
        ["notify", "schedule", "event", "Через 5 мин", "20:00", [], True, 180],
        ["state"],
        ["pop"], ["pop"], ["pop"],
        ["source", "chat", False, None],
        ["notify", "chat", "chat", "Скрыто", "", [], True, None],
        ["source", "chat", True, False],
        ["notify", "chat", "chat", "Без звука", "", [], True, None],
        ["notify", "status", "warning", "Игра", "", [], False, None],
        ["clock", 100.0], ["tick"], ["clock", 180.0], ["tick"], ["state"],
        ["pop"], ["pop"],
        ["snooze", 2, 30.0], ["clock", 200.0], ["tick"], ["clock", 210.0], ["tick"], ["pop"],
        ["ack", 2], ["clock", 400.0], ["tick"], ["ack", 999],
        ["dnd", True], ["notify", "chat", "chat", "Тихо", "", [], True, None], ["pop"], ["state"], ["dnd", False],
        ["notify", "chat", "chat", "Один", "", [], True, None],
        ["notify", "chat", "chat", "Два", "", [], True, None],
        ["notify", "chat", "chat", "Три", "", [], True, None],
        ["notify", "chat", "chat", "Четыре", "", [], True, None],
        ["state"], ["pop"], ["pop"], ["pop"], ["pop"],
        ["notify", "", "chat", "x", "", [], True, None],
        ["notify", "chat", "chat", "x", "", [], True, -1],
        ["snooze", 13, 0],
        ["snooze", 13, 5], ["clock", 405.0], ["tick"], ["pop"],
        # a repeating reminder nobody answers: it comes back every repeat_after, again and again
        ["notify", "schedule", "event", "Повтор", "", [], True, 50], ["pop"],
        ["clock", 455.0], ["tick"], ["pop"], ["clock", 505.0], ["tick"], ["pop"], ["clock", 530.0], ["tick"],
        ["state"], ["counts"], ["sounds"],
    ]
    out = []
    for op in ops:
        kind = op[0]
        try:
            if kind == "notify":
                actions = [NotificationAction(a, label) for a, label in op[5]]
                result = note(c.notify(op[1], op[2], op[3], op[4], actions, sound=op[6], repeat_after=op[7]))
            elif kind == "pop":
                result = note(c.pop_next())
            elif kind == "source":
                c.set_source(op[1], enabled=op[2], sound=op[3])
                result = None
            elif kind == "clock":
                clock[0] = op[1]
                result = None
            elif kind == "tick":
                result = c.tick()
            elif kind == "snooze":
                result = c.snooze(op[1], op[2])
            elif kind == "ack":
                result = c.acknowledge(op[1])
            elif kind == "dnd":
                c.do_not_disturb = op[1]
                result = None
            elif kind == "state":
                result = {"queued": c.queued, "unread": c.unread, "history": [e.id for e in c.history],
                          "rules": {k: [r.enabled, r.sound] for k, r in c.rules.items()}}
            elif kind == "counts":
                result = {"all": c.count(), "chat": c.count("chat"), "schedule": c.count("schedule"),
                          "none": c.count("nope")}
            else:
                result = list(sounds)
        except ValueError as error:
            result = {"error": str(error)}
        out.append(op + [result])
    return {"max_history": 6, "max_queue": 3, "ops": out}


def bridge_cases() -> dict:
    from core.notify.alert_bridge import AlertBridge
    from core.notify.notify_center import NotificationCenter

    c = NotificationCenter(clock=lambda: 0.0)
    b = AlertBridge(c)
    ops = []
    n1 = b.chat_match([1, 2], [("Nag", "wts 1/12", ["wts"]), ("B", "ищу", ["ищу группу", "wts"])], nag=True)
    ops.append(["chat_match", [1, 2], [["Nag", "wts 1/12", ["wts"]], ["B", "ищу", ["ищу группу", "wts"]]], True, note(n1)])
    n2 = b.chat_match([], [("C", "wts лук", ["wts"])], nag=False)
    ops.append(["chat_match", [], [["C", "wts лук", ["wts"]]], False, note(n2)])
    ops.append(["chat_match", [5], [], True, note(b.chat_match([5], [], nag=True))])
    ops.append(["alerts_done", [1], [e.id for e in c.history if (e.repeat_key or e.id) not in c._acknowledged]])
    b.alerts_done([1])
    ops.append(["active", [c.is_active(e) for e in c.history]])
    b.alerts_done([2])
    ops.append(["after_done_2", [c.is_active(e) for e in c.history]])
    n3 = b.chat_match([7, 8], [("D", "x", ["wts"])], nag=True)
    ops.append(["chat_match", [7, 8], [["D", "x", ["wts"]]], True, note(n3)])
    ops.append(["toast_accepted", n3.id, b.toast_accepted(n3)])
    ops.append(["toast_accepted_again", n3.id, b.toast_accepted(n3)])
    ops.append(["toast_accepted_none", b.toast_accepted(None)])
    g1 = b.game_running(False)
    ops.append(["game_running", False, note(g1)])
    ops.append(["game_running", False, note(b.game_running(False))])
    ops.append(["game_running", True, note(b.game_running(True)), c.is_active(g1)])
    ops.append(["game_running", True, note(b.game_running(True))])
    ops.append(["game_running", False, note(b.game_running(False))])
    return {"ops": ops}


def settings_cases() -> dict:
    from core.notify.notify_center import NotificationCenter
    from core.notify.notify_settings import CORNERS, DEFAULT_CORNER, DEFAULT_DURATION, DEFAULT_STACK, DURATIONS, \
        SOURCES, STACK, apply

    out = []
    for cfg in [
        dict(notify_off=[], notify_mute=[], notify_dnd=False, notify_corner="bottom", notify_duration=8, notify_stack=3),
        dict(notify_off=["chat"], notify_mute=["schedule", "nope"], notify_dnd=True, notify_corner="top",
             notify_duration=15, notify_stack=1),
        dict(notify_off=[], notify_mute=[], notify_dnd=False, notify_corner="left", notify_duration=7, notify_stack=9),
    ]:
        c = NotificationCenter(clock=lambda: 0.0)
        m = SimpleNamespace(corner=None, duration=None, max_visible=None)
        apply(SimpleNamespace(**cfg), c, m)
        apply(SimpleNamespace(**cfg), c)  # without a toast window
        out.append([cfg, {k: [r.enabled, r.sound] for k, r in c.rules.items()}, c.do_not_disturb,
                    [m.corner, m.duration, m.max_visible]])
    return {"cases": out, "sources": [list(s) for s in SOURCES], "corners": CORNERS, "durations": list(DURATIONS),
            "stack": list(STACK), "defaults": [DEFAULT_CORNER, DEFAULT_DURATION, DEFAULT_STACK]}


def notice_cases() -> dict:
    from core.notify.notices import release_notice, route_action, schedule_check_notice
    from core.schedule.schedule_update import decide, fingerprint, known_fingerprint
    from core.update.updater import latest_release, newer, parse_version

    def plain_notice(n):
        return None if n is None else {"source": n.source, "kind": n.kind, "title": n.title, "text": n.text,
                                       "actions": [list(a) for a in n.actions]}

    releases = [[None, True, "1.2.0", ""], [["v1.2.0", "u"], True, "1.2.0", ""], [["v1.3.0", "u"], True, "1.2.0", "v1.3.0"],
                [["v1.3.0", "u"], True, "1.2.0", ""], [["v1.3.0", "u"], False, "1.2.0", ""], [["1.10", "u"], False, "1.9.9", ""]]
    checks = [[s, v, k, seen, manual] for s, v in (("ok", "a"), ("ok", "b"), ("err", "timeout " * 30))
              for k in ("a",) for seen in ("", "b") for manual in (False, True)]
    routes = [[a, key, rk, sk] for a in ("site", "install", "release", "accept", "retry", "open", "other")
              for key in (5, 9, 3, None) for rk in (5, None) for sk in (9, None)]
    return {
        "release": [r + [plain_notice(release_notice(tuple(r[0]) if r[0] else None, r[1], r[2], r[3]))] for r in releases],
        "schedule_check": [c + [plain_notice(schedule_check_notice(*c))] for c in checks],
        "route": [r + [route_action(*r)] for r in routes],
        "decide": [[k, cur, seen, m, decide(k, cur, seen, m)] for k in ("a",) for cur in ("a", "b") for seen in ("", "b")
                   for m in (False, True)],
        "fingerprint": [fingerprint("https://x/a/schedule-20ru.jpg", '"e"', "Sun"),
                        known_fingerprint({"image": "schedule-20ru.jpg", "image_etag": '"e"', "image_modified": "Sun"}),
                        known_fingerprint({})],
        "versions": [[t, list(parse_version(t))] for t in ("v1.2.10", "1.2", "V2", "1.x.3", "", " v3.0.1 ")],
        "newer": [[a, b, newer(a, b)] for a, b in (("v1.10.0", "1.9.9"), ("1.0.0", "v1.0.0"), ("1.2", "1.2.0"),
                                                  ("1.2.1", "1.2"))],
        "latest": [[body, None if (r := latest_release(body)) is None else list(r)] for body in
                   ('{"tag_name": "v1.1.0", "html_url": "u"}', "{}", '{"tag_name": "v1"}')],
    }


def all_cases() -> dict[str, dict]:
    return {"notify_center": center_cases(), "notify_bridge": bridge_cases(), "notify_settings": settings_cases(),
            "notify_notices": notice_cases()}
