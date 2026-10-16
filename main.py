"""Pulse: beep when «Поиск группы» chat contains a keyword."""

import ctypes
import tkinter as tk

from watcher.app import App
from watcher.config import app_root


def enable_dpi_awareness() -> None:
    """Prefer per-monitor-v2 DPI before Tk creates any native windows."""
    try:
        set_awareness = ctypes.windll.user32.SetProcessDpiAwarenessContext
        set_awareness.argtypes = [ctypes.c_void_p]
        set_awareness.restype = ctypes.c_bool
        if set_awareness(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    # Windows 8.1 fallback: per-monitor awareness without the v2 window behaviors.
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    # Older Windows fallback retained for compatibility.
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def configure_tk_scaling(root: tk.Tk) -> None:
    """Set Tk's point-to-pixel scale from the DPI of the monitor hosting the window."""
    try:
        get_dpi = ctypes.windll.user32.GetDpiForWindow
        get_dpi.argtypes = [ctypes.c_void_p]
        get_dpi.restype = ctypes.c_uint
        dpi = get_dpi(ctypes.c_void_p(root.winfo_id()))
        if dpi:
            root.tk.call("tk", "scaling", dpi / 72.0)
    except (AttributeError, OSError, tk.TclError):
        # Keep Tk's platform default when the Windows DPI API is unavailable.
        pass


def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    configure_tk_scaling(root)
    App(root, app_root() / "config.json")
    root.mainloop()


if __name__ == "__main__":
    main()
