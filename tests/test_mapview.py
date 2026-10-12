import time
import tkinter as tk

import pytest

from watcher import theme
from core.items.catalog import load_link_names
from watcher.paths import resource_root
from watcher.mapview import MapView, Place, load_zones


@pytest.fixture
def root():
    r = tk.Tk()
    theme.apply_dark_theme(r)
    yield r
    r.destroy()


def zones():
    return load_zones(resource_root() / "data" / "maps", load_link_names(resource_root() / "data")[0])


def test_game_maps_follow_the_client_zonemap_framing():
    """data/maps/client: the game's own maps (newmap); transforms from zonemap.xml, checked on aiondb NPC markers."""
    found = zones()
    assert set(found) >= {"220010000", "220030000", "220020000", "220050000", "220040000", "220070000",
                          "210050000", "600010000", "120010000"}
    assert found["220070000"].name == "Келькмарос"
    assert all(z.path.parent.name == "client" for z in found.values())
    # the game's own maps are 3072 px; Elysium uses the radar picture (its newmap does not match the NPCs), the
    # temples and sacred arenas their small radar pictures enlarged (tools/build_radar_zone.py, add_small_zones.py)
    radar = {"110010000", "110020000", "120020000", "110070000", "120080000"}
    assert all(z.size == 3072 for map_id, z in found.items() if map_id not in radar)
    assert {"110020000", "120020000", "110070000", "120080000"} <= set(found)
    # Altgard: aiondb puts teleporter 203678 (client game x 2681.14, y 1023.92) at svg (960.92, 2140.14) of 2790
    k = 3072 / 2790
    x, y = found["220030000"].to_image(2681.1377, 1023.9208)
    assert x == pytest.approx(960.92 * k, abs=1) and y == pytest.approx(2140.14 * k, abs=1)
    # Ishalgen: merchant 203515 (618.24, 2430.12) at svg (1690.12, 618.24) of 2300
    k = 3072 / 2300
    x, y = found["220010000"].to_image(618.23633, 2430.1184)
    assert x == pytest.approx(1690.12 * k, abs=1) and y == pytest.approx(618.236 * k, abs=1)
    # Silentera: a 1536 world without an offset -> game x 2; aiondb teleporter 804460 at svg (1223.5, 555.37)
    assert found["600010000"].to_image(555.368, 1223.5) == pytest.approx((2447.0, 1110.74), abs=0.5)
    # Pandaemonium: offset 817, 697 and a 1035 m map; merchant Huron stands at game (1275, 1368)
    k = 3072 / 1035
    assert found["120010000"].to_image(1275, 1368) == pytest.approx(((1368 - 817) * k, (1275 - 697) * k), abs=0.5)


def test_points_follow_the_zone_transform(root):
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store)
    altgard = view.zones["220030000"]
    for p in view.poi.in_zone("220030000", {"teleport", "merchant"}):
        assert (p.x, p.y) == pytest.approx(altgard.to_image(p.gx, p.gy))


def test_missing_maps_dir_gives_no_zones(tmp_path):
    assert load_zones(tmp_path, load_link_names(resource_root() / "data")[0]) == {}


def test_show_centres_on_place_and_zoom_keeps_point_under_cursor(root):
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    place = Place("220070000", 978.8, 1265.0, "Место · Келькмарос")
    others = [Place("220070000", 1500, 1500, "Место", "12:00 Nick: го"), Place("210050000", 1, 1, "x")]
    window.show(place, others)
    root.update()
    # fly_to animates over four Tk frames (35 ms each).
    root.after(180, root.quit)
    root.mainloop()
    assert window.others == [others[0]]  # pins only from the same zone
    width, height = window._canvas_size()
    sx, sy = window.to_screen(*window.zone.to_image(place.x, place.y))
    assert abs(sx - width / 2) < 2 and abs(sy - height / 2) < 2
    before = window.zoom
    image_point = (window.left + 100 / window.zoom, window.top + 120 / window.zoom)
    window.zoom_at(1.25, 100, 120)
    assert window.zoom > before  # the first frame of the glide runs at once
    window.finish_zoom()
    assert window.zoom == pytest.approx(before * 1.25)
    assert window.to_screen(*image_point) == pytest.approx((100, 120), abs=1)
    window.render()
    assert window.canvas.find_withtag("pin") and window.canvas.find_withtag("other")
    for _ in range(40):
        window.zoom_at(0.5, 10, 10)
    window.finish_zoom()
    assert window.zoom == pytest.approx(window._fit_zoom())  # never smaller than the whole map


