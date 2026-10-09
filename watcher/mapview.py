"""Zone map window: opens on a click at a place link (<Место · Келькмарос>) in the chat.

Like the game map: the mouse wheel zooms to the point under the cursor, dragging moves the map,
a double click zooms in. The clicked place is a big orange pin; other places linked in the chat
for the same zone are small pins with «nick: message» on hover.

Maps and the game -> image transform come from data/maps (tools/fetch_maps.py):
    image_x = x[0] * game_y + x[1],   image_y = y[0] * game_x + y[1]
"""

import json
import tkinter as tk
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from watcher import theme

MIN_ZOOM_STEPS = 0  # zoom = fit * 1.25 ** steps
MAX_ZOOM = 4.0  # screen px per map px
ZOOM_STEP = 1.25
PIN = theme.ACCENT
OTHER_PIN = "#4fd1c5"
BG_RGB = tuple(int(theme.BG[i : i + 2], 16) for i in (1, 3, 5))


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

    def to_image(self, x: float, y: float) -> tuple[float, float]:
        return self.kx[0] * y + self.kx[1], self.ky[0] * x + self.ky[1]


def load_zones(maps_dir: Path, names: dict[str, str]) -> dict[str, Zone]:
    """data/maps/maps.json -> {map id: Zone}. Missing or broken data gives {}."""
    try:
        index = json.loads((Path(maps_dir) / "maps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    zones = {}
    for map_id, info in index.items():
        path = Path(maps_dir) / info["file"]
        if path.is_file():
            zones[map_id] = Zone(
                map_id, names.get(map_id, map_id), path, int(info["size"]), tuple(info["x"]), tuple(info["y"])
            )
    return zones


class MapWindow:
    """One reusable window; show() switches zone and centres on a place."""

    def __init__(self, root: tk.Misc, zones: dict[str, Zone]) -> None:
        self.root = root
        self.zones = zones
        self.window: tk.Toplevel | None = None
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

    def has_map(self, map_id: str) -> bool:
        return map_id in self.zones

    def show(self, place: Place, others: Iterable[Place] = ()) -> None:
        self._ensure_window()
        zone = self.zones.get(place.map_id)
        self.place = place
        self.others = [p for p in others if p.map_id == place.map_id and p != place]
        if zone is None:
            self._set_zone(None)
            self.title.configure(text=f"{place.label}  ·  карты этой зоны нет")
            return
        if zone is not self.zone:
            self._set_zone(zone)
        self.title.configure(text=place.label)
        self.window.deiconify()
        self.window.lift()
        self.window.update_idletasks()
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

    def close(self) -> None:
        if self.window is not None:
            self.window.destroy()
        self.window = None
        self.zone = None
        self._image = self._photo = None

    # --- window ----------------------------------------------------------------------
    def _ensure_window(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            return
        win = tk.Toplevel(self.root, background=theme.BG)
        win.title("Карта")
        win.geometry("980x980")
        win.minsize(420, 420)
        win.protocol("WM_DELETE_WINDOW", self.close)
        theme.dark_title_bar(win)
        bar = ttk.Frame(win, padding=(12, 8))
        bar.pack(fill="x")
        self.title = ttk.Label(bar, text="", style="Title.TLabel")
        self.title.pack(side="left")
        for text, command in (
            ("⌂", self._fit),
            ("−", lambda: self._zoom_center(1 / ZOOM_STEP)),
            ("+", lambda: self._zoom_center(ZOOM_STEP)),
            ("◎", self._back_to_place),
        ):
            ttk.Button(bar, text=text, width=3, command=command).pack(side="right", padx=(6, 0))
        self.hint = ttk.Label(bar, text="колесо — масштаб, перетаскивание — сдвиг", style="Muted.TLabel")
        self.hint.pack(side="right", padx=12)
        self.canvas = tk.Canvas(win, background=theme.BG, highlightthickness=0, borderwidth=0, cursor="fleur")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._on_resize())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_drag", None))
        self.canvas.bind("<Double-Button-1>", lambda e: self.zoom_at(2.0, e.x, e.y))
        self.canvas.tag_bind("other", "<Enter>", self._on_pin_enter)
        self.canvas.tag_bind("other", "<Leave>", lambda _e: self.canvas.delete("bubble"))
        self.window = win

    def _set_zone(self, zone: Zone | None) -> None:
        from PIL import Image

        self.zone = zone
        self._image = None
        if zone is not None:
            with Image.open(zone.path) as image:
                self._image = image.convert("RGB")
            self.window.title(f"Карта · {zone.name}")
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
        if self._render_after is None and self.window is not None:
            self._render_after = self.window.after_idle(self.render)

    def render(self) -> None:
        from PIL import Image, ImageTk

        self._render_after = None
        if self.window is None or self.zone is None or self._image is None:
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
