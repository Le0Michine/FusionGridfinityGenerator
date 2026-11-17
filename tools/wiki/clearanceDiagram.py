"""
A cross section where two bins meet over a baseplate, for the bin xy clearance on the wiki, in GitHub's light and dark
themes. The profile is the base's, see const.BIN_BASE_*, the clearance is drawn larger than it is to be seen.

    python3 tools/wiki/clearanceDiagram.py
"""

import math
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(ROOT_DIR, 'documentation', 'assets', 'diagrams')
NAME = 'bin-xy-clearance'

# mm, the base profile from the bottom up: 45 degrees in, straight up, 45 degrees in, see const.BIN_BASE_*
BOTTOM = 0.8
MIDDLE = 1.8
TOP = 2.4
BASE_HEIGHT = BOTTOM + MIDDLE + TOP
# mm, drawn instead of the 0.25mm default
CLEARANCE = 0.9
WALL = 1.2
FLOOR = 1.2
# mm, where the inside of the wall meets the floor, the bin's 4mm corner radius in by the 0.25mm clearance and the wall,
# see binBodyGenerator.compartmentCutoutFilletRadius
INSIDE_FILLET = 4.0 - 0.25 - WALL
# mm, how much of each bin is shown on either side of the grid line, and how high
HALF_WIDTH = 10.5
HEIGHT = 13.0

SCALE = 26
MARGIN_LEFT = 24
MARGIN_TOP = 64
MARGIN_BOTTOM = 96
WIDTH = HALF_WIDTH * 2 * SCALE + MARGIN_LEFT * 2
TOTAL_HEIGHT = HEIGHT * SCALE + MARGIN_TOP + MARGIN_BOTTOM

THEMES = {
    'light': {'text': '#1f2328', 'line': '#57606a', 'bin': '#4e79a7', 'binEdge': '#2f5277', 'plate': '#b6bec7', 'plateEdge': '#6e7781', 'mark': '#cf222e'},
    'dark': {'text': '#e6edf3', 'line': '#9198a1', 'bin': '#5b8cc4', 'binEdge': '#a9c6e8', 'plate': '#59636e', 'plateEdge': '#9198a1', 'mark': '#ff7b72'},
}


def point(x: float, z: float) -> str:
    """Drawing coordinates of a point in mm, x from the grid line, z up from the baseplate bottom"""
    return f'{MARGIN_LEFT + (x + HALF_WIDTH) * SCALE:.1f},{MARGIN_TOP + (HEIGHT - z) * SCALE:.1f}'


def profile(inset: float) -> list[tuple[float, float]]:
    """The base's side from the bottom up, standing inset from the grid line, on the right of it"""
    return [(inset + BOTTOM + TOP, 0), (inset + TOP, BOTTOM), (inset + TOP, BOTTOM + MIDDLE), (inset, BASE_HEIGHT)]


def mirrored(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(-x, z) for (x, z) in points]


def polygon(points: list[tuple[float, float]], fill: str, stroke: str) -> str:
    return f'<polygon points="{" ".join(point(x, z) for (x, z) in points)}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>'


def binSide(side: int) -> list[tuple[float, float]]:
    """The bin on the right of the grid line, or the left one for -1: its foot, wall and floor, cut off at the side"""
    foot = profile(CLEARANCE)
    # the inside corner rounded, from the wall down to the floor
    (centerX, centerZ) = (CLEARANCE + WALL + INSIDE_FILLET, BASE_HEIGHT + FLOOR + INSIDE_FILLET)
    fillet = [(centerX - INSIDE_FILLET * math.cos(angle), centerZ - INSIDE_FILLET * math.sin(angle)) for angle in (math.radians(step * 5) for step in range(19))]
    outline = [(HALF_WIDTH, 0)] + foot + [(CLEARANCE, HEIGHT), (CLEARANCE + WALL, HEIGHT)] + fillet + [(HALF_WIDTH, BASE_HEIGHT + FLOOR)]
    return outline if side > 0 else mirrored(outline)


