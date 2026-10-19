"""The «Карта» tab: browse zone maps; a click at a place link (<Место · Келькмарос>) opens it there.

Like the game map: the mouse wheel zooms to the point under the cursor, dragging moves the map,
a double click zooms in. The clicked place is a big orange pin; other places linked in the chat
for the same zone are small pins with «nick: message» on hover.

Map images and the game -> image transform come from data/maps/maps.json. The active rasters are
stitched from the local Aion client maps in data/maps/client:
    image_x = x[0] * game_y + x[1],   image_y = y[0] * game_x + y[1]
"""

import json
import math
import sqlite3
import tkinter as tk
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from watcher import theme
from watcher.catalog import resource_root
from watcher.bestiary_store import BestiaryStore
from watcher.bestiary_labels import plural
from watcher.bestiary_widgets import bind_wheel_tree
from watcher.search_worker import SearchWorker
from watcher.spawn_overlay import enclosing_spawn_circle, paint_spawn_circle
from watcher.ui_icons import IconSet
from watcher.hint import Hint
from watcher.mapcard import NEARBY_TYPES, PointCard
from watcher.matcher import normalize
from watcher.poi import Poi, PoiStore, cluster

MIN_ZOOM_STEPS = 0  # zoom = fit * 1.25 ** steps
MAX_ZOOM = 4.0  # screen px per map px
ZOOM_STEP = 1.25
MOB_JOBS_PER_TICK = 4  # result headers and cards built per tick
ZOOM_GLIDE = 0.45  # share of the remaining zoom distance covered by each frame: ~9 frames, about a quarter of a second
ZOOM_FRAME_MS = 10
RESIZE_SETTLE_MS = 120  # redraw this long after the last window size change
# The fixed set of points on the map (no layer panel). Gathering and quest points are not shown; portals are the
# map themes: the game map (newmap) or the client's radar map («Рельеф»), the choice is kept in config.json
THEMES = {"game": "Игра", "relief": "Рельеф"}
# whose NPCs the map shows where the two sides differ: fortress NPCs (the owner's stand) and quest givers
SIDES = {"dark": "Асмодиане", "light": "Элийцы"}

# Silentera Tunnel entrances only (tools/build_poi.py).
SHOWN_TYPES = ("teleport", "bindstone", "warehouse", "merchant", "coin_merchant", "vendor", "stigma", "postbox",
               "fortress", "artifact", "dungeon", "tunnel", "portal", "raid_boss")
QUEST_TYPES = ("quest_give", "quest_important", "quest_event")  # NPCs with quests; a check box shows / hides them
BIG_TYPES = {"teleport", "bindstone"}  # drawn larger than the rest
# landmarks drawn this many times the usual size: siege fortresses and the way into the Silentera tunnel
# +85 %, dungeon entrances +50 %, artifacts +25 %
ICON_SCALE = {"fortress": 1.85, "tunnel": 1.85, "dungeon": 1.5, "artifact": 1.25}
SPLIT_ZOOM = MAX_ZOOM / ZOOM_STEP * 0.999  # the last two zoom levels: no count badges, every point its own icon
SPLIT_ROW = 4  # icons per row when a group is laid out side by side
SEARCH_PLACEHOLDER = "Найти: NPC, район"
LABELS_MIN_WIDTH = 1300  # px the zone must take on screen before area names are drawn
LABELS_ZOOM_WIDTH = 4000  # px before the «zoom» names (camps, gates, small places) are drawn too
LABEL_LEVELS = ("main", "zoom")
PIN = theme.ACCENT
PLACE_ICON = 34  # px of the blue X that marks a place from the chat, as on the game's map
# a point found by the search or reached from «Рядом», and a place from the chat, blink this long so the eye
# finds them; a point picked with a click is ringed at once
BLINK_MS = 3000
BLINK_STEP_MS = 600  # the chat's place blinks: twice slower than before (user, 13.10)
# the selected point: no ring; its icon pulses while it stays selected — slow, with a soft grow and shrink and a
# dimmer small phase (user, 13.10). With animations off it is simply drawn PULSE_STILL times larger.
PULSE_PERIOD_MS = 1600
PULSE_STEP_MS = 50
PULSE_GROW = 0.25
PULSE_DIM = 0.45
PULSE_STILL = 1.2
OTHER_PIN = theme.PLACE
BG_RGB = tuple(int(theme.SURFACE[i : i + 2], 16) for i in (1, 3, 5))


@dataclass(frozen=True)
class Place:
    map_id: str
    x: float  # game coordinates
    y: float
    label: str
    note: str = ""  # «12:03 Nick: message» for pins from the chat


@dataclass(frozen=True)
class Zone:
    map_id: str
    name: str
    path: Path
    size: int
    kx: tuple[float, float]
    ky: tuple[float, float]
    labels: tuple[tuple[float, float, str, str], ...] = ()  # area names: (image x, image y, text, level)
    relief: Path | None = None  # the «Рельеф» theme: the radar map cut to the same frame (tools/build_relief.py)
    layers: tuple[tuple[int, str, Path], ...] = ()  # Abyss layer id, display name and map image

    def to_image(self, x: float, y: float) -> tuple[float, float]:
        return self.kx[0] * y + self.kx[1], self.ky[0] * x + self.ky[1]


def pulse_icon(path: Path, size: int, brightness: float, master: tk.Misc):
    """One frame of the selected point's pulse: the icon at size px with its colours dimmed to brightness."""
    from PIL import Image, ImageEnhance, ImageTk

    try:
        with Image.open(path) as image:
            image = image.convert("RGBA")
            ratio = size / max(image.size)
            image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.LANCZOS)
            rgb, alpha = image.convert("RGB"), image.getchannel("A")
            image = ImageEnhance.Brightness(rgb).enhance(brightness).convert("RGBA")
            image.putalpha(alpha)
            return ImageTk.PhotoImage(image, master=master)
    except OSError:
        return None


def load_icon(path: Path, size: int, master: tk.Misc):
    """A ready-made icon scaled to size px on its longer side, up or down (the game's own icons are 16-36 px);
    keeps the aspect ratio. None if the file is missing."""
    from PIL import Image, ImageTk

    try:
        with Image.open(path) as image:
            image = image.convert("RGBA")
            ratio = size / max(image.size)
            image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                                 Image.LANCZOS)
            return ImageTk.PhotoImage(image, master=master)
    except OSError:
        return None


