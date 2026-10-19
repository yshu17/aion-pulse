"""Know when the user drags the window edge, from Windows itself (WM_SIZING / WM_EXITSIZEMOVE).

Tk only sees the resulting size changes, one after another, and cannot tell a drag from a pause in it. Windows sends
WM_SIZING for every step of an edge drag (never for a plain move or maximize) and WM_EXITSIZEMOVE when the mouse is
released. The program stops drawing its content at the first and draws it once at the second.

    install_sizing_hook(root, on_start, on_end) -> bool   False where it is not Windows or the hook cannot be set
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

WM_SIZING = 0x0214
WM_EXITSIZEMOVE = 0x0232
WM_NCDESTROY = 0x0082
GWLP_WNDPROC = -4


def install_sizing_hook(root: tk.Misc, on_start: Callable[[], None], on_end: Callable[[], None]) -> bool:
    try:
        import ctypes
        from ctypes import wintypes as wt
        user32 = ctypes.windll.user32
    except (ImportError, AttributeError, OSError):
        return False
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.CallWindowProcW.restype = LRESULT
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
    user32.GetParent.restype = wt.HWND
    user32.GetParent.argtypes = [wt.HWND]
    try:
        root.update_idletasks()
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    except tk.TclError:
        return False
    state = {"sizing": False, "old": None}

    def proc(handle, message, wparam, lparam):
        try:
            if message == WM_SIZING and not state["sizing"]:
                state["sizing"] = True
                on_start()
            elif message == WM_EXITSIZEMOVE and state["sizing"]:
                state["sizing"] = False
                on_end()
        except Exception:  # a Python error must never break the window's own message handling
            pass
        result = user32.CallWindowProcW(state["old"], handle, message, wparam, lparam)
        if message == WM_NCDESTROY:  # the window is gone: put the original procedure back
            user32.SetWindowLongPtrW(handle, GWLP_WNDPROC, state["old"])
        return result

    callback = WNDPROC(proc)
    old = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(callback, ctypes.c_void_p))
    if not old:
        return False
    state["old"] = old
    root._sizing_hook = (callback, state)  # keep the callback alive as long as the window
    return True
