"""SN-2/3: focus-safe toast cards driven by NotificationCenter on the Tk thread."""
from __future__ import annotations

import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageTk

from watcher import theme
from watcher.catalog import resource_root
from core.notify.notify_center import Notification, NotificationCenter
from watcher.toast_native import WindowsDesktop, WorkArea

KINDS = {"match": "chat", "warn": "warning", "game": "warning", "boss": "siege"}


def nine_slice(source: Image.Image, size: tuple[int, int], scale: float) -> Image.Image:
    """Resize only the middle/edges of the client's v4_tooltip frame."""
    width, height = size
    result = Image.new("RGBA", size, theme.BG)
    xs, ys = [0, 18, source.width - 26, source.width], [0, 20, source.height - 22, source.height]
    dx = [0, round(9 * scale), width - round(13 * scale), width]
    dy = [0, round(10 * scale), height - round(11 * scale), height]
    for row in range(3):
        for col in range(3):
            tile = source.crop((xs[col], ys[row], xs[col + 1], ys[row + 1]))
            tile = tile.resize((max(1, dx[col + 1] - dx[col]), max(1, dy[row + 1] - dy[row])), Image.Resampling.LANCZOS)
            result.alpha_composite(tile, (dx[col], dy[row]))
    return result


class ToastAssets:
    def __init__(self, folder: Path | None = None) -> None:
        folder = folder or resource_root() / "data/ui/toasts"
        with Image.open(folder / "frame@2x.png") as image:
            self.frame = image.convert("RGBA")
        self.icons = {}
        for kind in ("chat", "event", "reset", "siege", "warning"):
            with Image.open(folder / f"{kind}@2x.png") as image:
                self.icons[kind] = image.convert("RGBA")


