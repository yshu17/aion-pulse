"""Item tooltip rendered from a spec (see core.items.specs)."""

import tkinter as tk

from watcher import theme

BG = theme.TOOLTIP_BG
FRAME = theme.TOOLTIP_FRAME
LINE = theme.TOOLTIP_LINE
DB_BG = theme.TOOLTIP_DB_BG
DB_FRAME = theme.TOOLTIP_DB_FRAME
EMPIRE_BG = theme.TOOLTIP_EMPIRE_BG
EMPIRE_FRAME = theme.TOOLTIP_EMPIRE_FRAME
NAME_COLORS = theme.GRADE_COLORS
PROPS = theme.TOOLTIP_PROPS
WARNING = theme.TOOLTIP_WARNING
WIDTH = 440
OFFSET = 18


class SpecTooltip:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.window: tk.Toplevel | None = None
        self.reduce_motion = False

    def show(self, spec: dict, icon: tk.PhotoImage | None, x: int, y: int) -> None:
        self.hide()
        layout = spec.get("layout")
        surface = DB_BG if layout == "database" else EMPIRE_BG if layout == "empire" else BG
        frame = DB_FRAME if layout == "database" else EMPIRE_FRAME if layout == "empire" else FRAME
        win = tk.Toplevel(self.root, background=frame, padx=1, pady=1)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        body = tk.Frame(win, background=surface, padx=10 if layout == "empire" else 14,
                        pady=10 if layout == "empire" else 12)
        body.pack(fill="both", expand=True)
        self._render(body, spec, icon)
        win.update_idletasks()
        self._place(win, x, y)
        self.window = win
        from watcher.motion import fade_window
        fade_window(win, 120, enabled=not self.reduce_motion)

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
        size = kw.pop("size", theme.TYPE["caption"][0])
        weight = kw.pop("weight", "normal")
        background = kw.pop("background", BG)
        wraplength = kw.pop("wraplength", WIDTH)
        return tk.Label(
            parent,
            text=text,
            background=background,
            foreground=color,
            font=(theme.FONT_FAMILY, size, weight),
            justify="left",
            anchor="w",
            wraplength=wraplength,
            **kw,
        )

    def _render(self, body: tk.Frame, spec: dict, icon: tk.PhotoImage | None) -> None:
        if spec.get("layout") == "database":
            self._render_database(body, spec, icon)
            return
        if spec.get("layout") == "empire":
            self._render_empire(body, spec, icon)
            return
        name_color = NAME_COLORS.get(spec.get("grade", ""), theme.TEXT)
        self._label(body, spec.get("name", ""), name_color, size=theme.TYPE["tooltip_name"][0], weight="bold").pack(
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

    def _render_database(self, body: tk.Frame, spec: dict, icon: tk.PhotoImage | None) -> None:
        """Compact field card for medal records, following the linked item database layout."""
        top = tk.Frame(body, background=DB_BG)
        top.pack(fill="x", pady=(0, 10))
        if icon is not None:
            tk.Label(top, image=icon, background=DB_BG, highlightthickness=1,
                     highlightbackground=DB_FRAME).pack(side="left", padx=(0, 12))
        names = tk.Frame(top, background=DB_BG)
        names.pack(side="left", fill="x", expand=True)
        self._label(names, spec["name"], NAME_COLORS.get(spec.get("title_grade", spec.get("grade")), theme.TEXT),
                    background=DB_BG, size=theme.TYPE["tooltip_name"][0], weight="bold").pack(fill="x")
        if spec.get("subtitle"):
            self._label(names, spec["subtitle"], background=DB_BG).pack(fill="x")
        tk.Frame(body, background=DB_FRAME, height=1).pack(fill="x", pady=(0, 6))
        for name, value in spec.get("facts", []):
            row = tk.Frame(body, background=DB_BG)
            row.pack(fill="x", pady=(4, 4))
            self._label(row, name, background=DB_BG).pack(side="left")
            value_color = NAME_COLORS["rare"] if name == "Качество" and spec.get("grade") == "rare" else theme.TEXT
            self._label(row, value, value_color, background=DB_BG, weight="bold").pack(side="right")
            tk.Frame(body, background=LINE, height=1).pack(fill="x")
        for restriction in spec.get("restrictions", []):
            self._label(body, restriction, PROPS, background=DB_BG).pack(fill="x", pady=(2, 0))
        if spec.get("description"):
            self._label(body, "Описание", theme.MUTED, background=DB_BG).pack(fill="x", pady=(10, 2))
            self._label(body, spec["description"], background=DB_BG).pack(fill="x", pady=(0, 10))
        if spec.get("item_link"):
            code = tk.Frame(body, background=DB_BG, highlightthickness=1, highlightbackground=DB_FRAME,
                            padx=8, pady=6)
            code.pack(fill="x")
            self._label(code, spec["item_link"], background=DB_BG, weight="bold").pack(side="left")

    def _render_empire(self, body: tk.Frame, spec: dict, icon: tk.PhotoImage | None) -> None:
        """Aion Empire's compact medal tooltip: title, information tab, rank and restrictions."""
        self._label(body, spec["name"], NAME_COLORS["rare"], background=EMPIRE_BG,
                    size=theme.TYPE["tooltip_name"][0], weight="bold").pack(fill="x", pady=(0, 12))
        tk.Label(body, text="Общая информация", background=theme.TOOLTIP_EMPIRE_TAB,
                 foreground=theme.TEXT, font=(theme.FONT_FAMILY, theme.TYPE["caption"][0]),
                 padx=9, pady=4, relief="solid", borderwidth=1,
                 highlightthickness=1, highlightbackground=theme.TOOLTIP_EMPIRE_TAB_FRAME).pack(
                     anchor="w", pady=(0, 13))
        details = tk.Frame(body, background=EMPIRE_BG)
        details.pack(fill="x")
        if icon is not None:
            tk.Label(details, image=icon, background=EMPIRE_BG, highlightthickness=1,
                     highlightbackground=theme.TOOLTIP_EMPIRE_TAB_FRAME).pack(side="left", anchor="n", padx=(0, 11))
        info = tk.Frame(details, background=EMPIRE_BG)
        info.pack(side="left", fill="x", expand=True)
        rank = tk.Frame(info, background=EMPIRE_BG)
        rank.pack(fill="x", pady=(0, 3))
        self._label(rank, "Ранг", background=EMPIRE_BG).pack(side="left", padx=(0, 42))
        self._label(rank, spec.get("rank", "[Обычный]"), background=EMPIRE_BG).pack(side="left")
        restrictions = "; ".join(f"[{line}]" for line in spec.get("restrictions", []))
        if restrictions:
            self._label(info, restrictions, theme.TOOLTIP_EMPIRE_PROPS, background=EMPIRE_BG,
                        wraplength=345).pack(fill="x")
        tk.Frame(body, background=theme.TOOLTIP_EMPIRE_LINE, height=1).pack(fill="x", pady=(9, 9))
        self._label(body, spec.get("description", ""), background=EMPIRE_BG,
                    wraplength=460).pack(fill="x")

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
                    background=theme.TOOLTIP_SLOT,
                    highlightthickness=1,
                    highlightbackground=theme.ACCENT if bonus else LINE,
                ).pack(side="left", padx=(0, 6))
        elif kind == "recipe":
            for number, recipe in enumerate(block["recipes"]):
                if number:
                    tk.Frame(parent, background=LINE, height=1).pack(fill="x", pady=4)
                title = "Создаётся по рецепту"
                if recipe.get("skill"):
                    title += f": {recipe['skill']}" + (f", {recipe['level']}" if recipe.get("level") else "")
                self._label(parent, title, theme.ACCENT, weight="bold").pack(fill="x")
                for name, quantity in recipe["ingredients"]:
                    self._label(parent, f"•  {name}" + (f"  ×{quantity}" if quantity > 1 else ""), theme.TEXT).pack(
                        fill="x", padx=(8, 0))
                if recipe.get("count", 1) > 1:
                    self._label(parent, f"Создаётся предметов: {recipe['count']}", theme.MUTED).pack(fill="x")
        elif kind == "set":
            for name in block["items"]:
                self._label(parent, f"•  {name}", theme.ACCENT).pack(fill="x", padx=(8, 0))