def test_zone_without_map_says_so(root):
    window = MapView(root, {})
    window.show(Place("400010000", 1, 2, "Место · Арэшурат"))
    assert "карты этой зоны нет" in window.title.cget("text")


def test_area_names_on_maps_from_the_client(root):
    found = zones()
    kelk = found["220070000"]
    names = {text.replace("\n", " "): level for _x, _y, text, level in kelk.labels}
    assert names["Митраканд"] == "main" and names["Запечатанная башня"] == "zoom"
    assert "Вход в тоннель Силентера в Келькмаросе" in names
    assert "Пещера Мариссы" not in names  # ui_map «none»: the game does not write it on the map
    assert all(0 <= x <= kelk.size and 0 <= y <= kelk.size for x, y, _t, _l in kelk.labels)
    assert "Коридор мучений" in {t for _x, _y, t, _l in found["600010000"].labels}
    assert found["120010000"].labels  # Pandaemonium has names now (aiondb had none)
    window = MapView(root, found)
    window.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    window.open_zone("220070000")
    window.zoom = 1300 / window.zone.size
    window.render()
    shown = {window.canvas.itemcget(i, "text") for i in window.canvas.find_withtag("label")}
    assert "Митраканд" in shown and "Запечатанная башня" not in shown  # whole map: «main» names only
    window.show(Place("220070000", 1173.0, 1227.4, "Место"))
    window.zoom = 2.0
    window.center_on(*window.zone.to_image(1173.0, 1227.4))
    window.render()
    shown = {window.canvas.itemcget(i, "text") for i in window.canvas.find_withtag("label")}
    assert "Запечатанная башня" in shown  # closer in: the «zoom» names too


def test_labels_file_errors_are_ignored(tmp_path):
    from watcher.mapview import load_labels

    path = tmp_path / "labels.tsv"
    path.write_text("# c\n220070000\tmain\t1\t2\tA|B\n220070000\tzoom\tx\t2\tbad\n"
                    "220070000\tnone\t1\t1\thidden\nshort\tline\n", encoding="utf-8")
    assert load_labels(path) == {"220070000": [(1.0, 2.0, "A\nB", "main")]}
    assert load_labels(tmp_path / "missing.tsv") == {}


def test_browse_zone_from_picker_with_chat_pins(root):
    places = [Place("220070000", 1500, 1500, "Место", "12:00 Nick: го"), Place("210050000", 9, 9, "x")]
    view = MapView(root, zones(), get_places=lambda: places)
    view.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    view.activate()  # first open: the zone of the last linked place
    assert view.zone.map_id == "210050000"
    view.zone_var.set("Келькмарос")
    view.zone_box.event_generate("<<ComboboxSelected>>")
    root.update()
    assert view.zone.map_id == "220070000" and view.place is None
    assert view.others == [places[0]]
    assert view.zoom == pytest.approx(view._fit_zoom())  # whole map
    assert "Келькмарос" in view.zone_box.cget("values")


def test_fixed_point_set_without_gathering_or_quests(root):
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    view.pack(fill="both", expand=True)
    root.geometry("1300x900")
    root.update()
    view.open_zone("220070000")
    root.update()
    view.render()
    assert not hasattr(view, "panel")  # no layer panel any more
    assert {"teleport", "warehouse", "merchant", "artifact"} <= view.layers
    hidden = {"quest_point"} | {t for t in store.types if t.startswith("gather_")}  # rifts are a menu entry now
    assert {"tunnel", "portal"} <= view.layers  # the Silentera entrances, Abyss gates and tunnel exits
    assert not view.layers & hidden
    shown = {m.type for _x, _y, members in view._drawn for m in members}
    assert "teleport" in shown and not shown & hidden
    # icons are big, teleporters bigger still
    assert view._icon_size("teleport") > view._icon_size("merchant") >= 28


