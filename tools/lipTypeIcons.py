"""
Draws the lip type dropdown icons: the profile of a bin's wall cut through, the lip on top, the outside on the
right, with the top trimmed as the dialog starts. Stretched across, to read at 16 pixels, drawn as an outline open at
the bottom, where the wall goes on.

    python3 tools/lipTypeIcons.py

Writes an svg per lip type to commands/commandCreateBin/resources/lipTypes/ and renders the dropdown pictures
from it into a folder of the same name, as tools/labelIcons.py does for the label icons.
"""

import math
import os

import labelIcons

ICONS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'commands', 'commandCreateBin', 'resources', 'lipTypes')
# icon units per mm, across stretched for the lip to show at 16 pixels, where the outside of the wall is and where the
# bin top, the lip's bottom, is. The lip fills the height, the full lip's support ends near the bottom
SCALE_X = 20
SCALE_Y = 13
OUTSIDE_X = 76
BIN_TOP_Y = 54
# lip and wall in mm: lip height, how much the top is trimmed, the bin wall
LIP_HEIGHT = 4.4
TOP_TRIM = 0.6
WALL = 1.2
# the stacking profile from the top: 45 degrees in, straight down, and only for the full lip, 45 degrees to its tip
TOP_SLOPE = 1.9
STRAIGHT = 1.8
TIP_SLOPE = 0.7
# under the full lip's tip a support goes straight down, then out into the wall at 45 degrees
SUPPORT_STRAIGHT = 1.2
# below the icon, the wall goes on past its bottom
WALL_BOTTOM_Y = 110
# the outline's width in icon units, a pixel at 16 pixels
LINE = 7

def point(inset: float, z: float) -> tuple[float, float]:
    """A point in mm, inset from the outside and up from the bin top, in icon units"""
    return (OUTSIDE_X - inset * SCALE_X, BIN_TOP_Y - z * SCALE_Y)

def loop(corners: list[tuple[float, float]]) -> str:
    return f'M{corners[0][0]:.2f},{corners[0][1]:.2f} ' + ' '.join(f'L{x:.2f},{y:.2f}' for x, y in corners[1:]) + ' Z'

def inset(corners: list[tuple[float, float]], distance: float) -> list[tuple[float, float]]:
    """The polygon with every edge moved in by the distance, its corners where the moved edges meet"""
    area = sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]))
    # inward is to the left of an edge going clockwise in the icon's y down coordinates
    side = 1 if area > 0 else -1
    lines = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        length = math.hypot(bx - ax, by - ay)
        (nx, ny) = (-(by - ay) / length * side, (bx - ax) / length * side)
        lines.append(((ax + nx * distance, ay + ny * distance), (bx - ax, by - ay)))
    result = []
    for ((p, d), (q, e)) in zip(lines[-1:] + lines[:-1], lines):
        cross = d[0] * e[1] - d[1] * e[0]
        t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / cross
        result.append((p[0] + d[0] * t, p[1] + d[1] * t))
    return result

def profile(points: list[tuple[float, float]]) -> str:
    """
    The outline of the wall from the bottom of the icon on the outside, around the lip and down the inside, open at the
    bottom
    """
    corners = [(OUTSIDE_X, WALL_BOTTOM_Y), point(0, LIP_HEIGHT - TOP_TRIM), point(TOP_TRIM, LIP_HEIGHT - TOP_TRIM), *points, (OUTSIDE_X - WALL * SCALE_X, WALL_BOTTOM_Y)]
    inner = inset(corners, LINE)
    # the inside runs past the bottom, the sides go down along the wall
    for index in [0, -1]:
        inner[index] = (inner[index][0], WALL_BOTTOM_Y + LINE * 2)
    return f'{loop(corners)} {loop(inner)}'

def lightLip() -> str:
    """The inside straight down from the end of the top slope, a chamfer under it into the wall"""
    return profile([
        point(TOP_SLOPE, LIP_HEIGHT - TOP_SLOPE),
        point(TOP_SLOPE, 0),
        point(WALL, -(TOP_SLOPE - WALL)),
    ])

def fullLip() -> str:
    """The original profile narrowing to a tip, the support under it"""
    tip = TOP_SLOPE + TIP_SLOPE
    tipZ = LIP_HEIGHT - TOP_SLOPE - STRAIGHT - TIP_SLOPE
    return profile([
        point(TOP_SLOPE, LIP_HEIGHT - TOP_SLOPE),
        point(TOP_SLOPE, LIP_HEIGHT - TOP_SLOPE - STRAIGHT),
        point(tip, tipZ),
        point(tip, tipZ - SUPPORT_STRAIGHT),
        point(WALL, tipZ - SUPPORT_STRAIGHT - (tip - WALL)),
    ])

# by the names of the dropdown's items, binBodyLipGeneratorInput.LIP_TYPES
ICONS = {
    'Light': lightLip(),
    'Full': fullLip(),
}

def main():
    os.makedirs(ICONS_FOLDER, exist_ok=True)
    for name, d in ICONS.items():
        path = os.path.join(ICONS_FOLDER, f'{name}.svg')
        with open(path, 'w') as file:
            file.write(labelIcons.svg(d))
        labelIcons.writePreviews(path)
        print(os.path.relpath(path))

if __name__ == '__main__':
    main()
