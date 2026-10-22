"""Golden results of core/chat for the TypeScript port (written by tools/golden_gen.py into tests/golden/chat*.json).

Scenarios are lists of operations with their results, so the port replays them step by step: the matcher's
cooldown, the repeat series, pending alerts and the log tail all keep state between steps.
"""

from __future__ import annotations

import base64
import dataclasses
import os
import tempfile
from datetime import datetime
from pathlib import Path

NAMES = {"110600968": "Кираса Рудры", "100000001": "Меч Циркулоса", "155007142": "Рецепт: клик",
         "186000163": "Монета"}
MAPS = {"220070000": "Келькмарос", "210050000": "Ингисон"}
QUESTS = {"2058": "Уничтожение повстанцев Ривара"}

LINES = [
    "2026.10.08 18:43:17 : [3.Поиск группы] [charname:Tiyamate;1.0000 0.6941 0.6941]: [cmd:Tiyamate;sx+=]WTB MMK 2.2KK SM+++ ",
    "2026.10.08 18:42:00 : [3.Поиск группы] [charname:Roflo;1.0000 0.6941 0.6941]: wts [item:110600968;ver2;;;][item:999;ver2;;;] вставка ",
    "2026.10.08 18:42:08 : [3.Поиск группы] [charname:Flomaster;1.0000 0.6941 0.6941]: А ангир будут исправлять?\r\n",
    "2026.10.08 18:42:29 : Бешеный ветер I: Скор. движ. цели Mockoco увеличивается. ",
    "2026.10.08 18:42:29 : [1.Общий] [charname:Someone;1.0000 1.0000 1.0000]: хил нужен",
    "2026.10.08 14:49:06 : [charname:Flama;0.0196 0.7843 0.8431]: 2 глада, чант? ",
    "2026.10.08 00:19:59 : [charname:Pyro;0.6275 1.0000 0.6275] шепчет: DP S? ",
    "2026.10.08 14:50:49 : [3.Поиск группы] Sexbomb: [cmd:S;KU9=]ищу +1 SUP ",
    "2026.10.08 14:50:49 : [3.????? ??????] Sexbomb: ищу хила ",
    "2026.10.09 14:52:29 : [pos:Место;220070000 1 2 0 0] тут",
    "2026.10.09 14:52:30 : [3.Поиск группы] [charname:Pin;1 1 1]: [pos:Место;220070000 2010.1 1315.8 0.0 0] [pos:Босс;0 210050000 978.8 1265.0 0.0 0] [pos:;999 1 2 0 0]",
    "2026.10.09 14:52:31 : [3.Поиск группы] [charname:Q;1 1 1]: кв [quest:2058] и [quest:99999999] лег [where:sweet bunny] [recipe:155007142;0] [item_ex:186000163;Tw] го? ?? ??? ????",
    "2026.10.09 14:52:32 : [3.Поиск группы] [charname:Cut;1 1 1]: [where:Вступай в легион][where:Окунись в PVE!!!] [where:Любой лвл!!!Г ",
    "2026.10.09 14:52:33 : [3.Поиск группы] [charname:Cut2;1 1 1]: wts [item:100000893;ver2",
    "2026.10.09 14:52:34 : [Event] PvP Team Arena 1x1 registration is open! ",
    "2026.10.09 14:52:35 : Вы получили 100 кинар.",
    "2026.10.09 14:52:36 : [charname:Leg;0.6118 0.9059 0.8627]: в легион",
    "2026.10.09 14:52:37 : [2.Торговля] [charname:Tr;1 1 1]: wts всё",
    "[3.Поиск группы] без даты",
    "",
    "2026.13.40 99:99:99 : [3.Поиск группы] [charname:Bad;1 1 1]: странная дата",
    "2026.10.09 14:52:38 : [3.Поиск группы] [charname:Long;1 1 1] кричит: ЁЛКА   и    пробелы  [item:;ver2;;;] ",
]


def plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, set):
        return sorted(plain(v) for v in value)
    return value