class ToastCard:
    def __init__(self, manager: ToastManager, event: Notification, area: WorkArea) -> None:
        self.manager, self.event = manager, event
        self.window = tk.Toplevel(manager.root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.0)
        self.canvas = tk.Canvas(self.window, highlightthickness=0, bd=0, background=theme.BG, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._click)
        self.native = None
        self.remaining = manager.duration
        self.born = manager.clock()
        self.x = self.y = 0
        self.redraw(area)
        self.window.update_idletasks()
        if manager.desktop:
            self.native = manager.desktop.attach(self.window)
        self.window.deiconify()

    def redraw(self, area: WorkArea) -> None:
        self.scale = scale = area.scale
        p = lambda value: round(value * scale)
        self.width = min(p(380), area.right - area.left - p(24))
        c = self.canvas
        c.delete("all")
        family, _, _ = theme.font("control")
        title_font = (family, -p(15), "bold")
        body_font = (family, -p(13))
        button_font = (family, -p(12))
        left, right = p(64), self.width - p(38)
        text_width = max(1, right - left)
        title = self._text(left, p(17), self.event.title, text_width, title_font, theme.TEXT, 2)
        body_y = c.bbox(title)[3] + p(7)
        body = self._text(left, body_y, self.event.text, text_width, body_font, theme.TEXT, 4)
        bottom = max(p(65), c.bbox(body)[3])
        self.action_boxes = []
        x, y = left, bottom + p(12)
        font = tkfont.Font(master=self.window, font=button_font)
        for action in self.event.actions:
            label = action.label
            while font.measure(label) > self.width - left - p(44) and len(label) > 1:
                label = label[:-2] + "…"
            w = font.measure(label) + p(20)
            if x + w > self.width - p(20) and x != left:
                x, y = left, y + p(32)
            box = (x, y, x + w, y + p(26))
            c.create_rectangle(*box, fill=theme.SURFACE, outline=theme.BORDER)
            c.create_text(x + w // 2, y + p(13), text=label, font=button_font, fill=theme.TEXT)
            self.action_boxes.append((box, action.id))
            x += w + p(7)
        if self.action_boxes:
            bottom = y + p(26)
        self.height = bottom + p(24)
        background = nine_slice(self.manager.assets.frame, (self.width, self.height), scale)
        self.background = ImageTk.PhotoImage(background, master=self.window)
        bg_id = c.create_image(0, 0, image=self.background, anchor="nw")
        c.tag_lower(bg_id)
        kind = KINDS.get(self.event.kind, self.event.kind)
        icon = self.manager.assets.icons.get(kind, self.manager.assets.icons["event"])
        self.icon = ImageTk.PhotoImage(icon.resize((p(36), p(36)), Image.Resampling.LANCZOS), master=self.window)
        c.create_image(p(17), p(18), image=self.icon, anchor="nw")
        self.close_box = (self.width - p(36), p(8), self.width - p(8), p(36))
        c.create_text(self.width - p(22), p(21), text="×", fill=theme.MUTED, font=(family, -p(21)))
        self.life = c.create_rectangle(p(15), self.height - p(10), self.width - p(15), self.height - p(8), fill=theme.ACCENT, outline="")
        c.configure(width=self.width, height=self.height)
        self.window.geometry(f"{self.width}x{self.height}")
        self.window.update_idletasks()

    def _text(self, x, y, text, width, font, color, lines):
        c = self.canvas
        item = c.create_text(x, y, text=text or " ", width=width, anchor="nw", font=font, fill=color)
        max_height = tkfont.Font(master=self.window, font=font).metrics("linespace") * lines + 2
        if c.bbox(item)[3] - y > max_height:
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                c.itemconfigure(item, text=text[:mid].rstrip() + "…")
                if c.bbox(item)[3] - y <= max_height:
                    lo = mid
                else:
                    hi = mid - 1
            c.itemconfigure(item, text=text[:lo].rstrip() + "…")
        return item

    def _click(self, event) -> None:
        inside = lambda box: box[0] <= event.x <= box[2] and box[1] <= event.y <= box[3]
        if inside(self.close_box):
            self.manager.dismiss(self, acknowledge=True)
            return
        for box, action in self.action_boxes:
            if inside(box):
                self.manager.act(self, action)
                return
        self.manager.act(self, "open")

    def move(self, x: int, y: int, alpha: float) -> None:
        self.x, self.y = x, y
        if self.native:
            self.native.move(x, y, self.width, self.height)
        else:
            self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.window.attributes("-alpha", alpha)

    def hovered(self) -> bool:
        x, y = self.window.winfo_pointerxy()
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def progress(self) -> None:
        inset = round(15 * self.scale)
        self.canvas.coords(self.life, inset, self.height - round(10 * self.scale),
                           inset + (self.width - inset * 2) * max(0, self.remaining / self.manager.duration),
                           self.height - round(8 * self.scale))

    def destroy(self) -> None:
        if self.native:
            self.native.close()
        try:
            self.window.destroy()
        except tk.TclError:
            pass


class ToastManager:
    """At most three visible cards; queued events wait until a slot is free.

    All methods run on the Tk thread. Closing/accepting acknowledges; natural
    expiry only hides a card so unacknowledged reminders may still repeat.
    """
    def __init__(self, root: tk.Misc, center: NotificationCenter, *,
                 on_open: Callable[[Notification], None],
                 on_action: Callable[[Notification, str], None] | None = None,
                 duration: float = 8.0, max_visible: int = 3,
                 reduce_motion: Callable[[], bool] = lambda: False,
                 clock: Callable[[], float] = time.monotonic,
                 work_area: Callable[[], WorkArea] | None = None) -> None:
        if duration <= 0 or not 1 <= max_visible <= 3:
            raise ValueError("duration must be positive; max_visible is 1..3")
        self.root, self.center = root, center
        self.on_open, self.on_action = on_open, on_action
        self.duration, self.max_visible = duration, max_visible
        self.corner = "bottom"  # SN-5: "bottom" — stack up from the lower right, "top" — down from the upper right
        self.reduce_motion, self.clock = reduce_motion, clock
        self.desktop = WindowsDesktop() if sys.platform == "win32" else None
        self.area_provider = work_area or (self.desktop.work_area if self.desktop else self._fallback_area)
        self.assets = ToastAssets()
        self.cards: list[ToastCard] = []
        self._area = self.area_provider()
        self._area_at = self._last_tick = clock()
        self._after = None
        self._closed = False
        self._destroy_binding = root.bind("<Destroy>", self._on_destroy, add="+")

    def _fallback_area(self) -> WorkArea:
        return WorkArea(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def start(self) -> None:
        if not self._closed and self._after is None:
            self._last_tick = self.clock()
            self._after = self.root.after(33, self._poll)

    def _poll(self) -> None:
        self._after = None
        if self._closed:
            return
        try:
            self.pump()
        finally:
            if not self._closed:
                self._after = self.root.after(33, self._poll)

    def pump(self) -> None:
        """One UI tick, exposed for deterministic lifecycle tests."""
        if self._closed:
            return
        now = self.clock()
        elapsed, self._last_tick = max(0, now - self._last_tick), now
        self.center.tick()
        if now - self._area_at >= 2 and (self.cards or self.center.queued):
            area = self.area_provider()
            if area.scale != self._area.scale or area.right - area.left != self._area.right - self._area.left:
                for card in self.cards:
                    card.redraw(area)
            self._area, self._area_at = area, now
        for card in list(self.cards):
            if self.center.do_not_disturb or not self.center.is_active(card.event):
                self.dismiss(card)
            elif now - card.born >= .22:
                if not card.hovered():
                    card.remaining -= elapsed
                card.progress()
                if card.remaining <= 0:
                    self.dismiss(card)
        while len(self.cards) < self.max_visible:
            # Leave a minimum card's worth of space on very small displays.
            used = sum(card.height + round(8 * self._area.scale) for card in self.cards)
            if self.cards and used + round(240 * self._area.scale) > self._area.bottom - self._area.top:
                break
            event = self.center.pop_next()
            if event is None:
                break
            self.cards.append(ToastCard(self, event, self._area))
        margin, gap = round(16 * self._area.scale), round(8 * self._area.scale)
        edge = self._area.top + margin if self.corner == "top" else self._area.bottom - margin
        for card in self.cards:
            t = 1.0 if self.reduce_motion() else min(1.0, max(0, (now - card.born) / .22))
            offset = round((1 - t) ** 3 * card.width)
            x = self._area.right - margin - card.width + offset
            if self.corner == "top":
                card.move(x, edge, t)
                edge += card.height + gap
            else:
                card.move(x, edge - card.height, t)
                edge -= card.height + gap

    def dismiss(self, card: ToastCard, *, acknowledge: bool = False) -> None:
        if acknowledge:
            self.center.acknowledge(card.event.id)
        if card in self.cards:
            self.cards.remove(card)
            card.destroy()

    def act(self, card: ToastCard, action: str) -> None:
        if action == "snooze":
            self.center.snooze(card.event.id, 300)
            self.dismiss(card)
            return
        try:
            if action == "open":
                self.on_open(card.event)
            elif self.on_action:  # «accept» too: a chat toast's «Принять» accepts the chat alerts (SN-4)
                self.on_action(card.event, action)
        finally:
            self.dismiss(card, acknowledge=True)

    def _on_destroy(self, event) -> None:
        if event.widget == self.root:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._after:
            self.root.after_cancel(self._after)
            self._after = None
        for card in list(self.cards):
            self.dismiss(card)
        try:
            self.root.unbind("<Destroy>", self._destroy_binding)
        except tk.TclError:
            pass