def load_zones(maps_dir: Path, names: dict[str, str]) -> dict[str, Zone]:
    """data/maps/maps.json -> {map id: Zone}. Missing or broken data gives {}."""
    try:
        index = json.loads((Path(maps_dir) / "maps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    labels = load_labels(Path(maps_dir) / "labels.tsv")
    zones = {}
    for map_id, info in index.items():
        path = Path(maps_dir) / info["file"]
        if path.is_file():
            kx, ky = tuple(info["x"]), tuple(info["y"])
            zones[map_id] = Zone(
                map_id, names.get(map_id, map_id), path, int(info["size"]), kx, ky,
                tuple((kx[0] * gy + kx[1], ky[0] * gx + ky[1], text, level)
                      for gx, gy, text, level in labels.get(map_id, [])),
                relief if (relief := Path(maps_dir) / "relief" / path.name).is_file() else None,
                tuple((int(layer["id"]), layer.get("name", f"Слой {layer['id']}"), Path(maps_dir) / layer["file"])
                      for layer in info.get("layers", []) if (Path(maps_dir) / layer["file"]).is_file()),
            )
    return zones


def load_labels(path: Path) -> dict[str, list[tuple[float, float, str, str]]]:
    """labels.tsv (tools/build_labels.py, the client's own area names) -> {map id: [(game x, game y, text,
    level), ...]}; level «main» is drawn on the whole map, «zoom» closer in; «|» in a name is a line break."""
    zones: dict[str, list] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        parts = line.split("\t")
        if line.startswith("#") or len(parts) != 5 or parts[1] not in LABEL_LEVELS:
            continue
        try:
            zones.setdefault(parts[0], []).append((float(parts[2]), float(parts[3]), parts[4].replace("|", "\n"),
                                                   parts[1]))
        except ValueError:
            continue
    return zones


class MapView(ttk.Frame):
    """The «Карта» tab: a zone picker and the map. show() opens a zone centred on a place."""

    def __init__(
        self,
        parent: tk.Misc,
        zones: dict[str, Zone],
        get_places: Callable[[], Iterable[Place]] = list,
        poi: PoiStore | None = None,
        icons_dir: Path | None = None,
        show_quests: bool = True,
        on_show_quests: Callable[[bool], None] | None = None,
        map_theme: str = "game",
        on_theme: Callable[[str], None] | None = None,
        side: str = "dark",
        on_side: Callable[[str], None] | None = None,
        bestiary_database: Path | None = None,
        bestiary_icons: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.zones = zones
        self.ui_icons = IconSet(self, resource_root() / "data" / "ui" / "icons")
        self.poi = (poi or PoiStore({}, {})).projected({map_id: z.to_image for map_id, z in zones.items()})
        self.icons_dir = icons_dir or Path(".")
        self.bestiary_database = bestiary_database
        self.bestiary_icons = bestiary_icons
        self._bestiary_store: BestiaryStore | None = None
        self._mob_search_after: str | None = None
        self._mob_search_query = ""
        self._mob_rows: list[dict] = []
        self._mob_icons: dict[str, object] = {}
        self.on_show_quests = on_show_quests or (lambda _on: None)
        self.theme = map_theme if map_theme in THEMES else "game"
        self.on_theme = on_theme or (lambda _theme: None)
        self.side = side if side in SIDES else "dark"
        self.on_side = on_side or (lambda _side: None)
        self.motion_enabled: Callable[[], bool] = lambda: True
        self.layers: set[str] = set()
        self._set_layers(show_quests)
        self._poi_icons: dict[tuple[str, int], object] = {}
        self._drawn: list[tuple[float, float, list[Poi]]] = []
        self._spots: dict[Poi, tuple[float, float]] = {}  # where each single point's icon was drawn
        self.get_places = get_places  # place links seen in the chat (pins)
        self.zone: Zone | None = None
        self.current_layer: int | None = None
        self.place: Place | None = None
        self.others: list[Place] = []
        self._external_places = False  # the selected Bestiary mob's other client spawn points
        self.spawn_areas: list[list[list[float]]] = []  # approximate image-pixel polygons for a selected mob
        self.zoom = 1.0  # screen px per map image px
        self.left = 0.0  # map image px at the canvas's left / top edge
        self.top = 0.0
        self._image = None  # PIL image of the zone
        self._photo = None
        self._render_after: str | None = None
        self._resize_after: str | None = None
        self._mob_worker: SearchWorker | None = None  # NPC searches run off the UI thread
        self._mob_seq = 0
        self._mob_pending: tuple[int, str, bool] | None = None
        self._mob_polling = False
        self._mob_render_after: str | None = None
        self._mob_generation = 0
        self._zoom_after: str | None = None  # frame timer of a zoom glide
        self._zoom_target = 1.0
        self._gliding = False  # a zoom glide is running: cheap scaling
        self._zoom_anchor = (0.0, 0.0)
        self._mob_panel_width_due = False
        self._blink_target: str | None = None  # "poi" (the selected point) or "pin" (the chat's place)
        self._blink_left = 0
        self._blink_dim = False
        self._blink_after: str | None = None
        self._pulse_after: str | None = None
        self._pulse_phase = 0.0  # 0..1 along PULSE_PERIOD_MS
        self._pulse_item: tuple | None = None  # (canvas item, poi type, base size) of the selected icon
        self._drag: tuple[int, int, float, float] | None = None
        self._by_name = {zone.name: map_id for map_id, zone in sorted(zones.items(), key=lambda kv: kv[1].name)}

        bar = self.bar = ttk.Frame(self, padding=(0, 0, 0, 8))  # its width sets the window minimum (ui:28)
        bar.pack(fill="x")
        bar.bind("<Configure>", self._fit_title, add=True)
        # ui:39: the zoom buttons are packed first, so a narrow window never pushes them off the edge; the zone,
        # search, side, quests and theme controls are one group centred in the rest of the row
        for name, hint, command in (
            ("crosshair", "Вернуться к метке из чата", self._back_to_place),
            ("plus", "Увеличить масштаб (или колесо мыши)", lambda: self._zoom_center(ZOOM_STEP)),
            ("minus", "Уменьшить масштаб (или колесо мыши)", lambda: self._zoom_center(1 / ZOOM_STEP)),
            ("house", "Показать всю карту (карту можно тянуть мышью)", self._fit),
        ):
            button = ttk.Button(bar, image=self.ui_icons.get(name, "muted"), command=command, padding=(6, 5))
            button.pack(side="right", padx=(6, 0))
            Hint(button, hint)
        group = ttk.Frame(bar)
        group.pack(side="left", expand=True)
        self.zone_var = tk.StringVar()
        self.zone_box = ttk.Combobox(group, textvariable=self.zone_var, values=list(self._by_name), state="readonly",
                                     width=16)
        self.zone_box.pack(side="left")
        self.zone_box.bind("<<ComboboxSelected>>", lambda _e: self.open_zone(self._by_name[self.zone_var.get()]))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(group, textvariable=self.search_var, style="Card.TEntry", width=20)
        self.search_entry.pack(side="left", padx=(10, 0))
        self.search_count = ttk.Label(group, text="", style="Muted.TLabel", anchor="w")  # natural width: no gap when empty
        self.search_count.pack(side="left", padx=(6, 0))
        self._show_placeholder()
        self.search_entry.bind("<FocusIn>", lambda _e: self._hide_placeholder())
        self.search_entry.bind("<FocusOut>", lambda _e: self._show_placeholder())
        self.search_entry.bind("<Return>", lambda _e: self._search(1))
        self.search_entry.bind("<Shift-Return>", lambda _e: self._search(-1))
        self.search_entry.bind("<Escape>", lambda _e: self.search_var.set(""))
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.side_var = tk.StringVar(value=SIDES[self.side])
        self.side_box = ttk.Combobox(group, textvariable=self.side_var, values=list(SIDES.values()), state="readonly",
                                     width=11)
        self.side_box.pack(side="left", padx=(12, 0))
        self.side_box.bind("<<ComboboxSelected>>", lambda _e: self._on_side_selected())
        self.quests_var = tk.BooleanVar(value=show_quests)
        if any(t in self.poi.types for t in QUEST_TYPES):
            ttk.Checkbutton(group, text=" Задания", variable=self.quests_var, style="Plain.TCheckbutton",
                            command=self._on_quests_toggled).pack(side="left", padx=(12, 0))
        self.theme_var = tk.StringVar(value=THEMES[self.theme])
        if any(z.relief is not None for z in zones.values()):
            self.theme_box = ttk.Combobox(group, textvariable=self.theme_var, values=list(THEMES.values()),
                                          state="readonly", width=8)
            self.theme_box.pack(side="left", padx=(12, 0))
            self.theme_box.bind("<<ComboboxSelected>>", lambda _e: self._on_theme_selected())
        self.layer_var = tk.StringVar()
        self.layer_box = ttk.Combobox(group, textvariable=self.layer_var, state="readonly", width=12)
        if any(z.layers for z in zones.values()):
            self.layer_box.pack(side="left", padx=(10, 0))
            self.layer_box.pack_forget()
            self.layer_box.bind("<<ComboboxSelected>>", lambda _e: self._on_layer_selected())
            Hint(self.layer_box, "Слой карты Бездны. Для NPC и подписей правило выбора по высоте в XML клиента не найдено.")
        self.title = ttk.Label(group, text="", style="Title.TLabel")
        # squeezed after the toolbar changed (a count appeared, a box widened): fit the title again
        self.title.bind("<Configure>", lambda e: self._fit_title() if self.title.winfo_reqwidth() > e.width + 2 else None)
        self.title.pack(side="left", padx=(14, 0))
        self.title.pack_forget()
        body = self.body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self._matches: list = []
        self._match_index = -1
        self._match_query = ""
        self.selected: Poi | None = None
        self.point_card = PointCard(body, get_icon=lambda t: self._poi_icon(t, 20))
        self.point_card.pack(side="right", fill="y", padx=(10, 0))
        self.mob_panel = tk.Frame(body, bg=theme.SURFACE, width=440)
        self.mob_panel.pack_propagate(False)
        self.mob_header = tk.Frame(self.mob_panel, bg=theme.SURFACE, padx=12, pady=12)
        self.mob_header.pack(fill="x")
        tk.Label(self.mob_header, text="Результаты поиска", bg=theme.SURFACE, fg=theme.TEXT,
                 font=theme.font("title"), anchor="w").pack(fill="x")
        self.mob_subtitle = tk.Label(self.mob_header, text="", bg=theme.SURFACE, fg=theme.MUTED,
                                     font=theme.font("small"), anchor="w", wraplength=370)
        self.mob_subtitle.pack(fill="x", pady=(5, 0))
        panel_body = tk.Frame(self.mob_panel, bg=theme.SURFACE)
        panel_body.pack(fill="both", expand=True)
        self.mob_canvas = tk.Canvas(panel_body, bg=theme.SURFACE, highlightthickness=0, borderwidth=0)
        self.mob_canvas.pack(side="left", fill="both", expand=True)
        mob_scroll = ttk.Scrollbar(panel_body, orient="vertical", command=self.mob_canvas.yview)
        mob_scroll.pack(side="right", fill="y")
        self.mob_canvas.configure(yscrollcommand=mob_scroll.set)
        self.mob_content = tk.Frame(self.mob_canvas, bg=theme.SURFACE)
        self._mob_window = self.mob_canvas.create_window((0, 0), window=self.mob_content, anchor="nw")
        self.mob_canvas.bind("<Configure>", self._fit_mob_content)
        self.mob_content.bind("<Configure>", lambda _e: self.mob_canvas.configure(scrollregion=self.mob_canvas.bbox("all")))
        self.mob_canvas.bind("<MouseWheel>", lambda e: self.mob_canvas.yview_scroll(-int(e.delta / 120), "units"))
        self.mob_selection = tk.Frame(self.mob_panel, bg=theme.SURFACE_2, padx=12, pady=10)
        self.mob_selection.pack(fill="x", padx=8, pady=8)
        self.mob_selection_title = tk.Label(self.mob_selection, text="Область появления", bg=theme.SURFACE_2,
                                             fg=theme.ACCENT, font=theme.font("control_strong"), anchor="w")
        self.mob_selection_title.pack(fill="x")
        self.mob_selection_info = tk.Label(self.mob_selection, text="Выберите результат", bg=theme.SURFACE_2,
                                            fg=theme.MUTED, font=theme.font("small"), anchor="w", wraplength=350)
        self.mob_selection_info.pack(fill="x", pady=(5, 7))
        self.mob_point_button = ttk.Button(self.mob_selection, text="➤  Перейти к точке",
                                            command=self._go_to_mob_point)
        self.mob_point_button.pack(fill="x")
        self.mob_point_button.configure(state="disabled")
        self._mob_target: tuple[str, float, float] | None = None
        body.bind("<Configure>", self._size_mob_panel, add="+")
        card = ttk.Frame(body, style="Card.TFrame", padding=6)
        card.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(card, background=theme.BG, highlightthickness=0, borderwidth=0)  # fleur only while dragging
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._on_resize())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", lambda e: self.zoom_at(2.0, e.x, e.y))
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.coords_var = tk.StringVar()
        tk.Label(card, textvariable=self.coords_var, background=theme.SURFACE, foreground=theme.MUTED,
                 font=theme.font("micro")).place(relx=0, rely=1, x=10, y=-8, anchor="sw")
        self.canvas.tag_bind("other", "<Enter>", self._on_pin_enter)
        self.canvas.tag_bind("other", "<Leave>", lambda _e: self.canvas.delete("bubble"))
        self.canvas.tag_bind("poi", "<Enter>", self._on_poi_enter)
        self.canvas.tag_bind("poi", "<Leave>", lambda _e: self.canvas.delete("bubble"))

    def has_map(self, map_id: str) -> bool:
        return map_id in self.zones

    def activate(self) -> None:
        """Tab opened: show a zone (the last linked one, else Келькмарос) and fresh pins."""
        if self.zone is None:
            recent = [p.map_id for p in self.get_places() if p.map_id in self.zones]
            default = recent[-1] if recent else ("220070000" if "220070000" in self.zones else next(iter(self.zones), None))
            if default is not None:
                self.open_zone(default)
        else:
            if not self._external_places:
                self._refresh_pins()
            self.render()

    def open_zone(self, map_id: str) -> None:
        """Browse a zone: the whole map, pins of the chat's places, no selected place."""
        zone = self.zones.get(map_id)
        if zone is None:
            return
        self._cancel_fly()
        self.place = None
        self._external_places = False
        self.spawn_areas = []
        self.selected = None
        self._stop_blink()
        self.point_card.clear()
        self._set_zone(zone)
        self._set_title("")
        self._refresh_pins()
        self.update_idletasks()
        self._fit()

    def show(
        self, place: Place, others: Iterable[Place] | None = None,
        source_label: str = "Место из чата",
        spawn_areas: Iterable[list[list[float]]] = (),
        fit_all: bool = False,
    ) -> None:
        """Show a place. fit_all: end on the whole zone in one drawing instead of flying to the place first."""
        self._cancel_fly()
        zone = self.zones.get(place.map_id)
        self.place = place
        self._external_places = others is not None
        self.spawn_areas = list(spawn_areas)
        if zone is None:
            self._set_title(f"{place.label}  ·  карты этой зоны нет")
            return
        if zone is not self.zone:
            self._set_zone(zone)
        self._refresh_pins(others)
        self._set_title(place.label)
        self.selected = None
        self.point_card.show(
            source_label, place.label, place.x, place.y, place.note, self.nearby(zone.map_id, place.x, place.y)
        )
        self.update_idletasks()
        if fit_all:
            self._cancel_zoom()
            self.zoom = self._fit_zoom()
            self._clamp()
            self._start_blink("pin")
            self.render()
            return
        if self.zoom < self._fit_zoom() * 2:
            self.zoom = min(MAX_ZOOM, self._fit_zoom() * 2)
        self._start_blink("pin")
        self.fly_to(*zone.to_image(place.x, place.y))

    def _set_title(self, text: str) -> None:
        """Only show the map title when it contains useful text (UI/UX item 18)."""
        self._title_full = text
        self.title.configure(text=text)
        if text:
            if not self.title.winfo_manager():
                self.title.pack(side="left", padx=(14, 0))
            self.after_idle(self._fit_title)
        elif self.title.winfo_manager():
            self.title.pack_forget()

    def _fit_title(self, _event=None) -> None:
        """A long name must not be squeezed to two letters in a narrow toolbar: shorten it to what fits, and hide
        it when even a few letters do not fit (the name is also in the results panel)."""
        text = getattr(self, "_title_full", "")
        if not text or not self.winfo_ismapped() or self.bar.winfo_width() < 300:
            return
        if not self.title.winfo_manager():
            self.title.pack(side="left", padx=(14, 0))
        self.title.configure(text=text)
        # room left for the title: the toolbar width minus everything else in it (no forced layout pass, which
        # cost a quarter of a second after every NPC search)
        def taken(widget: tk.Misc) -> int:
            padx = widget.pack_info().get("padx", 0)
            values = padx if isinstance(padx, (tuple, list)) else str(padx).split() if isinstance(padx, str) else (padx, padx)
            if len(values) == 1:
                values = (values[0], values[0])
            return widget.winfo_reqwidth() + sum(int(str(value)) for value in values)

        group = self.title.master
        available = self.bar.winfo_width() - sum(taken(w) for w in self.bar.pack_slaves() if w is not group)
        available -= sum(taken(w) for w in group.pack_slaves() if w is not self.title) + 14
        font = tkfont.Font(font=ttk.Style().lookup("Title.TLabel", "font") or "TkDefaultFont")
        available -= max(0, self.title.winfo_reqwidth() - font.measure(text))  # the label's own padding
        if font.measure(text) <= available + 2:
            return
        low, high = 0, len(text)
        while low < high:  # the longest prefix that fits with «…»
            middle = (low + high + 1) // 2
            if font.measure(text[:middle].rstrip() + "…") <= available:
                low = middle
            else:
                high = middle - 1
        if low < 5:
            self.title.pack_forget()
        else:
            self.title.configure(text=text[:low].rstrip() + "…")

    def center_on(self, image_x: float, image_y: float) -> None:
        width, height = self._canvas_size()
        self.left = image_x - width / 2 / self.zoom
        self.top = image_y - height / 2 / self.zoom
        self._clamp()
        self.render()

    def fly_to(self, image_x: float, image_y: float) -> None:
        """Move the map by four short frames without changing its zoom."""
        width, height = self._canvas_size()
        target_left = image_x - width / 2 / self.zoom
        target_top = image_y - height / 2 / self.zoom
        start_left, start_top = self.left, self.top
        if not self.motion_enabled() or (abs(target_left - start_left) < 2 and abs(target_top - start_top) < 2):
            self.left, self.top = target_left, target_top
            self._clamp()
            self.render()
            return
        self._cancel_zoom()
        self._cancel_fly()
        self._fly_frame = 0

        def step() -> None:
            if not self.winfo_exists():
                return
            self._fly_frame += 1
            t = self._fly_frame / 4
            ease = 1 - (1 - t) ** 3
            self.left = start_left + (target_left - start_left) * ease
            self.top = start_top + (target_top - start_top) * ease
            self._clamp()
            self.render()
            if self._fly_frame < 4:
                self._fly_after = self.after(35, step)
            else:
                self._fly_after = None

        step()

    def _cancel_fly(self) -> None:
        after_id = getattr(self, "_fly_after", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            self._fly_after = None

    def zoom_at(self, factor: float, screen_x: float, screen_y: float) -> None:
        """Zoom keeping the map point under (screen_x, screen_y) in place. The zoom glides to its new level over
        about ten frames (a wheel click moves the target, several clicks in a row add up); without motion it jumps."""
        self._cancel_fly()
        base = self._zoom_target if self._zoom_after is not None else self.zoom
        self._zoom_target = max(self._fit_zoom(), min(MAX_ZOOM, base * factor))
        self._zoom_anchor = (screen_x, screen_y)
        if not self.motion_enabled():
            self._zoom_step(1.0)
            return
        if self._zoom_after is None:
            self._zoom_frame()

    def _zoom_step(self, share: float) -> None:
        """Move `share` of the way to the target zoom, the point under the anchor staying where it is."""
        screen_x, screen_y = self._zoom_anchor
        new = self.zoom + (self._zoom_target - self.zoom) * share
        if abs(new - self._zoom_target) < self._zoom_target * 0.004:
            new = self._zoom_target
        image_x = self.left + screen_x / self.zoom
        image_y = self.top + screen_y / self.zoom
        self.zoom = new
        self.left = image_x - screen_x / new
        self.top = image_y - screen_y / new
        self._clamp()

    def _zoom_frame(self) -> None:
        self._zoom_after = None
        if not self.winfo_exists():
            return
        self._gliding = True
        self._zoom_step(ZOOM_GLIDE)
        self.render()
        if self.zoom != self._zoom_target:
            self._zoom_after = self.after(ZOOM_FRAME_MS, self._zoom_frame)
        else:
            self._gliding = False
            self._schedule_render()  # the final, sharp picture

    def finish_zoom(self) -> None:
        """Jump to the target zoom now (tests, and anything that needs the final level)."""
        self._cancel_zoom()
        if self.zoom != getattr(self, "_zoom_target", self.zoom):
            self._zoom_step(1.0)
            self._schedule_render()

    def _cancel_zoom(self) -> None:
        self._gliding = False
        if self._zoom_after is not None:
            try:
                self.after_cancel(self._zoom_after)
            except tk.TclError:
                pass
            self._zoom_after = None

    def _refresh_pins(self, others: Iterable[Place] | None = None) -> None:
        places = self.get_places() if others is None else others
        map_id = self.zone.map_id if self.zone is not None else None
        self.others = [p for p in places if p.map_id == map_id and p != self.place]

    def _set_zone(self, zone: Zone) -> None:
        from PIL import Image

        self.zone = zone
        self.current_layer = zone.layers[0][0] if zone.layers else None
        self._sync_layer_box()
        self._load_image()
        self.zone_var.set(zone.name)
        self.zoom = self._fit_zoom()
        self.canvas.delete("all")

    def _load_image(self) -> None:
        from PIL import Image

        layer_path = next((path for layer_id, _name, path in self.zone.layers if layer_id == self.current_layer), None)
        path = (self.zone.relief if self.theme == "relief" and self.zone.relief is not None else
                layer_path or self.zone.path)
        with Image.open(path) as image:
            self._image = image.convert("RGB")

    def _on_theme_selected(self) -> None:
        """«Игра» / «Рельеф»: both pictures share the frame, so the view and the points stay where they are."""
        self.theme = next(key for key, name in THEMES.items() if name == self.theme_var.get())
        self.on_theme(self.theme)
        if self.zone is not None:
            self._load_image()
            self.render()

    def _sync_layer_box(self) -> None:
        if self.zone is None or not self.zone.layers:
            self.layer_box.pack_forget()
            return
        self.layer_box.configure(values=[name for _layer_id, name, _path in self.zone.layers])
        selected = next((name for layer_id, name, _path in self.zone.layers if layer_id == self.current_layer),
                        self.zone.layers[0][1])
        self.layer_var.set(selected)
        if not self.layer_box.winfo_manager():
            self.layer_box.pack(side="left", padx=(10, 0), after=self.zone_box)

    def _on_layer_selected(self) -> None:
        if self.zone is None:
            return
        self.current_layer = next((layer_id for layer_id, name, _path in self.zone.layers
                                   if name == self.layer_var.get()), None)
        self._load_image()
        self._schedule_render()

    # --- geometry ----------------------------------------------------------------------
    def _canvas_size(self) -> tuple[int, int]:
        width = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else 960
        height = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else 900
        return width, height

    def _fit_zoom(self) -> float:
        if self.zone is None:
            return 1.0
        return min(self._canvas_size()) / self.zone.size

    def _clamp(self) -> None:
        if self.zone is None:
            return
        width, height = self._canvas_size()
        size = self.zone.size
        view_w, view_h = width / self.zoom, height / self.zoom
        # keep the map on screen; centre it when it is smaller than the window. When zoomed in, the map may
        # move half a view past its edge, so a point at the very edge can still be put in the centre.
        margin_w, margin_h = view_w / 2, view_h / 2
        if view_w >= size:
            self.left = (size - view_w) / 2
        else:
            self.left = min(max(self.left, -margin_w), size - view_w + margin_w)
        if view_h >= size:
            self.top = (size - view_h) / 2
        else:
            self.top = min(max(self.top, -margin_h), size - view_h + margin_h)

    def to_screen(self, image_x: float, image_y: float) -> tuple[float, float]:
        return (image_x - self.left) * self.zoom, (image_y - self.top) * self.zoom

    # --- drawing -------------------------------------------------------------------------
    def _schedule_render(self) -> None:
        if self._render_after is None:
            self._render_after = self.after_idle(self.render)

    def _schedule_sharp(self) -> None:
        if getattr(self, "_sharp_after", None):
            self.after_cancel(self._sharp_after)

        def sharpen() -> None:
            self._sharp_after = None
            self._sharp_due = True
            self.render()

        self._sharp_after = self.after(160, sharpen)

    def render(self) -> None:
        from PIL import Image, ImageTk

        self._render_after = None
        if self.zone is None or self._image is None:
            return
        width, height = self._canvas_size()
        # visible part of the map, cropped and scaled to the canvas
        size = self.zone.size
        x0, y0 = max(0.0, self.left), max(0.0, self.top)
        x1 = min(float(size), self.left + width / self.zoom)
        y1 = min(float(size), self.top + height / self.zoom)
        view = Image.new("RGB", (width, height), BG_RGB)  # around the map when it is smaller than the window
        part_w, part_h = round((x1 - x0) * self.zoom), round((y1 - y0) * self.zoom)
        if part_w > 0 and part_h > 0:
            if self.zoom >= 1 or self._gliding:  # while the zoom glides, scale only what is visible: one cheap pass
                part = self._image.resize((part_w, part_h), Image.BILINEAR, box=(x0, y0, x1, y1))
            else:
                # zoomed out: scale the whole picture once per zoom level, then dragging only crops it
                # (resizing the visible part on every frame made panning stutter)
                key = (id(self._image), self.zoom)
                if getattr(self, "_scaled_key", None) not in (key, key + ("fast",)):
                    # a new zoom: a fast picture now, the sharp one when the wheel stops
                    side = max(1, round(size * self.zoom))
                    self._scaled = self._image.resize((side, side), Image.BILINEAR, reducing_gap=2.0)
                    self._scaled_key = key + ("fast",)
                    self._schedule_sharp()
                elif self._scaled_key == key + ("fast",) and getattr(self, "_sharp_due", False):
                    side = max(1, round(size * self.zoom))
                    self._scaled = self._image.resize((side, side), Image.LANCZOS, reducing_gap=2.0)
                    self._scaled_key = key
                self._sharp_due = False
                sx, sy = round(x0 * self.zoom), round(y0 * self.zoom)
                part = self._scaled.crop((sx, sy, sx + part_w, sy + part_h))
            view.paste(part, (round((x0 - self.left) * self.zoom), round((y0 - self.top) * self.zoom)))
        circle = enclosing_spawn_circle(self.spawn_areas)
        if circle:
            cx, cy, radius = circle
            view = paint_spawn_circle(view, self.to_screen(cx, cy), radius * self.zoom)
        self._photo = ImageTk.PhotoImage(view, master=self.canvas)
        canvas = self.canvas
        canvas.delete("all")
        canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self._draw_labels(width, height)
        self._draw_poi(width, height)
        self._avoid_label_poi(width, height)  # ui:33: area text must not cover map icons
        for index, other in enumerate(self.others if self.zoom >= self._fit_zoom() * 1.7 else []):
            sx, sy = self.to_screen(*self.zone.to_image(other.x, other.y))
            canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=OTHER_PIN, outline=theme.PLACE_OUTLINE, width=2,
                               tags=("other", f"other_{index}"))
        if self.place is not None:
            sx, sy = self.to_screen(*self.zone.to_image(self.place.x, self.place.y))
            pin = ("pin", "blink") if self._blink_target == "pin" else "pin"
            cross = self._place_icon()
            if cross is not None:
                canvas.create_image(sx, sy, image=cross, tags=pin)
            else:
                canvas.create_oval(sx - 13, sy - 13, sx + 13, sy + 13, outline=PIN, width=3, tags=pin)
                canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=PIN, outline="", tags=pin)
            font = theme.font("body_bold")
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):  # dark outline, like the area names
                canvas.create_text(sx + 18 + dx, sy - 2 + dy, text=self.place.label, anchor="w", fill=theme.OUTLINE_DARK,
                                   font=font, tags="pin")
            canvas.create_text(sx + 18, sy - 2, text=self.place.label, anchor="w", fill=theme.MAP_TEXT, font=font,
                               tags="pin")
        if self._blink_dim:
            canvas.itemconfigure("blink", state="hidden")

    def _draw_labels(self, width: int, height: int) -> None:
        """Area names, like the game map: white text with a dark outline; size follows the zoom.

        Hidden while the whole zone is small on screen — they would cover each other.
        """
        if self.zoom * self.zone.size < LABELS_MIN_WIDTH:
            return
        size = max(8, min(15, round(5 + 4 * self.zoom)))
        fonts = {"main": (theme.FONT_FAMILY, size + 1, "bold"), "zoom": (theme.FONT_FAMILY, size - 1, "bold")}
        close = self.zoom * self.zone.size >= LABELS_ZOOM_WIDTH
        for index, (image_x, image_y, text, level) in enumerate(self.zone.labels):
            if level == "zoom" and not close:
                continue
            font = fonts[level]
            sx, sy = self.to_screen(image_x, image_y)
            if -200 < sx < width + 200 and -60 < sy < height + 60:
                tags = ("label", f"area_label_{index}")
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
                    self.canvas.create_text(sx + dx, sy + dy, text=text, fill=theme.OUTLINE_DARK, font=font,
                                            justify="center", tags=tags)
                self.canvas.create_text(sx, sy, text=text, fill=theme.MAP_LABEL, font=font, justify="center", tags=tags)

    def _avoid_label_poi(self, width: int, height: int) -> None:
        """Nudge area names around POI icons, including badges, at the current zoom."""
        canvas = self.canvas
        icon_boxes = [box for item in canvas.find_withtag("poi") if (box := canvas.bbox(item))]
        if not icon_boxes:
            return
        def overlaps(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
            return a[0] < b[2] + 5 and a[2] > b[0] - 5 and a[1] < b[3] + 5 and a[3] > b[1] - 5

        for index in range(len(self.zone.labels)):
            tag = f"area_label_{index}"
            box = canvas.bbox(tag)
            if box is None or not any(overlaps(box, icon) for icon in icon_boxes):
                continue
            nearby = [icon for icon in icon_boxes if icon[0] < box[2] + 90 and icon[2] > box[0] - 90
                      and icon[1] < box[3] + 90 and icon[3] > box[1] - 90]
            for dx, dy in ((0, -28), (0, 28), (-38, 0), (38, 0), (0, -56), (0, 56)):
                moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
                if (moved[0] >= 2 and moved[1] >= 2 and moved[2] <= width - 2 and moved[3] <= height - 2
                        and not any(overlaps(moved, icon) for icon in nearby)):
                    canvas.move(tag, dx, dy)
                    break
            else:
                canvas.itemconfigure(tag, state="hidden")

    # --- selection and «Рядом» ------------------------------------------------------------
    def nearby(self, zone: str, gx: float, gy: float, exclude: Poi | None = None):
        """Closest teleporter, warehouse, merchant, … around a game position, for the card."""
        out = []
        for type_ in NEARBY_TYPES:
            candidates = [p for p in self.poi.in_zone(zone, {type_}, self.side, self.current_layer) if p != exclude]
            if not candidates:
                continue
            best = min(candidates, key=lambda p: math.hypot(p.gx - gx, p.gy - gy))
            metres = math.hypot(best.gx - gx, best.gy - gy)
            out.append((type_, self.poi.type_name(type_), best.name, metres, lambda p=best: self.select(p, centre=True)))
        return out

    def select(self, poi: Poi, centre: bool = False) -> None:
        """Show a point in the card; its icon pulses on the map while it is selected. The search and «Рядом»
        (centre=True) also move the map to it."""
        self.selected = poi
        kind = self.poi.type_name(poi.type)
        self.point_card.show(kind, poi.name or kind, poi.gx, poi.gy, poi.note, self.nearby(poi.zone, poi.gx, poi.gy, poi))
        if self._blink_target == "pin":
            self._stop_blink(redraw=False)
        self._start_pulse()
        if centre:
            self.fly_to(poi.x, poi.y)
        else:
            self._schedule_render()

    def _on_release(self, event: tk.Event) -> None:
        start = self._drag
        self._drag = None
        self.canvas.configure(cursor="")
        if start is not None and abs(event.x - start[0]) < 4 and abs(event.y - start[1]) < 4:
            self._on_click(event)

    def _on_click(self, event: tk.Event) -> None:
        """A click (not a drag): a single point opens its card, a cluster zooms in on itself."""
        hits = self.canvas.find_overlapping(event.x - 2, event.y - 2, event.x + 2, event.y + 2)
        for item in reversed(hits):
            tags = self.canvas.gettags(item)
            index = next((int(t[4:]) for t in tags if t.startswith("poi_")), None)
            if index is not None and index < len(self._drawn):
                _sx, _sy, members = self._drawn[index]
                if len(members) == 1:
                    self.select(members[0])
                else:
                    self.zoom_at(2.0, event.x, event.y)
                return
            other = next((int(t[6:]) for t in tags if t.startswith("other_")), None)
            if other is not None and other < len(self.others) and self.zone is not None:
                place = self.others[other]
                self.selected = None
                self.point_card.show(
                    "Точка появления" if self._external_places else "Место из чата",
                    place.label, place.x, place.y, place.note,
                                     self.nearby(self.zone.map_id, place.x, place.y))
                return

    def search(self, query: str, step: int) -> str:
        """Find points (any layer, by name or type) and area names in the shown zone.

        step 0 = new query (go to the first match), 1 / -1 = next / previous. Returns «2 / 7» or «нет».
        """
        if self.zone is None:
            return ""
        if step == 0 or query != self._match_query:
            words = normalize(query).split()
            points = self.poi.search(self.zone.map_id, query, self.layers, self.side, self.current_layer)
            areas = [(x, y, text) for x, y, text, _level in self.zone.labels
                     if all(w in normalize(text) for w in words)]
            self._matches = list(points) + areas
            self._match_query = query
            self._match_index = -1
        if not self._matches:
            return "нет"
        self._match_index = (self._match_index + (step or 1)) % len(self._matches)
        match = self._matches[self._match_index]
        if self.zoom < 1.0:
            self.zoom = 1.0
        if isinstance(match, Poi):
            self.select(match, centre=True)
        else:
            x, y, text = match
            self.selected = None
            self.point_card.show("Район", text.replace("\n", " "), 0, 0, "", [])
            self.point_card.coords.configure(text="")
            self.fly_to(x, y)
        return f"{self._match_index + 1} / {len(self._matches)}"

    def _set_layers(self, show_quests: bool) -> None:
        shown = SHOWN_TYPES + (QUEST_TYPES if show_quests else ())
        self.layers = {t for t in shown if t in self.poi.types}

    def _on_side_selected(self) -> None:
        """«Асмодиане» / «Элийцы»: fortress NPCs of that side (as if it owned the fortresses) and its quest givers."""
        self.side = next(key for key, name in SIDES.items() if name == self.side_var.get())
        if self.selected is not None and self.selected.side and self.selected.side != self.side:
            self.selected = None
            self._stop_blink(redraw=False)
            self.point_card.clear()
        elif self.selected is not None:  # «Рядом» lists that side's NPCs now
            kind = self.poi.type_name(self.selected.type)
            p = self.selected
            self.point_card.show(kind, p.name or kind, p.gx, p.gy, p.note, self.nearby(p.zone, p.gx, p.gy, p))
        self._match_query = ""
        self.on_side(self.side)
        self._schedule_render()

    def _on_quests_toggled(self) -> None:
        """«Задания» check box: NPCs with quests (from aiondb links, see tools/build_poi.py) on or off."""
        on = bool(self.quests_var.get())
        self._set_layers(on)
        if self.selected is not None and self.selected.type not in self.layers:
            self.selected = None
            self.point_card.clear()
        self._match_query = ""
        self.on_show_quests(on)
        self._schedule_render()

    def _search(self, step: int) -> str:
        """Search box: next (1) / previous (-1) / first (0) match; shows «2 / 7» or «нет»."""
        query = self.search_var.get().strip()
        query = "" if query == SEARCH_PLACEHOLDER else query
        if self.bestiary_database and query:
            self._run_mob_search()
            if self._mob_rows:
                self.search_count.configure(text=f"{len(self._mob_rows)} NPC")
                return "break"
        self.search_count.configure(text=self.search(query, step) if query else "")
        return "break"

    def _on_search_key(self, event: tk.Event) -> None:
        if event.keysym not in ("Return", "Escape", "Shift_L", "Shift_R"):
            if self.bestiary_database:
                if self._mob_search_after:
                    self.after_cancel(self._mob_search_after)
                self._mob_search_after = self.after(220, self._run_mob_search)
            else:
                self._search(0)

    def _fit_mob_content(self, event: tk.Event) -> None:
        """Set the content width only when it changes: every real change re-lays out all result cards."""
        if int(self.mob_canvas.itemcget(self._mob_window, "width") or 0) != event.width:
            self.mob_canvas.itemconfigure(self._mob_window, width=event.width)

    def _size_mob_panel(self, event: tk.Event) -> None:
        """Panel width follows the window only when it settles: each step re-wraps every result card (70 ms)."""
        self._mob_panel_width_due = True
        self._schedule_resize()

    def _apply_mob_panel_width(self) -> None:
        if self._mob_panel_width_due and self.mob_panel.winfo_manager():
            self.mob_panel.configure(width=max(360, round(self.body.winfo_width() * 0.40)))
        self._mob_panel_width_due = False

    def _run_mob_search(self, preserve_map: bool = False) -> None:
        self._mob_search_after = None
        query = self.search_var.get().strip()
        if query == SEARCH_PLACEHOLDER:
            query = ""
        if not self.bestiary_database or len(query) < 2:
            self._mob_pending = None  # an answer still on its way must not bring the panel back
            self._hide_mob_results()
            return
        if self._mob_worker is None:
            self._mob_worker = SearchWorker(self.bestiary_database)
        self._mob_seq += 1
        self._mob_pending = (self._mob_seq, query, preserve_map)
        self._mob_worker.submit(self._mob_seq, query, limit=20)
        if not self._mob_polling:
            self._mob_polling = True
            self.after(25, self._poll_mob_search)

    def _poll_mob_search(self) -> None:
        """Pick up the newest finished NPC search; answers to replaced requests are dropped."""
        if not self.winfo_exists():
            return
        result = self._mob_worker.latest() if self._mob_worker else None
        if result is not None and self._mob_pending and result.seq == self._mob_pending[0]:
            _seq, query, preserve_map = self._mob_pending
            self._mob_pending = None
            self._mob_polling = False
            self._finish_mob_search(query, result, preserve_map)
            return
        self.after(25, self._poll_mob_search)

    def wait_for_mob_search(self, timeout: float = 5.0) -> None:
        """Run the event loop until the last NPC search is shown (tests, scripts)."""
        import time
        end = time.monotonic() + timeout
        while (self._mob_polling or self._mob_render_after is not None) and time.monotonic() < end:
            self.update()
            time.sleep(0.005)

    def _finish_mob_search(self, query: str, result, preserve_map: bool) -> None:
        if result.error:
            self.bestiary_database = None  # unreadable data: the map keeps working without the NPC search
            self._mob_worker.close()
            self._mob_worker = None
            self._hide_mob_results()
            return
        if self._bestiary_store is None:
            try:
                self._bestiary_store = BestiaryStore(self.bestiary_database)
            except (OSError, ValueError, sqlite3.Error):
                self.bestiary_database = None
                self._hide_mob_results()
                return
        rows, total = result.rows, result.total
        self._mob_rows = rows
        self._mob_search_query = query
        if not rows:
            self._hide_mob_results()
            self.search_count.configure(text=self.search(query, 0))
            return
        self.point_card.pack_forget()
        if not self.mob_panel.winfo_manager():
            self.mob_panel.pack(side="right", fill="y", padx=(10, 0))
        self._mob_target = None
        self.mob_selection_info.configure(text="Выберите результат")
        self.mob_point_button.configure(state="disabled")
        self.mob_panel.configure(width=max(360, round(self.body.winfo_width() * 0.40)))
        self.mob_subtitle.configure(text=f"По запросу: «{query}»  ·  {total} NPC")
        groups: dict[str, list[tuple[dict, dict, list[dict]]]] = {}
        for row in rows:
            detail = self._bestiary_store.detail(row["id"])
            if not detail:
                continue
            points_by_zone: dict[str, list[dict]] = {}
            for point in detail.get("points") or []:
                map_id = str(point.get("map_id") or "")
                if map_id in self.zones:
                    points_by_zone.setdefault(map_id, []).append(point)
            for map_id, points in points_by_zone.items():
                groups.setdefault(map_id, []).append((row, detail, points))
        self._render_mob_results(groups)
        if not preserve_map and groups:
            first_zone = min(groups, key=lambda map_id: self.zones[map_id].name)
            first = groups[first_zone][0]
            self._show_mob_zone(first[1], first_zone, first[2])
        elif preserve_map and self.place:
            for row, detail, points in groups.get(self.place.map_id, []):
                if detail["name"] == self.place.label:
                    self._set_mob_selection(detail, self.place.map_id, points)
                    break
        self.search_count.configure(text=f"{total} NPC")

    def _hide_mob_results(self) -> None:
        self._mob_generation += 1  # cards still being built are dropped
        self._mob_rows = []
        self._mob_search_query = ""
        self._mob_target = None
        if self.mob_panel.winfo_manager():
            self.mob_panel.pack_forget()
            self.point_card.pack(side="right", fill="y", padx=(10, 0))
        if self._external_places:
            self.spawn_areas = []
            self._external_places = False
            self._refresh_pins()
            self._schedule_render()

    def _render_mob_results(self, groups: dict[str, list[tuple[dict, dict, list[dict]]]]) -> None:
        """Header and card builders run a few at a time, so a long result list never freezes the map."""
        self._swap_mob_content()
        if self._mob_render_after is not None:
            self.after_cancel(self._mob_render_after)
            self._mob_render_after = None
        if not groups:
            tk.Label(self.mob_content, text="Для найденных NPC нет точек на доступных картах.",
                     bg=theme.SURFACE, fg=theme.MUTED, wraplength=350, justify="left").pack(anchor="w", padx=12, pady=12)
            return
        jobs: list[Callable[[], None]] = []
        for map_id, entries in sorted(groups.items(), key=lambda pair: self.zones[pair[0]].name):
            total_points = sum(len(points) for _row, _detail, points in entries)
            jobs.append(lambda m=map_id, n=total_points: self._mob_header(m, n))
            for row, detail, points in entries:
                jobs.append(lambda d=detail, m=map_id, p=points: self._mob_card(d, m, p))
        self._mob_generation += 1
        self._run_mob_jobs(jobs, 0, self._mob_generation)

    def _swap_mob_content(self) -> None:
        """A fresh list container instead of destroying a hundred old widgets at once (that was a 100 ms freeze);
        the old one is taken apart a few widgets at a time."""
        old = self.mob_content
        old.unbind("<Configure>")
        new = self.mob_content = tk.Frame(self.mob_canvas, bg=theme.SURFACE)
        new.bind("<Configure>", lambda _e: self.mob_canvas.configure(scrollregion=self.mob_canvas.bbox("all")))
        self.mob_canvas.itemconfigure(self._mob_window, window=new)
        old.lower()
        self._discard_mob_content(old)

    def _discard_mob_content(self, old: tk.Misc) -> None:
        if not old.winfo_exists():
            return
        children = old.winfo_children()
        for child in children[:6]:
            child.destroy()
        if len(children) > 6:
            self.after(10, lambda: self._discard_mob_content(old))
        else:
            old.destroy()

    def _run_mob_jobs(self, jobs: list, start: int, generation: int) -> None:
        self._mob_render_after = None
        if generation != self._mob_generation or not self.winfo_exists():
            return
        for job in jobs[start:start + MOB_JOBS_PER_TICK]:
            job()
        bind_wheel_tree(self.mob_content, self.mob_canvas)
        if start == 0:
            self.mob_canvas.yview_moveto(0)
        if start + MOB_JOBS_PER_TICK < len(jobs):
            self._mob_render_after = self.after(8, lambda: self._run_mob_jobs(jobs, start + MOB_JOBS_PER_TICK, generation))

    def _mob_header(self, map_id: str, total_points: int) -> None:
        tk.Label(self.mob_content, text=f"⌖  {self.zones[map_id].name}  ·  {plural(total_points, "точка", "точки", "точек")}",
                 bg=theme.SURFACE_2, fg=theme.ACCENT, font=theme.font("control_strong"),
                 anchor="w", padx=12, pady=9).pack(fill="x", padx=8, pady=(8, 4))

    def _mob_card(self, detail: dict, map_id: str, points: list[dict]) -> None:
        card = tk.Frame(self.mob_content, bg=theme.SURFACE_2, padx=10, pady=10)
        card.pack(fill="x", padx=8, pady=(0, 7))
        top = tk.Frame(card, bg=theme.SURFACE_2)
        top.pack(fill="x")
        icon = self._mob_icon(detail)
        tk.Label(top, image=icon, bg=theme.SURFACE_2, width=56, height=56).pack(side="left", padx=(0, 9))
        info = tk.Frame(top, bg=theme.SURFACE_2)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=detail["name"], bg=theme.SURFACE_2, fg=theme.TEXT,
                 font=theme.font("control_strong"), anchor="w").pack(fill="x")
        chips = tk.Frame(info, bg=theme.SURFACE_2)
        chips.pack(anchor="w", pady=(3, 0))
        for key, color in (("kind", theme.PLACE), ("faction", theme.DANGER), ("rank", theme.TEXT)):
            value = detail.get(key)
            if value:
                tk.Label(chips, text=str(value).upper(), bg=theme.SURFACE_3, fg=color,
                         font=theme.font("micro"), padx=5, pady=1).pack(side="left", padx=(0, 4))
        level = f"Ур. {detail['level']}  ·  " if detail.get("level") else ""
        tk.Label(info, text=f"{level}{plural(len(points), "точка", "точки", "точек")} появления", bg=theme.SURFACE_2,
                 fg=theme.MUTED, font=theme.font("small"), anchor="w").pack(fill="x")
        ttk.Button(card, text="⌖  Показать на карте",
                   command=lambda d=detail, m=map_id, p=points: self._show_mob_zone(d, m, p)).pack(fill="x", pady=(9, 0))

    def _mob_icon(self, detail: dict):
        asset = "ui/monster.png" if detail.get("category") == "monster" else detail.get("icon_asset") or ""
        if asset in self._mob_icons:
            return self._mob_icons[asset]
        path = (self.bestiary_icons or Path(".")) / asset
        image = load_icon(path, 54, self.mob_canvas) if path.is_file() else None
        self._mob_icons[asset] = image
        return image

    def _show_mob_zone(self, detail: dict, map_id: str, points: list[dict]) -> None:
        if not points:
            return
        first = points[0]
        x, y = float(first["gx"]), float(first["gy"])
        areas = [a["polygon"] for a in (self._bestiary_store.areas(detail["id"]) if self._bestiary_store else [])
                 if a["map_id"] == map_id]
        self.show(Place(map_id, x, y, detail["name"], "Точка появления из файлов клиента"),
                  others=[Place(map_id, float(p["gx"]), float(p["gy"]), detail["name"])
                          for p in points[1:]], source_label="Точка появления", spawn_areas=areas, fit_all=True)
        self._set_mob_selection(detail, map_id, points)

    def _set_mob_selection(self, detail: dict, map_id: str, points: list[dict]) -> None:
        if not points:
            return
        first = points[0]
        self._mob_target = (map_id, float(first["gx"]), float(first["gy"]))
        self.mob_selection_info.configure(
            text=f"{detail['name']}  ·  {self.zones[map_id].name}\n{plural(len(points), "точка", "точки", "точек")} появления"
        )
        self.mob_point_button.configure(state="normal")

    def destroy(self) -> None:
        self._mob_pending = None
        if self._mob_worker is not None:
            self._mob_worker.close()
            self._mob_worker = None
        super().destroy()

    def _go_to_mob_point(self) -> None:
        if not self._mob_target or not self.zone:
            return
        map_id, x, y = self._mob_target
        if self.zone.map_id != map_id:
            return
        self.zoom = min(MAX_ZOOM, self._fit_zoom() * 2.2)
        self.center_on(*self.zone.to_image(x, y))

    def _show_placeholder(self) -> None:
        if not self.search_var.get():
            self.search_var.set(SEARCH_PLACEHOLDER)
            self.search_entry.configure(foreground=theme.MUTED)

    def _hide_placeholder(self) -> None:
        if self.search_var.get() == SEARCH_PLACEHOLDER:
            self.search_var.set("")
        self.search_entry.configure(foreground=theme.TEXT)

    def _icon_size(self, type_: str) -> int:
        """Icon px for the current zoom: big enough to read on the whole map, teleporters bigger."""
        size = max(28, min(40, round(22 + 8 * self.zoom)))
        if type_ in BIG_TYPES:
            size += 8
        return round(size * ICON_SCALE.get(type_, 1.0))

    def _place_icon(self):
        key = ("place", PLACE_ICON)
        if key not in self._poi_icons:
            self._poi_icons[key] = load_icon(self.icons_dir / "place.png", PLACE_ICON, self.canvas)
        return self._poi_icons[key]

    def _poi_icon(self, type_: str, size: int):
        key = (type_, size)
        if key not in self._poi_icons:
            icon = self.poi.types.get(type_, {}).get("icon")
            self._poi_icons[key] = load_icon(self.icons_dir / icon, size, self.canvas) if icon else None
        return self._poi_icons[key]

    def _draw_poi(self, width: int, height: int) -> None:
        """Points as their icons; close points of one type merge into an icon with a count.

        On the last two zoom levels nothing merges: points that would cover each other are laid out side by side
        (rows of SPLIT_ROW) around their common centre, each one its own clickable icon.
        """
        self._drawn = []
        self._spots = {}
        self._pulse_item = None
        if self.zone is None or not self.layers:
            return
        points = self.poi.in_zone(self.zone.map_id, self.layers, self.side, self.current_layer)
        if self.zoom >= SPLIT_ZOOM:
            groups = self._split(points)
        else:
            groups = cluster(points, self.to_screen, radius_px=self._icon_size("") * 1.1, key=lambda p: p.type)
        # big landmarks (fortresses, the tunnel, dungeons) at the bottom, teleporters and kisks on top
        groups.sort(key=lambda g: (g[2][0].type in BIG_TYPES, g[2][0].type not in ICON_SCALE))
        canvas = self.canvas
        for sx, sy, members in groups:
            if len(members) == 1:
                self._spots[members[0]] = (sx, sy)
            size = self._icon_size(members[0].type)
            if not (-size < sx < width + size and -size < sy < height + size):
                continue
            tags = ("poi", f"poi_{len(self._drawn)}")
            chosen = self.selected in members
            if chosen:
                tags += ("pulse",)
            self._drawn.append((sx, sy, members))
            icon = self._pulse_frame(members[0].type, size) if chosen else self._poi_icon(members[0].type, size)
            if icon is not None:
                item = canvas.create_image(sx, sy, image=icon, tags=tags)
                if chosen:
                    self._pulse_item = (item, members[0].type, size)
            else:
                canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=theme.ACCENT, outline=theme.OUTLINE_DARK, tags=tags)
            if len(members) > 1:
                bx, by = sx + size * 0.45, sy - size * 0.45
                canvas.create_oval(bx - 9, by - 9, bx + 9, by + 9, fill=theme.OUTLINE_DARK, outline=theme.ACCENT, tags=tags)
                canvas.create_text(bx, by, text=str(len(members)) if len(members) < 100 else "99+",
                                   fill=theme.MAP_TEXT, font=theme.font("badge"), tags=tags)

    # --- the selected point's pulse -----------------------------------------------------------
    def _pulse_frame(self, type_: str, size: int):
        """The selected icon at the current pulse phase: grown (up to PULSE_GROW) and bright, or small and dimmer."""
        if not self.motion_enabled():
            return self._poi_icon(type_, round(size * PULSE_STILL))
        wave = 0.5 - 0.5 * math.cos(2 * math.pi * self._pulse_phase)  # 0 -> 1 -> 0, soft at both ends
        step = round(wave * 10)  # 11 cached frames per icon size
        key = ("pulse", type_, size, step)
        if key not in self._poi_icons:
            icon = self.poi.types.get(type_, {}).get("icon")
            self._poi_icons[key] = (pulse_icon(self.icons_dir / icon, round(size * (1 + PULSE_GROW * step / 10)),
                                               1 - PULSE_DIM * (1 - step / 10), self.canvas) if icon else None)
        return self._poi_icons[key]

    def _start_pulse(self) -> None:
        self._stop_pulse()
        self._pulse_phase = 0.5  # start big and bright: the eye finds it at once
        if self.motion_enabled():
            self._pulse_after = self.after(PULSE_STEP_MS, self._pulse_tick)

    def _stop_pulse(self) -> None:
        if self._pulse_after is not None:
            self.after_cancel(self._pulse_after)
            self._pulse_after = None

    def _pulse_tick(self) -> None:
        self._pulse_after = None
        if self.selected is None:
            return
        self._pulse_phase = (self._pulse_phase + PULSE_STEP_MS / PULSE_PERIOD_MS) % 1.0
        try:
            if self._pulse_item is not None:
                item, type_, size = self._pulse_item
                frame = self._pulse_frame(type_, size)
                if frame is not None and self.canvas.find_withtag(item):
                    self.canvas.itemconfigure(item, image=frame)
            self._pulse_after = self.after(PULSE_STEP_MS, self._pulse_tick)
        except tk.TclError:  # the window is closing
            self._pulse_after = None

    # --- blinking ---------------------------------------------------------------------------
    def _start_blink(self, target: str) -> None:
        self._stop_blink(redraw=False)
        self._blink_target = target
        self._blink_left = BLINK_MS // BLINK_STEP_MS
        self._blink_dim = False
        self._blink_after = self.after(BLINK_STEP_MS, self._blink_tick)

    def _stop_blink(self, redraw: bool = True) -> None:
        if self._blink_after is not None:
            self.after_cancel(self._blink_after)
            self._blink_after = None
        was = self._blink_target
        self._blink_target = None
        self._blink_dim = False
        if was and redraw:
            self._schedule_render()

    def _blink_tick(self) -> None:
        """Hide / show the blinking items; when the time is up the point gets its usual ring."""
        self._blink_after = None
        self._blink_left -= 1
        if self._blink_left <= 0:
            self._stop_blink()
            return
        self._blink_dim = not self._blink_dim
        self.canvas.itemconfigure("blink", state="hidden" if self._blink_dim else "normal")
        self._blink_after = self.after(BLINK_STEP_MS, self._blink_tick)

    def _split(self, points: list[Poi]) -> list[tuple[float, float, list[Poi]]]:
        """Single icons that never cover each other: touching points are laid out side by side; if a laid-out row
        then reaches a neighbouring group, both are merged and laid out again (a few rounds at most)."""
        groups = self._touching([(p, self.to_screen(p.x, p.y)) for p in points])
        for _ in range(6):
            spots = [(m[0], (x, y)) for cx, cy, members in groups for x, y, m in self._spread(members, cx, cy)]
            merged = self._touching(spots)
            if len(merged) == len(groups):
                break
            # merge by exact position again, so a merged group is centred on its real points
            groups = [(sum(self.to_screen(p.x, p.y)[0] for p in m) / len(m),
                       sum(self.to_screen(p.x, p.y)[1] for p in m) / len(m), m) for _x, _y, m in merged]
        return [g for cx, cy, members in groups for g in self._spread(members, cx, cy)]

    def _touching(self, items: list[tuple[Poi, tuple[float, float]]]) -> list[tuple[float, float, list[Poi]]]:
        """Groups of (point, screen spot) whose icons would touch (chains included), with each group's centre."""
        step = self._icon_size("teleport") + 4
        points = [p for p, _spot in items]
        screen = [spot for _p, spot in items]
        parent = list(range(len(points)))

        def root(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        order = sorted(range(len(points)), key=lambda i: screen[i][0])
        for a, i in enumerate(order):  # sweep along x: only neighbours closer than step can touch
            for j in order[a + 1:]:
                if screen[j][0] - screen[i][0] >= step:
                    break
                if abs(screen[j][1] - screen[i][1]) < step:
                    parent[root(j)] = root(i)
        groups: dict[int, list[int]] = {}
        for i in range(len(points)):
            groups.setdefault(root(i), []).append(i)
        return [(sum(screen[i][0] for i in idx) / len(idx), sum(screen[i][1] for i in idx) / len(idx),
                 [points[i] for i in idx]) for idx in groups.values()]

    def _spread(self, members: list[Poi], cx: float, cy: float) -> list[tuple[float, float, list[Poi]]]:
        """One group -> single icons in rows around (cx, cy), spaced by the biggest icon among them."""
        if len(members) == 1:
            return [(cx, cy, members)]
        ordered = sorted(members, key=lambda p: (p.type not in BIG_TYPES, p.type, p.name))
        step = max(self._icon_size(p.type) for p in ordered) + 4
        rows = [ordered[i:i + SPLIT_ROW] for i in range(0, len(ordered), SPLIT_ROW)]
        out = []
        for r, row in enumerate(rows):
            y = cy + (r - (len(rows) - 1) / 2) * step
            for c, p in enumerate(row):
                out.append((cx + (c - (len(row) - 1) / 2) * step, y, [p]))
        return out

    def _on_poi_enter(self, event: tk.Event) -> None:
        current = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(current[0]) if current else ()
        index = next((int(t[4:]) for t in tags if t.startswith("poi_")), None)
        if index is None or index >= len(self._drawn):
            return
        _sx, _sy, members = self._drawn[index]
        first = members[0]
        kind = self.poi.type_name(first.type)
        if len(members) > 1:
            by_type: dict[str, int] = {}
            for m in members:
                by_type[m.type] = by_type.get(m.type, 0) + 1
            text = "\n".join(f"{self.poi.type_name(t)}: {n}" for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]))
        else:
            text = f"{first.name} · {kind}" if first.name else kind
        self._bubble(event.x + 14, event.y - 10, text)

    def _bubble(self, x: float, y: float, text: str) -> None:
        self.canvas.delete("bubble")
        item = self.canvas.create_text(x + 8, y, text=text, anchor="w", fill=theme.TEXT, width=420,
                                       font=theme.font("caption"), tags="bubble")
        x0, y0, x1, y1 = self.canvas.bbox(item)
        self.canvas.create_rectangle(x0 - 8, y0 - 5, x1 + 8, y1 + 5, fill=theme.SURFACE_2, outline=theme.BORDER,
                                     tags="bubble")
        self.canvas.tag_raise(item)

    def _on_pin_enter(self, event: tk.Event) -> None:
        current = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(current[0]) if current else ()
        index = next((int(t[6:]) for t in tags if t.startswith("other_")), None)
        if index is None or index >= len(self.others):
            return
        note = self.others[index].note or self.others[index].label
        x, y = event.x + 14, event.y - 10
        text = self.canvas.create_text(x + 8, y, text=note, anchor="w", fill=theme.TEXT, width=420,
                                       font=theme.font("caption"), tags="bubble")
        x0, y0, x1, y1 = self.canvas.bbox(text)
        self.canvas.create_rectangle(x0 - 8, y0 - 5, x1 + 8, y1 + 5, fill=theme.SURFACE_2, outline=theme.BORDER,
                                     tags="bubble")
        self.canvas.tag_raise(text)

    # --- events --------------------------------------------------------------------------
    def _on_resize(self) -> None:
        """Window size changes come in dozens per second while dragging a window edge. The picture is redrawn
        once, after the size settles, instead of on every step (that was 2-3 fps)."""
        if self.zone is not None:
            self.zoom = max(self.zoom, self._fit_zoom())
            self._clamp()
        self._schedule_resize()

    def _schedule_resize(self) -> None:
        if self._resize_after is not None:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(RESIZE_SETTLE_MS, self._resize_settled)

    def _resize_settled(self) -> None:
        self._resize_after = None
        self._apply_mob_panel_width()
        if self.zone is not None:
            self.zoom = max(self.zoom, self._fit_zoom())
            self._clamp()
            self.render()

    def _on_wheel(self, event: tk.Event) -> None:
        self.zoom_at(ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP, event.x, event.y)

    def game_at(self, screen_x: float, screen_y: float) -> tuple[float, float] | None:
        """Game coordinates under a canvas point (inverse of Zone.to_image)."""
        if self.zone is None or not self.zone.kx[0] or not self.zone.ky[0]:
            return None
        image_x = self.left + screen_x / self.zoom
        image_y = self.top + screen_y / self.zoom
        return (image_y - self.zone.ky[1]) / self.zone.ky[0], (image_x - self.zone.kx[1]) / self.zone.kx[0]

    def _on_motion(self, event: tk.Event) -> None:
        game = self.game_at(event.x, event.y)
        self.coords_var.set(f"x {game[0]:.0f} · y {game[1]:.0f}" if game else "")

    def _on_press(self, event: tk.Event) -> None:
        self._cancel_fly()  # the user takes the map: the flight's remaining frames must not pull it back (ui:30)
        self._cancel_zoom()
        self._drag = (event.x, event.y, self.left, self.top)
        self.canvas.configure(cursor="fleur")

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag is None:
            return
        x, y, left, top = self._drag
        self.left = left - (event.x - x) / self.zoom
        self.top = top - (event.y - y) / self.zoom
        self._clamp()
        self._schedule_render()

    def _zoom_center(self, factor: float) -> None:
        width, height = self._canvas_size()
        self.zoom_at(factor, width / 2, height / 2)

    def _fit(self) -> None:
        self._cancel_fly()
        self._cancel_zoom()
        self.zoom = self._fit_zoom()
        self._clamp()
        self.render()

    def _back_to_place(self) -> None:
        if self.place is not None and self.zone is not None:
            self.fly_to(*self.zone.to_image(self.place.x, self.place.y))