def test_point_card_and_nearby(root):
    from types import SimpleNamespace

    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    view.pack(fill="both", expand=True)
    root.geometry("1400x900")
    root.update()
    # a chat place inside the Kelkmaros fortress: the card lists the nearest useful points
    view.show(Place("220070000", 1830, 2850, "Место · Келькмарос", "12:00 Leader: сбор у склада"))
    root.update()
    assert view.point_card.title.cget("text") == "Место · Келькмарос"
    assert "сбор у склада" in view.point_card.note.cget("text")
    types = [t for t, _name, _m in view.point_card.rows]
    assert types[:3] == ["teleport", "bindstone", "warehouse"]
    assert all(m < 600 for t, _n, m in view.point_card.rows if t in ("warehouse", "merchant"))
    # clicking a «Рядом» row jumps to that point: its icon pulses (no ring)
    view.point_card.near.winfo_children()[types.index("warehouse")].event_generate("<Button-1>")
    root.update()
    assert view.selected is not None and view.selected.type == "warehouse"
    view.render()
    assert view.canvas.find_withtag("pulse") and not view.canvas.find_withtag("selected")
    # a click (no drag) on a single drawn point opens its card
    view.open_zone("220070000")
    root.update()
    teleport = view.poi.in_zone("220070000", {"teleport"})[0]
    view.zoom = 4.0  # closest zoom: every point is its own icon
    view.center_on(teleport.x, teleport.y)
    sx, sy = view._spots[teleport]
    members = [teleport]
    view._on_press(SimpleNamespace(x=int(sx), y=int(sy)))
    view._on_release(SimpleNamespace(x=int(sx), y=int(sy)))
    assert view.selected == members[0]


def test_map_search_points_and_areas(root):
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    view.pack(fill="both", expand=True)
    root.geometry("1400x900")
    root.update()
    view.open_zone("220070000")
    count = len(view.poi.in_zone("220070000", {"teleport"}))
    assert count >= 5 and view.search("привратник", 0) == f"1 / {count}"
    first = view.selected
    assert first.type == "teleport"
    assert view.search("привратник", 1) == f"2 / {count}" and view.selected != first
    for _ in range(count - 1):
        view.search("привратник", 1)
    assert view.selected == first  # wraps around
    assert view.search("митраканд", 0).endswith("/ 2")  # area names: «Митраканд», «Сигнальный маяк Митраканда»
    assert view.point_card.kind.cget("text") == "Район"
    assert view.search("абвгд", 0) == "нет"
    assert view.search("травы", 0) == "нет"  # hidden kinds (gathering) are not found either
    view.search_var.set("склад")
    view._search(0)
    assert view.search_count.cget("text").startswith("1 /")


def test_game_coordinates_under_cursor_round_trip(root):
    view = MapView(root, zones())
    view.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    view.show(Place("220070000", 1173.0, 1227.4, "Место"))
    sx, sy = view.to_screen(*view.zone.to_image(1173.0, 1227.4))
    gx, gy = view.game_at(sx, sy)
    assert gx == pytest.approx(1173.0, abs=0.5) and gy == pytest.approx(1227.4, abs=0.5)


def test_point_at_map_edge_can_be_centred(root):
    view = MapView(root, zones())
    view.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    view.open_zone("220070000")
    view.zoom = 2.0
    size = view.zone.size
    view.center_on(size - 20, 30)  # near the top-right corner
    width, height = view._canvas_size()
    sx, sy = view.to_screen(size - 20, 30)
    assert abs(sx - width / 2) < 2 and abs(sy - height / 2) < 2


