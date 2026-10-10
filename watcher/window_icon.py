"""Application window icon loaded from the bundled PNG sizes."""

from pathlib import Path
import tkinter as tk


ICON_SIZES = (16, 32)


def load_app_icon(window: tk.Misc, ui_dir: Path) -> tuple[tk.PhotoImage, ...]:
    """Set the app's default window icon and return references to its Tk images."""
    images = tuple(
        tk.PhotoImage(master=window, file=str(ui_dir / f"aion_app_{size}.png"))
        for size in ICON_SIZES
    )
    window.iconphoto(True, *images)
    return images


def apply_app_icon(window: tk.Misc, images: tuple[tk.PhotoImage, ...]) -> None:
    """Apply the same icon to a secondary top-level window."""
    if images:
        window.iconphoto(False, *images)
