"""core/map/poi.py: the map's icon groups."""

from core.map.poi import Poi, cluster


def test_icon_groups_do_not_change_while_the_map_is_dragged():
    """Dragging at one zoom must not merge, split or move icons: the cells are laid out from the map's origin."""
    points = [Poi("z", "merchant", 100 + 37 * i % 211, 200 + 53 * i % 197, 0, 0, f"p{i}") for i in range(60)]
    zoom, radius = 0.45, 36.0

    def groups(left, top):
        to_screen = lambda x, y: ((x - left) * zoom, (y - top) * zoom)
        return {frozenset(m.name for m in members): (round(sx + left * zoom, 6), round(sy + top * zoom, 6))
                for sx, sy, members in cluster(points, to_screen, radius)}

    base = groups(0.0, 0.0)
    for left, top in ((13.3, 0.0), (0.0, 41.7), (-77.1, 129.9), (333.3, -250.5)):
        assert groups(left, top) == base  # the same groups at the same map positions, whatever the view
