import tkinter as tk

import pytest

from watcher import theme
from watcher.catalog import resource_root
from watcher.mapview import MapWindow, Place, load_zones
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
    window = MapWindow(root, zones())
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
    window.close()


def test_zone_without_map_says_so(root):
    window = MapWindow(root, {})
    window.show(Place("400010000", 1, 2, "Место · Арэшурат"))
    assert "карты этой зоны нет" in window.title.cget("text")
    window.close()
