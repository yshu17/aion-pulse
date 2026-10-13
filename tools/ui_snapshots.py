"""Windows-only, deterministic visual snapshots for Aion Chat Watcher.

Uses Win32 PrintWindow(PW_CLIENTONLY) and temporary app inputs. Run from the repo:
    python tools/ui_snapshots.py check
"""

from __future__ import annotations

import argparse
import fnmatch
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RUNS = ROOT / "tmp" / "ui-snapshots"
BASELINE = ROOT / "docs" / "ui" / "baseline"
# known layout defects: a match does not fail a scenario, but is written to the report with its ticket
KNOWN_DEFECTS = ROOT / "docs" / "ui" / "known_defects.json"
WINDOWS = ((1400, 860), (1000, 600))
SCENARIOS = ("tabs-search", "tabs-chat", "tabs-map", "tabs-schedule", "map-100", "map-125", "map-150",
             "settings-open", "settings-closed", "header-idle", "header-counters")
GEOMETRY_TOLERANCE = 1
PIXEL_CHANNEL_THRESHOLD = 16
MAX_DIFFERENT_FRACTION = 0.002
WORKER_TIMEOUT = 60
# Dynamic areas are centralized here. The fixture disables animations, so no mask is currently needed.
DYNAMIC_MASKS: dict[str, tuple[tuple[int, int, int, int], ...]] = {}


def make_fixture(directory: Path) -> Path:
    """Create fixed, private Chat.log and configuration under a disposable directory."""
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "Chat.log"
    log.write_bytes((
        "2026.10.10 18:01:07 : [3.Поиск группы] [charname:Tester;1.0000 0.6941 0.6941]: Ищу группу\\r\\n"
        "2026.10.10 18:01:08 : [3.Поиск группы] [charname:Friend;1.0000 0.6941 0.6941]: Привет\\r\\n"
    ).replace("\\r\\n", "\r\n").encode("cp1251"))
    config = directory / "config.json"
    config.write_text(json.dumps({
        "chat_log": str(log), "game_dir": str(directory), "game_check": False,
        "reduce_motion": True, "nag_popup": False, "settings_open": False,
        "sound_path": "", "keywords": ["группа"], "watch_items": [],
        "history_min": 0, "map_theme": "game", "map_side": "dark",
    }, ensure_ascii=False), encoding="utf-8")
    return config


def compare_geometry(actual: dict, expected: dict, tolerance: int = GEOMETRY_TOLERANCE) -> list[str]:
    """Report named-widget movement, clipping and overlapping header controls."""
    issues: list[str] = []
    a_widgets = actual.get("widgets", {})
    e_widgets = expected.get("widgets", {})
    for name in sorted(set(a_widgets) | set(e_widgets)):
        if name not in a_widgets or name not in e_widgets:
            issues.append(f"{name}: missing in {'actual' if name not in a_widgets else 'baseline'}")
            continue
        a, e = a_widgets[name], e_widgets[name]
        for key in ("x", "y", "width", "height"):
            if abs(int(a[key]) - int(e[key])) > tolerance:
                issues.append(f"{name}.{key}: {a[key]} vs {e[key]}")
        if "requested_width" in a and int(a["requested_width"]) > int(a["width"]):
            issues.append(f"{name}: clipped ({a['requested_width']} > {a['width']})")
    for overlap in actual.get("overlaps", []):
        issues.append(f"overlap: {overlap}")
    return issues


def load_known_defects(path: Path = KNOWN_DEFECTS) -> list[dict]:
    """Entries: {"id", "ticket", "scenarios": glob patterns, "issue": prefix of the geometry issue text}."""
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def split_known(issues: list[str], scenario: str, known: list[dict]) -> tuple[list[str], list[str]]:
    """Return (new issues, known issues). A known issue is matched by scenario glob and text prefix only,
    so a different widget or another kind of problem still fails."""
    new, matched = [], []
    for issue in issues:
        hit = next((d for d in known
                    if fnmatch.fnmatch(scenario, d["scenarios"]) and issue.startswith(d["issue"])), None)
        if hit is None:
            new.append(issue)
        else:
            matched.append(f"{hit['id']} ({hit['ticket']}): {issue}")
    return new, matched