def test_last_two_zoom_levels_split_groups_into_icons_side_by_side(root):
    import math

    from watcher.mapview import MAX_ZOOM, ZOOM_STEP
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    view.pack(fill="both", expand=True)
    root.geometry("1300x900")
    root.update()
    view.open_zone("120010000")  # Pandaemonium: merchants stand in tight rows
    view.zoom = 0.55
    view.center_on(1620, 1650)
    assert any(len(members) > 1 for _x, _y, members in view._drawn)  # still grouped below the last two levels
    for zone, cx, cy, zoom in (("120010000", 1620, 1650, MAX_ZOOM), ("120010000", 1620, 1650, MAX_ZOOM / ZOOM_STEP),
                               ("220070000", 2890, 1790, MAX_ZOOM)):  # Kelkmaros fortress: rows of merchants
        if view.zone.map_id != zone:
            view.open_zone(zone)
        view.zoom = zoom
        view.center_on(cx, cy)
        assert view._drawn and all(len(members) == 1 for _x, _y, members in view._drawn)
        spots = [(x, y, members[0]) for x, y, members in view._drawn]
        for i, (x1, y1, p1) in enumerate(spots):  # no two icons cover each other
            for x2, y2, p2 in spots[i + 1:]:
                assert math.hypot(x1 - x2, y1 - y2) >= min(view._icon_size(p1.type), view._icon_size(p2.type)) - 1
    # the pulsing icon is the laid-out icon itself, not a mark at the hidden exact spot
    x, y, members = view._drawn[0]
    view.select(members[0])
    view.render()
    assert tuple(view.canvas.coords(view.canvas.find_withtag("pulse")[0])) == pytest.approx(view._spots[members[0]], abs=1)


def test_fortresses_tunnel_and_dungeons_drawn_bigger(root):
    view = MapView(root, zones())
    for zoom in (0.2, 1.0, 3.0):
        view.zoom = zoom
        usual = view._icon_size("merchant")
        assert view._icon_size("fortress") == view._icon_size("tunnel") == round(usual * 1.85)  # +85 %
        assert view._icon_size("dungeon") == round(usual * 1.5)  # +50 %
        assert view._icon_size("artifact") == round(usual * 1.25)  # +25 %
        assert view._icon_size("portal") == usual  # Abyss gates and the tunnel's exits stay as they were


def test_selected_point_pulses_slowly_without_a_ring(root):
    """User, 13.10: no ring; the selected icon pulses (soft grow / shrink, dimmer small phase) while it is selected;
    the chat's place still blinks, slower; with animations off the icon is just drawn larger."""
    from watcher import mapview as mv
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    view.pack(fill="both", expand=True)
    root.geometry("1300x900")
    root.update()
    view.open_zone("220070000")
    teleport = next(iter(view.poi.in_zone("220070000", {"teleport"})))
    view.select(teleport)  # a click
    view.render()
    assert not view.canvas.find_withtag("selected")  # no ring any more
    item = view.canvas.find_withtag("pulse")[0]
    sizes = set()
    for _ in range(int(mv.PULSE_PERIOD_MS / mv.PULSE_STEP_MS)):  # one full cycle
        view._pulse_tick()
        sizes.add(view.tk.call("image", "width", view.canvas.itemcget(item, "image")))
    base = view._icon_size(teleport.type)
    assert min(sizes) <= base + 1 and max(sizes) >= round(base * (1 + mv.PULSE_GROW)) - 1  # soft grow and shrink
    assert len(sizes) >= 4  # many steps, not an on/off blink
    assert mv.PULSE_PERIOD_MS >= 1200 and mv.BLINK_STEP_MS >= 600  # slower than the old 300 ms blink
    view.search("привратник", 0)  # the search: the found icon pulses too
    root.after(180, root.quit)
    root.mainloop()
    view.render()
    assert view.canvas.find_withtag("pulse") and not view.canvas.find_withtag("selected")
    view.show(Place("220070000", 1173.0, 1227.4, "Место"))  # a place from the chat still blinks
    view.render()
    blinking = set(view.canvas.find_withtag("blink"))
    assert view._blink_target == "pin" and blinking and blinking < set(view.canvas.find_withtag("pin"))
    view.select(teleport)  # a click stops the place's blinking
    assert view._blink_target is None
    view.motion_enabled = lambda: False  # «Отключить анимации»: a still, larger icon
    view.select(teleport)
    view.render()
    still = view.canvas.find_withtag("pulse")[0]
    assert view.tk.call("image", "width", view.canvas.itemcget(still, "image")) >= round(base * mv.PULSE_STILL) - 1
    assert view._pulse_after is None


