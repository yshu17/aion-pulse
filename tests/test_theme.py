import tkinter as tk
from tkinter import ttk

import pytest

from watcher import theme
from watcher.catalog import resource_root

UI_DIR = resource_root() / "data" / "ui"


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def first_element(style, name):
    return style.layout(name)[0][0]


def test_rounded_images_are_bundled():
    for name in ("btn", "card_btn", "accent", "danger", "field", "field_focus", "card", "group", "pill", "tab_selected"):
        assert (UI_DIR / f"{name}.png").is_file(), name


def test_rounded_theme_uses_image_elements(root):
    theme.apply_dark_theme(root, UI_DIR)
    style = ttk.Style(root)
    assert first_element(style, "TButton") == "Rounded.Button.border"
    assert first_element(style, "Card.TButton") == "Card.Rounded.Button.border"
    assert first_element(style, "Accent.TButton") == "Accent.Rounded.border"
    assert first_element(style, "TEntry") == "Rounded.field"
    assert first_element(style, "TCombobox") == "Rounded.field"
    assert first_element(style, "Card.TFrame") == "Card.border"
    assert first_element(style, "TNotebook.Tab") == "Rounded.tab"
    assert first_element(style, "Found.Counter.TLabel") == "Pill.border"


def test_without_images_theme_stays_flat(root, tmp_path):
    theme.apply_dark_theme(root, tmp_path)
    assert "Rounded" not in first_element(ttk.Style(root), "TButton")


# --- contrast of the theme's colour pairs (WCAG 2.x): a colour change cannot quietly fail the norm
def luminance(hex_color: str) -> float:
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


TEXT_AA = 4.5  # SC 1.4.3, normal text (13 pt bold is not «large» yet)
UI_AA = 3.0  # SC 1.4.11, boundaries of controls

# (foreground, background, norm, where) — every pair that carries text or outlines a control
PAIRS = [
    (theme.TEXT, theme.BG, TEXT_AA, "main text"),
    (theme.TEXT, theme.SURFACE, TEXT_AA, "text in cards"),
    (theme.MUTED, theme.BG, TEXT_AA, "labels"),
    (theme.MUTED, theme.SURFACE_2, TEXT_AA, "labels on fields"),
    (theme.DANGER, theme.SURFACE_2, TEXT_AA, "«Пропущено» counter"),
    (theme.DANGER, theme.BG, TEXT_AA, "warning label"),
    ("#ffffff", theme.DANGER_FILL, TEXT_AA, "Stop button"),
    ("#ffffff", theme.DANGER_FILL_HOVER, TEXT_AA, "Stop button, hover"),
    (theme.ACCENT_TEXT, theme.ACCENT, TEXT_AA, "Start button"),
    (theme.BORDER_CONTROL, theme.BG, UI_AA, "field outline on the window"),
    (theme.BORDER_CONTROL, theme.SURFACE, UI_AA, "field outline in a card"),
    (theme.DISABLED, theme.SURFACE, UI_AA, "unavailable text (exempt; kept readable)"),
]


@pytest.mark.parametrize("fg,bg,norm,where", PAIRS, ids=[p[3] for p in PAIRS])
def test_colour_pairs_meet_their_contrast_norm(fg, bg, norm, where):
    assert contrast(fg, bg) >= norm, f"{where}: {fg} on {bg} is {contrast(fg, bg):.2f}, needs {norm}"


def test_measured_values_written_in_the_theme():
    # the numbers in theme.py's comments are these measurements
    assert round(contrast(theme.DANGER, theme.SURFACE_2), 2) == 5.26
    assert round(contrast("#ffffff", theme.DANGER_FILL), 2) == 5.15
    assert round(contrast(theme.BORDER_CONTROL, theme.BG), 2) == 3.37
    assert round(contrast(theme.DISABLED, theme.SURFACE), 2) == 3.56
