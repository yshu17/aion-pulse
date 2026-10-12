"""Contract tests for the Windows UI snapshot tool."""

from PIL import Image

from tools.ui_snapshots import compare_geometry, compare_images, make_fixture


def test_geometry_allows_one_pixel_but_reports_larger_shift():
    expected = {"widgets": {"start": {"x": 10, "y": 20, "width": 100, "height": 30, "requested_width": 90}}, "overlaps": []}
    actual = {"widgets": {"start": {"x": 11, "y": 20, "width": 100, "height": 30, "requested_width": 90}}, "overlaps": []}
    assert compare_geometry(actual, expected) == []
    actual["widgets"]["start"]["x"] = 12
    assert any("start.x" in issue for issue in compare_geometry(actual, expected))


def test_geometry_reports_clipped_control_and_overlap():
    expected = {"widgets": {"tab-search": {"x": 0, "y": 0, "width": 80, "height": 40, "requested_width": 70}}, "overlaps": []}
    actual = {"widgets": {"tab-search": {"x": 0, "y": 0, "width": 60, "height": 40, "requested_width": 70}}, "overlaps": ["start/status"]}
    issues = compare_geometry(actual, expected)
    assert any("clipped" in issue for issue in issues)
    assert any("overlap" in issue for issue in issues)


def test_pixel_threshold_and_masks():
    expected = Image.new("RGB", (100, 100), (20, 20, 20))
    actual = expected.copy()
    actual.putpixel((4, 4), (36, 20, 20))  # exactly 16: unchanged
    actual.putpixel((5, 5), (37, 20, 20))  # 17: different
    result = compare_images(actual, expected, masks=[])
    assert result["different_pixels"] == 1
    assert result["fraction"] == 0.0001
    assert result["passed"]
    assert compare_images(actual, expected, masks=[(0, 0, 10, 10)])["different_pixels"] == 0


def test_pixel_fraction_at_limit_fails():
    expected = Image.new("RGB", (10, 10), "black")
    actual = expected.copy()
    actual.putpixel((0, 0), (255, 255, 255))
    assert not compare_images(actual, expected, masks=[], max_fraction=0.002)["passed"]


def test_fixture_is_local_and_disables_side_effects(tmp_path):
    import json

    config = make_fixture(tmp_path)
    data = json.loads(config.read_text(encoding="utf-8"))
    assert config.parent == tmp_path
    assert data["chat_log"] == str(tmp_path / "Chat.log")
    assert data["game_check"] is False
    assert data["reduce_motion"] is True
    assert data["nag_popup"] is False
    assert (tmp_path / "Chat.log").read_text(encoding="cp1251").startswith("2026.10.10 18:01:07")

def test_tab_geometry_uses_ttk_identify_not_grid_bbox():
    import tkinter as tk
    from tkinter import ttk
    from tools.ui_snapshots import measure_tab_rects

    root = tk.Tk()
    root.geometry("600x200+100+100")
    try:
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)
        for title in ("Поиск", "Весь чат", "Карта"):
            notebook.add(ttk.Frame(notebook), text=title)
        root.update_idletasks()
        root.update()
        rects = measure_tab_rects(notebook)
        assert len(rects) == 3
        assert all(rect[2] > 0 and rect[3] > 0 for rect in rects)
    finally:
        root.destroy()


def test_printwindow_captures_full_client_background():
    import tkinter as tk
    from tools.ui_snapshots import print_client_window

    root = tk.Tk()
    root.geometry("200x100+100+100")
    root.configure(bg="#123456")
    root.attributes("-topmost", True)
    try:
        import time
        for _ in range(3):
            root.update_idletasks()
            root.update()
            time.sleep(0.05)
        image = print_client_window(root)
        assert image.getpixel((5, 5)) == (18, 52, 86)
    finally:
        root.destroy()

def test_worker_records_actual_requested_minimum_size(tmp_path):
    import json
    from tools.ui_snapshots import _worker

    assert _worker(tmp_path, "tabs-search", 1000, 600) == 0
    geometry = json.loads((tmp_path / "geometry-parts" / "1000x600_tabs-search.json").read_text(encoding="utf-8"))
    assert geometry["window"] == [1000, 600]

def test_settings_snapshot_uses_fixed_visible_path(tmp_path, capsys):
    from tools.ui_snapshots import _worker

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    assert _worker(first, "settings-open", 1400, 860) == 0
    assert _worker(second, "settings-open", 1400, 860) == 0
    image_name = "1400x860_settings-open.png"
    assert (first / "shots" / image_name).read_bytes() == (second / "shots" / image_name).read_bytes()
    assert "invalid command name" not in capsys.readouterr().err

def test_freeze_dynamic_map_coordinate_label():
    from types import SimpleNamespace
    from tools.ui_snapshots import freeze_dynamic_state

    field = SimpleNamespace(value="x 1756 · y 3562")
    field.set = lambda value: setattr(field, "value", value)
    deleted = []
    canvas = SimpleNamespace(delete=lambda tag: deleted.append(tag))
    app = SimpleNamespace(map_view=SimpleNamespace(coords_var=field, canvas=canvas))
    freeze_dynamic_state(app)
    assert field.value == ""
    assert deleted == ["bubble"]

def test_run_report_discloses_forced_minimum_and_dpi_limit():
    from tools.ui_snapshots import render_run_report

    geometry = {"1000x600_tabs-search": {"window": [1000, 600], "native_minimum": [1132, 600], "widgets": {}, "overlaps": []}}
    report = render_run_report(geometry)
    assert "1000x600_tabs-search" in report
    assert "1132" in report
    assert "системный DPI" in report

def test_wrong_tab_padding_is_detected_visually_and_geometrically():
    import tkinter as tk
    from tkinter import ttk
    from watcher import theme
    from watcher.catalog import resource_root
    from tools.ui_snapshots import measure_tab_rects, print_client_window

    root = tk.Tk()
    root.geometry("600x200+100+100")
    root.attributes("-topmost", True)
    try:
        theme.apply_dark_theme(root, resource_root() / "data" / "ui")
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)
        for title in ("Поиск", "Весь чат", "Карта"):
            notebook.add(ttk.Frame(notebook), text=title)
        for _ in range(3):
            root.update_idletasks()
            root.update()
        expected_rect = measure_tab_rects(notebook)[0]
        expected_image = print_client_window(root)
        ttk.Style(root).configure("TNotebook.Tab", padding=(22, 8))
        root.update_idletasks()
        root.update()
        actual_rect = measure_tab_rects(notebook)[0]
        actual_image = print_client_window(root)
        expected = {"widgets": {"tab-0": dict(zip(("x", "y", "width", "height"), expected_rect))}, "overlaps": []}
        actual = {"widgets": {"tab-0": dict(zip(("x", "y", "width", "height"), actual_rect))}, "overlaps": []}
        assert any("tab-0.width" in issue for issue in compare_geometry(actual, expected))
        assert compare_images(actual_image, expected_image)["different_pixels"] > 0
    finally:
        root.destroy()