def test_side_switch_shows_that_sides_fortress_npcs_and_quest_givers(root):
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    saved = []
    view = MapView(root, zones(), poi=store, side="dark", on_side=saved.append)
    view.open_zone("220070000")
    names = lambda: {p.name for p in view.poi.in_zone("220070000", view.layers, view.side)}  # noqa: E731
    assert {"Инсидра", "Иссейм"} <= names() and not {"Бецария", "Мадония"} & names()  # Запечатанная башня
    tower = next(p for p in view.poi.in_zone("220070000", {"fortress"}) if p.name == "Запечатанная башня")
    view.select(tower)
    assert "Инсидра" in {name for _t, name, _m in view.point_card.rows}
    view.side_var.set("Элийцы")
    view._on_side_selected()
    assert saved == ["light"] and view.side == "light"
    assert "Бецария" in {name for _t, name, _m in view.point_card.rows}  # the card's «Рядом» follows the side
    assert {"Бецария", "Мадония"} <= names() and not {"Инсидра", "Иссейм"} & names()
    elyos = [p for p in view.poi.in_zone("210050000", {"quest_give", "quest_important"}, "light") if p.side == "light"]
    assert elyos and not [p for p in view.poi.in_zone("210050000", {"quest_give"}, "dark") if p.side == "light"]
    assert view.search("инсидра", 0) == "нет"  # the other side is not found either


def test_small_game_icons_are_scaled_up_to_the_wanted_size(root):
    from watcher.mapview import load_icon

    icons = resource_root() / "data" / "maps" / "icons"
    for name in ("teleport", "coin_merchant", "postbox"):  # 26, 16 and 35x36 px in the client
        icon = load_icon(icons / f"{name}.png", 36, root)
        assert max(icon.width(), icon.height()) == 36
    assert load_icon(icons / "missing.png", 36, root) is None


def test_teleporters_and_kisks_from_the_game_files(root):
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    assert "bindstone" in view.layers
    kelk = {p.name for p in view.poi.in_zone("220070000", {"teleport"})}
    # the client's world XML: Раниу and Нотуд plus the ether ships right next to them, and the ship to Pandaemonium
    assert {"Раниу", "Нотуд", "Эфирный корабль", "Корабль до Пандемониума"} <= kelk
    assert len(view.poi.in_zone("220070000", {"teleport"})) == 6
    assert sum(len(store.in_zone(z, {"bindstone"})) for z in zones()) >= 30


def test_quest_givers_toggle_and_card_lists_quests(root):
    from core.map.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    saved = []
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons",
                   on_filters=saved.append)
    quest_types = {"quest_give", "quest_important", "quest_event"}
    assert quest_types & view.layers and not hasattr(view, "quests_var")  # the check box is an entry of «Метки» now
    giver = next(p for p in view.poi.in_zone("220070000", quest_types))
    view.select(giver)
    assert view.point_card.note.cget("text").startswith("Задания (")
    view._filter_vars["quests"].set(False)
    view._on_filters_changed()
    assert not quest_types & view.layers and saved == [["quests"]]
    assert view.search(giver.name, 0) in ("нет", "") or view.selected.type not in quest_types
    hidden = MapView(root, zones(), poi=store, hidden_groups=["quests"])
    assert not quest_types & hidden.layers


def test_area_label_moves_away_from_poi_icon(root):
    from types import SimpleNamespace

    view = MapView(root, zones())
    view.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    view.zone = SimpleNamespace(labels=[(0, 0, "Район", "main")])
    canvas = view.canvas
    canvas.create_text(250, 180, text="Район", tags=("label", "area_label_0"))
    canvas.create_rectangle(225, 165, 275, 195, tags="poi")
    original = canvas.bbox("area_label_0")
    assert original is not None
    view._avoid_label_poi(500, 400)
    moved = canvas.bbox("area_label_0")
    icon = canvas.bbox("poi")
    assert moved != original
    assert moved is not None and icon is not None
    assert moved[3] + 5 <= icon[1] or moved[1] >= icon[3] + 5 or moved[2] + 5 <= icon[0] or moved[0] >= icon[2] + 5