def compare_images(actual: Image.Image, expected: Image.Image, masks: list[tuple[int, int, int, int]] | tuple = (),
                   channel_threshold: int = PIXEL_CHANNEL_THRESHOLD,
                   max_fraction: float = MAX_DIFFERENT_FRACTION) -> dict:
    """Compare RGB pixels; masked rectangles and sub-threshold channel changes are ignored."""
    if actual.size != expected.size:
        return {"passed": False, "different_pixels": None, "fraction": 1.0,
                "size_error": f"{actual.size} vs {expected.size}", "diff": None}
    a, e = actual.convert("RGB"), expected.convert("RGB")
    width, height = a.size
    mask = Image.new("1", a.size, 0)
    if masks:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        for x0, y0, x1, y1 in masks:
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=1)
    a_pixels, e_pixels, m_pixels = a.load(), e.load(), mask.load()
    diff = Image.new("RGB", a.size, (0, 0, 0))
    d_pixels = diff.load()
    count = 0
    eligible = 0
    for y in range(height):
        for x in range(width):
            if m_pixels[x, y]:
                continue
            eligible += 1
            if max(abs(v1 - v2) for v1, v2 in zip(a_pixels[x, y], e_pixels[x, y])) > channel_threshold:
                count += 1
                d_pixels[x, y] = (255, 0, 0)
    fraction = count / eligible if eligible else 0.0
    return {"passed": fraction < max_fraction, "different_pixels": count,
            "fraction": fraction, "size_error": None, "diff": diff}


def _rect(widget, root) -> dict[str, int]:
    return {"x": widget.winfo_rootx() - root.winfo_rootx(),
            "y": widget.winfo_rooty() - root.winfo_rooty(),
            "width": widget.winfo_width(), "height": widget.winfo_height()}


def measure_tab_rects(notebook) -> list[tuple[int, int, int, int]]:
    """Find tab bounds via ttk identify tab; Notebook.bbox is grid's unrelated method."""
    count = len(notebook.tabs())
    y = min(20, max(0, notebook.winfo_height() - 1))
    groups: list[list[int]] = [[] for _ in range(count)]
    seen = set()
    for x in range(notebook.winfo_width()):
        index = notebook.tk.call(notebook._w, "identify", "tab", x, y)
        if index != "":
            number = int(index)
            if 0 <= number < count:
                groups[number].append(x)
                seen.add(number)
        elif len(seen) == count:
            break
    rects = []
    for xs in groups:
        if not xs:
            raise RuntimeError("Tk did not expose all tab rectangles")
        middle = (xs[0] + xs[-1]) // 2
        ys = [row for row in range(min(100, notebook.winfo_height()))
              if notebook.tk.call(notebook._w, "identify", "tab", middle, row) != ""]
        if not ys:
            raise RuntimeError("Tk tab height is zero")
        rects.append((xs[0], ys[0], xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1))
    return rects

