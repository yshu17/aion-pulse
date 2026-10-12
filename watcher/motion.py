"""Small, cancellation-safe Tk animations shared by UI components."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def tween_color(
    widget: tk.Misc,
    setter: Callable[[str], None],
    start: str,
    end: str,
    duration_ms: int = 150,
    *,
    enabled: bool = True,
    steps: int = 4,
    done: Callable[[], None] | None = None,
) -> str | None:
    """Interpolate a color on Tk's event loop; returns the first timer id, if animated."""
    if not enabled or duration_ms <= 0 or steps < 2:
        setter(end)
        if done:
            done()
        return None
    first: str | None = None
    a, b = _rgb(start), _rgb(end)

    def frame(index: int) -> None:
        nonlocal first
        try:
            if not widget.winfo_exists():
                return
            t = index / steps
            color = _hex(tuple(round(x + (y - x) * t) for x, y in zip(a, b)))
            setter(color)
            if index >= steps:
                if done:
                    done()
                return
            timer = widget.after(max(1, duration_ms // steps), lambda: frame(index + 1))
            if first is None:
                first = timer
        except tk.TclError:
            return

    frame(0)
    return first


def fade_window(window: tk.Toplevel, duration_ms: int = 150, *, enabled: bool = True) -> None:
    """Fade in a top-level window where the platform supports Tk's alpha attribute."""
    if not enabled or duration_ms <= 0:
        return
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        return

    steps = 5

    def frame(index: int) -> None:
        try:
            if not window.winfo_exists():
                return
            window.attributes("-alpha", min(1.0, index / steps))
            if index < steps:
                window.after(max(1, duration_ms // steps), lambda: frame(index + 1))
        except tk.TclError:
            pass

    frame(0)