def test_dragging_or_zooming_stops_the_flight(root):
    """ui:30 recheck: grabbing the map in the middle of a flight hands it to the user — the remaining frames of the
    flight must not pull it back to the target."""
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    window.open_zone("220070000")
    window.zoom = window._fit_zoom() * 3
    window._clamp()
    window.render()
    root.update()
    zone = window.zone
    window.fly_to(*zone.to_image(1500, 1500))  # first frame now, three more queued
    event = type("E", (), {"x": 300, "y": 300})()
    window._on_press(event)
    event.x, event.y = 340, 330
    window._on_drag(event)
    grabbed = (window.left, window.top)
    root.after(200, root.quit)
    root.mainloop()
    assert (window.left, window.top) == pytest.approx(grabbed)


def test_unreadable_npc_database_does_not_break_the_map(root, tmp_path):
    """QA: a broken or missing NPC database only switches the NPC search off."""
    for name, data in (("garbage.sqlite", b"not a database" * 500), ("missing.sqlite", None)):
        path = tmp_path / name
        if data is not None:
            path.write_bytes(data)
        window = MapView(root, {}, bestiary_database=path)
        window.search_var.set("страж")
        window._run_mob_search()
        window.wait_for_mob_search()
        assert window.bestiary_database is None



def test_wheel_zoom_glides_in_frames_and_keeps_the_point_under_the_cursor(root):
    root.geometry("1400x900")
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    window.open_zone("220070000")
    root.update()
    window.zoom = window._fit_zoom() * 2
    before = window.zoom
    image_point = (window.left + 300 / window.zoom, window.top + 200 / window.zoom)
    window.zoom_at(1.25, 300, 200)
    window.zoom_at(1.25, 300, 200)  # two clicks in a row add up
    seen = [window.zoom]
    deadline = time.monotonic() + 3
    while window._zoom_after is not None and time.monotonic() < deadline:
        root.update()
        seen.append(window.zoom)
    assert window.zoom == pytest.approx(before * 1.25 * 1.25)
    assert len(set(round(z, 6) for z in seen)) > 3  # it passed through in-between levels
    assert seen == sorted(seen)  # and never went back
    assert window.to_screen(*image_point) == pytest.approx((300, 200), abs=1.5)


def test_zoom_jumps_when_motion_is_off(root):
    window = MapView(root, zones())
    window.open_zone("220070000")
    window.motion_enabled = lambda: False
    before = window.zoom
    window.zoom_at(1.25, 50, 50)
    assert window.zoom == pytest.approx(before * 1.25) and window._zoom_after is None


def test_npc_search_runs_in_the_background_and_builds_cards_in_batches(root, tmp_path, monkeypatch):
    """The map stays responsive: the search is answered by a thread, the result cards appear tick by tick."""
    import watcher.mapview as module
    from core.bestiary.search_worker import SearchWorker

    class FakeStore:
        def __init__(self, path): pass
        def search(self, text="", *args, **kwargs):
            time.sleep(0.05)
            return [{"id": str(i)} for i in range(9)], 9
        def detail(self, npc_id):
            return {"id": npc_id, "name": f"Моб {npc_id}", "kind": "Монстр", "level": "5", "category": "monster",
                    "points": [{"map_id": "220070000", "gx": 100.0, "gy": 100.0}]}
        def areas(self, npc_id): return []
        def close(self): pass

    monkeypatch.setattr(module, "BestiaryStore", FakeStore)
    monkeypatch.setattr(module, "SearchWorker", lambda path: SearchWorker(path, store_factory=FakeStore))
    window = MapView(root, zones(), bestiary_database=tmp_path / "fake.sqlite")
    window.pack(fill="both", expand=True)
    window.open_zone("220070000")
    root.update()
    window.search_var.set("моб")
    window._run_mob_search()
    assert window._mob_polling and not window.mob_content.winfo_children()  # returned at once, nothing built yet
    ticks = []
    real = window._run_mob_jobs
    window._run_mob_jobs = lambda jobs, start, generation: (ticks.append(start), real(jobs, start, generation))
    window.wait_for_mob_search()
    cards = [w for w in window.mob_content.winfo_children() if isinstance(w, tk.Frame)]
    assert len(cards) == 9
    assert len(ticks) >= 3  # the list was built in several ticks, not in one
    window.destroy()


