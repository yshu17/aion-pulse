"""Is the window edge being dragged right now? Answered by asking Windows whether the mouse button is held.

A window size change while the primary mouse button is down is a drag of the edge or corner (a plain move does not
change the size, maximize and snap happen on release). The drag ends when the button is released, whatever pauses
the hand makes on the way.

An earlier version replaced the window procedure to catch WM_SIZING; calling back into Python from there broke the
interpreter's thread state inside Tk and crashed the program. This only reads the button state: a plain call, no
callback.

    primary_button_down() -> bool      False where it is not Windows
"""

from __future__ import annotations

VK_LBUTTON, VK_RBUTTON = 0x01, 0x02
SM_SWAPBUTTON = 23


def primary_button_down() -> bool:
    try:
        import ctypes
        user32 = ctypes.windll.user32
    except (ImportError, AttributeError, OSError):
        return False
    button = VK_RBUTTON if user32.GetSystemMetrics(SM_SWAPBUTTON) else VK_LBUTTON
    return bool(user32.GetAsyncKeyState(button) & 0x8000)
