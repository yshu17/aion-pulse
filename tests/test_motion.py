"""watcher.motion: colour tweens and window fades end in the right state, honour reduce_motion, survive a closed window
(UI/UX items 21-25, re-checked 13.10.2026)."""

import time
import tkinter as tk

import pytest

from watcher.motion import fade_window, tween_color


@pytest.fixture
def root():
    r = tk.Tk()
    yield r
    r.destroy()


def pump(root, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


def test_tween_passes_through_middle_colours_and_ends_on_the_target(root):
    seen = []
    done = []
    tween_color(root, seen.append, "#000000", "#ffffff", 80, steps=4, done=lambda: done.append(True))
    pump(root, 0.3)
    assert seen[0] == "#000000" and seen[-1] == "#ffffff"
    assert len(seen) == 5 and "#808080" in seen  # four steps: 0, 1/4, 1/2, 3/4, 1
    assert done == [True]


def test_disabled_tween_jumps_to_the_target_without_timers(root):
    seen = []
    done = []
    assert tween_color(root, seen.append, "#000000", "#ffffff", 500, enabled=False,
                       done=lambda: done.append(True)) is None
    assert seen == ["#ffffff"] and done == [True]


def test_tween_stops_quietly_when_its_widget_is_destroyed(root):
    label = tk.Label(root)
    seen = []
    tween_color(label, seen.append, "#000000", "#ffffff", 200, steps=4)
    label.destroy()
    pump(root, 0.3)
    assert seen == ["#000000"]  # no frame after the widget is gone, no TclError


def test_fade_window_ends_opaque(root):
    win = tk.Toplevel(root)
    fade_window(win, 60)
    pump(root, 0.3)
    assert float(win.attributes("-alpha")) == pytest.approx(1.0)


def test_fade_window_does_nothing_with_reduced_motion(root):
    win = tk.Toplevel(root)
    fade_window(win, 60, enabled=False)
    assert float(win.attributes("-alpha")) == pytest.approx(1.0)


def test_fade_survives_a_window_closed_mid_way(root):
    win = tk.Toplevel(root)
    fade_window(win, 100)
    win.destroy()
    pump(root, 0.2)  # no TclError from the pending frames


def test_animate_eases_a_number_to_its_end_and_can_be_cancelled(root):
    from watcher.motion import animate
    seen, done = [], []
    animate(root, 0, 100, 80, seen.append, steps=4, done=lambda: done.append(True))
    pump(root, 0.3)
    assert seen[-1] == 100 and done == [True]
    assert seen == sorted(seen) and seen[1] > 25  # ease-out: the first step covers more than a linear quarter
    seen2 = []
    handle = animate(root, 0, 100, 200, seen2.append, steps=8)
    handle.cancel()
    pump(root, 0.3)
    assert seen2 == [0]


def test_animate_without_motion_jumps_to_the_end(root):
    from watcher.motion import animate
    seen = []
    animate(root, 0, 100, 200, seen.append, enabled=False)
    assert seen == [100]
