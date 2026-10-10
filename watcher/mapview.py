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
import tkinter as tk
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from watcher import theme
from watcher.mapcard import NEARBY_TYPES, PointCard
from watcher.matcher import normalize
from watcher.poi import Poi, PoiStore, cluster

MIN_ZOOM_STEPS = 0  # zoom = fit * 1.25 ** steps
MAX_ZOOM = 4.0  # screen px per map px
ZOOM_STEP = 1.25
# The fixed set of points on the map (no layer panel). Gathering and quest points are not shown; portals are the
# map themes: the game map (newmap) or the client's radar map («Рельеф»), the choice is kept in config.json
THEMES = {"game": "Игра", "relief": "Рельеф"}

# Silentera Tunnel entrances only (tools/build_poi.py).
SHOWN_TYPES = ("teleport", "bindstone", "warehouse", "merchant", "coin_merchant", "vendor", "stigma", "postbox",
               "fortress", "artifact", "dungeon", "portal")
QUEST_TYPES = ("quest_give", "quest_important", "quest_event")  # NPCs with quests; a check box shows / hides them
BIG_TYPES = {"teleport", "bindstone"}  # drawn larger than the rest
SPLIT_ZOOM = MAX_ZOOM / ZOOM_STEP * 0.999  # the last two zoom levels: no count badges, every point its own icon
SPLIT_ROW = 4  # icons per row when a group is laid out side by side
SEARCH_PLACEHOLDER = "Найти: NPC, район"
LABELS_MIN_WIDTH = 1300  # px the zone must take on screen before area names are drawn
PIN = theme.ACCENT
OTHER_PIN = "#4fd1c5"
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
    labels: tuple[tuple[float, float, str], ...] = ()  # area names: (image x, image y, text)
    relief: Path | None = None  # the «Рельеф» theme: the radar map cut to the same frame (tools/build_relief.py)

    def to_image(self, x: float, y: float) -> tuple[float, float]:
        return self.kx[0] * y + self.kx[1], self.ky[0] * x + self.ky[1]


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
            size = int(info["size"])
            view_box, rows = labels.get(path.stem, (size, []))
            k = size / view_box
            zones[map_id] = Zone(
                map_id, names.get(map_id, map_id), path, size, tuple(info["x"]), tuple(info["y"]),
                tuple((x * k, y * k, text) for x, y, text in rows),
                relief if (relief := Path(maps_dir) / "relief" / path.name).is_file() else None,
            )
    return zones