def test_map_cursor_is_a_hand_only_while_dragging_and_plain_otherwise(root):
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    window.open_zone("220070000")
    root.update()
    assert str(window.canvas.cget("cursor")) == ""  # not stuck on fleur
    press = type("E", (), {"x": 50, "y": 50})()
    window._on_press(press)
    assert str(window.canvas.cget("cursor")) == "fleur"
    window._on_release(type("E", (), {"x": 90, "y": 90})())
    assert str(window.canvas.cget("cursor")) == ""


def test_clear_all_removes_pins_areas_search_and_results(root):
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    root.update()
    window.show(Place("220070000", 1421, 1346, "Натараз"), others=[Place("220070000", 1500, 1400, "x")],
                spawn_areas=[[[100, 100], [140, 100], [120, 140]]])
    window.search_var.set("страж")
    window._mob_rows = [{"id": "1"}]
    window.clear_all()
    root.update()
    assert window.place is None and window.others == [] and window.spawn_areas == [] and window.selected is None
    assert window.search_var.get() in ("", "Найти: NPC, район") and not window.title.cget("text")
    assert not window.mob_panel.winfo_manager() and window._mob_rows == []
    assert not window.canvas.find_withtag("pin") and not window.canvas.find_withtag("other")
    window.show(Place("220070000", 1421, 1346, "Натараз"))  # the next place brings the pins back
    assert window._pins_cleared is False


def test_every_npc_point_of_elysium_and_the_new_zones_is_on_its_map():
    """Elysium's points were partly off its picture (market, port); the new zones are framed around their NPCs."""
    from core.map.poi import PoiStore
    found = zones()
    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    for map_id in ("110010000", "110020000", "120020000", "110070000", "120080000"):
        zone = found[map_id]
        points = store.in_zone(map_id, set(store.types), "", None)
        assert points, map_id
        for p in points:
            x, y = zone.to_image(p.gx, p.gy)
            assert 0 <= x <= zone.size and 0 <= y <= zone.size, (zone.name, p.name)


def test_abyss_points_and_area_names_belong_to_one_layer():
    from core.map.poi import PoiStore
    zone = zones()["400010000"]
    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    assert all(p.layer in (1, 2, 3) for p in store.in_zone("400010000", set(store.types), "", None))
    assert zone.label_layers and all(layer in (1, 2, 3) for layer in zone.label_layers)


def test_zone_list_follows_the_race_common_zones_and_that_races_own(root):
    window = MapView(root, zones(), side="dark")
    names = set(window.zone_box.cget("values"))
    assert {"Пандемониум", "Альтгард", "Келькмарос", "Ингисон", "Арэшурат", "Тоннель Силентера"} <= names  # own + common
    assert not {"Элизиум", "Фоэта", "Бертрон"} & names  # the other race's zones are not offered
    window.side_var.set("Элийцы")
    window._on_side_selected()
    names = set(window.zone_box.cget("values"))
    assert {"Элизиум", "Фоэта", "Келькмарос", "Арэшурат"} <= names and not {"Пандемониум", "Альтгард"} & names


def test_switching_the_race_leaves_a_zone_of_the_other_race_for_the_capital(root):
    window = MapView(root, zones(), side="dark")
    window.open_zone("220030000")  # Altgard
    window.side_var.set("Элийцы")
    window._on_side_selected()
    assert window.zone.map_id == "110010000"  # Elysium
    window.open_zone("220070000")  # Gelkmaros: shared, stays
    window.side_var.set("Асмодиане")
    window._on_side_selected()
    assert window.zone.map_id == "220070000"


def test_every_zone_has_a_race_from_the_client():
    found = zones()
    assert found["120010000"].side == "dark" and found["110010000"].side == "light"
    assert found["220070000"].side == "" and found["400010000"].side == "" and found["600010000"].side == ""
    assert found["120020000"].side == "dark" and found["110070000"].side == "light"  # temples and arenas


