"""Dark ttk theme with an «epic orange» accent."""

import ctypes
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 13

BG = "#141519"
SURFACE = "#1c1e24"
SURFACE_2 = "#262931"
SURFACE_3 = "#30343e"
# Contrast is WCAG 2.x, measured by tests/test_theme.py (which fails if a value drifts below its norm):
# text 4.5:1, borders of controls 3:1 (SC 1.4.3, 1.4.11). The number after each colour is that measurement.
BORDER = "#363a45"  # dividers inside cards, decorative (border.subtle) — not for controls: 1.61 on BG
BORDER_CONTROL = "#646a7a"  # outline of fields, check boxes: 3.37 on BG, 3.08 on SURFACE — AA
# (the plan's #4a505e measured 2.26 on BG — fails 3:1, not used)
TEXT = "#e9e7e4"
MUTED = "#8c919c"
ACCENT = "#ff8c1a"
ACCENT_HOVER = "#ffa54a"
ACCENT_TEXT = "#1b1206"
DISABLED = "#6f7480"  # only for really unavailable controls: 3.56 on SURFACE (WCAG exempts inactive ones; was 2.65)
DANGER = "#ff6b70"  # danger as text («Пропущено», warnings): 5.26 on SURFACE_2, 6.59 on BG — AA (was 3.72)
SUCCESS = "#5fd38d"  # «Слежу», «Отреагировал»: 7.75 on SURFACE_2 — AAA
SUCCESS_PULSE = "#9be8bd"
WARNING = "#f5b544"  # «Игра не запущена», «Chat.log не найден»: 8.02 on SURFACE_2 — AAA
DANGER_FILL = "#c9363b"  # Stop button fill: white text 5.15 — AA (was #e5484d, 3.91)
DANGER_FILL_HOVER = "#d13b40"  # its hover: white text 4.76 — AA (was #f06a6e, 3.00)
STAT_COLORS = {"Found": TEXT, "Reacted": SUCCESS, "Missed": DANGER}  # header statistics: dot and number
ACCENT_SUBTLE = "#3a2810"  # a quiet orange ground: ACCENT text on it 6.05 — AA
# a match in the chat (UI/UX item 9): orange bold words on the quiet ground plus a 3 px stripe at the line's left,
# instead of a solid orange block — still easy to spot, and the text stays readable
HIT_BG = ACCENT_SUBTLE
HIT_FG = ACCENT
HIT_STRIPE = 3  # px; ACCENT on SURFACE 7.15
NICK = "#9cc4ff"
CHECK_SIZE = 24
# item name colours by grade, as in the game
GRADE_COLORS = {
    "common": TEXT,
    "rare": "#6fd56f",
    "legend": "#5fa8ff",
    "unique": "#f0c75e",
    "epic": ACCENT,
    "mythic": "#c77dff",
    "finality": "#ff6b6b",
}


