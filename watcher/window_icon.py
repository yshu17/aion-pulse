"""Application window icon loaded from the bundled PNG sizes."""

import time
from pathlib import Path
import tkinter as tk


ICON_SIZES = (16, 32)


def load_app_icon(window: tk.Misc, ui_dir: Path) -> tuple[tk.PhotoImage, ...]:
    """Set the app's default window icon and return references to its Tk images.

    The icon is cosmetic: Windows may hold a PNG for a moment (a virus scan, a build touching the folder), so reading
    is retried, and a file that still cannot be read leaves the window with the default icon instead of failing.
    """
    images = []
    for size in ICON_SIZES:
        for attempt in range(3):
            try:
                images.append(tk.PhotoImage(master=window, file=str(ui_dir / f"aion_app_{size}.png")))
                break
            except tk.TclError:
                time.sleep(0.05 * (attempt + 1))
    if images:
        window.iconphoto(True, *images)
    return tuple(images)


def apply_app_icon(window: tk.Misc, images: tuple[tk.PhotoImage, ...]) -> None:
    """Apply the same icon to a secondary top-level window."""
    if images:
        window.iconphoto(False, *images)