def test_marks_menu_switches_kinds_of_points_without_an_all_entry(root):
    saved = []
    window = MapView(root, zones(), poi=None, on_filters=saved.append)
    menu = window.filter_menu
    assert [menu.entrycget(i, "label") for i in range(7)] == [
        "Здания", "Подземелья", "Пространственные разломы", "Торговцы", "Телепорты", "Склад, стигмы, почта", "Задания"]
    assert menu.index("end") == 6  # seven entries and nothing like «show all»
    window._filter_vars["merchants"].set(False)
    window._on_filters_changed()
    assert saved == [["merchants"]]
    assert not {"merchant", "coin_merchant", "vendor"} & window.layers or not window.poi.types  # off (no data here)


def test_marks_filter_hides_the_chosen_kinds_and_is_restored_from_config(root):
    from core.map.poi import PoiStore
    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    window = MapView(root, zones(), poi=store, hidden_groups=["merchants", "buildings", "dungeons"])
    assert not {"merchant", "coin_merchant", "vendor", "fortress", "dungeon"} & window.layers
    assert {"teleport", "warehouse", "stigma"} <= window.layers
    window._filter_vars["merchants"].set(True)
    window._on_filters_changed()
    assert {"merchant", "vendor"} <= window.layers and "fortress" not in window.layers


def test_toolbar_is_at_the_left_and_the_theme_switch_is_gone(root):
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    root.geometry("1300x700")
    root.update()
    group = window.zone_box.master
    assert group.winfo_x() < 20  # not centred in the bar
    assert not hasattr(window, "theme_box") and not hasattr(window, "theme_var")



def test_dungeons_rifts_and_quests_are_menu_entries_and_the_check_box_is_gone(root):
    from core.map.poi import PoiStore
    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    assert store.types["direct_portal"]["name"] == "Пространственный разлом"
    window = MapView(root, zones(), poi=store, hidden_groups=["rifts"])
    assert "dungeon" in window.layers and "direct_portal" not in window.layers  # rifts off by default (config)
    window._filter_vars["rifts"].set(True)
    window._on_filters_changed()
    assert "direct_portal" in window.layers
    window._filter_vars["dungeons"].set(False)
    window._on_filters_changed()
    assert "dungeon" not in window.layers and "fortress" in window.layers  # the buildings are a group of their own
    assert [w for w in window.zone_box.master.winfo_children() if "Checkbutton" in w.winfo_class()] == []
    rifts = window.poi.in_zone("220040000", {"direct_portal"})
    assert len(rifts) > 0 and all(p.type == "direct_portal" for p in rifts)  # Beluslan has them


def test_icon_groups_do_not_change_while_the_map_is_dragged():
    """Dragging at one zoom must not merge, split or move icons: the cells are laid out from the map's origin."""
    from core.map.poi import Poi, cluster

    points = [Poi("z", "merchant", 100 + 37 * i % 211, 200 + 53 * i % 197, 0, 0, f"p{i}") for i in range(60)]
    zoom, radius = 0.45, 36.0

    def groups(left, top):
        to_screen = lambda x, y: ((x - left) * zoom, (y - top) * zoom)
        return {frozenset(m.name for m in members): (round(sx + left * zoom, 6), round(sy + top * zoom, 6))
                for sx, sy, members in cluster(points, to_screen, radius)}

    base = groups(0.0, 0.0)
    for left, top in ((13.3, 0.0), (0.0, 41.7), (-77.1, 129.9), (333.3, -250.5)):
        assert groups(left, top) == base  # the same groups at the same map positions, whatever the view


def test_silentera_tunnel_passes_belong_to_the_rifts_entry():
    from watcher.mapview import FILTER_GROUPS
    assert "tunnel" in FILTER_GROUPS["rifts"][1] and "tunnel" not in FILTER_GROUPS["buildings"][1]


def test_place_marker_is_65_percent_of_the_former_size(root):
    """map:32: the blue X of a place from the chat went from 34 px to 22 px (34 * 0.65 = 22.1), scaled from place.png."""
    from watcher.mapview import PLACE_ICON, load_icon

    assert PLACE_ICON == 22
    icon = load_icon(resource_root() / "data" / "maps" / "icons" / "place.png", PLACE_ICON, root)
    assert icon is not None and max(icon.width(), icon.height()) == 22