def collect_geometry(root, app, scenario: str) -> dict:
    """Measure visible UI controls in client coordinates after the render settles."""
    widgets = {"notebook": _rect(app.tabs, root), "start": _rect(app.start_btn, root),
               "status-chip": _rect(app.status_label, root), "counters": _rect(app.counters_bar, root),
               "settings-button": _rect(app.settings_btn, root)}
    widgets["start"]["requested_width"] = app.start_btn.winfo_reqwidth()
    widgets["settings-button"]["requested_width"] = app.settings_btn.winfo_reqwidth()
    for name, widget in (("feed", app.feed), ("item-list", app.item_list.canvas),
                         ("map-canvas", app.map_view.canvas), ("settings-card", app.settings_card)):
        if widget.winfo_ismapped():
            widgets[name] = _rect(widget, root)
    tab_rects = []
    measured_tabs = measure_tab_rects(app.tabs)
    for index, label in enumerate(("Поиск", "Весь чат", "Карта")):
        x, y, w, h = measured_tabs[index]
        if w > 0 and h > 0:
            tab_rect = {"x": widgets["notebook"]["x"] + x, "y": widgets["notebook"]["y"] + y,
                        "width": w, "height": h}
            tab_rects.append((label, tab_rect))
            widgets[f"tab-{index}"] = tab_rect
    if len(tab_rects) != 3:
        raise RuntimeError("Tk did not provide nonzero tab bbox after layout")
    # A clipping check for tabs needs actual text width + style padding, not the notebook's reqwidth.
    from tkinter import font as tkfont, ttk
    style = ttk.Style(root)
    pad = tuple(map(int, root.tk.splitlist(style.configure("TNotebook.Tab")["padding"])))
    tab_font = tkfont.Font(root=root, font=style.configure("TNotebook.Tab")["font"])
    for index, (label, rect) in enumerate(tab_rects):
        widgets[f"tab-{index}"]["requested_width"] = tab_font.measure(label) + 2 * pad[0]
    header_names = ("start", "status-chip", "settings-button")
    overlaps = []
    for i, first in enumerate(header_names):
        for second in header_names[i + 1:]:
            a, b = widgets[first], widgets[second]
            if a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and \
               a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]:
                overlaps.append(f"{first}/{second}")
    return {"scenario": scenario, "window": [root.winfo_width(), root.winfo_height()],
            "widgets": widgets, "overlaps": overlaps}


def print_client_window(root, frame: bool = False) -> Image.Image:
    """Capture Tk client area with PrintWindow(PW_CLIENTONLY | PW_RENDERFULLCONTENT); with ``frame`` the whole
    top-level window, title bar and its icon included (evidence for window-chrome tasks such as ui:17)."""
    if os.name != "nt":
        raise RuntimeError("PrintWindow capture requires Windows")
    hwnd = root.winfo_id()
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    if frame:
        hwnd = int(root.wm_frame(), 16)
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    user32.PrintWindow.argtypes = (wintypes.HWND, wintypes.HDC, wintypes.UINT)
    gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.GetDIBits.argtypes = (wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                               ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
    gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
    gdi32.DeleteDC.argtypes = (wintypes.HDC,)
    rect = wintypes.RECT()
    if frame:
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise OSError("GetWindowRect failed")
        width, height = rect.right - rect.left, rect.bottom - rect.top
    elif not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise OSError("GetClientRect failed")
    else:
        width, height = rect.right, rect.bottom
    if width < 1 or height < 1:
        raise RuntimeError("Window has an empty client area")
    window_dc = user32.GetDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    if not window_dc or not memory_dc or not bitmap:
        raise OSError("Cannot allocate PrintWindow bitmap")
    old = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, memory_dc, 2 if frame else 3):
            raise OSError("PrintWindow(PW_CLIENTONLY) failed")
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]
        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down, client coordinates
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        buffer = ctypes.create_string_buffer(width * height * 4)
        if gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0) != height:
            raise OSError("GetDIBits failed")
        return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(memory_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def _settle(root, app) -> None:
    for _ in range(4):
        root.update_idletasks()
        root.update()
        time.sleep(0.05)
    deadline = time.monotonic() + 10
    while getattr(app.map_view, "_render_after", None) is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.05)
    root.update_idletasks()
    root.update()


def freeze_dynamic_state(app) -> None:
    """Clear pointer coordinates, which depend on where the host mouse happens to be."""
    app.map_view.coords_var.set("")
    app.map_view.canvas.delete("bubble")


