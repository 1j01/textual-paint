"""Drawing utilities for use with the AnsiArtDocument class."""

from typing import TYPE_CHECKING, Iterator

from textual.geometry import Offset, Region

if TYPE_CHECKING:
    from textual_paint.paint import AnsiArtDocument


def bresenham_walk(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
    """Bresenham's line algorithm"""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err = err - dy
            x0 = x0 + sx
        if e2 < dx:
            err = err + dx
            y0 = y0 + sy


def polygon_walk(points: list[Offset]) -> Iterator[tuple[int, int]]:
    """Yields points along the perimeter of a polygon."""
    for i in range(len(points)):
        yield from bresenham_walk(
            points[i][0],
            points[i][1],
            points[(i + 1) % len(points)][0],
            points[(i + 1) % len(points)][1]
        )

def polyline_walk(points: list[Offset]) -> Iterator[tuple[int, int]]:
    """Yields points along a polyline (unclosed polygon)."""
    for i in range(len(points) - 1):
        yield from bresenham_walk(
            points[i][0],
            points[i][1],
            points[i + 1][0],
            points[i + 1][1]
        )

def is_inside_polygon(x: int, y: int, points: list[Offset]) -> bool:
    """Returns True if the point is inside the polygon."""
    # https://stackoverflow.com/a/217578
    # Actually I just got this from Copilot, and don't know the source
    n = len(points)
    inside = False
    p1x, p1y = points[0]
    for i in range(n + 1):
        p2x, p2y = points[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    x_intersection: float = x  # Avoid "possibly unbound" type checker error
                    # I don't know if this is right; should it flip `inside` in this case?
                    # Is this an actual case that can occur, where p1y == p2y AND p1x != p2x?
                    if p1y != p2y:
                        x_intersection = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= x_intersection:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# def polygon_fill(points: list[Offset]) -> Iterator[tuple[int, int]]:
#     """Yields points inside a polygon."""

#     # Find the bounding box
#     min_x = min(points, key=lambda p: p[0])[0]
#     min_y = min(points, key=lambda p: p[1])[1]
#     max_x = max(points, key=lambda p: p[0])[0]
#     max_y = max(points, key=lambda p: p[1])[1]

#     # Check each point in the bounding box, and yield any points that are inside the polygon
#     for x in range(min_x, max_x + 1):
#         for y in range(min_y, max_y + 1):
#             if is_inside_polygon(x, y, points):
#                 yield x, y

# adapted from https://github.com/Pomax/bezierjs
def compute_bezier(t: float, start_x: float, start_y: float, control_1_x: float, control_1_y: float, control_2_x: float, control_2_y: float, end_x: float, end_y: float) -> tuple[float, float]:
    """Returns a point along a bezier curve."""
    mt = 1 - t
    mt2 = mt * mt
    t2 = t * t

    a = mt2 * mt
    b = mt2 * t * 3
    c = mt * t2 * 3
    d = t * t2

    return (
        a * start_x + b * control_1_x + c * control_2_x + d * end_x,
        a * start_y + b * control_1_y + c * control_2_y + d * end_y,
    )

# It's possible to walk a bezier curve more correctly,
# but is it possible to tell the difference?
def bezier_curve_walk(start_x: float, start_y: float, control_1_x: float, control_1_y: float, control_2_x: float, control_2_y: float, end_x: float, end_y: float) -> Iterator[tuple[int, int]]:
    """Yields points along a bezier curve."""
    steps = 100
    point_a = (start_x, start_y)
    # TypeError: 'float' object cannot be interpreted as an integer
    # for t in range(0, 1, 1 / steps):
    for i in range(steps):
        t = i / steps
        point_b = compute_bezier(t, start_x, start_y, control_1_x, control_1_y, control_2_x, control_2_y, end_x, end_y)
        yield from bresenham_walk(int(point_a[0]), int(point_a[1]), int(point_b[0]), int(point_b[1]))
        point_a = point_b

def quadratic_curve_walk(start_x: float, start_y: float, control_x: float, control_y: float, end_x: float, end_y: float) -> Iterator[tuple[int, int]]:
    """Yields points along a quadratic curve."""
    return bezier_curve_walk(start_x, start_y, control_x, control_y, control_x, control_y, end_x, end_y)

def midpoint_ellipse(xc: int, yc: int, rx: int, ry: int) -> Iterator[tuple[int, int]]:
    """Midpoint ellipse drawing algorithm. Yields points out of order, and thus can't legally be called a "walk", except in Britain."""
    # Source: https://www.geeksforgeeks.org/midpoint-ellipse-drawing-algorithm/

    x = 0
    y = ry

    # Initial decision parameter of region 1
    d1 = ((ry * ry) - (rx * rx * ry) +
                      (0.25 * rx * rx))
    dx = 2 * ry * ry * x
    dy = 2 * rx * rx * y

    # For region 1
    while (dx < dy):
        # Yield points based on 4-way symmetry
        yield x + xc, y + yc
        yield -x + xc, y + yc
        yield x + xc, -y + yc
        yield -x + xc, -y + yc

        # Checking and updating value of
        # decision parameter based on algorithm
        if (d1 < 0):
            x += 1
            dx = dx + (2 * ry * ry)
            d1 = d1 + dx + (ry * ry)
        else:
            x += 1
            y -= 1
            dx = dx + (2 * ry * ry)
            dy = dy - (2 * rx * rx)
            d1 = d1 + dx - dy + (ry * ry)

    # Decision parameter of region 2
    d2 = (((ry * ry) * ((x + 0.5) * (x + 0.5))) +
          ((rx * rx) * ((y - 1) * (y - 1))) -
           (rx * rx * ry * ry))

    # Plotting points of region 2
    while (y >= 0):
        # Yielding points based on 4-way symmetry
        yield x + xc, y + yc
        yield -x + xc, y + yc
        yield x + xc, -y + yc
        yield -x + xc, -y + yc

        # Checking and updating parameter
        # value based on algorithm
        if (d2 > 0):
            y -= 1
            dy = dy - (2 * rx * rx)
            d2 = d2 + (rx * rx) - dy
        else:
            y -= 1
            x += 1
            dx = dx + (2 * ry * ry)
            dy = dy - (2 * rx * rx)
            d2 = d2 + dx - dy + (rx * rx)

def flood_fill(document: 'AnsiArtDocument', x: int, y: int, fill_ch: str, fill_fg: str, fill_bg: str) -> Region|None:
    """Flood fill algorithm."""

    # Get the original value of the cell.
    # This is the color to be replaced.
    original_fg = document.fg[y][x]
    original_bg = document.bg[y][x]
    original_ch = document.ch[y][x]

    # Track the region affected by the fill.
    min_x = x
    min_y = y
    max_x = x
    max_y = y

    def inside(x: int, y: int) -> bool:
        """Returns true if the cell at the given coordinates matches the color to be replaced. Treats foreground color as equal if character is a space."""
        if x < 0 or x >= document.width or y < 0 or y >= document.height:
            return False
        return (
            document.ch[y][x] == original_ch and
            document.bg[y][x] == original_bg and
            (original_ch == " " or document.fg[y][x] == original_fg) and
            (document.ch[y][x] != fill_ch or document.bg[y][x] != fill_bg or document.fg[y][x] != fill_fg)
        )

    def set_cell(x: int, y: int) -> None:
        """Sets the cell at the given coordinates to the fill color, and updates the region bounds."""
        document.ch[y][x] = fill_ch
        document.fg[y][x] = fill_fg
        document.bg[y][x] = fill_bg
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    # Simple translation of the "final, combined-scan-and-fill span filler"
    # pseudo-code from https://en.wikipedia.org/wiki/Flood_fill
    if not inside(x, y):
        return None
    stack: list[tuple[int, int, int, int]] = [(x, x, y, 1), (x, x, y - 1, -1)]
    while stack:
        x1, x2, y, dy = stack.pop()
        x = x1
        if inside(x, y):
            while inside(x - 1, y):
                set_cell(x - 1, y)
                x = x - 1
        if x < x1:
            stack.append((x, x1-1, y-dy, -dy))
        while x1 <= x2:
            while inside(x1, y):
                set_cell(x1, y)
                x1 = x1 + 1
                stack.append((x, x1 - 1, y+dy, dy))
                if x1 - 1 > x2:
                    stack.append((x2 + 1, x1 - 1, y-dy, -dy))
            x1 = x1 + 1
            while x1 < x2 and not inside(x1, y):
                x1 = x1 + 1
            x = x1

    # Return the affected region.
    return Region(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
