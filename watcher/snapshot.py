"""A picture of part of the program's own window (Windows, via PrintWindow). Used while the window edge is dragged:
the tab pages are taken out of the layout and this picture stands in for them. Returns None elsewhere or on any
failure, and the caller shows a plain background instead."""

from __future__ import annotations

import tkinter as tk


def capture_widget(widget: tk.Misc):
    """PIL image of `widget` as it is painted now, or None."""
    try:
        import ctypes
        from ctypes import wintypes as wt

        from PIL import Image
    except (ImportError, ValueError):
        return None
    try:
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    except (AttributeError, OSError):
        return None
    try:
        hwnd = user32.GetParent(widget.winfo_id()) or widget.winfo_toplevel().winfo_id()
        hwnd = user32.GetParent(widget.winfo_toplevel().winfo_id()) or hwnd
        rect = wt.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        width, height = rect.right - rect.left, rect.bottom - rect.top
        wx, wy, ww, wh = widget.winfo_rootx() - rect.left, widget.winfo_rooty() - rect.top, widget.winfo_width(), widget.winfo_height()
        if width <= 0 or height <= 0 or ww <= 1 or wh <= 1:
            return None

        class BitmapInfo(ctypes.Structure):
            _fields_ = [("size", wt.DWORD), ("width", wt.LONG), ("height", wt.LONG), ("planes", wt.WORD),
                        ("bits", wt.WORD), ("compression", wt.DWORD), ("image", wt.DWORD), ("x", wt.LONG),
                        ("y", wt.LONG), ("used", wt.DWORD), ("important", wt.DWORD)]

        window_dc = user32.GetWindowDC(hwnd)
        memory_dc = gdi32.CreateCompatibleDC(window_dc)
        bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
        gdi32.SelectObject(memory_dc, bitmap)
        try:
            user32.PrintWindow(hwnd, memory_dc, 2)  # PW_RENDERFULLCONTENT
            info = BitmapInfo(ctypes.sizeof(BitmapInfo), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
            buffer = ctypes.create_string_buffer(width * height * 4)
            gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0)
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(hwnd, window_dc)
        picture = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")
        return picture.crop((max(0, wx), max(0, wy), min(width, wx + ww), min(height, wy + wh)))
    except (OSError, ValueError, tk.TclError):
        return None
