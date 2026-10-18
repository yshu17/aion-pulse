import math

from PIL import Image

from watcher.spawn_overlay import enclosing_spawn_circle, paint_spawn_circle


def test_all_groups_are_inside_one_circle():
    groups = [[[0, 0], [30, 20], [10, 40]], [[200, 100], [220, 150]]]
    cx, cy, radius = enclosing_spawn_circle(groups)
    assert all(math.hypot(x-cx, y-cy) < radius for group in groups for x, y in group)
    assert enclosing_spawn_circle([]) is None


def test_circle_is_translucent_and_has_soft_edge():
    base = Image.new('RGB', (200, 200), (40, 40, 40))
    result = paint_spawn_circle(base, (100, 100), 50)
    assert result.getpixel((0, 0)) == (40, 40, 40)
    center = result.getpixel((100, 100))
    assert 40 < center[2] < 165
    assert center[2] > result.getpixel((150, 100))[2] > result.getpixel((165, 100))[2]