def parser_cases() -> dict:
    from core.chat.categories import category, is_notice
    from core.chat.parser import clean_text, display_text, parse_any_line, parse_line, places_in, split_place

    out = []
    for line in LINES:
        parsed = parse_any_line(line, NAMES, maps=MAPS, quests=QUESTS)
        out.append({
            "line": line,
            "any": plain(parsed),
            "is_player": None if parsed is None else parsed.is_player,
            "lfg": plain(parse_line(line, NAMES, maps=MAPS, quests=QUESTS)),
            "bare": plain(parse_any_line(line)),
            "display": None if parsed is None else display_text(parsed.text),
            "places": None if parsed is None else plain(places_in(parsed.text)),
            "category": None if parsed is None else category(parsed),
            "notice": None if parsed is None else is_notice(parsed),
        })
    texts = ["  [cmd:X;abc=]Хил [item:1;ver2;;;] ", "[item:1;ver2;;;] и [item:2;ver2;;;]", "wts [item:100000893;ver2",
             "кв [quest:99999999]", "a ??? b    c", "[where:  ]", "[where:x"]
    return {
        "lines": out,
        "clean": [[t, clean_text(t), clean_text(t, {"2": "Меч Фланаса"}, maps=MAPS, quests=QUESTS)] for t in texts],
        "split_place": [[s, plain(split_place(s))] for s in
                        ["Место · Келькмарос¦220070000 2010.1 1315.8", "sweet bunny", "x¦bad", "x¦1 2", "x¦1 a b"]],
    }


def matcher_cases() -> dict:
    from core.chat.matcher import Matcher, highlight_segments, normalize
    from core.chat.parser import ChatMessage

    def msg(nick, text, ids=()):
        return ChatMessage("2026.10.08 18:00:00", nick, text, "", tuple(ids))

    steps = []
    m = Matcher([" WTS ", "ищу ГРУППУ", "", "wts", "ёлка"], 60, watch_items={"7": "Кираса Рудры"}, mode="or")
    steps.append(["keywords", m.keywords])
    script = [
        ("check", msg("A", "WTS меч"), 0), ("check", msg("A", "wts меч"), 30), ("check", msg("A", "wts меч"), 61),
        ("check", msg("B", "Ищу группу в бездну"), 61), ("check", msg("C", "продам", ["7", "7"]), 62),
        ("check", msg("D", "Елка в лесу"), 63), ("check", msg("E", "ничего"), 64),
        ("mode", "words"), ("check", msg("F", "wts [Кираса]", ["7"]), 65),
        ("mode", "items"), ("check", msg("G", "wts", ["7"]), 66), ("check", msg("G2", "wts"), 66),
        ("mode", "and"), ("check", msg("H", "wts", ["7"]), 67), ("check", msg("I", "wts"), 67),
        ("check", msg("J", "x", ["7"]), 67), ("mode", "nonsense"), ("check", msg("K", "wts кираса рудры", ["7"]), 68),
        ("items", {}), ("check", msg("L", "кираса", ["7"]), 69), ("keywords", ["кираса"]),
        ("check", msg("M", "КИРАСА рудры"), 70),
    ]
    for op in script:
        if op[0] == "check":
            steps.append(["check", plain(op[1]), op[2], m.check(op[1], op[2])])
        elif op[0] == "mode":
            m.set_mode(op[1])
            steps.append(["mode", op[1], m.mode])
        elif op[0] == "items":
            m.set_watch_items(op[1])
            steps.append(["items", op[1]])
        else:
            m.set_keywords(op[1])
            steps.append(["keywords", op[1], m.keywords])
    purge = Matcher(["w"], 10)
    for i in range(1001):
        purge.check(msg(f"N{i}", "w"), float(i))
    purge_result = [purge.check(msg("N0", "w"), 1001.0), purge.check(msg("N1000", "w"), 1001.0), len(purge._seen)]
    return {
        "steps": steps,
        "purge": purge_result,
        "normalize": [[t, normalize(t)] for t in ["ЁЛКА Ёж", "ABC", "Ёё"]],
        "highlight": [[t, k, plain(highlight_segments(t, k))] for t, k in [
            ("WTS меч, wts щит", ["wts"]), ("Ёлка и елка", ["елка"]), ("abc", ["", "  "]), ("ааа", ["аа"]),
            ("x", []), ("", ["a"])]],
    }


