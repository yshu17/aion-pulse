import tkinter as tk

import pytest

from watcher import theme
from watcher.catalog import resource_root
from watcher.mapview import MapView, Place, load_zones
from watcher.parser import MAP_NAMES


@pytest.fixture
def root():
    r = tk.Tk()
    theme.apply_dark_theme(r)
    yield r
    r.destroy()


def zones():
    return load_zones(resource_root() / "data" / "maps", MAP_NAMES)


def test_game_maps_follow_the_client_zonemap_framing():
    """data/maps/client: the game's own maps (newmap); transforms from zonemap.xml, checked on aiondb NPC markers."""
    found = zones()
    assert set(found) >= {"220010000", "220030000", "220020000", "220050000", "220040000", "220070000",
                          "210050000", "600010000", "120010000"}
    assert found["220070000"].name == "Келькмарос"
    assert all(z.path.parent.name == "client" and z.size == 3072 for z in found.values())
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
    from watcher.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store)
    altgard = view.zones["220030000"]
    for p in view.poi.in_zone("220030000", {"teleport", "merchant"}):
        assert (p.x, p.y) == pytest.approx(altgard.to_image(p.gx, p.gy))


def test_missing_maps_dir_gives_no_zones(tmp_path):
    assert load_zones(tmp_path, MAP_NAMES) == {}


def test_show_centres_on_place_and_zoom_keeps_point_under_cursor(root):
    window = MapView(root, zones())
    window.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    place = Place("220070000", 978.8, 1265.0, "Место · Келькмарос")
    others = [Place("220070000", 1500, 1500, "Место", "12:00 Nick: го"), Place("210050000", 1, 1, "x")]
    window.show(place, others)
    root.update()
    assert window.others == [others[0]]  # pins only from the same zone
    width, height = window._canvas_size()
    sx, sy = window.to_screen(*window.zone.to_image(place.x, place.y))
    assert abs(sx - width / 2) < 2 and abs(sy - height / 2) < 2
    before = window.zoom
    image_point = (window.left + 100 / window.zoom, window.top + 120 / window.zoom)
    window.zoom_at(1.25, 100, 120)
    assert window.zoom > before
    assert window.to_screen(*image_point) == pytest.approx((100, 120), abs=1)
    window.render()
    assert window.canvas.find_withtag("pin") and window.canvas.find_withtag("other")
    for _ in range(40):
        window.zoom_at(0.5, 10, 10)
    assert window.zoom == pytest.approx(window._fit_zoom())  # never smaller than the whole map


def test_zone_without_map_says_so(root):
    window = MapView(root, {})
    window.show(Place("400010000", 1, 2, "Место · Арэшурат"))
    assert "карты этой зоны нет" in window.title.cget("text")


def test_area_names_on_maps(root):
    found = zones()
    kelk = found["220070000"]
    names = {text for _x, _y, text in kelk.labels}
    assert {"Митраканд", "Крепость Келькмарос", "Вход в тоннель Силентера в Келькмаросе"} <= names
    assert all(0 <= x <= kelk.size and 0 <= y <= kelk.size for x, y, _t in kelk.labels)
    assert "Коридор\nмучений" in {t for _x, _y, t in found["600010000"].labels}  # «|» is a line break
    window = MapView(root, found)
    window.pack(fill="both", expand=True)
    root.geometry("1000x900")
    root.update()
    window.show(Place("220070000", 1173.0, 1227.4, "Место"))
    root.update()
    window.render()
    shown = {window.canvas.itemcget(i, "text") for i in window.canvas.find_withtag("label")}
    assert "Запечатанная башня" in shown


def test_labels_file_errors_are_ignored(tmp_path):
    from watcher.mapview import load_labels

    path = tmp_path / "labels.tsv"
    path.write_text("# c\n@df4\t3072\ndf4\t1\t2\tA|B\ndf4\tx\t2\tbad\nzz\t1\t1\tno zone\n", encoding="utf-8")
    assert load_labels(path) == {"df4": (3072.0, [(1.0, 2.0, "A\nB")])}
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


def test_fixed_point_set_without_gathering_quests_or_portals(root):
    from watcher.poi import PoiStore

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
    hidden = {"portal", "direct_portal", "quest_point"} | {t for t in store.types if t.startswith("gather_")}
    assert not view.layers & hidden
    shown = {m.type for _x, _y, members in view._drawn for m in members}
    assert "teleport" in shown and not shown & hidden
    # icons are big, teleporters bigger still
    assert view._icon_size("teleport") > view._icon_size("merchant") >= 24


def test_point_card_and_nearby(root):
    from types import SimpleNamespace

    from watcher.poi import PoiStore

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
    assert types[:2] == ["teleport", "warehouse"]
    assert all(m < 600 for t, _n, m in view.point_card.rows if t in ("warehouse", "merchant"))
    # clicking a «Рядом» row selects that point and rings it
    view.point_card.near.winfo_children()[1].event_generate("<Button-1>")
    root.update()
    assert view.selected is not None and view.selected.type == "warehouse"
    view.render()
    assert view.canvas.find_withtag("selected")
    # a click (no drag) on a single drawn point opens its card
    view.open_zone("220070000")
    root.update()
    teleport = view.poi.in_zone("220070000", {"teleport"})[0]
    view.zoom = 3.0
    view.center_on(teleport.x, teleport.y)
    sx, sy, members = next(d for d in view._drawn if d[2] == [teleport])
    view._on_press(SimpleNamespace(x=int(sx), y=int(sy)))
    view._on_release(SimpleNamespace(x=int(sx), y=int(sy)))
    assert view.selected == members[0]


def test_map_search_points_and_areas(root):
    from watcher.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons")
    view.pack(fill="both", expand=True)
    root.geometry("1400x900")
    root.update()
    view.open_zone("220070000")
    assert view.search("привратник", 0) == "1 / 2"
    first = view.selected
    assert first.type == "teleport"
    assert view.search("привратник", 1) == "2 / 2" and view.selected != first
    assert view.search("привратник", 1) == "1 / 2"  # wraps around
    assert view.search("митраканд", 0).endswith("/ 2")  # area names: «Митраканд», «Сигнальный маяк Митраканда»
    assert view.point_card.kind.cget("text") == "Район"
    assert view.search("абвгд", 0) == "нет"
    assert view.search("портал", 0) == "нет"  # hidden kinds are not found either
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
