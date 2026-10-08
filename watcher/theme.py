"""Dark ttk theme with an «epic orange» accent."""

import ctypes
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 13

BG = "#141519"
SURFACE = "#1c1e24"
SURFACE_2 = "#262931"
SURFACE_3 = "#30343e"
BORDER = "#363a45"
TEXT = "#e9e7e4"
MUTED = "#8c919c"
ACCENT = "#ff8c1a"
ACCENT_HOVER = "#ffa54a"
ACCENT_TEXT = "#1b1206"
DANGER = "#e5484d"
DANGER_HOVER = "#f06a6e"
HIT_BG = "#ff8c1a"
HIT_FG = "#1b1206"
NICK = "#9cc4ff"
CHECK_SIZE = 24

_images: list[tk.PhotoImage] = []  # keep references, Tk does not


def apply_dark_theme(root: tk.Tk) -> None:
    """Configure fonts and ttk styles for the whole app."""
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=FONT_FAMILY, size=FONT_SIZE)
    root.configure(background=BG)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        fieldbackground=SURFACE_2,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        troughcolor=SURFACE,
        focuscolor=ACCENT,
        selectbackground=ACCENT,
        selectforeground=ACCENT_TEXT,
        insertcolor=TEXT,
    )
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Status.TLabel", background=BG, foreground=MUTED)
    style.configure("Live.TLabel", background=BG, foreground="#5fd38d")
    style.configure(
        "Title.TLabel",
        background=SURFACE,
        foreground=ACCENT,
        font=(FONT_FAMILY, FONT_SIZE + 1, "bold"),
    )
    style.configure(
        "AppTitle.TLabel",
        background=BG,
        foreground=TEXT,
        font=(FONT_FAMILY, FONT_SIZE + 5, "bold"),
    )

    button = dict(
        background=SURFACE_2,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=SURFACE_2,
        darkcolor=SURFACE_2,
        relief="flat",
        padding=(14, 6),
    )
    style.configure("TButton", **button)
    style.map(
        "TButton",
        background=[("pressed", SURFACE_3), ("active", SURFACE_3)],
        lightcolor=[("active", SURFACE_3)],
        darkcolor=[("active", SURFACE_3)],
        bordercolor=[("focus", ACCENT)],
    )
    _solid_button(style, "Accent.TButton", ACCENT, ACCENT_HOVER, ACCENT_TEXT)
    _solid_button(style, "Danger.TButton", DANGER, DANGER_HOVER, "#ffffff")

    style.configure(
        "TEntry",
        fieldbackground=SURFACE_2,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=SURFACE_2,
        darkcolor=SURFACE_2,
        insertcolor=TEXT,
        padding=6,
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])

    style.configure(
        "TCombobox",
        fieldbackground=SURFACE_2,
        background=SURFACE_2,
        foreground=TEXT,
        arrowcolor=ACCENT,
        bordercolor=BORDER,
        lightcolor=SURFACE_2,
        darkcolor=SURFACE_2,
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE_2)],
        foreground=[("readonly", TEXT)],
        selectbackground=[("readonly", SURFACE_2)],
        selectforeground=[("readonly", TEXT)],
        bordercolor=[("focus", ACCENT), ("hover", SURFACE_3)],
        background=[("active", SURFACE_3)],
    )
    root.option_add("*TCombobox*Listbox.background", SURFACE_2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)
    root.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, FONT_SIZE))

    style.configure(
        "Vertical.TScrollbar",
        background=SURFACE_3,
        troughcolor=SURFACE,
        bordercolor=SURFACE,
        lightcolor=SURFACE_3,
        darkcolor=SURFACE_3,
        arrowcolor=MUTED,
        gripcount=0,
        arrowsize=14,
    )
    style.map("Vertical.TScrollbar", background=[("active", BORDER)])

    off, on = _check_images(root)
    style.element_create("Item.indicator", "image", off, ("selected", on), border=0, sticky="")
    style.layout(
        "Item.TCheckbutton",
        [
            (
                "Checkbutton.padding",
                {
                    "sticky": "nswe",
                    "children": [
                        ("Item.indicator", {"side": "left", "sticky": ""}),
                        ("Checkbutton.label", {"side": "left", "sticky": "w"}),
                    ],
                },
            )
        ],
    )
    style.configure("Item.TCheckbutton", background=SURFACE, foreground=TEXT, padding=(8, 4))
    style.map(
        "Item.TCheckbutton",
        background=[("active", SURFACE_2)],
        foreground=[("selected", ACCENT)],
    )


def _check_images(root: tk.Tk) -> tuple[tk.PhotoImage, tk.PhotoImage]:
    """Draw 24px unchecked / checked boxes (no external image files needed)."""
    size = CHECK_SIZE
    off = tk.PhotoImage(master=root, width=size + 12, height=size)
    on = tk.PhotoImage(master=root, width=size + 12, height=size)
    for image, fill, border in ((off, SURFACE_2, BORDER), (on, ACCENT, ACCENT)):
        image.put(SURFACE, to=(0, 0, size + 12, size))
        image.put(border, to=(1, 1, size - 1, size - 1))
        image.put(fill, to=(3, 3, size - 3, size - 3))
    # checkmark: short stroke down-right, long stroke up-right
    for x in range(6, 11):
        _dot(on, x, 11 + (x - 6), ACCENT_TEXT)
    for x in range(10, 19):
        _dot(on, x, 15 - (x - 10), ACCENT_TEXT)
    _images.extend((off, on))
    return off, on


def _dot(image: tk.PhotoImage, x: int, y: int, color: str) -> None:
    image.put(color, to=(x, y, x + 2, y + 3))


def _solid_button(style: ttk.Style, name: str, color: str, hover: str, text: str) -> None:
    style.configure(
        name,
        background=color,
        foreground=text,
        bordercolor=color,
        lightcolor=color,
        darkcolor=color,
        font=(FONT_FAMILY, FONT_SIZE, "bold"),
        padding=(18, 6),
    )
    style.map(
        name,
        background=[("pressed", color), ("active", hover)],
        lightcolor=[("active", hover)],
        darkcolor=[("active", hover)],
        bordercolor=[("active", hover)],
    )


def style_text(widget: tk.Text) -> None:
    """Dark colors for a plain tk.Text (not a ttk widget)."""
    widget.configure(
        background=SURFACE,
        foreground=TEXT,
        insertbackground=TEXT,
        selectbackground=SURFACE_3,
        selectforeground=TEXT,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        padx=12,
        pady=10,
        font=(FONT_FAMILY, FONT_SIZE),
        spacing1=4,
        spacing3=4,
    )
    widget.tag_configure("meta", foreground=MUTED)
    widget.tag_configure("nick", foreground=NICK, font=(FONT_FAMILY, FONT_SIZE, "bold"))
    widget.tag_configure("hit", background=HIT_BG, foreground=HIT_FG)


def dark_title_bar(root: tk.Tk) -> None:
    """Ask Windows 10/11 for a dark window title bar. No-op elsewhere."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
    except (AttributeError, OSError):
        pass
