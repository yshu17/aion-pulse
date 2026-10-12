"""Windows toast positioning without activation; no game process modification.

SetWindowPos flags: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowpos
WM_MOUSEACTIVATE: https://learn.microsoft.com/windows/win32/inputdev/about-mouse-input
"""
from __future__ import annotations

import ctypes as ct
import os
from ctypes import wintypes as wt
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int
    scale: float = 1.0


class MonitorInfo(ct.Structure):
    _fields_ = [("size", wt.DWORD), ("monitor", wt.RECT), ("work", wt.RECT), ("flags", wt.DWORD)]


class WindowsDesktop:
    def __init__(self) -> None:
        self.user = ct.WinDLL("user32", use_last_error=True)
        self.kernel = ct.WinDLL("kernel32", use_last_error=True)
        self.proc_type = ct.WINFUNCTYPE(ct.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self.enum_type = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        self.user.GetAncestor.argtypes = [wt.HWND, wt.UINT]
        self.user.GetAncestor.restype = wt.HWND
        self.user.GetWindowLongW.argtypes = [wt.HWND, ct.c_int]
        self.user.GetWindowLongW.restype = wt.LONG
        self.user.SetWindowLongW.argtypes = [wt.HWND, ct.c_int, wt.LONG]
        self.user.SetWindowLongW.restype = wt.LONG
        self.set_proc = self.user.SetWindowLongPtrW if ct.sizeof(ct.c_void_p) == 8 else self.user.SetWindowLongW
        self.set_proc.argtypes = [wt.HWND, ct.c_int, ct.c_ssize_t]
        self.set_proc.restype = ct.c_ssize_t
        self.user.CallWindowProcW.argtypes = [ct.c_void_p, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        self.user.CallWindowProcW.restype = ct.c_ssize_t
        self.user.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ct.c_int, ct.c_int, ct.c_int, ct.c_int, wt.UINT]
        self.user.SetWindowPos.restype = wt.BOOL
        self.user.IsWindow.argtypes = [wt.HWND]
        self.user.IsWindowVisible.argtypes = [wt.HWND]
        self.user.IsIconic.argtypes = [wt.HWND]
        self.user.EnumWindows.argtypes = [self.enum_type, wt.LPARAM]
        self.user.GetWindowThreadProcessId.argtypes = [wt.HWND, ct.POINTER(wt.DWORD)]
        self.user.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
        self.user.MonitorFromWindow.restype = wt.HANDLE
        self.user.GetMonitorInfoW.argtypes = [wt.HANDLE, ct.POINTER(MonitorInfo)]
        self.kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.kernel.OpenProcess.restype = wt.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)]
        self.kernel.CloseHandle.argtypes = [wt.HANDLE]

    def work_area(self) -> WorkArea:
        """Prefer a visible Aion window; otherwise use the primary monitor."""
        found = []

        @self.enum_type
        def visit(hwnd, _param):
            if not self.user.IsWindowVisible(hwnd) or self.user.IsIconic(hwnd):
                return True
            pid = wt.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ct.byref(pid))
            process = self.kernel.OpenProcess(0x1000, False, pid.value)
            if process:
                try:
                    path = ct.create_unicode_buffer(32768)
                    size = wt.DWORD(len(path))
                    if self.kernel.QueryFullProcessImageNameW(process, 0, path, ct.byref(size)):
                        if os.path.basename(path.value).lower() == "aion.bin":
                            found.append(hwnd)
                            return False
                finally:
                    self.kernel.CloseHandle(process)
            return True

        self.user.EnumWindows(visit, 0)
        monitor = self.user.MonitorFromWindow(found[0] if found else None, 1)
        info = MonitorInfo()
        info.size = ct.sizeof(info)
        if not self.user.GetMonitorInfoW(monitor, ct.byref(info)):
            raise ct.WinError(ct.get_last_error())
        scale = 1.0
        try:
            dpi = ct.WinDLL("shcore").GetDpiForMonitor
            dpi.argtypes = [wt.HANDLE, ct.c_int, ct.POINTER(wt.UINT), ct.POINTER(wt.UINT)]
            x, y = wt.UINT(), wt.UINT()
            if dpi(monitor, 0, ct.byref(x), ct.byref(y)) == 0:
                scale = x.value / 96.0
        except (AttributeError, OSError):
            pass
        r = info.work
        return WorkArea(r.left, r.top, r.right, r.bottom, scale)

    def attach(self, window) -> NativeToast:
        return NativeToast(self, window)


class NativeToast:
    def __init__(self, desktop: WindowsDesktop, window) -> None:
        self.desktop = desktop
        self.hwnd = desktop.user.GetAncestor(window.winfo_id(), 2)
        user = desktop.user
        style = user.GetWindowLongW(self.hwnd, -20)
        user.SetWindowLongW(self.hwnd, -20, (style | 0x08000000 | 0x80) & ~0x40000)
        self.old_proc = 0

        @desktop.proc_type
        def procedure(hwnd, message, wparam, lparam):
            if message == 0x21:  # WM_MOUSEACTIVATE: also covers focus-follows-mouse.
                return 3  # MA_NOACTIVATE: deliver clicks without activating this window.
            return user.CallWindowProcW(self.old_proc, hwnd, message, wparam, lparam)

        self.callback = procedure  # keep alive while installed in Windows
        ct.set_last_error(0)
        self.old_proc = desktop.set_proc(self.hwnd, -4, ct.cast(procedure, ct.c_void_p).value)
        if not self.old_proc and ct.get_last_error():
            raise ct.WinError(ct.get_last_error())

    def move(self, x: int, y: int, width: int, height: int) -> None:
        # Absolute screen coordinates (negative coordinates work on left monitors).
        self.desktop.user.SetWindowPos(self.hwnd, wt.HWND(-1), x, y, width, height, 0x10 | 0x40)

    def close(self) -> None:
        if self.old_proc and self.desktop.user.IsWindow(self.hwnd):
            self.desktop.set_proc(self.hwnd, -4, self.old_proc)
        self.old_proc = 0
