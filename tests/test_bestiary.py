"""The generated index keeps exact IDs, Unicode search, map points and source detail."""

import gzip
import json

from tools.build_bestiary_index import build
from watcher.bestiary_store import BestiaryStore


def test_bestiary_index_supports_links_filters_and_locations(tmp_path):
    source = tmp_path / "npcs.json.gz"
    areas = tmp_path / "areas.json.gz"
    database = tmp_path / "npcs.sqlite"
    records = {
        "zones": {"210010000": "Фоэта"},
        "records": [
            {
                "id": "210065", "name": "Когтистая рефисма", "site_name": "Когтистая рефисма",
                "local_name": "", "internal_name": "lepismа_3_n", "category": "npc",  # KB type overrides client heuristic
                "role": "", "race": "beast", "site_level": 15, "icon_asset": "npc/mob.jpg",
                "kb_url": "https://kb.aionempire.com/npc/210065", "kb_status": "loaded",
                "points": [{"map_id": "210010000", "x": 100, "y": 200, "gx": 11, "gy": 22}],
                "kb": {
                    "badges": {"type": "Монстр", "race": "Зверь", "rank": "Обычный"},
                    "stats": {"Макс. ХП": "282"},
                    "drops": [{"item_id": "1", "name": "Прах рефисмы", "rarity": "junk"}],
                    "locations": [{"name": "Фоэта", "points": [{"x": 1, "y": 2}]}],
                },
            },
            {
                "id": "220000", "name": "Торговец 100%", "site_name": "", "local_name": "",
                "internal_name": "Merchant", "category": "npc", "role": "merchant", "race": "",
                "site_level": None, "icon_asset": "", "kb_url": "", "kb_status": "client_only",
                "points": [], "kb": None,
            },
        ],
    }
    regions = {
        "areas": [{
            "npc_id": "210065", "map_id": "210010000", "area_id": "area-1",
            "point_count": 1, "center": [100, 200], "area_names": ["Пастбище Акариоса"],
            "polygon": [[90, 190], [110, 190], [100, 210]],
        }],
    }
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False)
    with gzip.open(areas, "wt", encoding="utf-8") as stream:
        json.dump(regions, stream, ensure_ascii=False)
    with gzip.open(source.with_name("services.json.gz"), "wt", encoding="utf-8") as stream:
        json.dump({"npcs": {"220000": {"tabs": ["Оружие"], "stock": [{"item_id": "1", "name": "Меч новичка"}]}}}, stream)

    assert build(source, areas, database) == (2, 1)
    store = BestiaryStore(database)
    try:
        for query in ("РЕФИСМА", "210065", "pulse://npc/210065", "https://kb.aionempire.com/npc/210065"):
            rows, count = store.search(query)
            assert count == 1
            assert rows[0]["id"] == "210065"
        assert store.search(category="monster", race="Зверь", rank="Обычный", map_id="210010000")[1] == 1
        assert store.search(category="merchant")[1] == 1
        rows, count = store.search("меч", category="merchant")  # a merchant is found by a sold item
        assert (count, rows[0]["id"], rows[0]["sold"]) == (1, "220000", "Меч новичка")
        assert store.search("меч", category="monster")[1] == 0
        rows, count = store.search("прах")  # a mob is found by a dropped item
        assert (count, rows[0]["id"], rows[0]["dropped"]) == (1, "210065", "Прах рефисмы")
        assert store.races() == ["Элийцы", "Асмодиане", "Балауры", "Другие"]
        assert store.search(race="Другие")[1] == 2
        assert store.search(race="Балауры")[1] == 0
        assert store.search("100%")[1] == 1  # SQL wildcard is escaped
        assert store.search("100_")[1] == 0
        assert store.search(min_level=15, max_level=15)[1] == 1
        assert store.search(min_level=16)[1] == 0
        assert store.search(max_level=20)[1] == 1  # unknown levels are excluded
        assert store.regions("210010000") == ["Пастбище Акариоса"]
        assert store.search(region="Пастбище Акариоса", map_id="210010000")[1] == 1
        assert store.search(region="Пастбище Акариоса", map_id="missing")[1] == 0
        detail = store.detail("210065")
        assert detail["stats"]["Макс. ХП"] == "282"
        assert detail["faction"] == "Другие"
        assert detail["drops"][0]["name"] == "Прах рефисмы"
        assert detail["points"][0]["gx"] == 11
        assert store.areas("210065")[0]["polygon"][2] == [100, 210]
    finally:
        store.close()


