"""Game-style item tooltip rendered from a spec (see watcher.specs)."""

import tkinter as tk

from watcher import theme

BG = "#0e1014"
FRAME = "#5a4a2e"
LINE = "#3a3d46"
NAME_COLORS = {"epic": theme.ACCENT, "unique": "#f0c75e", "legend": "#5fa8ff", "rare": "#6fd56f"}
PROPS = "#e8c55a"
WARNING = "#ff5b5b"
WIDTH = 440
OFFSET = 18


class SpecTooltip:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.window: tk.Toplevel | None = None

    def show(self, spec: dict, icon: tk.PhotoImage | None, x: int, y: int) -> None:
        self.hide()
        win = tk.Toplevel(self.root, background=FRAME, padx=1, pady=1)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        body = tk.Frame(win, background=BG, padx=14, pady=12)
        body.pack(fill="both", expand=True)
        self._render(body, spec, icon)
        win.update_idletasks()
        self._place(win, x, y)
        self.window = win

    def hide(self) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None

    # --- layout ----------------------------------------------------------------
    def _place(self, win: tk.Toplevel, x: int, y: int) -> None:
        width, height = win.winfo_reqwidth(), win.winfo_reqheight()
        screen_w, screen_h = win.winfo_screenwidth(), win.winfo_screenheight()
        left = x + OFFSET if x + OFFSET + width <= screen_w else max(0, x - OFFSET - width)
        top = min(max(0, y - 20), max(0, screen_h - height - 8))
        win.geometry(f"+{left}+{top}")

    def _label(self, parent: tk.Misc, text: str, color: str = theme.TEXT, **kw) -> tk.Label:
        size = kw.pop("size", theme.FONT_SIZE - 1)
        weight = kw.pop("weight", "normal")
        return tk.Label(
            parent,
            text=text,
            background=BG,
            foreground=color,
            font=(theme.FONT_FAMILY, size, weight),
            justify="left",
            anchor="w",
            wraplength=WIDTH,
            **kw,
        )

    def _render(self, body: tk.Frame, spec: dict, icon: tk.PhotoImage | None) -> None:
        name_color = NAME_COLORS.get(spec.get("grade", ""), theme.TEXT)
        self._label(body, spec.get("name", ""), name_color, size=theme.FONT_SIZE + 3, weight="bold").pack(
            fill="x", pady=(0, 8)
        )
        blocks = spec.get("blocks", [])
        top = tk.Frame(body, background=BG)
        top.pack(fill="x")
        if icon is not None:
            tk.Label(top, image=icon, background=BG).pack(side="left", anchor="n", padx=(0, 12))
        head = tk.Frame(top, background=BG)
        head.pack(side="left", fill="x", expand=True)
        rest = blocks
        while rest and rest[0]["kind"] in ("pairs", "props", "warning"):
            self._block(head, rest[0])
            rest = rest[1:]
        for block in rest:
            self._block(body, block)

    def _block(self, parent: tk.Misc, block: dict) -> None:
        kind = block["kind"]
        if kind == "hr":
            tk.Frame(parent, background=LINE, height=1).pack(fill="x", pady=6)
        elif kind == "pairs":
            grid = tk.Frame(parent, background=BG)
            grid.pack(fill="x")
            for row, (name, value) in enumerate(block["rows"]):
                self._label(grid, name, theme.MUTED).grid(row=row, column=0, sticky="w", padx=(0, 18))
                self._label(grid, value).grid(row=row, column=1, sticky="w")
        elif kind == "props":
            for line in block["lines"]:
                self._label(parent, line, PROPS).pack(fill="x")
        elif kind == "warning":
            self._label(parent, block["text"], WARNING).pack(fill="x")
        elif kind == "grid":
            color = theme.MUTED if block.get("dim") else theme.TEXT
            grid = tk.Frame(parent, background=BG)
            grid.pack(fill="x")
            for i, (name, value) in enumerate(block["pairs"]):
                row, col = divmod(i, 2)
                self._label(grid, name, color).grid(row=row, column=col * 2, sticky="w", padx=(0, 12))
                self._label(grid, value, color, weight="bold" if not block.get("dim") else "normal").grid(
                    row=row, column=col * 2 + 1, sticky="w", padx=(0, 28)
                )
        elif kind == "text":
            color = {"epic": theme.ACCENT, "muted": theme.MUTED}.get(block.get("style"), theme.TEXT)
            self._label(parent, block["text"], color).pack(fill="x", pady=1)
        elif kind == "stones":
            row = tk.Frame(parent, background=BG)
            row.pack(fill="x", pady=4)
            for i in range(block["count"]):
                bonus = i >= block["count"] - block.get("bonus", 0)
                tk.Frame(
                    row,
                    width=22,
                    height=22,
                    background="#1c1f26",
                    highlightthickness=1,
                    highlightbackground=theme.ACCENT if bonus else LINE,
                ).pack(side="left", padx=(0, 6))
        elif kind == "set":
            for name in block["items"]:
                self._label(parent, f"•  {name}", theme.ACCENT).pack(fill="x", padx=(8, 0))
