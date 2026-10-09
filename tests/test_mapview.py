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


def test_bundled_zones_and_transform():
    found = zones()
    assert {"220070000", "210050000", "120010000", "600010000"} <= set(found)
    kelk = found["220070000"]
    assert kelk.name == "Келькмарос"
    # aioncodex: an NPC at game (978.8, 1265.0) sits at (1687.70, 1305.98) of its 4096 px map
    x, y = kelk.to_image(978.8, 1265.0)
    scale = kelk.size / 4096
    assert abs(x - 1687.70 * scale) < 2 and abs(y - 1305.98 * scale) < 2


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


def test_layers_draw_points_and_presets(root, tmp_path):
    from watcher.poi import PoiStore

    store = PoiStore.load(resource_root() / "data" / "maps" / "poi.json")
    saved = []
    view = MapView(root, zones(), poi=store, icons_dir=resource_root() / "data" / "maps" / "icons",
                   layers=None, on_layers=saved.append)
    view.pack(fill="both", expand=True)
    root.geometry("1300x900")
    root.update()
    view.open_zone("220070000")
    root.update()
    view.render()
    assert view.layers >= {"teleport", "warehouse", "portal"}  # default: NPCs and landmarks
    assert not any(t.startswith("gather_") for t in view.layers)
    assert view.canvas.find_withtag("poi")
    shown = {m.type for _x, _y, members in view._drawn for m in members}
    assert "teleport" in shown
    view.panel.apply_preset("Сбор")
    root.update()
    view.render()
    assert saved[-1] and all(t.startswith("gather_") for t in saved[-1])
    assert {m.type for _x, _y, ms in view._drawn for m in ms} <= saved[-1]
    view.panel.apply_preset("Ничего")
    view.render()
    assert not view.canvas.find_withtag("poi")
    assert view.panel.count_labels["teleport"].cget("text") == "2"  # Kelkmaros has 2 teleporters in the client
