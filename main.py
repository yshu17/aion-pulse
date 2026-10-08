"""Aion Chat Watcher: beep when «Поиск группы» chat contains a keyword."""

import ctypes
import tkinter as tk

from watcher.app import App
from watcher.config import app_root


def enable_dpi_awareness() -> None:
    """Render at native resolution on scaled Windows displays (sharp text and icons)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    App(root, app_root() / "config.json")
    root.mainloop()


if __name__ == "__main__":
    main()
