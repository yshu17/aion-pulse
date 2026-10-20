"""Small Tk widgets for the sourced Bestiary profile and scrollable cards."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from watcher import theme
from core.bestiary.bestiary_labels import stat_text


def keep_pane_cursor(split: tk.PanedWindow, *panes: tk.Misc) -> None:
    """The divider's double arrow must not leak into the panes. Tk sets it on the paned window itself while the
    pointer is on the divider and children without a cursor of their own inherit it; if the pointer leaves the
    divider by jumping onto a pane, Tk never takes it back. An explicit arrow on every pane stops the inheritance,
    and entering a pane puts the paned window's own cursor back."""
    split.configure(cursor="arrow")
    for pane in panes:
        pane.configure(cursor="arrow")
        pane.bind("<Enter>", lambda _e: split.configure(cursor="arrow"), add="+")


def refresh_pointer_cursor(widget: tk.Misc) -> None:
    """Tk recomputes the cursor only when the pointer moves, so a cursor stays a hand or an arrow after the widget
    under the pointer was hidden, replaced or repainted. Re-applying the cursor of the widget now under the pointer
    makes Tk look again."""
    try:
        x, y = widget.winfo_pointerxy()
        under = widget.winfo_containing(x, y)
        if under is not None:
            under.configure(cursor=under.cget("cursor"))
    except (tk.TclError, KeyError):
        pass


def wrap_badges(frame: tk.Frame):
    """Wrap badges to the available width, including after window resizing. Badges with no text are hidden.
    Returns the arrange function, to call after the badge texts change. Nothing is re-placed or resized when the
    layout is the same: every change made Tk lay out the whole result list again."""
    placed: dict[str, tuple[int, int]] = {}

    def arrange(_event=None):
        width = max(1, frame.winfo_width())
        x = y = height = 0
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and not child.cget("text"):
                if placed.pop(str(child), None) is not None:
                    child.place_forget()
                continue
            w, h = child.winfo_reqwidth(), child.winfo_reqheight()
            if x and x + w > width:
                x, y = 0, y + height + 4
                height = 0
            if placed.get(str(child)) != (x, y):
                child.place(x=x, y=y)
                placed[str(child)] = (x, y)
            x += w + 4
            height = max(height, h)
        if int(frame.cget("height")) != y + height:
            frame.configure(height=y + height)
    frame.bind("<Configure>", arrange)
    frame.after_idle(arrange)
    return arrange


def bind_wheel_tree(widget: tk.Misc, canvas: tk.Canvas) -> None:
    """Route wheel events over child labels/cards to their own scroll surface."""
    def scroll(event):
        if canvas.yview() == (0.0, 1.0):
            return "break"
        delta = getattr(event, "delta", 0)
        direction = -1 if getattr(event, "num", None) == 4 or delta > 0 else 1
        steps = max(1, abs(int(delta / 120))) if delta else 1
        canvas.yview_scroll(direction * steps * 2, "units")
        return "break"
    widget.bind("<MouseWheel>", scroll)
    widget.bind("<Button-4>", scroll)
    widget.bind("<Button-5>", scroll)
    for child in widget.winfo_children():
        bind_wheel_tree(child, canvas)


class ScrollArea(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=theme.SURFACE, highlightthickness=0, borderwidth=0, yscrollincrement=18)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.content = tk.Frame(self.canvas, bg=theme.SURFACE)
        self.window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.content.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        bind_wheel_tree(self.canvas, self.canvas)

    def refresh(self):
        bind_wheel_tree(self.content, self.canvas)
        self.canvas.yview_moveto(0)