def test_profile_parser_reads_level_from_hp_bar():
    from tools.build_bestiary_data import parse_profile
    profile = parse_profile("215000", '''
      <div class="header-title npc-name">Легат Бакрам</div>
      <div class="hp-bar v-align-middle bar-3"><div class="icon"><span>50</span></div></div>
      <span class="npc-badge npc-badge--rank" data-key="hero">Героический</span>
      <div class="npc-stat"><div class="npc-stat-label">Макс. ХП</div><div class="npc-stat-value">1194594</div></div>
    ''')
    assert profile["level"] == 50
    assert profile["hp_bar"] == 3
    assert profile["badges"]["rank"] == "Героический"
    assert profile["stats"]["Макс. ХП"] == "1194594"


def test_factions_normalize_client_case_and_keep_species_separate():
    from watcher.bestiary_labels import faction_for, race_label
    assert faction_for("PC_Light") == "Элийцы"
    assert faction_for("pc_dark") == "Асмодиане"
    assert faction_for("Drakan") == "Балауры"
    assert faction_for("Naga") == "Балауры"
    assert faction_for("Beast") == "Другие"
    assert race_label("Beast") == "Зверь"
    assert race_label("construct") == "Конструкт"


def test_mouse_wheel_over_nested_card_scrolls_its_surface():
    import tkinter as tk
    from watcher.bestiary_widgets import ScrollArea
    root = tk.Tk()
    try:
        root.geometry("400x240")
        panel = ScrollArea(root)
        panel.pack(fill="both", expand=True)
        labels = []
        for i in range(30):
            card = tk.Frame(panel.content)
            card.pack(fill="x")
            label = tk.Label(card, text=f"Creature {i}", height=3)
            label.pack(fill="x")
            labels.append(label)
        panel.refresh()
        root.update()
        before = panel.canvas.yview()[0]
        labels[0].event_generate("<MouseWheel>", delta=-120)
        root.update()
        assert panel.canvas.yview()[0] > before
    finally:
        root.destroy()


def test_profile_cache_keeps_success_after_network_failure(tmp_path):
    from tools.build_bestiary_data import load_cache
    cache = tmp_path / "profiles.jsonl"
    cache.write_text('\n'.join(json.dumps(row) for row in [
        {"id": "1", "name": "Creature", "parser_version": 2},
        {"id": "1", "error": "timeout"},
    ]) + '\n' + '{"id":', encoding="utf-8")
    assert load_cache(cache)["1"]["name"] == "Creature"


def test_profile_scraper_stops_after_repeated_network_failures(tmp_path, monkeypatch):
    from tools import build_bestiary_data as importer
    monkeypatch.setattr(importer, "fetch_profile", lambda npc_id: {"id": npc_id, "error": "timeout"})
    cache = tmp_path / "profiles.jsonl"
    importer.scrape([str(i) for i in range(100)], cache, workers=1)
    report = json.loads(cache.with_name("import-status.json").read_text(encoding="utf-8"))
    assert report["stopped_on_network_errors"] is True
    assert report["remaining"] == 100
    assert len(report["errors"]) == 4


def test_badges_wrap_when_card_is_narrow():
    import tkinter as tk
    from watcher.bestiary_widgets import wrap_badges
    root = tk.Tk()
    try:
        root.geometry("220x150")
        frame = tk.Frame(root)
        frame.pack(fill="x")
        labels = [tk.Label(frame, text=text, padx=8) for text in ("МОНСТР", "БАЛАУРЫ", "ГЕРОИЧЕСКИЙ")]
        wrap_badges(frame)
        root.update()
        assert labels[-1].winfo_y() > labels[0].winfo_y()
        assert all(label.winfo_x() + label.winfo_width() <= frame.winfo_width() for label in labels)
    finally:
        root.destroy()


def test_drop_search_preserves_original_item_link(tmp_path, monkeypatch):
    import tkinter as tk
    from watcher.bestiary_view import BestiaryView
    import watcher.bestiary_view as module
    root = tk.Tk()
    try:
        view = BestiaryView(root, tmp_path / "missing.sqlite", tmp_path, {}, lambda *args: None)
        view._detail = {"kb_status": "loaded", "drops": [
            {"item_id": "100", "name": "Меч", "rarity": "rare"},
            {"item_id": "200", "name": "Щит", "rarity": "unique"},
        ]}
        view.detail_tabs.select(view.drops_tab)  # lists are filled when their tab is open
        view.drop_query.set("ЩИТ")
        assert view.drops.get_children() == ("d1",)
        view.drops.selection_set("d1")
        opened = []
        monkeypatch.setattr(module.webbrowser, "open", opened.append)
        view._open_item()
        assert opened == ["https://kb.aionempire.com/items/200"]
        view.drop_query.set("Нет такого предмета")
        assert not view.drops.get_children()
        assert "0 из 2" in view.drop_count.cget("text")
    finally:
        root.destroy()


