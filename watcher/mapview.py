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
from watcher.maplayers import LayerPanel, default_layers, load_icon
from watcher.poi import Poi, PoiStore, cluster

MIN_ZOOM_STEPS = 0  # zoom = fit * 1.25 ** steps
MAX_ZOOM = 4.0  # screen px per map px
ZOOM_STEP = 1.25
DENSE_GROUPS = {"gather", "quest"}
DENSE_SPLIT_ZOOM = 1.0  # below this zoom, gathering / quest points of all kinds merge into one cluster
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

    def to_image(self, x: float, y: float) -> tuple[float, float]:
        return self.kx[0] * y + self.kx[1], self.ky[0] * x + self.ky[1]


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
        layers: Iterable[str] | None = None,
        on_layers: Callable[[set[str]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.zones = zones
        self.poi = poi or PoiStore({}, {})
        self.icons_dir = icons_dir or Path(".")
        self.on_layers = on_layers or (lambda _l: None)
        self._poi_icons: dict[tuple[str, int], object] = {}
        self._drawn: list[tuple[float, float, list[Poi]]] = []
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
        self.title = ttk.Label(bar, text="", style="Title.TLabel")
        self.title.pack(side="left", padx=(14, 0))
        for text, command in (
            ("⌂", self._fit),
            ("−", lambda: self._zoom_center(1 / ZOOM_STEP)),
            ("+", lambda: self._zoom_center(ZOOM_STEP)),
            ("◎", self._back_to_place),
        ):
            ttk.Button(bar, text=text, width=3, command=command).pack(side="right", padx=(6, 0))
        self.hint = ttk.Label(bar, text="колесо — масштаб, перетаскивание — сдвиг, точки — места из чата",
                              style="Muted.TLabel")
        self.hint.pack(side="right", padx=12)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        start = default_layers(self.poi) if layers is None else set(layers)
        self.panel = LayerPanel(body, self.poi, self.icons_dir, start, self._on_layers)
        if self.poi.types:
            self.panel.pack(side="left", fill="y", padx=(0, 10))
        self.layers: set[str] = set(self.panel.layers)
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
        self.panel.set_zone(zone.map_id)
        with Image.open(zone.path) as image:
            self._image = image.convert("RGB")
        self.zone_var.set(zone.name)
        self.zoom = self._fit_zoom()
        self.canvas.delete("all")

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
        # keep the map on screen; centre it when it is smaller than the window
        self.left = (size - view_w) / 2 if view_w >= size else min(max(self.left, 0), size - view_w)
        self.top = (size - view_h) / 2 if view_h >= size else min(max(self.top, 0), size - view_h)

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
            sx, sy = self.to_screen(self.selected.x, self.selected.y)
            canvas.create_oval(sx - 17, sy - 17, sx + 17, sy + 17, outline=PIN, width=3, tags="selected")
        for index, other in enumerate(self.others):
            sx, sy = self.to_screen(*self.zone.to_image(other.x, other.y))
            canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=OTHER_PIN, outline="#0b2b28", width=2,
                               tags=("other", f"other_{index}"))
        if self.place is not None:
            sx, sy = self.to_screen(*self.zone.to_image(self.place.x, self.place.y))
            canvas.create_oval(sx - 13, sy - 13, sx + 13, sy + 13, outline=PIN, width=3, tags="pin")
            canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=PIN, outline="", tags="pin")
            canvas.create_text(sx + 18, sy - 2, text=self.place.label, anchor="w", fill="#ffffff",
                               font=(theme.FONT_FAMILY, theme.FONT_SIZE, "bold"), tags="pin")

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
        self.point_card.show(kind, poi.name or kind, poi.gx, poi.gy, "", self.nearby(poi.zone, poi.gx, poi.gy, poi))
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

    def _on_layers(self, layers: set[str]) -> None:
        self.layers = layers
        self.on_layers(layers)
        self.canvas.delete("bubble")
        self._schedule_render()

    def _poi_icon(self, type_: str, size: int):
        key = (type_, size)
        if key not in self._poi_icons:
            icon = self.poi.types.get(type_, {}).get("icon")
            self._poi_icons[key] = load_icon(self.icons_dir / icon, size, self.canvas) if icon else None
        return self._poi_icons[key]

    def _draw_poi(self, width: int, height: int) -> None:
        """Layer points as their icons; close points of one type merge into an icon with a count."""
        self._drawn = []
        if self.zone is None or not self.layers:
            return
        size = max(18, min(30, round(14 + 6 * self.zoom)))
        points = self.poi.in_zone(self.zone.map_id, self.layers)
        # dense layers (gathering, quests) merge across their kinds until the map is zoomed in
        dense = self.zoom < DENSE_SPLIT_ZOOM
        group_of = {t: info.get("group", "") for t, info in self.poi.types.items()}

        def key(p: Poi) -> str:
            group = group_of.get(p.type, "")
            return group if dense and group in DENSE_GROUPS else p.type

        groups = cluster(points, self.to_screen, radius_px=size * (2.2 if dense else 1.3), key=key)
        canvas = self.canvas
        for index, (sx, sy, members) in enumerate(groups):
            if not (-size < sx < width + size and -size < sy < height + size):
                continue
            tags = ("poi", f"poi_{len(self._drawn)}")
            self._drawn.append((sx, sy, members))
            kinds = {m.type for m in members}
            icon = self._poi_icon(max(kinds, key=lambda t: sum(m.type == t for m in members)), size)
            if icon is not None:
                canvas.create_image(sx, sy, image=icon, tags=tags)
            else:
                canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=theme.ACCENT, outline="#0d0e11", tags=tags)
            if len(members) > 1:
                bx, by = sx + size * 0.45, sy - size * 0.45
                canvas.create_oval(bx - 9, by - 9, bx + 9, by + 9, fill="#0d0e11", outline=theme.ACCENT, tags=tags)
                canvas.create_text(bx, by, text=str(len(members)) if len(members) < 100 else "99+",
                                   fill="#ffffff", font=(theme.FONT_FAMILY, 8, "bold"), tags=tags)

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
