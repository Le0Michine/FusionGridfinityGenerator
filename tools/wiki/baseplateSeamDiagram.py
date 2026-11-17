"""
A cross section where two full baseplates meet, for the plate edge clearance and the top trim on
the wiki, in GitHub's light and dark themes. The ridge is the one of the bin xy clearance diagram, the clearances are
drawn larger than they are to be seen.

    python3 tools/wiki/baseplateSeamDiagram.py
"""

import os

from clearanceDiagram import BASE_HEIGHT, OUTPUT, THEMES, ridgeSide

NAME = 'baseplate-seam'
# mm, drawn instead of the 0.05mm default plate edge clearance, the 0.25mm bin xy clearance and the 0.5mm top
# trim, the edge short of where the ridge's cut top ends
EDGE_CLEARANCE = 0.45
CLEARANCE = 0.6
VERTICAL_CLEARANCE = 1.2 + CLEARANCE
# mm, drawn thinner than the 6.4mm default extra bottom thickness
EXTRA_BOTTOM = 2.6
# mm, how much of each plate is shown on either side of the grid line, and down to up
HALF_WIDTH = 8.5
LOWEST = -EXTRA_BOTTOM
HIGHEST = BASE_HEIGHT + 1.6

SCALE = 34
MARGIN_LEFT = 24
MARGIN_TOP = 52
MARGIN_BOTTOM = 118
WIDTH = HALF_WIDTH * 2 * SCALE + MARGIN_LEFT * 2
TOTAL_HEIGHT = (HIGHEST - LOWEST) * SCALE + MARGIN_TOP + MARGIN_BOTTOM


def point(x: float, z: float) -> str:
    """Drawing coordinates of a point in mm, x from the grid line, z up from the bottom of the sockets"""
    return f'{MARGIN_LEFT + (x + HALF_WIDTH) * SCALE:.1f},{MARGIN_TOP + (HIGHEST - z) * SCALE:.1f}'


def xy(x: float, z: float) -> tuple[float, float]:
    return tuple(map(float, point(x, z).split(',')))


def plateSide(side: int) -> list[tuple[float, float]]:
    """
    The plate on the right of the grid line, or the left one for -1: its bottom, the socket on its far side and the
    half ridge at the seam, which stops the plate edge clearance short of the grid line
    """
    ridge = ridgeSide(CLEARANCE, VERTICAL_CLEARANCE, EDGE_CLEARANCE)
    outline = [(HALF_WIDTH, LOWEST), (EDGE_CLEARANCE, LOWEST), *ridge[::-1], (HALF_WIDTH, 0)]
    return outline if side > 0 else [(-x, z) for (x, z) in outline]


def polygon(points: list[tuple[float, float]], fill: str, stroke: str) -> str:
    return f'<polygon points="{" ".join(point(x, z) for (x, z) in points)}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>'


def label(x: float, z: float, text: str, color: str, anchor: str = 'middle', bold: bool = False) -> str:
    (px, py) = xy(x, z)
    weight = ' font-weight="600"' if bold else ''
    return f'<text x="{px:.1f}" y="{py + 5:.1f}" text-anchor="{anchor}" fill="{color}"{weight}>{text}</text>'


def arrowHead(x: float, y: float, dx: float, dy: float, color: str) -> str:
    """An arrow head with its tip at the point, pointing along the direction, a unit vector"""
    (length, half) = (9, 4)
    (bx, by) = (x - dx * length, y - dy * length)
    return f'<polygon points="{x:.1f},{y:.1f} {bx - dy * half:.1f},{by + dx * half:.1f} {bx + dy * half:.1f},{by - dx * half:.1f}" fill="{color}"/>'


def gapDimension(x1: float, x2: float, z: float, color: str, tail: float = 1.0) -> str:
    """Arrows pointing in at a narrow horizontal gap from outside it, tails in mm"""
    ((lx, y), (rx, _)) = (xy(min(x1, x2), z), xy(max(x1, x2), z))
    return '\n'.join([
        f'<line x1="{lx - tail * SCALE:.1f}" y1="{y:.1f}" x2="{lx:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.5"/>',
        f'<line x1="{rx:.1f}" y1="{y:.1f}" x2="{rx + tail * SCALE:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.5"/>',
        arrowHead(lx, y, 1, 0, color),
        arrowHead(rx, y, -1, 0, color),
    ])