def mix(color: str, ground: str, share: float) -> str:
    """color laid over ground at share (0–1) opacity, as a #rrggbb colour."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(ground[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x * share + y * (1 - share)) for x, y in zip(a, b))


# grade filter chips (UI/UX item 13): «on» — a quiet ground of the grade colour, its text and a 1 px outline in
# that colour; «off» — no ground, MUTED text, BORDER_CONTROL outline; grade text on its ground ≥ 4.57 — AA
GRADE_CHIP_SHARE = 0.18
GRADE_SUBTLE = {grade: mix(color, SURFACE, GRADE_CHIP_SHARE) for grade, color in GRADE_COLORS.items()}
RADIUS = 9  # buttons, fields, tabs, counters (images drawn by tools/build_ui.py)
CARD_RADIUS = 12  # cards (feed, item list)

# ---- The rest of the registry (UI/UX item 5). Every colour, type role, space, radius and motion value of the
# program lives here; other modules use these names only (tests/test_theme.py rejects a #rrggbb anywhere else).
# The number after a text colour is its measured WCAG contrast on the background named.

# match feed (watcher/feed.py)
PENDING_BRIGHT = "#7a5410"  # bright phase of a waiting alert's blink
PENDING_DIM = "#3a2a0c"  # its dim phase
ACCEPTED_BG = "#173a24"  # a row the user accepted
MISSED_BG = "#3d1a1d"  # a row that ran out of time
QUIET_NOTE = "#7fd69b"  # «Уже принято»: 9.52 on SURFACE — AAA
COUNTDOWN = "#ffd166"  # seconds left: 9.60 on PENDING_DIM, 4.69 on PENDING_BRIGHT — AA
COUNTDOWN_URGENT = "#ffd0d1"  # last seconds: 10.02 on PENDING_DIM, 4.90 on PENDING_BRIGHT — AA
# (it was DANGER #ff6b70: 2.45 on PENDING_BRIGHT — fails; the red stays in its hue, lighter)
MISSED_TEXT = "#ff8a8f"  # «Пропущено» on a row: 6.81 on MISSED_BG — AA
ALARM_DIM = ACCENT_SUBTLE  # dim phase of the «Найдено в чате!» window frame: ACCENT ↔ ACCENT_SUBTLE (UI/UX 14)
# item list (watcher/itemlist.py)
MATCH_BG = "#3a2a12"  # a searched item's row: TEXT 11.20, epic orange 5.93 — AA
# chat text (watcher/textview.py, watcher/mapview.py)
SELECT_BG = "#2f4a6d"  # mouse selection: TEXT 7.33 — AAA
PLACE = "#4fd1c5"  # «Место» links and the other places on the map, like the game's teal: 8.93 on SURFACE — AAA
PLACE_OUTLINE = "#0b2b28"  # outline of those map pins
# map drawing (watcher/mapview.py): text on a picture gets a dark outline, so no fixed background to measure
MAP_LABEL = "#f2e6c9"  # area names, like the game's map
MAP_TEXT = "#ffffff"  # the chat place's label, count badges
OUTLINE_DARK = "#0d0e11"  # outline under map text, badge fill
# game colours — copied from the game, kept as they are
CHAT_COLORS = {  # chat channels, as [charname:Name;r g b] in Chat.log (Aion's defaults)
    "Поиск группы": "#ffb45e",  # 9.47 on SURFACE
    "Общий": "#e9e7e4",  # 13.5
    "Личное": "#a0ffa0",  # 13.73
    "Группа": "#05c8d7",  # 8.13
    "Легион": "#9ce7dc",  # 11.80
}
TOOLTIP_BG = "#0e1014"  # item tooltip in the game's style (watcher/tooltip.py)
TOOLTIP_FRAME = "#5a4a2e"
TOOLTIP_LINE = "#3a3d46"
TOOLTIP_SLOT = "#1c1f26"  # empty manastone / socket slot
TOOLTIP_PROPS = "#e8c55a"  # 11.39 on TOOLTIP_BG
TOOLTIP_WARNING = "#ff5b5b"  # 6.26 on TOOLTIP_BG

# Type scale (UI/UX item 6, plan section 2). Families are tried in order: Segoe UI Variable (Windows 11) first,
# then Segoe UI (Windows 10); a «strong» role uses a Semibold family, or bold Segoe UI where that is missing.
FAMILIES = {
    "display_strong": ("Segoe UI Variable Display Semib", "Segoe UI Semibold"),
    "text": ("Segoe UI Variable Text", "Segoe UI"),
    "text_strong": ("Segoe UI Variable Text Semibold", "Segoe UI Semibold"),
    "small": ("Segoe UI Variable Small", "Segoe UI"),
    "small_strong": ("Segoe UI Variable Small Semibol", "Segoe UI Semibold"),
    "mono": ("Cascadia Mono", "Consolas"),  # the time column: every digit the same width
}
TYPE = {  # role: (size in Tk points, family)
    "display": (18, "display_strong"),  # program name
    "alarm": (18, "display_strong"),  # «Найдено в чате!» — over the game, so as large as the name
    "tooltip_name": (16, "text_strong"),  # item name in its tooltip, as in the game
    "title": (14, "text_strong"),  # card titles
    "body": (13, "text"),  # feed and «Весь чат» — read from the corner of an eye
    "body_strong": (13, "text_strong"),  # nicks, counters
    "body_bold": (13, "text_strong"),  # map place label (same as body_strong)
    "control": (12, "text"),  # buttons, fields, tabs, lists
    "control_strong": (12, "text_strong"),  # main buttons, status chip
    "caption": (11, "text"),  # hints, notes, bubbles
    "caption_strong": (11, "text_strong"),  # countdowns
    "caption_bold": (11, "text_strong"),
    "small": (11, "text"),  # levels, coordinates in the card (= caption)
    "micro": (10, "small"),  # coordinates under the map cursor
    "badge": (8, "small_strong"),  # count on a map group (inside an 18 px circle)
    "mono": (11, "mono"),  # time in the feed, «Весь чат» and the alarm window
}
_resolved: dict[str, str] = {}  # family key -> the installed family (filled by resolve_fonts)


def resolve_fonts(root: tk.Misc) -> None:
    """Pick the first installed family of each chain (needs a Tk root)."""
    installed = set(tkfont.families(root))
    for key, chain in FAMILIES.items():
        _resolved[key] = next((name for name in chain if name in installed), FONT_FAMILY)


def font(role: str) -> tuple[str, int, str]:
    """A type role as a Tk font tuple, e.g. font("caption")."""
    size, key = TYPE[role]
    family = _resolved.get(key, FONT_FAMILY)
    # a Semibold family is already heavy; plain Segoe UI needs Tk's bold to stand out
    weight = "bold" if key.endswith("_strong") and "semi" not in family.lower() else "normal"
    return (family, size, weight)


SPACE = {1: 4, 2: 8, 3: 12, 4: 16, 6: 24, 8: 32}  # px, a 4 px unit; window gutter 16, inside cards 12–16
RADII = {"control": RADIUS, "card": CARD_RADIUS}
MOTION = {"fast": 120, "base": 200, "blink": 300, "alarm_blink": 500, "found_blink": 3000}  # ms

# every named colour, for the record and for tests
COLOR = {name: value for name, value in globals().items()
         if name.isupper() and isinstance(value, str) and value.startswith("#")}

_images: list[tk.PhotoImage] = []  # keep references, Tk does not
CHECKS: dict[str, tk.PhotoImage] = {}  # "off", "on", "off_dim", "on_dim" (set by apply_dark_theme)


def apply_dark_theme(root: tk.Tk, ui_dir: Path | None = None) -> None:
    """Configure fonts and ttk styles for the whole app.

    With ui_dir (data/ui) the controls get rounded corners from its images; without it they are flat.
    """
    # images made for an earlier (destroyed) root are useless; dropping them frees Tk's resources
    _images.clear()
    CHECKS.clear()
    resolve_fonts(root)
    family, size, _weight = font("control")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=size)
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
    style.configure("Surface.TFrame", background=SURFACE)  # flat, for frames inside a card
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("Caption.TLabel", background=SURFACE, foreground=MUTED, font=font("caption"))
    style.configure("Status.TLabel", background=BG, foreground=MUTED)
    style.configure("Live.TLabel", background=BG, foreground="#5fd38d")
    style.configure("Warn.TLabel", background=BG, foreground=DANGER)
    style.configure(
        "Horizontal.TScale",
        background=ACCENT,
        troughcolor=SURFACE_2,
        bordercolor=SURFACE_2,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        sliderthickness=16,
    )
    style.map("Horizontal.TScale", background=[("active", ACCENT_HOVER)])
    style.configure(
        "Title.TLabel",
        background=SURFACE,
        foreground=TEXT,  # UI/UX item 7: headings are neutral; orange means «important» or «selected» only
        font=font("title"),
    )
    style.configure(
        "AppTitle.TLabel",
        background=BG,
        foreground=TEXT,
        font=font("display"),
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
        foreground=[("disabled", DISABLED)],
        background=[("disabled", SURFACE), ("pressed", SURFACE_3), ("active", SURFACE_3)],
        lightcolor=[("active", SURFACE_3)],
        darkcolor=[("active", SURFACE_3)],
        bordercolor=[("focus", ACCENT)],
    )
    _solid_button(style, "Accent.TButton", ACCENT, ACCENT_HOVER, ACCENT_TEXT)
    _solid_button(style, "Danger.TButton", DANGER_FILL, DANGER_FILL_HOVER, "#ffffff")

    style.configure(
        "TEntry",
        fieldbackground=SURFACE_2,
        foreground=TEXT,
        bordercolor=BORDER_CONTROL,
        lightcolor=SURFACE_2,
        darkcolor=SURFACE_2,
        insertcolor=TEXT,
        padding=6,
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", SURFACE)],
        foreground=[("disabled", DISABLED)],
        bordercolor=[("disabled", SURFACE), ("focus", ACCENT)],
        lightcolor=[("disabled", SURFACE), ("focus", ACCENT)],
    )

    style.configure(
        "TCombobox",
        fieldbackground=SURFACE_2,
        background=SURFACE_2,
        foreground=TEXT,
        arrowcolor=MUTED,  # neutral arrow; lighter on hover (item 7)
        bordercolor=BORDER_CONTROL,
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
        arrowcolor=[("active", TEXT), ("hover", TEXT)],
        background=[("active", SURFACE_3)],
    )
    root.option_add("*TCombobox*Listbox.background", SURFACE_2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)
    root.option_add("*TCombobox*Listbox.font", font("control"))

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

    off, on, off_dim, on_dim, off_focus, on_focus = _check_images(root)
    style.element_create(
        "Item.indicator",
        "image",
        off,
        ("disabled", "selected", on_dim),
        ("disabled", off_dim),
        ("focus", "selected", on_focus),
        ("focus", off_focus),
        ("selected", on),
        border=0,
        sticky="",
    )
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
    style.layout("Group.TCheckbutton", style.layout("Item.TCheckbutton"))
    style.configure("Group.TCheckbutton", background=SURFACE_2, foreground=MUTED, padding=(4, 0))
    style.map(
        "Group.TCheckbutton",
        background=[("disabled", SURFACE_2), ("active", SURFACE_3)],
        foreground=[("disabled", DISABLED), ("selected", ACCENT)],
    )
    style.layout("Accept.TCheckbutton", style.layout("Item.TCheckbutton"))
    style.configure("Accept.TCheckbutton", background=SURFACE, foreground=ACCENT, padding=(2, 0))
    style.map("Accept.TCheckbutton", background=[("active", SURFACE_2)])
    style.layout("Missed.TCheckbutton", style.layout("Item.TCheckbutton"))
    style.configure("Missed.TCheckbutton", background=SURFACE, foreground=MUTED, padding=(2, 0))

    # right-edge checkbox of a pending alert: tight images, blinks between two styles
    cold, hot, done = _pending_images(root)
    style.element_create("Pend.indicator", "image", cold, ("selected", done), border=0, sticky="")
    style.element_create("PendHot.indicator", "image", hot, ("selected", done), border=0, sticky="")
    for name, element, background in (
        ("Pend.TCheckbutton", "Pend.indicator", SURFACE),
        ("PendHot.TCheckbutton", "PendHot.indicator", "#5a3610"),
    ):
        style.layout(name, [("Checkbutton.padding", {"sticky": "nswe", "children": [(element, {"sticky": ""})]})])
        style.configure(name, background=background, padding=(0, 0))
        style.map(name, background=[("active", background)])
    accepted, missed = _result_images(root)
    for name, element, image, background in (
        ("Accept.TCheckbutton", "Accept.indicator", accepted, "#173a24"),
        ("Missed.TCheckbutton", "Missed.indicator", missed, "#3d1a1d"),
    ):
        style.element_create(element, "image", image, border=0, sticky="")
        style.layout(name, [("Checkbutton.padding", {"sticky": "nswe", "children": [(element, {"sticky": ""})]})])
        style.configure(name, background=background, padding=(0, 0))
        style.map(name, background=[("disabled", background), ("active", background)])

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure(
        "TNotebook.Tab",
        background=SURFACE_2,
        foreground=MUTED,
        padding=(16, 8),
        borderwidth=0,
        font=font("body_strong"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", SURFACE), ("active", SURFACE_3)],
        foreground=[("selected", TEXT), ("active", TEXT)],  # UI/UX item 11: the orange is the bar under the tab
        lightcolor=[("selected", SURFACE)],
        expand=[("selected", (0, 0, 0, 0))],
        padding=[],  # clam shrinks the selected tab's padding to 6 4 6 2: its label jumped up and left
    )

    # status chip next to Start (UI/UX item 4): icon + text + colour, never colour alone
    for name, color in (("Idle", MUTED), ("Live", SUCCESS), ("Warn", WARNING), ("Error", DANGER)):
        style.configure(f"{name}.Chip.TLabel", background=SURFACE_2, foreground=color,
                        font=font("control_strong"), padding=(12, 6))
    # counters are statistics, not buttons (UI/UX item 10): no ground, a coloured dot, a large number, a caption
    style.configure("Stat.TLabel", background=BG, foreground=MUTED, font=font("caption"))
    for name, color in STAT_COLORS.items():
        style.configure(f"{name}.Stat.TLabel", background=BG, foreground=color, font=font("title"))
    # ghost button: no ground until hovered — still an action, quieter than the stats next to it
    style.configure("Ghost.TButton", background=BG, foreground=MUTED, bordercolor=BG, lightcolor=BG, darkcolor=BG,
                    padding=(10, 6))
    style.map(
        "Ghost.TButton",
        foreground=[("disabled", DISABLED), ("active", TEXT)],
        background=[("pressed", SURFACE_3), ("active", SURFACE_2)],
        lightcolor=[("active", SURFACE_2)],
        darkcolor=[("active", SURFACE_2)],
    )
    # the same ghost on a card (ui:29: the filter reset weighed as much as the search arrows beside it)
    style.configure("CardGhost.TButton", background=SURFACE, foreground=MUTED, bordercolor=SURFACE,
                    lightcolor=SURFACE, darkcolor=SURFACE, padding=(6, 5))
    style.map("CardGhost.TButton", foreground=[("disabled", DISABLED), ("active", TEXT)],
              background=[("pressed", SURFACE_3), ("active", SURFACE_2)])
    style.layout("Plain.TCheckbutton", style.layout("Item.TCheckbutton"))
    style.configure("Plain.TCheckbutton", background=BG, foreground=TEXT, padding=(0, 0))
    style.map("Plain.TCheckbutton", background=[("active", BG)], foreground=[("selected", ACCENT)])
    style.layout("CardPlain.TCheckbutton", style.layout("Item.TCheckbutton"))  # the same check box, on a card
    style.configure("CardPlain.TCheckbutton", background=SURFACE, foreground=TEXT, padding=(0, 0))
    style.map("CardPlain.TCheckbutton", background=[("active", SURFACE)], foreground=[("selected", ACCENT)])
    style.configure("Group.TFrame", background=SURFACE_2)
    style.configure(
        "Group.TLabel",
        background=SURFACE_2,
        foreground=TEXT,
        font=font("body_strong"),
        padding=(4, 2),
    )
    if ui_dir is not None and (Path(ui_dir) / "btn.png").is_file():
        _apply_rounded(style, root, Path(ui_dir))
        if all((Path(ui_dir) / f"scrollbar_thumb{suffix}.png").is_file() for suffix in ("", "_hover")):
            _apply_scrollbar(style, root, Path(ui_dir))
        if all((Path(ui_dir) / name).is_file() for name in ("scale_track.png", "scale_thumb.png", "scale_thumb_hover.png")):
            _apply_scale(style, root, Path(ui_dir))
    style.configure("Item.TCheckbutton", background=SURFACE, foreground=TEXT, padding=(8, 4))
    style.map(
        "Item.TCheckbutton",
        background=[("disabled", SURFACE), ("active", SURFACE_2)],
        foreground=[("disabled", DISABLED), ("selected", ACCENT)],
    )


def _apply_rounded(style: ttk.Style, root: tk.Tk, ui_dir: Path) -> None:
    """Swap the flat clam borders for 9-slice rounded images."""
    scale = _ui_dpi_scale(root)
    suffix = min(((1.0, ""), (1.25, "@125"), (1.5, "@150"), (2.0, "@2x")),
                 key=lambda item: abs(item[0] - scale))[1]

    def img(name: str) -> tk.PhotoImage:
        variant = ui_dir / f"{name}{suffix}.png"
        image = load_png(root, variant if variant.is_file() else ui_dir / f"{name}.png")
        _images.append(image)
        return image

    def element(name: str, base: str, states: list[tuple], border: int, padding=None) -> None:
        specs = [(*state, img(file)) for *state, file in states]
        options = {"border": border, "sticky": "nswe"}
        if padding is not None:
            options["padding"] = padding
        style.element_create(name, "image", img(base), *specs, **options)

    edge = round((RADIUS + 1) * scale)
    inner = (round((RADIUS // 2 + 3) * scale), round(3 * scale))  # preserve the text inset at high DPI
    # buttons: on the window background, and on cards («Card.» prefix)
    for prefix, file_prefix in (("", ""), ("Card.", "card_")):
        name = f"{prefix}Rounded.Button.border"
        element(
            name,
            f"{file_prefix}btn",
            [("disabled", f"{file_prefix}btn_disabled"), ("pressed", f"{file_prefix}btn_active"),
             ("focus", f"{file_prefix}btn_focus"), ("active", f"{file_prefix}btn_active")],
            edge,
            inner,
        )
        style.layout(
            f"{prefix}TButton",
            [(name, {"sticky": "nswe", "children": [
                ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})
            ]})],
        )
    style.configure("Card.TButton", background=SURFACE, foreground=TEXT, padding=(14, 6))
    # ghost button: transparent until hovered, then the ordinary button's rounded ground
    hover = img("btn_active")
    ghost_focus = img("ghost_focus")
    blank = tk.PhotoImage(master=root, width=hover.width(), height=hover.height())  # fully transparent
    _images.append(blank)
    style.element_create("Ghost.Rounded.border", "image", blank, ("focus", ghost_focus),
                         ("pressed", hover), ("active", hover),
                         border=edge, sticky="nswe", padding=inner)
    style.layout(
        "Ghost.TButton",
        [("Ghost.Rounded.border", {"sticky": "nswe", "children": [
            ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})
        ]})],
    )
    style.layout("CardGhost.TButton", style.layout("Ghost.TButton"))  # ui:29
    style.map("Card.TButton", foreground=[("disabled", DISABLED)])
    for name, base, hover in (("Accent", "accent", "accent_active"), ("Danger", "danger", "danger_active")):
        element(f"{name}.Rounded.border", base,
                [("focus", f"{base}_focus"), ("pressed", base), ("active", hover)], edge, inner)
        style.layout(
            f"{name}.TButton",
            [(f"{name}.Rounded.border", {"sticky": "nswe", "children": [
                ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})
            ]})],
        )

    # entry and combobox fields
    element(
        "Rounded.field",
        "field",
        [("disabled", "field_disabled"), ("focus", "field_focus")],
        edge,
        (3, 2),
    )
    style.layout(
        "TEntry",
        [("Rounded.field", {"sticky": "nswe", "children": [
            ("Entry.padding", {"sticky": "nswe", "children": [("Entry.textarea", {"sticky": "nswe"})]})
        ]})],
    )
    # The clam arrow draws a second frame inside our rounded field. Use the
    # bundled borderless UI arrow so the whole combobox has one outline.
    arrow_size = 20 if scale >= 1.25 else 16
    arrow_dir = ui_dir / "icons"
    arrow_path = arrow_dir / f"caret-down_{arrow_size}_muted.png"
    arrow_hot_path = arrow_dir / f"caret-down_{arrow_size}_text.png"
    downarrow = "Combobox.downarrow"
    if arrow_path.is_file() and arrow_hot_path.is_file():
        arrow = load_png(root, arrow_path)
        arrow_hot = load_png(root, arrow_hot_path)
        _images.extend((arrow, arrow_hot))
        downarrow = "Flat.Combobox.downarrow"
        style.element_create(
            downarrow, "image", arrow, ("active", arrow_hot),
            sticky="", padding=(round(6 * scale), 0, round(6 * scale), 0),
        )
    style.layout(
        "TCombobox",
        [("Rounded.field", {"sticky": "nswe", "children": [
            (downarrow, {"side": "right", "sticky": ""}),
            ("Combobox.padding", {"expand": "1", "sticky": "nswe", "children": [
                ("Combobox.textarea", {"sticky": "nswe"})
            ]}),
        ]})],
    )
    element(
        "Card.Rounded.field",
        "card_field",
        [("disabled", "card_field_disabled"), ("focus", "card_field_focus")],
        edge,
        (3, 2),
    )
    style.layout(
        "Card.TEntry",
        [("Card.Rounded.field", {"sticky": "nswe", "children": [
            ("Entry.padding", {"sticky": "nswe", "children": [("Entry.textarea", {"sticky": "nswe"})]})
        ]})],
    )
    style.configure("Card.TEntry", padding=(6, 4))
    style.layout(
        "Card.TCombobox",
        [("Card.Rounded.field", {"sticky": "nswe", "children": [
            (downarrow, {"side": "right", "sticky": ""}),
            ("Combobox.padding", {"expand": "1", "sticky": "nswe", "children": [
                ("Combobox.textarea", {"sticky": "nswe"})
            ]}),
        ]})],
    )
    style.configure("TEntry", padding=(6, 4))
    style.configure("TCombobox", padding=(6, 3), arrowsize=14)
    style.map("TCombobox", background=[("active", SURFACE_2), ("readonly", SURFACE_2)])

    # cards, group headers, counters
    element("Card.border", "card", [], round((CARD_RADIUS + 1) * scale))
    style.layout("Card.TFrame", [("Card.border", {"sticky": "nswe"})])
    element("Group.border", "group", [], edge)
    style.layout("Group.TFrame", [("Group.border", {"sticky": "nswe"})])
    element("Pill.border", "pill", [], edge, inner)
    for name in ("Idle.Chip", "Live.Chip", "Warn.Chip", "Error.Chip"):
        style.layout(
            f"{name}.TLabel",
            [("Pill.border", {"sticky": "nswe", "children": [
                ("Label.padding", {"sticky": "nswe", "children": [("Label.label", {"sticky": "nswe"})]})
            ]})],
        )

    # notebook tabs: rounded top corners
    element("Rounded.tab", "tab", [("selected", "tab_selected"), ("active", "tab_active")], edge, inner)
    style.configure("TNotebook", bordercolor=BG, lightcolor=BG, darkcolor=BG)
    style.map("TNotebook.Tab", expand=[])
    style.layout(
        "TNotebook.Tab",
        [("Rounded.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})
            ]})
        ]})],
    )


def _ui_dpi_scale(root: tk.Misc) -> float:
    """Return the display scale represented by Tk (1.0 at 96 DPI)."""
    try:
        tk_scale = float(root.tk.call("tk", "scaling"))
    except (TypeError, ValueError, tk.TclError):
        return 1.0
    # Tk scaling is pixels per point: the Windows 96 DPI baseline is 96 / 72.
    return max(1.0, min(2.0, tk_scale / (96 / 72)))


def _apply_scrollbar(style: ttk.Style, root: tk.Tk, ui_dir: Path) -> None:
    """Use a slim, arrowless 8px scrollbar with a rounded thumb."""
    thumb = load_png(root, ui_dir / "scrollbar_thumb.png")
    thumb_hover = load_png(root, ui_dir / "scrollbar_thumb_hover.png")
    _images.extend((thumb, thumb_hover))
    element = "Slim.Vertical.Scrollbar.thumb"
    style.element_create(
        element,
        "image",
        thumb,
        ("active", thumb_hover),
        border=(2, 4, 2, 4),
        sticky="nswe",
    )
    style.configure(
        "Vertical.TScrollbar",
        width=8,
        background=SURFACE_3,
        troughcolor=SURFACE,
        bordercolor=SURFACE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        relief="flat",
        borderwidth=0,
        padding=0,
        arrowsize=0,
    )
    style.layout(
        "Vertical.TScrollbar",
        [("Vertical.Scrollbar.trough", {
            "sticky": "nswe",
            "children": [(element, {"unit": "1", "sticky": "nswe"})],
        })],
    )


def _apply_scale(style: ttk.Style, root: tk.Tk, ui_dir: Path) -> None:
    """Use a slim image track and a round, stateful thumb for horizontal scales."""
    track = load_png(root, ui_dir / "scale_track.png")
    thumb = load_png(root, ui_dir / "scale_thumb.png")
    thumb_hover = load_png(root, ui_dir / "scale_thumb_hover.png")
    _images.extend((track, thumb, thumb_hover))
    # rounded ends stay whole, only the flat middle repeats (border=0 tiled the whole pill: a dashed track, ui:19)
    end = track.height() // 2
    style.element_create("Slim.Horizontal.Scale.trough", "image", track, border=(end, 0, end, 0), sticky="we")
    style.element_create(
        "Round.Horizontal.Scale.slider",
        "image",
        thumb,
        ("active", thumb_hover),
        border=0,
        sticky="",
    )
    style.layout(
        "Horizontal.TScale",
        [("Slim.Horizontal.Scale.trough", {
            "sticky": "we",
            "children": [("Round.Horizontal.Scale.slider", {"side": "left", "sticky": ""})],
        })],
    )
    style.configure("Horizontal.TScale", background=SURFACE, troughcolor=SURFACE_2, sliderthickness=16)


def _check_images(root: tk.Tk) -> tuple[tk.PhotoImage, ...]:
    """Draw 24px boxes: unchecked, checked, and their dimmed (disabled) variants."""
    size = CHECK_SIZE
    images = [tk.PhotoImage(master=root, width=size + 12, height=size) for _ in range(4)]
    off, on, off_dim, on_dim = images
    for image, fill, border in (
        (off, SURFACE_2, BORDER_CONTROL),
        (on, ACCENT, ACCENT),
        (off_dim, SURFACE, SURFACE_2),
        (on_dim, "#6b4a26", "#6b4a26"),
    ):
        image.put(border, to=(1, 1, size - 1, size - 1))
        image.put(fill, to=(3, 3, size - 3, size - 3))
    # checkmark: short stroke down-right, long stroke up-right
    for image, color in ((on, ACCENT_TEXT), (on_dim, "#2a1d0e")):
        for x in range(6, 11):
            _dot(image, x, 11 + (x - 6), color)
        for x in range(10, 19):
            _dot(image, x, 15 - (x - 10), color)
    off_focus, on_focus = off.copy(), on.copy()
    for image in (off_focus, on_focus):
        image.put(ACCENT, to=(0, 0, size, 2))
        image.put(ACCENT, to=(0, size - 2, size, size))
        image.put(ACCENT, to=(0, 0, 2, size))
        image.put(ACCENT, to=(size - 2, 0, size, size))
    images.extend((off_focus, on_focus))
    _images.extend(images)
    CHECKS.update(off=off, on=on, off_dim=off_dim, on_dim=on_dim)
    return off, on, off_dim, on_dim, off_focus, on_focus


def _pending_images(root: tk.Tk) -> tuple[tk.PhotoImage, tk.PhotoImage, tk.PhotoImage]:
    """24px boxes without side padding: normal, highlighted (blink) and checked."""
    size = CHECK_SIZE
    cold, hot, done = (tk.PhotoImage(master=root, width=size, height=size) for _ in range(3))
    cold.put(ACCENT, to=(1, 1, size - 1, size - 1))
    cold.put(SURFACE_2, to=(3, 3, size - 3, size - 3))
    hot.put(ACCENT_HOVER, to=(0, 0, size, size))
    hot.put("#7a4a14", to=(4, 4, size - 4, size - 4))
    done.put(ACCENT, to=(1, 1, size - 1, size - 1))
    for x in range(6, 11):
        _dot(done, x, 11 + (x - 6), ACCENT_TEXT)
    for x in range(10, 19):
        _dot(done, x, 15 - (x - 10), ACCENT_TEXT)
    _images.extend((cold, hot, done))
    return cold, hot, done


def _result_images(root: tk.Tk) -> tuple[tk.PhotoImage, tk.PhotoImage]:
    """24px boxes for finished alerts: green check (accepted) and red cross (missed)."""
    size = CHECK_SIZE
    accepted, missed = (tk.PhotoImage(master=root, width=size, height=size) for _ in range(2))
    accepted.put("#3fbf6f", to=(1, 1, size - 1, size - 1))
    for x in range(6, 11):
        _dot(accepted, x, 11 + (x - 6), "#0c2414")
    for x in range(10, 19):
        _dot(accepted, x, 15 - (x - 10), "#0c2414")
    missed.put(DANGER, to=(1, 1, size - 1, size - 1))
    for i in range(6, 17):
        missed.put("#ffffff", to=(i, i, i + 2, i + 2))
        missed.put("#ffffff", to=(i, size - i - 2, i + 2, size - i))
    _images.extend((accepted, missed))
    return accepted, missed


def load_png(root: tk.Misc, path: Path) -> tk.PhotoImage:
    """PNG file -> PhotoImage. The bytes are read by Python: Tk's own file loading now and then
    fails on paths with Cyrillic letters (e.g. the user's profile folder)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise tk.TclError(f"cannot read {path}: {exc}") from exc
    return tk.PhotoImage(master=root, data=data, format="png")


def placeholder_icon(root: tk.Misc, size: int = 56) -> tk.PhotoImage:
    """Framed dark square for items whose icon is unavailable."""
    image = tk.PhotoImage(master=root, width=size, height=size)
    image.put(BORDER, to=(0, 0, size, size))
    image.put(SURFACE_2, to=(2, 2, size - 2, size - 2))
    middle = size // 2
    for offset in range(0, 12):
        image.put(ACCENT, to=(middle - offset, middle - 12 + offset, middle - offset + 2, middle - 10 + offset))
        image.put(ACCENT, to=(middle + offset - 2, middle - 12 + offset, middle + offset, middle - 10 + offset))
    _images.append(image)
    return image


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
        font=font("control_strong"),
        padding=(18, 6),
    )
    style.map(
        name,
        background=[("pressed", color), ("active", hover)],
        lightcolor=[("active", hover)],
        darkcolor=[("active", hover)],
        bordercolor=[("active", hover)],
    )