def session_cases() -> dict:
    from core.chat.session import WatchSession

    def lfg(nick, text, at="2026.10.20 18:00:00"):
        return f"{at} : [3.Поиск группы] [charname:{nick};1.0000 0.6941 0.6941]: {text} "

    s = WatchSession(NAMES, MAPS, QUESTS, keywords=["wts", "ищу группу"], watch_items={"110600968": "Кираса Рудры"},
                     cooldown_sec=0, alert_mode="nag", react_sec=10)
    ops = [
        ["history", [lfg("Old", "wts щит"), lfg("Pin", "тут [pos:Место;220070000 2010.1 1315.8 0.0 0]"), "мусор"], 0.0],
        ["process", [lfg("A", "wts 1/12"), lfg("B", "ищу группу"), lfg("C", "[item:110600968;ver2;;;] 2kk")], 1.0],
        ["state", 2.0],
        ["accept", 1],
        ["process", [lfg("A", "wts 2/12")], 3.0],
        ["state", 3.0],
        ["accept", 99],
        ["expire", 11.5],
        ["state", 12.0],
        ["process", [lfg("D", "wts лук"), lfg("A", "wts 3/12")], 13.0],
        ["accept_all"],
        ["mode", "standard"],
        ["process", [lfg("E", "wts шлем"), lfg("F", "просто текст")], 14.0],
        ["state", 14.0],
        ["stop"],
        ["mode", "nag"],
        ["process", [lfg("A", "wts 4/12")], 15.0],
        ["reset"],
        ["state", 15.0],
        ["keywords", ["шлем"]],
        ["items", {}],
        ["process", [lfg("G", "wts шлем"), lfg("H", "[item:110600968;ver2;;;]")], 16.0],
        ["mode", "bogus"],
        ["process", [lfg("I", "шлем")], 17.0],
    ]
    out = []
    for op in ops:
        kind = op[0]
        if kind in ("history", "process"):
            batch = getattr(s, kind)(op[1], op[2])
            out.append(op + [{**plain(batch), "loud": plain(batch.loud)}])
        elif kind == "state":
            out.append(op + [{"counters": list(s.counters), "pending": s.pending_ids, "remaining": plain(s.remaining(op[1]))}])
        elif kind == "accept":
            out.append(op + [s.accept(op[1])])
        elif kind == "accept_all":
            out.append(op + [s.accept_all()])
        elif kind == "expire":
            out.append(op + [s.expire(op[1])])
        elif kind == "mode":
            s.set_alert_mode(op[1])
            out.append(op + [s.alert_mode])
        elif kind == "stop":
            s.stop()
            out.append(op + [None])
        elif kind == "reset":
            s.reset_counters()
            out.append(op + [None])
        elif kind == "keywords":
            s.set_keywords(op[1])
            out.append(op + [None])
        elif kind == "items":
            s.set_watch_items(op[1])
            out.append(op + [None])
    return {"init": {"keywords": ["wts", "ищу группу"], "watch_items": {"110600968": "Кираса Рудры"}, "cooldown_sec": 0,
                     "alert_mode": "nag", "react_sec": 10}, "ops": out}


def series_cases() -> dict:
    from core.chat.parser import ChatMessage
    from core.chat.series import SeriesTracker

    t = SeriesTracker(limit=3, idle_sec=100)

    def msg(nick):
        return ChatMessage("x", nick, "t", "")

    ops = []
    for step in [("record", " Nag ", [" WTS "], 0, 1), ("silent", "nag", ["wts"], 1), ("accept", 1),
                 ("silent", "NAG", ["wts", "x"], 2), ("silent", "nag", ["wts"], 2), ("record", "nag", ["wts"], 3, None),
                 ("record", "nag", ["wts"], 4, 2), ("silent", "nag", ["wts"], 5), ("record", "nag", ["wts"], 6, 3),
                 ("silent", "nag", ["wts"], 7), ("accept", 3), ("silent", "nag", ["wts"], 8),
                 ("silent", "nag", ["wts"], 200), ("keys", "  Ник ", [" a ", "A", "", "b"]), ("silent", "x", [], 1)]:
        if step[0] == "record":
            t.record(msg(step[1]), step[2], step[3], step[4])
            ops.append(list(step) + [None])
        elif step[0] == "silent":
            ops.append(list(step) + [t.is_silent(msg(step[1]), step[2], step[3])])
        elif step[0] == "accept":
            ops.append(list(step) + [sorted(t.accept(step[1]))])
        else:
            ops.append(list(step) + [plain(t.keys(msg(step[1]), step[2]))])
    return {"limit": 3, "idle_sec": 100, "ops": ops}


