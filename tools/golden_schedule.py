"""Golden results of core/schedule for the TypeScript port (written by tools/golden_gen.py into tests/golden/schedule*.json;
the own-events file is schedule_edits.json, since .gitignore hides schedule_custom.json).

Naive datetimes travel as [year, month, day, hour, minute, second] and come back as `isoformat()` strings; a time zone
is its UTC offset in minutes. The events are the real data/schedule.json plus a few made-up edge cases (a zero-length
event, «24:00», an end before the start, a Sunday overnight run, places on the map).
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXTRA = [
    {"day": "sun", "start": "23:30", "end": "01:30", "name": "Ночной рейд", "kind": "Рейд"},
    {"day": "mon", "start": "00:00", "end": "24:00", "name": "Весь день", "group": "Свои группы"},
    {"day": "tue", "start": "09:00", "end": "09:00", "name": "Откат"},
    {"day": "wed", "start": "12:15", "end": "12:45", "name": "Осада крепости", "maps": ["210050000", "220070000"]},
    {"day": "wed", "start": "12:30", "end": "13:00", "name": "Дер", "maps": ["220070000"]},
    {"day": "thu", "start": "18:00", "end": "19:00", "name": "PVP турнир", "kind": "PVP 1x1", "maps": ["300100000"]},
    {"day": "fri", "start": "18:00", "end": "18:30", "name": "Пустой вид", "kind": ""},
]
TZS = [-330, -300, 0, 120, 180, 345, 600]
NOWS = [[2026, 10, 19, 0, 30, 0], [2026, 10, 19, 1, 29, 59], [2026, 10, 20, 8, 58, 0], [2026, 10, 21, 12, 20, 15],
        [2026, 10, 22, 19, 55, 0], [2026, 10, 25, 23, 59, 0], [2026, 10, 25, 23, 30, 0], [2024, 2, 29, 13, 59, 30]]


def dt(parts):
    return datetime(*parts)


def iso(value):
    return value.isoformat()


def zone(minutes):
    return timezone(timedelta(minutes=minutes))


def events():
    data = json.loads((ROOT / "data" / "schedule.json").read_text(encoding="utf-8"))
    return data["events"] + EXTRA


def timing_cases() -> dict:
    from core.schedule import timing as t

    tmp = Path(tempfile.mkdtemp())
    texts = [None, "{bad", "[1, 2]", '{"events": "ab"}', '{"events": {"x": 1}}', "{}",
             json.dumps({"events": EXTRA[:2]}, ensure_ascii=False)]
    loads = []
    for i, text in enumerate(texts):
        path = tmp / f"s{i}.json"
        if text is not None:
            path.write_text(text, encoding="utf-8")
        loads.append([text, t.load_events(path)])
    utc = [[2026, 10, 22, 21, 30, 5], [2026, 12, 31, 22, 0, 0], [2027, 1, 1, 0, 0, 0]]
    ends = [[e, s, iso(t.end_of(e, dt(s)))] for e in EXTRA + [{"end": "04:00"}, {"end": "02:00"}, {"end": "00:00"}]
            for s in ([2026, 10, 19, 2, 0, 0], [2026, 10, 25, 23, 30, 0])]
    untils = []
    for now in ([2026, 10, 22, 20, 35, 30], [2026, 10, 22, 19, 20, 0], [2026, 10, 22, 17, 0, 0],
                [2026, 10, 22, 19, 59, 59], [2026, 10, 22, 21, 0, 0], [2026, 10, 21, 20, 0, 0],
                [2026, 10, 21, 19, 0, 0], [2026, 10, 20, 20, 0, 0], [2026, 10, 20, 19, 59, 0],
                [2026, 10, 18, 20, 0, 0], [2026, 10, 22, 20, 0, 0]):
        s, e = [2026, 10, 22, 20, 0, 0], [2026, 10, 22, 21, 0, 0]
        untils.append([s, e, now, t.until_text(dt(s), dt(e), dt(now))])
    msk = [2026, 10, 22, 20, 0, 0]
    return {
        "load": loads,
        "msk_now": [[u, iso(t.msk_now(dt(u).replace(tzinfo=timezone.utc)))] for u in utc],
        "to_local": [[n, z, iso(t.to_local(dt(n), zone(z)).replace(tzinfo=None))] for n in NOWS for z in TZS],
        "end_of": ends,
        "until": untils,
        "zone_name": [[z, t.zone_name(dt(msk), zone(z))] for z in TZS + [-60, 30, 181]],
        "bell_key": [t.bell_key(e) for e in EXTRA],
        "lead_label": [[m, t.lead_label(m)] for m in (5, 15, 30, 60, 7, 0)],
        "leads": [[k, v] for k, v in t.LEADS.items()],
        "time_range": [[s, z, t.time_range(dt(s), t.end_of(EXTRA[0], dt(s)), zone(z))] for s in NOWS for z in TZS],
        "today_key": [[n, t.today_key(dt(n))] for n in NOWS],
        "day_names": t.DAY_NAMES, "days_order": list(t.DAYS_ORDER), "default_lead": t.DEFAULT_LEAD,
    }


def reminder_cases() -> dict:
    from core.schedule import reminders as r

    evs = events()
    due = []
    for n in NOWS + [[2026, 10, 22, 19, 45, 0], [2026, 10, 22, 13, 55, 0]]:
        for lead in (0, 5, 15, 60):
            found = r.due_reminders(evs, dt(n), lead, set())
            due.append([n, lead, [[k, e["name"], iso(at)] for k, e, at in found]])
    first = r.due_reminders(evs, dt([2026, 10, 22, 19, 45, 0]), 15, set())
    sent = {first[0][0]} if first else set()
    try:
        r.due_reminders(evs, dt(NOWS[0]), -1, set())
        error = None
    except ValueError as e:
        error = str(e)
    between = [[a, b, [[e["name"], iso(at)] for e, at in r.occurrences_between(evs, dt(a), dt(b))]]
               for a, b in ([[2026, 10, 18, 22, 0, 0], [2026, 10, 19, 11, 0, 0]],
                            [[2026, 10, 22, 13, 0, 0], [2026, 10, 22, 13, 0, 0]],
                            [[2026, 10, 22, 13, 0, 0], [2026, 10, 22, 14, 0, 0]],
                            [[2026, 10, 1, 0, 0, 0], [2026, 10, 2, 0, 0, 0]])]
    return {
        "events": evs,
        "starts_at": [[e, iso(r.starts_at(e, dt([2026, 10, 19, 0, 0, 0])))] for e in EXTRA],
        "week_start": [[n, iso(r.week_start(dt(n)))] for n in NOWS],
        "due": due,
        "due_sent": [sorted(sent), [k for k, _, _ in r.due_reminders(evs, dt([2026, 10, 22, 19, 45, 0]), 15, sent)]],
        "error": error,
        "between": between,
    }


def view_cases() -> dict:
    from core.schedule import schedule_view as v

    evs = events()
    nxt = [[n, limit, [[e["name"], iso(at)] for e, at in v.next_events(evs, dt(n), limit)]]
           for n in NOWS for limit in (0, 1, 3, 8)]
    nxt.append([NOWS[0], 3, [[e["name"], iso(at)] for e, at in v.next_events(EXTRA[:1], dt(NOWS[0]), 3)]])
    labels = [[d, n, t, v.day_label(d, dt(n), dt(t))] for d in v.DAYS for n, t in
              ((NOWS[2], NOWS[2]), (NOWS[2], NOWS[3]), (NOWS[5], NOWS[5]), (NOWS[7], NOWS[7]))]
    hidden = [set(), {"Осады", "Прочее"}, {"PVP арена", "Свои группы"}]
    return {
        "by_day": {d: [e["name"] + " " + e["start"] for e in v.events_for_day(evs, d)] for d in v.DAYS},
        "today": [[n, [e["name"] for e in v.today_events(evs, dt(n))]] for n in NOWS],
        "next": nxt,
        "kinds": v.kinds(evs),
        "kind_of": [v.kind_of(e) for e in EXTRA],
        "visible": [len(v.visible(evs, {"Арены", "Рейд"})), len(v.visible(evs, set()))],
        "map_for": [[e.get("maps"), side, v.map_for(e, side)] for e in EXTRA for side in ("dark", "light")],
        "blocks": {d: [[e["name"], s, en, lane] for e, s, en, lane in v.day_blocks(v.events_for_day(evs, d))]
                   for d in v.DAYS},
        "groups": [v.groups(evs), v.groups(EXTRA), v.groups([])],
        "group_of": [[e["name"], v.group_of(e)] for e in evs],
        "group_hidden": [[sorted(h), [e["name"] for e in v.group_hidden(evs, h)]] for h in hidden],
        "day_label": labels,
        "clock_pair": [[u, z, list(v.clock_pair(dt(u).replace(tzinfo=timezone.utc), zone(z)))]
                       for u in ([2026, 10, 22, 21, 30, 5], [2026, 10, 22, 0, 0, 59]) for z in TZS],
        "group_names": list(v.GROUPS), "day_short": v.DAY_SHORT,
    }


def flow_cases() -> dict:
    from core.schedule.reminder_flow import MISSED_DAYS, START_WINDOW_S, ReminderPlanner, missed_events, missed_text

    belled = [e for e in events() if e["day"] == "thu" and e["start"] in ("20:00", "21:00")] + EXTRA[:1] + EXTRA[2:3]
    runs = []
    for lead, tz, start, steps in ((5, 180, [2026, 10, 22, 19, 50, 0], 50), (15, 120, [2026, 10, 22, 19, 40, 10], 50),
                                   (60, -330, [2026, 10, 25, 22, 20, 0], 120), (5, 600, [2026, 10, 20, 8, 50, 0], 40)):
        planner = ReminderPlanner()
        out = []
        for i in range(steps):
            now = dt(start) + timedelta(seconds=30 * i)
            for rem in planner.due(belled, now, lead, zone(tz)):
                out.append([iso(now), rem.key, rem.title, rem.text, rem.event["name"], iso(rem.start), iso(rem.end)])
        runs.append([lead, tz, start, steps, out])
    missed = []
    for last, now in ((None, [2026, 10, 22, 20, 0, 0]), ([2026, 10, 22, 19, 0, 0], [2026, 10, 22, 21, 1, 0]),
                      ([2026, 10, 22, 19, 0, 0], [2026, 10, 22, 21, 2, 0]), ([2026, 9, 1, 0, 0, 0], [2026, 10, 22, 21, 30, 0]),
                      ([2026, 10, 25, 23, 0, 0], [2026, 10, 26, 9, 5, 0])):
        found = missed_events(belled, None if last is None else dt(last), dt(now))
        texts = [list(missed_text(found, zone(z))) for z in (180, -330)] + [list(missed_text(found, zone(0), 2))]
        missed.append([last, now, [[e["name"], iso(at)] for e, at in found], texts])
    return {"belled": belled, "runs": runs, "missed": missed, "consts": [MISSED_DAYS, START_WINDOW_S],
            "max_days": [[e["name"], iso(at)] for e, at in
                         missed_events(belled, dt([2026, 9, 1, 0, 0, 0]), dt([2026, 10, 22, 21, 30, 0]), max_days=2)]}


def custom_cases() -> dict:
    from core.schedule.schedule_custom import Custom, check, event_key, parse_text, to_text

    tmp = Path(tempfile.mkdtemp())
    path = tmp / "schedule_custom.json"
    base = events()
    c = Custom.load(path)
    ops = []

    def step(name, *args):
        getattr(c, name)(*args)
        merged = c.merge(base)
        ops.append([name, list(args), path.read_text(encoding="utf-8"),
                    [[e["day"], e["start"], e["name"], e.get("kind")] for e in merged][-6:], len(merged)])

    step("add", {"day": "fri", "start": "19:30", "end": "20:30", "name": "  Рейд ", "group": "Мои", "color": "",
                 "extra": 1})
    step("add", {"day": "fri", "start": "19:30", "end": "21:00", "name": "Рейд", "color": "Синий"})
    step("add_days", {"day": "mon", "start": "07:00", "end": "07:30", "name": "Зарядка"}, ["mon", "wed", "sun"])
    step("remove", base[0])
    step("remove", base[0])
    step("remove", {"day": "wed", "start": "07:00", "end": "07:30", "name": "Зарядка"})
    step("edit", base[25], {**base[25], "start": "20:15", "name": "Осада (моя)"})
    step("add", {"day": "mon", "start": "20:00", "end": "21:30", "name": base[25]["name"]})
    nopath = Custom(None)
    nopath.add({"day": "sat", "start": "10:00", "end": "11:00", "name": "x"})

    loads = []
    for text in [None, "{bad", "[]", '{"added": {}, "removed": []}', '{"added": [{"day": "xx"}], "removed": []}',
                 '{"added": [], "removed": [1]}', '{"removed": ["mon|02:00|A"]}',
                 json.dumps({"added": [{"day": "fri", "start": "10:00", "end": "11:00", "name": "A", "n": 1},
                                       {"day": "fri", "start": "12:00", "end": "13:00", "name": "B"},
                                       {"day": "fri", "start": "10:00", "end": "12:00", "name": "A", "n": 2}],
                             "removed": ["x"], "other": 5}, ensure_ascii=False)]:
        p = tmp / "load.json"
        if p.exists():
            p.unlink()
        if text is not None:
            p.write_text(text, encoding="utf-8")
        loads.append([text, Custom.load(p).data])
    checks = [{"day": "mon", "start": "19:30", "end": "20:30", "name": "x"},
              {"day": "Mon", "start": "19:30", "end": "20:30", "name": "x"},
              {"start": "19:30"}, {"day": "mon", "start": "9:30", "end": "20:30", "name": "x"},
              {"day": "mon", "start": "24:00", "end": "20:30", "name": "x"},
              {"day": "mon", "start": "19:30", "end": "24:00", "name": "x"},
              {"day": "mon", "start": "19:30", "end": "24:01", "name": "x"},
              {"day": "mon", "start": "19:30", "end": "20:60", "name": "x"},
              {"day": "mon", "start": "19:30", "end": "20:30", "name": "   "},
              {"day": "mon", "start": "19:30", "end": "20:30"},
              {"day": "mon", "start": "19:30", "end": "20:30", "name": 0},
              {"day": "mon", "start": "19:30\n", "end": "20:30", "name": "x"}]
    texts = ["пн 20:00-21:00 Осада\n\nВТ 9:00 – 10:00  Утро  \nчт 25:00-26:00 Плохо\nхм\r\nсб 10:00-11:00 "
             "вс 01:00-02:00 Ночь", "", "  \n", "Пн 20:00 -21:00 A\x0bср 10:00-11:00 B"]
    return {
        "ops": ops, "loads": loads, "nopath": nopath.data,
        "checks": [[e, check(e)] for e in checks],
        "keys": [event_key(e) for e in EXTRA],
        "to_text": [to_text(EXTRA), to_text(base[:12]), to_text([])],
        "parse": [[t, *parse_text(t)] for t in texts],
    }


def all_cases() -> dict[str, dict]:
    return {"schedule_timing": timing_cases(), "schedule_reminders": reminder_cases(), "schedule_view": view_cases(),
            "schedule_flow": flow_cases(), "schedule_edits": custom_cases()}
