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