def _worker(run_dir: Path, scenario: str, width: int, height: int) -> int:
    import tkinter as tk
    from watcher.app import App
    key = f"{width}x{height}_{scenario}"
    frame = scenario.startswith("frame-")  # evidence only: whole window with its title bar, not in SCENARIOS
    if frame:
        scenario = scenario[len("frame-"):]
    with tempfile.TemporaryDirectory(prefix="inputs-", dir=run_dir) as temporary:
        input_dir = Path(temporary)
        config = make_fixture(input_dir)
        prior_cwd = Path.cwd()
        os.chdir(input_dir)
        root = None
        app = None
        try:
            root = tk.Tk()
            base = float(root.tk.call("tk", "scaling"))
            factor = {"map-100": 1.0, "map-125": 1.25, "map-150": 1.5}.get(scenario, 1.0)
            root.tk.call("tk", "scaling", base * factor)
            app = App(root, config)
            app.game_dir_var.set(r"C:\Snapshot\Chat.log")  # fixed display; cfg still points to temporary log
            if hasattr(app, "toasts"):  # older commits (evidence shots) have no toast centre
                app.toasts.close()  # no notifications or toast windows in the fixture
            root.update_idletasks()
            root.update()  # run App._init_split, which may raise the normal minimum width
            native_minimum = list(root.minsize())
            # fixture-only: expose clipping at the contractual sizes, below the scaled native minimum (ui:28)
            root.minsize(min(width, native_minimum[0]), min(height, native_minimum[1]))
            root.geometry(f"{width}x{height}+100+100")
            root.attributes("-topmost", True)
            if scenario in ("tabs-chat",):
                app.tabs.select(app.all_chat)
            elif scenario in ("tabs-map", "map-100", "map-125", "map-150"):
                app.tabs.select(app.map_view)
                _settle(root, app)
                app.map_view.open_zone("220070000")
            elif scenario == "tabs-schedule":
                # a fixed Wednesday 20:30 MSK shown in MSK: the shot does not depend on today or the machine zone
                from datetime import timedelta as _td, timezone as _tz
                from datetime import datetime as _dt
                app.schedule_tab.clock = lambda: _dt(2026, 10, 14, 20, 30)
                app.schedule_tab.tz = _tz(_td(hours=3))
                app.schedule_tab.day_var.set("Среда")
                app.schedule_tab.refresh()
                app.tabs.select(app.schedule_tab)
            elif scenario == "feed-long":  # evidence only (ui:32), not in SCENARIOS
                from watcher.parser import ChatMessage
                text = ("ищу группу в Бездну, нужен хил и танк, кто свободен — пишите в личку, "
                        "собираемся у крепости через десять минут, берём всех от 60 уровня")
                app.feed.add(ChatMessage("2026.10.13 18:43:17", "Длинноенеразрывноеимяигрока", text, ""), ["группу"])
                app.feed.add(ChatMessage("2026.10.13 18:44:02", "Nick", "короткое: группа в данж", ""), ["группа"],
                             alert_id=1)
            elif scenario == "items-filtered":  # evidence only (ui:29), not in SCENARIOS
                app.item_list._toggle_grade(app.item_list.grades[0])
            elif scenario == "banner-game-off":  # evidence only (ui:27), not in SCENARIOS
                from watcher.app import GAME_OFF
                app._set_status(GAME_OFF)
            elif scenario == "settings-open":
                app._show_settings(True)
            elif scenario == "header-counters":
                app.tracker.found, app.tracker.reacted, app.tracker.missed = 3, 2, 1
                app._update_counters()
            _settle(root, app)
            freeze_dynamic_state(app)
            root.update_idletasks()
            shot = print_client_window(root, frame=frame)
            geometry = {"scenario": scenario, "window": [width, height]} if frame else collect_geometry(root, app, scenario)
            geometry["native_minimum"] = native_minimum
            if not frame and geometry["window"] != [width, height]:
                raise RuntimeError(f"Requested {width}x{height}, got {geometry['window']}")
            (run_dir / "shots").mkdir(exist_ok=True)
            shot.save(run_dir / "shots" / f"{key}.png")
            (run_dir / "geometry-parts").mkdir(exist_ok=True)
            (run_dir / "geometry-parts" / f"{key}.json").write_text(
                json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0
        finally:
            if app is not None:
                app._on_close()  # cancel Tk timers before destroying the interpreter
            elif root is not None:
                root.destroy()
            os.chdir(prior_cwd)


def render_run_report(geometry: dict) -> str:
    """Summarize captured sizes and current clipping before a baseline is available."""
    rows = ["# UI snapshot run", "", "Эмуляция Tk-масштаба; системный DPI 125/150 % не проверен.", "",
            "| Сценарий | Фактическое окно | Обычный минимум приложения | Геометрия |",
            "|---|---|---|---|"]
    for key, data in sorted(geometry.items()):
        width, height = data["window"]
        native = data.get("native_minimum", [width, height])
        issues = compare_geometry(data, data)
        rows.append(f"| {key} | {width}×{height} | {native[0]}×{native[1]} | "
                    f"{'; '.join(issues) or 'без обрезки'} |")
    rows.extend(["", "Сравнение с базой не выполнялось. Маски: " +
                 (str(DYNAMIC_MASKS) if DYNAMIC_MASKS else "нет; динамика выключена в фикстуре"), ""])
    return "\n".join(rows)

def _run() -> Path:
    if os.name != "nt":
        raise RuntimeError("UI snapshots require Windows")
    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS / f"{stamp}-{os.getpid()}"
    run_dir.mkdir()
    cases = [(scenario, width, height) for width, height in WINDOWS for scenario in SCENARIOS]
    for index, (scenario, width, height) in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {width}x{height} {scenario}", flush=True)
        command = [sys.executable, str(Path(__file__).resolve()), "_worker", str(run_dir), scenario,
                   str(width), str(height)]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=WORKER_TIMEOUT)
        if result.returncode:
            raise RuntimeError(f"Worker failed for {scenario} {width}x{height}:\n{result.stdout}\n{result.stderr}")
    geometry = {}
    for path in sorted((run_dir / "geometry-parts").glob("*.json")):
        geometry[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    shutil.rmtree(run_dir / "geometry-parts")
    (run_dir / "geometry.json").write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_run_report(geometry), encoding="utf-8")
    manifest = {"utc": stamp, "windows": [list(size) for size in WINDOWS], "scenarios": list(SCENARIOS),
                "tk_dpi_note": "эмуляция Tk-масштаба; системный DPI 125/150 % не проверен",
                "masks": {key: list(rects) for key, rects in DYNAMIC_MASKS.items()},
                "pixel_channel_threshold": PIXEL_CHANNEL_THRESHOLD,
                "max_different_fraction": MAX_DIFFERENT_FRACTION}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUNS / "latest.json").write_text(json.dumps({"path": run_dir.name}), encoding="utf-8")
    return run_dir