def install_header_gradient(header: ttk.Frame) -> tk.Canvas:
    """Subtle vertical tint in the header's empty top band; redraw only when its size changes.

    Tk labels are opaque: a tint behind the title and the counters showed their rectangles (ui:31 recheck), so the
    gradient fades to BG within the header's top padding, above every widget."""
    backdrop = tk.Canvas(header, background=BG, borderwidth=0, highlightthickness=0)
    backdrop.place(x=0, y=0, relwidth=1, relheight=1)
    backdrop.tk.call("lower", backdrop._w)
    start = mix(SURFACE_2, BG, 0.30)
    raw = header.cget("padding")
    padding = [int(str(v)) for v in (raw if isinstance(raw, (tuple, list)) else str(raw).split())] or [0]
    band = padding[1] if len(padding) > 1 else padding[0]

    def redraw(event: tk.Event) -> None:
        backdrop.delete("gradient")
        for y in range(max(0, min(band, event.height))):
            shade = mix(start, BG, y / max(1, band))
            backdrop.create_line(0, y, event.width, y, fill=shade, tags="gradient")

    backdrop.bind("<Configure>", redraw)
    return backdrop


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
        padx=12 - HIT_STRIPE,  # every row has a HIT_STRIPE left margin (tag «row»), so text still starts at 12
        pady=10,
        font=font("body"),
        spacing1=4,
        spacing3=4,
    )
    widget.tag_configure("meta", foreground=MUTED, font=font("mono"))  # time: an even column of digits
    widget.tag_configure("nick", foreground=NICK, font=font("body_strong"))
    widget.tag_configure("hit", background=HIT_BG, foreground=HIT_FG, font=font("body_strong"))
    # Tk's left stripe adds three pixels; reserve the same space at the right
    # so long chat rows keep a balanced inset instead of touching the edge.
    widget.tag_configure("row", lmargin1=HIT_STRIPE, lmargin2=HIT_STRIPE, rmargin=HIT_STRIPE)
    widget.tag_configure("hitline", lmargin1=HIT_STRIPE, lmargin2=HIT_STRIPE,
                         rmargin=HIT_STRIPE, lmargincolor=ACCENT)


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