def load_labels(path: Path) -> dict[str, tuple[float, list[tuple[float, float, str]]]]:
    """labels.tsv -> {zone code: (viewBox size, [(x, y, text), ...])}; «|» in a name is a line break."""
    zones: dict[str, tuple[float, list]] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        try:
            if line.startswith("@"):
                zones[parts[0][1:]] = (float(parts[1]), [])
            elif parts[0] in zones and len(parts) == 4:
                zones[parts[0]][1].append((float(parts[1]), float(parts[2]), parts[3].replace("|", "\n")))
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
    ) -> None:
        super().__init__(parent)
        self.zones = zones
        self.poi = (poi or PoiStore({}, {})).projected({map_id: z.to_image for map_id, z in zones.items()})
        self.icons_dir = icons_dir or Path(".")
        self.on_show_quests = on_show_quests or (lambda _on: None)
        self.theme = map_theme if map_theme in THEMES else "game"
        self.on_theme = on_theme or (lambda _theme: None)
        self.layers: set[str] = set()
        self._set_layers(show_quests)
        self._poi_icons: dict[tuple[str, int], object] = {}
        self._drawn: list[tuple[float, float, list[Poi]]] = []
        self._spots: dict[Poi, tuple[float, float]] = {}  # where each single point's icon was drawn
        self.get_places = get_places  # place links seen in the chat (pins)
        self.zone: Zone | None = None
        self.place: Place | None = None
        self.others: list[Place] = []
        self.zoom = 1.0  # screen px per map image px
        self.left = 0.0  # map image px at the canvas's left / top edge
        self.top = 0.0
        self._image = None  # PIL image of the zone
        self._photo = None
        self._render_after: str | None = None
        self._drag: tuple[int, int, float, float] | None = None
        self._by_name = {zone.name: map_id for map_id, zone in sorted(zones.items(), key=lambda kv: kv[1].name)}

        bar = ttk.Frame(self, padding=(0, 0, 0, 8))
        bar.pack(fill="x")
        self.zone_var = tk.StringVar()
        self.zone_box = ttk.Combobox(bar, textvariable=self.zone_var, values=list(self._by_name), state="readonly",
                                     width=20)
        self.zone_box.pack(side="left")
        self.zone_box.bind("<<ComboboxSelected>>", lambda _e: self.open_zone(self._by_name[self.zone_var.get()]))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, style="Card.TEntry", width=26)
        self.search_entry.pack(side="left", padx=(10, 0))
        self.search_count = ttk.Label(bar, text="", style="Muted.TLabel", width=6, anchor="w")
        self.search_count.pack(side="left", padx=(6, 0))
        self._show_placeholder()
        self.search_entry.bind("<FocusIn>", lambda _e: self._hide_placeholder())
        self.search_entry.bind("<FocusOut>", lambda _e: self._show_placeholder())
        self.search_entry.bind("<Return>", lambda _e: self._search(1))
        self.search_entry.bind("<Shift-Return>", lambda _e: self._search(-1))
        self.search_entry.bind("<Escape>", lambda _e: self.search_var.set(""))
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.quests_var = tk.BooleanVar(value=show_quests)
        if any(t in self.poi.types for t in QUEST_TYPES):
            ttk.Checkbutton(bar, text=" Задания", variable=self.quests_var, style="Plain.TCheckbutton",
                            command=self._on_quests_toggled).pack(side="left", padx=(12, 0))
        self.theme_var = tk.StringVar(value=THEMES[self.theme])
        if any(z.relief is not None for z in zones.values()):
            self.theme_box = ttk.Combobox(bar, textvariable=self.theme_var, values=list(THEMES.values()),
                                          state="readonly", width=8)
            self.theme_box.pack(side="left", padx=(12, 0))
            self.theme_box.bind("<<ComboboxSelected>>", lambda _e: self._on_theme_selected())
        self.title = ttk.Label(bar, text="", style="Title.TLabel")
        self.title.pack(side="left", padx=(14, 0))
        for text, command in (
            ("⌂", self._fit),
            ("−", lambda: self._zoom_center(1 / ZOOM_STEP)),
            ("+", lambda: self._zoom_center(ZOOM_STEP)),
            ("◎", self._back_to_place),
        ):
            ttk.Button(bar, text=text, width=3, command=command).pack(side="right", padx=(6, 0))
        self.hint = ttk.Label(bar, text="колесо — масштаб · тяни — сдвиг · клик — карточка", style="Muted.TLabel")
        self.hint.pack(side="right", padx=12)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self._matches: list = []
        self._match_index = -1
        self._match_query = ""
        self.selected: Poi | None = None
        self.point_card = PointCard(body, get_icon=lambda t: self._poi_icon(t, 20))
        self.point_card.pack(side="right", fill="y", padx=(10, 0))
        card = ttk.Frame(body, style="Card.TFrame", padding=6)
        card.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(card, background=theme.SURFACE, highlightthickness=0, borderwidth=0, cursor="fleur")
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
                 font=(theme.FONT_FAMILY, theme.FONT_SIZE - 3)).place(relx=0, rely=1, x=10, y=-8, anchor="sw")
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
            self._refresh_pins()
            self.render()

    def open_zone(self, map_id: str) -> None:
        """Browse a zone: the whole map, pins of the chat's places, no selected place."""
        zone = self.zones.get(map_id)
        if zone is None:
            return
        self.place = None
        self.selected = None
        self.point_card.clear()
        self._set_zone(zone)
        self.title.configure(text="")
        self._refresh_pins()
        self.update_idletasks()
        self._fit()

    def show(self, place: Place, others: Iterable[Place] | None = None) -> None:
        zone = self.zones.get(place.map_id)
        self.place = place
        if zone is None:
            self.title.configure(text=f"{place.label}  ·  карты этой зоны нет")
            return
        if zone is not self.zone:
            self._set_zone(zone)
        self._refresh_pins(others)
        self.title.configure(text=place.label)
        self.selected = None
        self.point_card.show(
            "Место из чата", place.label, place.x, place.y, place.note, self.nearby(zone.map_id, place.x, place.y)
        )
        self.update_idletasks()
        if self.zoom < self._fit_zoom() * 2:
            self.zoom = min(MAX_ZOOM, self._fit_zoom() * 2)
        self.center_on(*zone.to_image(place.x, place.y))

    def center_on(self, image_x: float, image_y: float) -> None:
        width, height = self._canvas_size()
        self.left = image_x - width / 2 / self.zoom
        self.top = image_y - height / 2 / self.zoom
        self._clamp()
        self.render()

    def zoom_at(self, factor: float, screen_x: float, screen_y: float) -> None:
        """Zoom keeping the map point under (screen_x, screen_y) in place."""
        new = max(self._fit_zoom(), min(MAX_ZOOM, self.zoom * factor))
        image_x = self.left + screen_x / self.zoom
        image_y = self.top + screen_y / self.zoom
        self.zoom = new
        self.left = image_x - screen_x / new
        self.top = image_y - screen_y / new
        self._clamp()
        self._schedule_render()

    def _refresh_pins(self, others: Iterable[Place] | None = None) -> None:
        places = self.get_places() if others is None else others
        map_id = self.zone.map_id if self.zone is not None else None
        self.others = [p for p in places if p.map_id == map_id and p != self.place]

    def _set_zone(self, zone: Zone) -> None:
        from PIL import Image

        self.zone = zone
        self._load_image()
        self.zone_var.set(zone.name)
        self.zoom = self._fit_zoom()
        self.canvas.delete("all")

    def _load_image(self) -> None:
        from PIL import Image

        path = self.zone.relief if self.theme == "relief" and self.zone.relief is not None else self.zone.path
        with Image.open(path) as image:
            self._image = image.convert("RGB")

    def _on_theme_selected(self) -> None:
        """«Игра» / «Рельеф»: both pictures share the frame, so the view and the points stay where they are."""
        self.theme = next(key for key, name in THEMES.items() if name == self.theme_var.get())
        self.on_theme(self.theme)
        if self.zone is not None:
            self._load_image()
            self.render()

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
            resample = Image.BILINEAR if self.zoom >= 1 else Image.LANCZOS
            part = self._image.resize((part_w, part_h), resample, box=(x0, y0, x1, y1))
            view.paste(part, (round((x0 - self.left) * self.zoom), round((y0 - self.top) * self.zoom)))
        self._photo = ImageTk.PhotoImage(view, master=self.canvas)
        canvas = self.canvas
        canvas.delete("all")
        canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self._draw_labels(width, height)
        self._draw_poi(width, height)
        if self.selected is not None and self.selected.zone == self.zone.map_id:
            sx, sy = self._spots.get(self.selected) or self.to_screen(self.selected.x, self.selected.y)
            canvas.create_oval(sx - 17, sy - 17, sx + 17, sy + 17, outline=PIN, width=3, tags="selected")
        for index, other in enumerate(self.others):
            sx, sy = self.to_screen(*self.zone.to_image(other.x, other.y))
            canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=OTHER_PIN, outline="#0b2b28", width=2,
                               tags=("other", f"other_{index}"))
        if self.place is not None:
            sx, sy = self.to_screen(*self.zone.to_image(self.place.x, self.place.y))
            canvas.create_oval(sx - 13, sy - 13, sx + 13, sy + 13, outline=PIN, width=3, tags="pin")
            canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=PIN, outline="", tags="pin")
            font = (theme.FONT_FAMILY, theme.FONT_SIZE, "bold")
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):  # dark outline, like the area names
                canvas.create_text(sx + 18 + dx, sy - 2 + dy, text=self.place.label, anchor="w", fill="#0d0e11",
                                   font=font, tags="pin")
            canvas.create_text(sx + 18, sy - 2, text=self.place.label, anchor="w", fill="#ffffff", font=font,
                               tags="pin")

    def _draw_labels(self, width: int, height: int) -> None:
        """Area names, like the game map: white text with a dark outline; size follows the zoom.

        Hidden while the whole zone is small on screen — they would cover each other.
        """
        if self.zoom * self.zone.size < LABELS_MIN_WIDTH:
            return
        size = max(8, min(15, round(5 + 4 * self.zoom)))
        font = (theme.FONT_FAMILY, size, "bold")
        for image_x, image_y, text in self.zone.labels:
            sx, sy = self.to_screen(image_x, image_y)
            if -200 < sx < width + 200 and -60 < sy < height + 60:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
                    self.canvas.create_text(sx + dx, sy + dy, text=text, fill="#0d0e11", font=font,
                                            justify="center", tags="label")
                self.canvas.create_text(sx, sy, text=text, fill="#f2e6c9", font=font, justify="center", tags="label")

    # --- selection and «Рядом» ------------------------------------------------------------
    def nearby(self, zone: str, gx: float, gy: float, exclude: Poi | None = None):
        """Closest teleporter, warehouse, merchant, … around a game position, for the card."""
        out = []
        for type_ in NEARBY_TYPES:
            candidates = [p for p in self.poi.in_zone(zone, {type_}) if p != exclude]
            if not candidates:
                continue
            best = min(candidates, key=lambda p: math.hypot(p.gx - gx, p.gy - gy))
            metres = math.hypot(best.gx - gx, best.gy - gy)
            out.append((type_, self.poi.type_name(type_), best.name, metres, lambda p=best: self.select(p, centre=True)))
        return out

    def select(self, poi: Poi, centre: bool = False) -> None:
        """Show a point in the card (and ring it on the map)."""
        self.selected = poi
        kind = self.poi.type_name(poi.type)
        self.point_card.show(kind, poi.name or kind, poi.gx, poi.gy, poi.note, self.nearby(poi.zone, poi.gx, poi.gy, poi))
        if centre:
            self.center_on(poi.x, poi.y)
        else:
            self._schedule_render()

    def _on_release(self, event: tk.Event) -> None:
        start = self._drag
        self._drag = None
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
                self.point_card.show("Место из чата", place.label, place.x, place.y, place.note,
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
            points = self.poi.search(self.zone.map_id, query, self.layers)
            areas = [(x, y, text) for x, y, text in self.zone.labels if all(w in normalize(text) for w in words)]
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
            self.center_on(x, y)
        return f"{self._match_index + 1} / {len(self._matches)}"

    def _set_layers(self, show_quests: bool) -> None:
        shown = SHOWN_TYPES + (QUEST_TYPES if show_quests else ())
        self.layers = {t for t in shown if t in self.poi.types}

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
        self.search_count.configure(text=self.search(query, step) if query else "")
        return "break"

    def _on_search_key(self, event: tk.Event) -> None:
        if event.keysym not in ("Return", "Escape", "Shift_L", "Shift_R"):
            self._search(0)

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
        return size + 8 if type_ in BIG_TYPES else size

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
        if self.zone is None or not self.layers:
            return
        points = self.poi.in_zone(self.zone.map_id, self.layers)
        if self.zoom >= SPLIT_ZOOM:
            groups = self._split(points)
        else:
            groups = cluster(points, self.to_screen, radius_px=self._icon_size("") * 1.1, key=lambda p: p.type)
        # teleporters and kisks on top of the rest
        groups.sort(key=lambda g: g[2][0].type in BIG_TYPES)
        canvas = self.canvas
        for sx, sy, members in groups:
            if len(members) == 1:
                self._spots[members[0]] = (sx, sy)
            size = self._icon_size(members[0].type)
            if not (-size < sx < width + size and -size < sy < height + size):
                continue
            tags = ("poi", f"poi_{len(self._drawn)}")
            self._drawn.append((sx, sy, members))
            icon = self._poi_icon(members[0].type, size)
            if icon is not None:
                canvas.create_image(sx, sy, image=icon, tags=tags)
            else:
                canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=theme.ACCENT, outline="#0d0e11", tags=tags)
            if len(members) > 1:
                bx, by = sx + size * 0.45, sy - size * 0.45
                canvas.create_oval(bx - 9, by - 9, bx + 9, by + 9, fill="#0d0e11", outline=theme.ACCENT, tags=tags)
                canvas.create_text(bx, by, text=str(len(members)) if len(members) < 100 else "99+",
                                   fill="#ffffff", font=(theme.FONT_FAMILY, 8, "bold"), tags=tags)

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
                                       font=(theme.FONT_FAMILY, theme.FONT_SIZE - 1), tags="bubble")
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
                                       font=(theme.FONT_FAMILY, theme.FONT_SIZE - 1), tags="bubble")
        x0, y0, x1, y1 = self.canvas.bbox(text)
        self.canvas.create_rectangle(x0 - 8, y0 - 5, x1 + 8, y1 + 5, fill=theme.SURFACE_2, outline=theme.BORDER,
                                     tags="bubble")
        self.canvas.tag_raise(text)

    # --- events --------------------------------------------------------------------------
    def _on_resize(self) -> None:
        if self.zone is not None:
            self.zoom = max(self.zoom, self._fit_zoom())
            self._clamp()
            self._schedule_render()

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
        self._drag = (event.x, event.y, self.left, self.top)

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
        self.zoom = self._fit_zoom()
        self._clamp()
        self.render()

    def _back_to_place(self) -> None:
        if self.place is not None and self.zone is not None:
            self.center_on(*self.zone.to_image(self.place.x, self.place.y))