def test_padded_item_icon_is_cropped_before_scaling(tmp_path):
    import tkinter as tk
    from PIL import Image, ImageTk
    from watcher.bestiary_view import BestiaryView
    folder = tmp_path / 'items'
    folder.mkdir()
    source = Image.new('RGBA', (64, 64), (128, 128, 128, 255))
    source.paste((220, 10, 20, 255), (0, 0, 40, 40))
    source.save(folder / 'item.png')
    root = tk.Tk()
    try:
        view = BestiaryView(root, tmp_path / 'none.sqlite', tmp_path, {}, lambda *args: None)
        icon = view._load_icon('items/item.png', 32)
        result = ImageTk.getimage(icon)
        assert result.size == (32, 32)
        assert result.getpixel((31, 31))[:3] == (220, 10, 20)
    finally:
        root.destroy()


def _view_with_fake_store(tmp_path, delay):
    """A BestiaryView whose search runs in the worker thread against a store that answers after `delay` s."""
    import time
    import tkinter as tk
    from types import SimpleNamespace
    import watcher.bestiary_view as module
    from watcher.search_worker import SearchWorker

    class FakeStore:
        def __init__(self, path): pass
        def search(self, text="", *args, **kwargs):
            time.sleep(delay)
            return [{"id": "1", "name": text, "kind": "Монстр", "race": "", "rank": "", "level": "5",
                     "icon_asset": "", "zone_names": "", "faction": "", "point_count": 0, "drop_count": 0,
                     "has_profile": 0, "sold": "", "dropped": ""}], 1
        def close(self): pass

    root = tk.Tk()
    view = module.BestiaryView(root, tmp_path / "x.sqlite", tmp_path, {}, lambda *a: None)
    view.pack()
    view.store = SimpleNamespace(search=None, close=lambda: None, detail=lambda i: None, regions=lambda m="": [])
    view._select_npc = lambda i: None
    view._worker.close()
    view._worker = SearchWorker(tmp_path / "x.sqlite", store_factory=FakeStore)
    return root, view, module


def test_fast_search_shows_no_loading_indicator(tmp_path, monkeypatch):
    root, view, module = _view_with_fake_store(tmp_path, delay=0.02)
    try:
        monkeypatch.setattr(module, "LOADING_DELAY_MS", 300)
        view.query.set("кабан")
        view._search(reset=True)
        shown = []
        end = __import__("time").monotonic() + 3
        while view._polling and __import__("time").monotonic() < end:
            root.update()
            shown.append(view._loading.winfo_ismapped())
        assert not any(shown)  # a search under the delay shows nothing
        assert "из 1 NPC" in view.page_label.cget("text")
    finally:
        view.destroy()
        root.destroy()


def test_slow_search_shows_loading_and_hides_it_when_done(tmp_path, monkeypatch):
    import time
    root, view, module = _view_with_fake_store(tmp_path, delay=0.5)
    try:
        monkeypatch.setattr(module, "LOADING_DELAY_MS", 100)
        view.query.set("кабан")
        view._search(reset=True)
        end = time.monotonic() + 3
        seen = False
        while view._polling and time.monotonic() < end:
            root.update()
            seen = seen or view._loading.winfo_ismapped()
            time.sleep(0.01)
        assert seen and not view._loading.winfo_ismapped()
        assert str(view._loading.cget("cursor")) == "watch"
    finally:
        view.destroy()
        root.destroy()


def test_typing_fast_shows_only_the_last_search(tmp_path, monkeypatch):
    root, view, module = _view_with_fake_store(tmp_path, delay=0.1)
    try:
        for text in ("к", "ка", "каб", "каба", "кабан"):
            view.query.set(text)
            view._search(reset=True)
        view.wait_for_search()
        assert next(iter(view._result_rows)) == "1"
        assert view._cards[0].name.cget("text") == "кабан"  # the answer to the newest request
    finally:
        view.destroy()
        root.destroy()


def test_refresh_pointer_cursor_never_raises_and_keeps_the_cursor(tmp_path):
    import tkinter as tk
    from watcher.bestiary_widgets import refresh_pointer_cursor

    root = tk.Tk()
    try:
        label = tk.Label(root, text="x", cursor="hand2")
        label.pack()
        root.update()
        refresh_pointer_cursor(label)  # whatever is under the pointer, no error
        refresh_pointer_cursor(root)
        assert str(label.cget("cursor")) == "hand2"
    finally:
        root.destroy()