def _latest() -> Path:
    pointer = json.loads((RUNS / "latest.json").read_text(encoding="utf-8"))["path"]
    run_dir = (RUNS / pointer).resolve()
    if run_dir.parent != RUNS.resolve() or not run_dir.is_dir():
        raise RuntimeError("Latest run path is outside tmp/ui-snapshots")
    return run_dir


def _compare(run_dir: Path, pixel_fraction: float, pixel_channel: int) -> bool:
    geometry_path = BASELINE / "geometry.json"
    if not geometry_path.is_file():
        raise RuntimeError("Baseline missing; Claude must approve creation with the baseline command")
    actual = json.loads((run_dir / "geometry.json").read_text(encoding="utf-8"))
    expected = json.loads(geometry_path.read_text(encoding="utf-8"))
    results = {}
    passed = True
    known = load_known_defects()
    (run_dir / "diff").mkdir(exist_ok=True)
    for key in sorted(set(actual) | set(expected)):
        if key not in actual or key not in expected:
            results[key] = {"passed": False, "geometry_issues": ["scenario missing"], "different_pixels": None,
                            "fraction": 1.0, "diff": None}
            passed = False
            continue
        issues, known_hits = split_known(compare_geometry(actual[key], expected[key]),
                                         key.split("_", 1)[1], known)
        a_path, e_path = run_dir / "shots" / f"{key}.png", BASELINE / "shots" / f"{key}.png"
        with Image.open(a_path) as image_a, Image.open(e_path) as image_e:
            scenario = key.split("_", 1)[1]
            masks = DYNAMIC_MASKS.get(scenario, ())
            pixel = compare_images(image_a, image_e, masks, pixel_channel, pixel_fraction)
        diff_path = None
        if not pixel["passed"] and pixel["diff"] is not None:
            diff_path = f"diff/{key}.png"
            pixel["diff"].save(run_dir / diff_path)
        case_ok = not issues and pixel["passed"]
        passed = passed and case_ok
        results[key] = {"passed": case_ok, "geometry_issues": issues,
                        "different_pixels": pixel["different_pixels"], "fraction": pixel["fraction"],
                        "size_error": pixel["size_error"], "diff": diff_path, "masks": list(masks),
                        "known_defects": known_hits}
    (run_dir / "compare.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = ["# UI snapshot comparison", "", "Эмуляция Tk-масштаба; системный DPI 125/150 % не проверен.", "",
            f"Порог: канал > {pixel_channel}; доля различий < {pixel_fraction:.3%}; геометрия ±1 px.", "",
            "| Сценарий | Результат | Отличающихся пикселей | Доля | Геометрия | Diff |",
            "|---|---|---:|---:|---|---|"]
    for key, result in results.items():
        rows.append(f"| {key} | {'PASS' if result['passed'] else 'FAIL'} | {result['different_pixels']} | "
                    f"{result['fraction']:.3%} | "
                    f"{'; '.join(result['geometry_issues'] + result.get('known_defects', [])) or '—'} | "
                    f"{result['diff'] or '—'} |")
    rows.extend(["", f"Итог: {'PASS' if passed else 'FAIL'}. Маски: " +
                 (str(DYNAMIC_MASKS) if DYNAMIC_MASKS else "нет; динамика отключена фикстурой"), ""])
    (run_dir / "report.md").write_text("\n".join(rows), encoding="utf-8")
    return passed


