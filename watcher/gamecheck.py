"""Is the game running? Looks for the client process (aion.bin) in the Windows process list.

Uses the ToolHelp snapshot through ctypes: no console window, no extra packages, and it needs no
rights on the game process itself.
"""

import ctypes
from collections.abc import Iterable
from ctypes import wintypes

GAME_PROCESSES = ("aion.bin",)  # bin32 and bin64 clients have the same name
_TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_names() -> list[str] | None:
    """Executable names of all running processes (lower case), None if the list can't be read."""
    try:
        kernel32 = ctypes.windll.kernel32
    except AttributeError:
        return None
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == _INVALID_HANDLE:
        return None
    names = []
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(_ProcessEntry)
        ok = kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        while ok:
            names.append(entry.szExeFile.lower())
            ok = kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))
    return names


def game_running(names: Iterable[str] | None = None) -> bool | None:
    """True / False, or None when the process list is unavailable (then the caller should not stop)."""
    running = process_names() if names is None else [n.lower() for n in names]
    if running is None:
        return None
    return any(name in GAME_PROCESSES for name in running)
