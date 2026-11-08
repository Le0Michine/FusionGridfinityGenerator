"""
Where long bin walls get folded in to stiffen them, origami style. Each straight wall is split into panels, every panel
is pressed in along a ridge, which makes two triangles at its ends and two trapezoids, the larger one below the ridge:

    ┌──────────────────┐
    │ ╲              ╱ │
    │   A──────────B   │   ridge, the fold depth in from the wall
    │  ╱            ╲  │
    │╱                ╲│
    └──────────────────┘

The panel edges stay in the wall, so the wall keeps its outline and only folds in between.
"""

import math

from . import binShape

# ridge height up the panel, the lower trapezoid takes the larger part
RIDGE_HEIGHT_RATIO = 0.7
# width of the triangles at each end of a panel, as a part of its width
TRIANGLE_WIDTH_RATIO = 0.25

class WallSide:
    """
    A straight side of the outline in grid units. It runs along the axis, 'x' or 'y', on the grid line of the other
    axis, from start to end, start being the smaller. Inward is the direction of the bin interior across the line, 1 or -1
    """
    def __init__(self, axis: str, line: int, inward: int, start: int, end: int):
        self.axis = axis
        self.line = line
        self.inward = inward
        self.start = start
        self.end = end

    def __eq__(self, other):
        return isinstance(other, WallSide) and vars(self) == vars(other)

    def __repr__(self):
        return f'WallSide({self.axis!r}, {self.line}, {self.inward}, {self.start}, {self.end})'

def wallSides(cells) -> list[WallSide]:
    """Straight sides around a valid shape, the outline's, see binShape.outline"""
    corners = binShape.outline(cells)
    sides = []
    for (index, (x, y, _)) in enumerate(corners):
        (nextX, nextY, _) = corners[(index + 1) % len(corners)]
        # the outline runs counterclockwise, the inside is on its left
        if y == nextY:
            sides.append(WallSide('x', y, 1 if nextX > x else -1, min(x, nextX), max(x, nextX)))
        else:
            sides.append(WallSide('y', x, 1 if nextY < y else -1, min(y, nextY), max(y, nextY)))
    return sides

def isFrontSide(side: WallSide) -> bool:
    """The front wall of a plain bin, where the scoop is"""
    return side.axis == 'x' and side.line == 0 and side.inward == 1

def straightLength(side: WallSide, unit: float, cornerRadius: float) -> float:
    """
    Length of the flat part of a side, every corner of the outline is centred where a bin's corner is, so on both
    the outside and inside of the wall the corner arcs end the corner radius from the grid point, see binShape.cornerRadius
    """
    return (side.end - side.start) * unit - cornerRadius * 2

def creaseLayout(
    cells,
    unitWidth: float,
    unitLength: float,
    minLength: float,
    maxPanelLength: float,
    skipFront: bool,
) -> list[tuple[WallSide, int]]:
    """
    Creased sides of a bin with their panel count, none when its longest wall is shorter than the min length.
    Lengths of the thresholds are in base units, like the feet, and count whole walls, corners included. Every wall
    is split into as few even panels as keep them under the max, which sets the panel length of the longest one.
    Walls as long as that panel or longer get creases too, their panels stretched to fill them. The front is left
    out for a scoop, which braces it already. Panels themselves only cover the flat part, see straightLength
    """
    def length(side: WallSide) -> float:
        return (side.end - side.start) * (unitWidth if side.axis == 'x' else unitLength)

    def count(side: WallSide) -> int:
        return math.ceil((side.end - side.start) / maxPanelLength)

    sides = [side for side in wallSides(cells) if not (skipFront and isFrontSide(side))]
    if len(sides) == 0:
        return []
    reference = max(sides, key=length)
    if reference.end - reference.start < minLength:
        return []
    panelLength = length(reference) / count(reference)
    return [(side, count(side)) for side in sides if length(side) >= panelLength - 1e-9]
