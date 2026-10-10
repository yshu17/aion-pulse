"""Small cached Phosphor PNGs used by the Tk interface."""

from pathlib import Path

import tkinter as tk

from watcher.theme import load_png


class IconSet:
    def __init__(self, master: tk.Misc, directory: Path) -> None:
        self.master = master
        self.directory = Path(directory)
        self._images: dict[tuple[str, str, int], tk.PhotoImage | None] = {}

    def get(self, name: str, color: str = "muted", size: int = 16) -> tk.PhotoImage | None:
        key = (name, color, size)
        if key not in self._images:
            path = self.directory / f"{name}_{size}_{color}.png"
            try:
                self._images[key] = load_png(self.master, path) if path.is_file() else None
            except tk.TclError:
                self._images[key] = None
        return self._images[key]
