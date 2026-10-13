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


class Animation:
    """A running :func:`animate`; ``cancel()`` stops it where it is (``value`` keeps the last set number)."""

    def __init__(self, widget: tk.Misc) -> None:
        self.widget = widget
        self.after_id: str | None = None
        self.value: float = 0.0
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None


def animate(
    widget: tk.Misc,
    start: float,
    end: float,
    duration_ms: int,
    setter: Callable[[float], None],
    *,
    enabled: bool = True,
    steps: int = 8,
    done: Callable[[], None] | None = None,
) -> Animation:
    """Ease-out (cubic) a number from ``start`` to ``end`` on Tk's event loop — heights, positions, progress."""
    handle = Animation(widget)
    if not enabled or duration_ms <= 0 or steps < 2:
        handle.value = end
        setter(end)
        if done:
            done()
        return handle

    def frame(index: int) -> None:
        handle.after_id = None
        if handle.cancelled:
            return
        try:
            if not widget.winfo_exists():
                return
            t = index / steps
            handle.value = start + (end - start) * (1 - (1 - t) ** 3)
            setter(round(handle.value, 3) if index < steps else end)
            if index >= steps:
                if done:
                    done()
                return
            handle.after_id = widget.after(max(1, duration_ms // steps), lambda: frame(index + 1))
        except tk.TclError:
            return

    frame(0)
    return handle