def heightDimension(x: float, z1: float, z2: float, color: str, tail: float = 0.9) -> str:
    """Arrows pointing in at a narrow vertical gap from above and below it"""
    ((_, top), (px, bottom)) = (xy(x, max(z1, z2)), xy(x, min(z1, z2)))
    return '\n'.join([
        f'<line x1="{px:.1f}" y1="{top - tail * SCALE:.1f}" x2="{px:.1f}" y2="{top:.1f}" stroke="{color}" stroke-width="1.5"/>',
        f'<line x1="{px:.1f}" y1="{bottom:.1f}" x2="{px:.1f}" y2="{bottom + tail * SCALE:.1f}" stroke="{color}" stroke-width="1.5"/>',
        arrowHead(px, top, 0, 1, color),
        arrowHead(px, bottom, 0, -1, color),
    ])


def dashed(points: list[tuple[float, float]], color: str) -> str:
    return f'<polyline points="{" ".join(point(x, z) for (x, z) in points)}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="5 4"/>'


def diagram(theme: str) -> str:
    colors = THEMES[theme]
    top = BASE_HEIGHT - VERTICAL_CLEARANCE
    ((gridX, gridTop), (_, gridBottom)) = (xy(0, HIGHEST - 0.3), xy(0, LOWEST - 0.6))
    # the ridge before the cut, its faces meeting the bin xy clearance below the top of the plate, see ridgeSide
    peak = [(-(VERTICAL_CLEARANCE - CLEARANCE), top), (0, BASE_HEIGHT - CLEARANCE), (VERTICAL_CLEARANCE - CLEARANCE, top)]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH:.0f}" height="{TOTAL_HEIGHT:.0f}" viewBox="0 0 {WIDTH:.0f} {TOTAL_HEIGHT:.0f}" '
        f'font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif" font-size="15">',
        polygon(plateSide(-1), colors['plate'], colors['plateEdge']),
        polygon(plateSide(1), colors['plate'], colors['plateEdge']),
        dashed(peak, colors['plateEdge']),
        f'<line x1="{gridX:.1f}" y1="{gridTop:.1f}" x2="{gridX:.1f}" y2="{gridBottom:.1f}" stroke="{colors["line"]}" stroke-width="1.5" stroke-dasharray="6 5"/>',
        label(0, HIGHEST + 0.2, 'grid line', colors['text']),
        label(-HALF_WIDTH + 0.4, LOWEST + EXTRA_BOTTOM / 2, 'plate', colors['text'], 'start'),
        label(HALF_WIDTH - 0.4, LOWEST + EXTRA_BOTTOM / 2, 'plate', colors['text'], 'end'),
        label(-HALF_WIDTH + 0.4, 1.0, 'socket', colors['text'], 'start'),
        label(HALF_WIDTH - 0.4, 1.0, 'socket', colors['text'], 'end'),
        # the gap down the seam, told under the drawing
        gapDimension(0, EDGE_CLEARANCE, LOWEST + 1.7, colors['mark']),
        gapDimension(-EDGE_CLEARANCE, EDGE_CLEARANCE, LOWEST + 0.7, colors['mark']),
        label(0, LOWEST - 1.1, 'plate edge clearance from the grid line', colors['mark'], bold=True),
        label(0, LOWEST - 1.8, '2 × plate edge clearance between plates', colors['mark'], bold=True),
        # what the cut takes off the ridge, told beside it
        heightDimension(VERTICAL_CLEARANCE + 0.9, top, BASE_HEIGHT, colors['mark']),
        f'<line x1="{xy(0, BASE_HEIGHT)[0]:.1f}" y1="{xy(0, BASE_HEIGHT)[1]:.1f}" x2="{xy(VERTICAL_CLEARANCE + 1.3, BASE_HEIGHT)[0]:.1f}" y2="{xy(0, BASE_HEIGHT)[1]:.1f}" stroke="{colors["mark"]}" stroke-width="1" stroke-dasharray="3 3"/>',
        label(VERTICAL_CLEARANCE + 1.4, (top + BASE_HEIGHT) / 2, 'top trim', colors['mark'], 'start', True),
        f'<text x="{WIDTH / 2:.0f}" y="{TOTAL_HEIGHT - 14:.0f}" text-anchor="middle" fill="{colors["line"]}" font-size="13">'
        'Not to scale, the clearances and the trim are drawn larger to be seen</text>',
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