def dimension(x1: float, x2: float, z: float, color: str, tail: float = 1.4, rightTail: float = None) -> str:
    """Arrows pointing in at a narrow gap between two x from outside it, tails in mm"""
    (left, right) = (min(x1, x2), max(x1, x2))
    rightTail = tail if rightTail is None else rightTail
    (lx, y) = map(float, point(left, z).split(','))
    (rx, _) = map(float, point(right, z).split(','))
    arrow = 9
    return '\n'.join([
        f'<line x1="{lx - tail * SCALE:.1f}" y1="{y:.1f}" x2="{lx:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.5"/>',
        f'<line x1="{rx:.1f}" y1="{y:.1f}" x2="{rx + rightTail * SCALE:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.5"/>',
        f'<polygon points="{lx:.1f},{y:.1f} {lx - arrow:.1f},{y - 4:.1f} {lx - arrow:.1f},{y + 4:.1f}" fill="{color}"/>',
        f'<polygon points="{rx:.1f},{y:.1f} {rx + arrow:.1f},{y - 4:.1f} {rx + arrow:.1f},{y + 4:.1f}" fill="{color}"/>',
    ])


def leader(points: list[tuple[float, float]], color: str) -> str:
    return f'<polyline points="{" ".join(point(x, z) for (x, z) in points)}" fill="none" stroke="{color}" stroke-width="1.2"/>'


def label(x: float, z: float, text: str, color: str, anchor: str = 'middle', bold: bool = False) -> str:
    """Text with its middle at the height"""
    (px, py) = point(x, z).split(',')
    weight = ' font-weight="600"' if bold else ''
    return f'<text x="{px}" y="{float(py) + 5:.1f}" text-anchor="{anchor}" fill="{color}"{weight}>{text}</text>'


def diagram(theme: str) -> str:
    colors = THEMES[theme]
    # a ridge between sockets, its top on the grid line
    plate = mirrored(profile(0)) + profile(0)[::-1][1:]
    (gridX, gridTop) = point(0, HEIGHT + 0.6).split(',')
    (_, gridBottom) = point(0, -0.8).split(',')
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH:.0f}" height="{TOTAL_HEIGHT:.0f}" viewBox="0 0 {WIDTH:.0f} {TOTAL_HEIGHT:.0f}" '
        f'font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif" font-size="15">',
        polygon(plate, colors['plate'], colors['plateEdge']),
        polygon(binSide(-1), colors['bin'], colors['binEdge']),
        polygon(binSide(1), colors['bin'], colors['binEdge']),
        f'<line x1="{gridX}" y1="{gridTop}" x2="{gridX}" y2="{gridBottom}" stroke="{colors["line"]}" stroke-width="1.5" stroke-dasharray="6 5"/>',
        label(0, HEIGHT + 1.1, 'grid line, every base unit', colors['text']),
        label(-HALF_WIDTH + 0.4, HEIGHT - 1.6, 'bin', colors['text'], 'start'),
        label(HALF_WIDTH - 0.4, HEIGHT - 1.6, 'bin', colors['text'], 'end'),
        label(0, -1.5, 'baseplate', colors['text']),
        # between the bins, each stands the clearance in from the grid line, told inside the right bin
        dimension(-CLEARANCE, CLEARANCE, HEIGHT - 2.6, colors['mark'], rightTail=WALL + 0.5),
        label(CLEARANCE + WALL + 0.8, HEIGHT - 2.6, '2 × clearance between bins', colors['mark'], 'start', True),
        dimension(0, CLEARANCE, HEIGHT - 5.0, colors['mark'], rightTail=WALL + 0.5),
        label(CLEARANCE + WALL + 0.8, HEIGHT - 5.0, 'clearance from the grid line', colors['mark'], 'start', True),
        # the foot in the socket, told under the drawing, the leader goes down the gap
        dimension(TOP, TOP + CLEARANCE, BOTTOM + MIDDLE / 2, colors['mark'], tail=0.9),
        leader([(TOP + CLEARANCE / 2, BOTTOM + MIDDLE / 2 - 0.25), (TOP + CLEARANCE / 2, BOTTOM), (BOTTOM + TOP + CLEARANCE / 2, 0), (BOTTOM + TOP + CLEARANCE / 2, -0.9)], colors['mark']),
        label(BOTTOM + TOP + CLEARANCE / 2, -1.5, 'clearance from the socket', colors['mark'], 'start', True),
        f'<text x="{WIDTH / 2:.0f}" y="{TOTAL_HEIGHT - 14:.0f}" text-anchor="middle" fill="{colors["line"]}" font-size="13">'
        'Not to scale, the clearance is drawn larger to be seen</text>',
        '</svg>',
    ]
    return '\n'.join(parts) + '\n'


if __name__ == '__main__':
    os.makedirs(OUTPUT, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(OUTPUT, f'{NAME}-{theme}.svg')
        with open(path, 'w', encoding='utf-8') as file:
            file.write(diagram(theme))
        print(path)