def segment_cases() -> dict:
    from core.chat.segments import message_segments
    from core.chat.status import empty_feed, error_status, game_off_note, not_found_status, read_error_status, \
        search_hint, status_chip, watching_status
    from core.text import metres_text, plural, split_keywords

    spec = {"Кираса Рудры": "110600968", "Меч Фланаса": "2"}
    grades = {"110600968": "legend", "2": "nonsense"}
    texts = [
        ("wts [Кираса Рудры] и [Хлам] у ⟪Место · Келькмарос¦220070000 1 2⟫", ["wts"]),
        ("[Меч Рудры] за 1кк", ["меч"]), ("[Меч Фланаса] ⟪Задание: X⟫ ⟪sweet bunny⟫", ["фланаса", " "]),
        ("простой текст", []), ("", ["a"]), ("ИЩУ группу, ищу хила", ["ищу"]), ("[a[b]c]", ["b"]),
    ]
    statuses = ["Слежу за C:/Chat.log", "Слежу за C:/Chat.log  ·  нет ключевых слов", "Игра не запущена — x",
                "Chat.log не найден: C:/x", "Ошибка: коротко", "Ошибка: очень длинное описание ошибки", "Остановлен", ""]
    hints = [(mode, kw, items) for mode in ("or", "words", "items", "and", "x") for kw in ([], ["a"])
             for items in ([], ["1"])]
    return {
        "segments": [[t, h, plain(message_segments(t, h, spec, grades))] for t, h in texts],
        "segments_plain": [[t, h, plain(message_segments(t, h))] for t, h in texts],
        "status_chip": [[s, list(status_chip(s))] for s in statuses],
        "hints": [[m, k, i, search_hint(m, k, i), list(empty_feed(True, m, k, i)), list(empty_feed(False, m, k, i))]
                  for m, k, i in hints],
        "texts": [watching_status("C:/a", ""), watching_status("C:/a", "нет"), not_found_status("C:/b"),
                  error_status("boom"), read_error_status("io"), game_off_note("18:05")],
        "plural": [[n, plural(n, "слово", "слова", "слов")] for n in (0, 1, 2, 4, 5, 11, 12, 14, 21, 22, 25, 101, 111, 112)],
        "split_keywords": [[t, split_keywords(t)] for t in (" хил,  ММК ,,чант , ", "", ",", "a")],
        "metres": [[m, metres_text(m)] for m in (0, 0.5, 1.5, 2.5, 384.4, 999.5, 999.4, 1000, 1250, 1350, 1600, 12345.6)],
    }


def tailer_cases() -> dict:
    """A log file changed step by step; the port replays the same writes on its own temporary file."""
    from core.chat.tailer import MAX_LINE_BYTES, LogTailer

    utf = "2026.10.20 18:00:01 : [3.Поиск группы] привет\r\n".encode("utf-8")
    cp = "2026.10.20 18:00:02 : [3.Поиск группы] ищу хила\r\n".encode("cp1251")
    ops = [
        ["write", base64.b64encode(b"2026.10.20 17:00:00 : old line\r\n").decode()],
        ["start_at_end"],
        ["read"],
        ["append", base64.b64encode(utf + cp + b"half").decode()],
        ["read"],
        ["append", base64.b64encode(b" done\r\nnext\n").decode()],
        ["read"],
        ["append", base64.b64encode(b"x" * (MAX_LINE_BYTES + 10)).decode()],
        ["read"],
        ["append", base64.b64encode(b"still junk\nafter junk\n").decode()],
        ["read"],
        ["write", base64.b64encode(b"short\n").decode()],
        ["read"],
        ["append", base64.b64encode("\ufeffBOM строка\n".encode("utf-8") + b"\x98\xff\n").decode()],
        ["read"],
    ]
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "Chat.log"
        t = LogTailer(str(path))
        for op in ops:
            if op[0] == "write":
                path.write_bytes(base64.b64decode(op[1]))
                out.append(op + [None])
            elif op[0] == "append":
                with path.open("ab") as f:
                    f.write(base64.b64decode(op[1]))
                out.append(op + [None])
            elif op[0] == "start_at_end":
                t.start_at_end()
                out.append(op + [None])
            else:
                out.append(op + [t.read_new_lines()])
        backlog_lines = [f"2026.10.20 {h:02d}:{m:02d}:00 : line {h}:{m}" for h in (16, 17, 18) for m in (0, 30)]
        path.write_bytes(("\r\n".join(["без времени", *backlog_lines, "2026.13.01 00:00:00 : плохая дата"]) + "\r\nхвост")
                         .encode("utf-8"))
        b = LogTailer(str(path))
        b.start_at_end()
        backlog = {f"{since}|{chunk}": b.read_backlog(datetime.fromisoformat(since), chunk_size=chunk)
                   for since in ("2026-10-20T17:15:00", "2026-10-20T00:00:00", "2026-10-21T00:00:00")
                   for chunk in (16, 1000000)}
        backlog_text = base64.b64encode(path.read_bytes()).decode()
    return {"max_line_bytes": MAX_LINE_BYTES, "ops": out, "backlog_file": backlog_text, "backlog": backlog}


def all_cases() -> dict[str, dict]:
    return {"chat_parser": parser_cases(), "chat_matcher": matcher_cases(), "chat_series": series_cases(),
            "chat_session": session_cases(), "chat_segments": segment_cases(), "chat_tailer": tailer_cases()}


if __name__ == "__main__":
    os.sys.exit(0)
