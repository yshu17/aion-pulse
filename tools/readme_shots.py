"""Screenshots for README.md: the real app on invented data, so no player name or private message gets published.

    python tools/readme_shots.py [output folder, default screenshots]

Runs the program in-process with a temporary Chat.log and config (made-up players, a fixed Wednesday 20:30 MSK
schedule), takes each tab with PrintWindow at 1400x860 and saves PNGs. Windows only.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from ui_snapshots import _settle, print_client_window  # noqa: E402

WIDTH, HEIGHT = 1400, 860
KEYWORDS = ["wts", "продам", "ищу группу"]
CHAT = [  # (minutes ago, channel, nick, text); item and place links are filled in at run time
    (29, "[1.Общий]", "Brightblade", "всем привет! кто сегодня на арену хаоса?"),
    (27, "[3.Поиск группы]", "Valkyra", "ищу группу в Бездну, нужен хил и чант, 55 лвл"),
    (26, "[3.Поиск группы]", "Morgrim", "wts {item0} 2kk, торг в личке"),
    (24, "[1.Общий]", "Elyra", "кто знает, где сейчас рифт? {place}"),
    (23, "[2.Торговля]", "Ironveil", "wtb {item4} 1.5kk"),
    (21, "[3.Поиск группы]", "Dagon", "продам {item1} недорого"),
    (20, "[3.Поиск группы]", "Sunhaze", "нужен танк в Дерадикон, идём через 5 минут"),
    (18, "[1.Общий]", "Kaelith", "кв {quest} уже сдал, награда норм"),
    (17, "[3.Поиск группы]", "Nightfox", "ищу группу на арену хаоса, ДД 54"),
    (16, "[2.Торговля]", "Moonwhisper", "продаю камни маны пачками, пишите"),
    (15, "[3.Поиск группы]", "Zephyra", "wts {item2} + {item3} 3kk"),
    (14, "[1.Общий]", "Stormcaller", "сервер сегодня без лагов, красота"),
    (13, "[3.Поиск группы]", "Aurelia", "ищу группу в Рентус, жду хила"),
    (12, "[3.Поиск группы]", "Thornwood", "в Дерадикон нужен ДД, 53+"),
    (11, "[1.Общий]", "Pyrelord", "кто знает, когда следующий Ингисон?"),
    (10, "[3.Поиск группы]", "Silverlake", "продам {item0}, цена в личку"),
    (9, "[2.Торговля]", "Frostbane", "куплю эссенции, дорого"),
    (7, "[3.Поиск группы]", "Emberwing", "собираю рейд на Инг, 6/12, нужны хилы"),
    (6, "[1.Общий]", "Whisperwind", "спасибо за группу, было весело"),
    (4, "[3.Поиск группы]", "Hollowkin", "wts {item1} 800k"),
    (2, "[3.Поиск группы]", "Cinderfall", "ищу группу в Кромедэ, танк с ДД"),
    (1, "[1.Общий]", "Starling", "всем привет, кто на Инг?"),
    (28, "[3.Поиск группы]", "Ravenholt", "ищу группу в Дерадикон, ДД 55, есть руны"),
    (25, "[3.Поиск группы]", "Lunaris", "wts {item3} 1.2kk"),
    (22, "[3.Поиск группы]", "Galeforce", "продам {item2}, торг уместен"),
    (19, "[3.Поиск группы]", "Duskmantle", "ищу группу на осаду, нужен чант"),
    (8, "[3.Поиск группы]", "Wildfire", "wts {item4} 900k"),
    (5, "[3.Поиск группы]", "Amberleaf", "продам перья и камни, оптом дешевле"),
    (3, "[3.Поиск группы]", "Cragmoor", "ищу группу в Бездну, 3/6, нужен хил"),
]


def item_ids(names: list[str]) -> list[str]:
    """Ids of the items with these exact names from the bundled catalog (a missing name keeps its number slot)."""
    found = {}
    for line in (ROOT / "data" / "item_names.tsv").read_text(encoding="utf-8").splitlines():
        item_id, _, name = line.partition("\t")
        if name in names and name not in found:
            found[name] = item_id
    return [found.get(name, "0") for name in names]


def make_inputs(directory: Path) -> Path:
    ids = item_ids(["Кираса Рудры", "Латные сапоги Рудры", "Кольчуга Рудры", "Латные щитки Рудры", "Латные рукавицы Рудры"])
    now = datetime.now()
    lines = []
    for ago, channel, nick, text in sorted(CHAT, key=lambda row: -row[0]):
        text = text.replace("{place}", "[pos:Место;220070000 2010.1 1315.8 0.0 0]").replace("{quest}", "[quest:2058]")
        for index, item_id in enumerate(ids):
            text = text.replace("{item%d}" % index, f"[item:{item_id};ver2;;;]")
        stamp = (now - timedelta(minutes=ago)).strftime("%Y.%m.%d %H:%M:%S")
        lines.append(f"{stamp} : {channel} [charname:{nick};1.0000 0.6941 0.6941]: {text} ")
    log = directory / "Chat.log"
    log.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1251", errors="replace"))
    config = directory / "config.json"
    config.write_text(json.dumps({
        "chat_log": str(log), "game_dir": str(directory), "game_check": False, "reduce_motion": True,
        "nag_popup": False, "settings_open": False, "sound_path": "", "keywords": KEYWORDS, "watch_items": ids[:3],
        "history_min": 60, "map_side": "dark",
    }, ensure_ascii=False), encoding="utf-8")
    return config


def select_tab(app, label: str) -> None:
    for index, tab in enumerate(app.tabs.tabs()):
        if app.tabs.tab(tab, "text").strip() == label:
            app.tabs.select(index)
            return
    raise KeyError(label)


def main(out: Path) -> int:
    import tkinter as tk
    from watcher.app import App

    out = out.resolve()  # the program runs inside a temporary folder: keep the target absolute
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="readme-shots-") as temporary:
        folder = Path(temporary)
        config = make_inputs(folder)
        prior = Path.cwd()
        os.chdir(folder)
        root = app = None
        try:
            root = tk.Tk()
            app = App(root, config)
            app.game_dir_var.set(r"C:\Games\Aion Empire")
            app.toasts.close()
            root.update_idletasks()
            root.update()
            root.minsize(WIDTH, HEIGHT)
            root.geometry(f"{WIDTH}x{HEIGHT}+60+40")
            root.attributes("-topmost", True)
            app.settle_layout()

            def shot(name: str) -> None:
                _settle(root, app)
                app.map_view.coords_var.set("")
                app.map_view.canvas.delete("bubble")
                root.update()
                time.sleep(0.2)
                image = print_client_window(root)
                if image.size != (WIDTH, HEIGHT):
                    raise RuntimeError(f"{name}: got {image.size}, wanted {(WIDTH, HEIGHT)}")
                image.save(out / name)
                print("saved", out / name)

            # 01: the search tab while watching: history matches, counters, «Слежу»
            select_tab(app, "Поиск")
            app.start()  # watch the temporary Chat.log: the history fills the feed through the real matching code
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                root.update()
                time.sleep(0.05)
            rows = app.feed._rows  # the history does not count as «found»; show the counters of a live session
            app.tracker.found, app.tracker.reacted, app.tracker.missed = rows, rows - 2, 1
            app._update_counters()
            shot("01-matches.png")

            # 02: «Что искать» with a grade filter and a search; the feed gives way to the list
            app.item_list.search_var.set("рудр")
            app.item_list.search("рудр")
            app.item_list.scroll(14)
            shot("02-items.png")

            # 06: the whole chat
            select_tab(app, "Весь чат")
            app.all_chat.activate()
            shot("06-chat.png")

            # 03: the map of Kelkmaros
            select_tab(app, "Карта")
            _settle(root, app)
            app.map_view.open_zone("220070000")
            shot("03-map.png")

            # 07: a point found by search with its card
            app.map_view.search("торговец", 0)
            shot("07-map-card.png")

            # 04: the schedule on a fixed Wednesday evening, shown in MSK
            app.schedule_tab.clock = lambda: datetime(2026, 10, 14, 20, 30)
            app.schedule_tab.tz = timezone(timedelta(hours=3))
            app.schedule_tab.day_var.set("Среда")
            app.schedule_tab.refresh()
            select_tab(app, "Расписание")
            shot("04-schedule.png")

            # 05: settings
            select_tab(app, "Поиск")
            app.item_list.search_var.set("")
            app.item_list.search("")
            app._show_settings(True)
            shot("05-settings.png")
            return 0
        finally:
            if app is not None:
                app._on_close()
            elif root is not None:
                root.destroy()
            os.chdir(prior)


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tmp" / "readme-shots"))