class ProfileHeader(ttk.Frame):
    """Use the reference site's original rank-specific HP artwork, not live HP."""
    FRAMES = {1: (25, 0, 297, 79), 2: (26, 98, 310, 188),
              3: (5, 205, 333, 296), 4: (0, 322, 336, 420)}
    ICON_TOP = {1: 22, 2: 25, 3: 28, 4: 25}

    def __init__(self, parent, icons_dir: Path):
        super().__init__(parent, style="Card.TFrame")
        self.icons_dir = icons_dir
        self.title = ttk.Label(self, text="Выберите существо", style="Title.TLabel", wraplength=650)
        self.title.pack(anchor="w")
        self.subtitle = ttk.Label(self, text="", style="Muted.TLabel", wraplength=600)
        self.subtitle.pack(anchor="w", pady=(2, 0))
        self.bar = tk.Canvas(self, bg=theme.SURFACE, height=105, highlightthickness=0, borderwidth=0)
        self.bar.pack(fill="x", pady=(4, 0))
        self.chips = tk.Frame(self, bg=theme.SURFACE)
        self.chips.pack(fill="x", pady=(0, 7))
        self._photos = []
        self._detail = None
        self.bar.bind("<Configure>", lambda _e: self._render())
        self.bind("<Configure>", lambda e: self.title.configure(wraplength=max(250, e.width - 20)))

    def show(self, detail: dict | None):
        self._detail = detail
        self.title.configure(text=detail["name"] if detail else "Выберите существо")
        self.subtitle.configure(text=detail.get("title", "") if detail else "")
        for child in self.chips.winfo_children():
            child.destroy()
        if detail:
            for text, color in ((detail.get("kind"), theme.PLACE),
                                (detail.get("faction") if detail.get("faction") != "Другие" else detail.get("race"), theme.DANGER),
                                (detail.get("rank"), theme.ACCENT)):
                if text:
                    tk.Label(self.chips, text=str(text).upper(), bg=theme.SURFACE_2, fg=color,
                             padx=9, pady=4, font=theme.font("small"))
            wrap_badges(self.chips)
        self._render()

    def _render(self):
        self.bar.delete("all")
        self._photos.clear()
        detail = self._detail
        if not detail:
            return
        from PIL import Image, ImageDraw, ImageTk
        rank = detail.get("hp_bar") or {"Обычный": 1, "Элитный": 2, "Героический": 3, "Легендарный": 4}.get(detail.get("rank"))
        if rank is None:
            self.bar.create_text(0, 30, text=f"Уровень {detail.get('level') or '—'} · Ранг не указан",
                                 anchor="w", fill=theme.MUTED, font=theme.font("control_strong"))
            return
        rank = rank if rank in self.FRAMES else 1
        path = self.icons_dir / "npc/hp-bars.png"
        if path.is_file():
            with Image.open(path) as raw:
                photo = ImageTk.PhotoImage(raw.crop(self.FRAMES[rank]), master=self.bar)
            self._photos.append(photo)
            self.bar.create_image(0, 0, image=photo, anchor="nw")
        asset = self.icons_dir / (detail.get("icon_asset") or "ui/monster.png")
        if asset.is_file():
            with Image.open(asset) as raw:
                icon = raw.convert("RGBA").resize((40, 40), Image.Resampling.LANCZOS)
            mask = Image.new("L", (40, 40), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 39, 39), fill=255)
            icon.putalpha(mask)
            photo = ImageTk.PhotoImage(icon, master=self.bar)
            self._photos.append(photo)
            self.bar.create_image(27 if rank != 2 else 24, self.ICON_TOP[rank], image=photo, anchor="nw")
        self.bar.create_text(14, self.ICON_TOP[rank] + 20, text=str(detail.get("level") or "?"),
                             fill=theme.TEXT, font=theme.font("small"))
        if self.bar.winfo_width() > 465:
            hp = stat_text((detail.get("stats") or {}).get("Макс. ХП", "—"))
            self.bar.create_text(355, 30, text=f"Уровень {detail.get('level') or '—'}", anchor="w",
                                 fill=theme.TEXT, font=theme.font("control_strong"))
            self.bar.create_text(355, 57, text=f"Макс. ХП: {hp}", anchor="w", fill=theme.MUTED, font=theme.font("small"))