def _baseline(run_dir: Path) -> None:
    if BASELINE.exists() and any(BASELINE.iterdir()):
        raise RuntimeError("Baseline already exists; refusing to overwrite without Claude review")
    BASELINE.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir / "shots", BASELINE / "shots")
    shutil.copy2(run_dir / "geometry.json", BASELINE / "geometry.json")
    shutil.copy2(run_dir / "manifest.json", BASELINE / "manifest.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "run", "compare", "baseline", "_worker"))
    parser.add_argument("worker_args", nargs="*")
    parser.add_argument("--pixel-fraction", type=float, default=MAX_DIFFERENT_FRACTION)
    parser.add_argument("--pixel-channel", type=int, default=PIXEL_CHANNEL_THRESHOLD)
    args = parser.parse_args(argv)
    try:
        if args.command == "_worker":
            run, scenario, width, height = args.worker_args
            return _worker(Path(run), scenario, int(width), int(height))
        if not 0 <= args.pixel_fraction <= 1 or not 0 <= args.pixel_channel <= 255:
            raise ValueError("Invalid pixel threshold")
        if args.command == "run":
            print(_run())
            return 0
        if args.command == "baseline":
            _baseline(_latest())
            print(BASELINE)
            return 0
        run_dir = _run() if args.command == "check" else _latest()
        matched = _compare(run_dir, args.pixel_fraction, args.pixel_channel)
        print(f"{'PASS' if matched else 'FAIL'}: {run_dir / 'report.md'}")
        return 0 if matched else 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
