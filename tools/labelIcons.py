"""
Writes the built in label icons and renders dropdown previews for every label icon.

    python3 tools/labelIcons.py

Icons are svg files in lib/gridfinityUtils/labelIcons/<type>/, filled shapes drawn with paths of
absolute M, L, A and Z commands, holes as inner loops. Next to each svg a folder of the same name holds
its dropdown previews. An svg dropped in by hand gets previews too, as long as it sticks to those commands.
"""

import math
import os
import re
import struct
import zlib

ICONS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lib', 'gridfinityUtils', 'labelIcons')
PREVIEW_SIZES = [16, 32]
PREVIEW_COLORS = {'': (0, 0, 0), '-dark': (230, 230, 230)}

def hexagon(cx: float, cy: float, r: float, firstAngle: float = 0) -> str:
    points = [(cx + r * math.cos(math.radians(firstAngle + a)), cy + r * math.sin(math.radians(firstAngle + a))) for a in range(0, 360, 60)]
    return f'M{points[0][0]:.2f},{points[0][1]:.2f} ' + ' '.join(f'L{x:.2f},{y:.2f}' for x, y in points[1:]) + ' Z'

def circle(cx: float, cy: float, r: float) -> str:
    return f'M{cx - r:.2f},{cy:.2f} A{r},{r} 0 1 0 {cx + r:.2f},{cy:.2f} A{r},{r} 0 1 0 {cx - r:.2f},{cy:.2f} Z'

# screws are a side view with the head up next to a top view of the head with its hex socket
SIDE_X, TOP_X, TOP_Y = 7, 66.5, 53.5

def flipY(d: str) -> str:
    """The path mirrored vertically in the 100 by 100 view box, arcs turn the other way"""
    tokens = re.findall(r'[MLAZ]|-?\d*\.?\d+(?:e-?\d+)?', d)
    result, i = [], 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command in ('M', 'L'):
            result.append(f'{command}{tokens[i]},{100 - float(tokens[i + 1]):.2f}')
            i += 2
        elif command == 'A':
            (rx, ry, rotation, largeArc, sweep, x, y) = tokens[i:i + 7]
            result.append(f'A{rx},{ry} {rotation} {largeArc} {1 - int(sweep)} {x},{100 - float(y):.2f}')
            i += 7
        else:
            result.append(command)
    return ' '.join(result)

def socketTopView() -> str:
    return circle(TOP_X, TOP_Y, 26) + ' ' + hexagon(TOP_X, TOP_Y, 13.86, 30)

def socketHeadScrew() -> str:
    x = lambda v: f'{SIDE_X + v:.2f}'
    side = (f'M{x(0)},89.5 L{x(0)},71.5 L{x(2)},69.5 L{x(7.5)},69.5 L{x(7.5)},23 L{x(10)},20.5 L{x(23)},20.5 L{x(25.5)},23 '
            f'L{x(25.5)},69.5 L{x(31)},69.5 L{x(33)},71.5 L{x(33)},89.5 Z')
    return flipY(side) + ' ' + socketTopView()

def domePoints(cx: float, cy: float, rx: float, ry: float, segments: int = 24) -> str:
    """Half ellipse below its center from right to left, as lines: a half ellipse arc is ambiguous enough
    that Fusion's svg import bulges it the other way"""
    points = [(cx + rx * math.cos(math.pi * i / segments), cy + ry * math.sin(math.pi * i / segments)) for i in range(1, segments + 1)]
    return ' '.join(f'L{px:.2f},{py:.2f}' for px, py in points)

def buttonHeadScrew() -> str:
    x = lambda v: f'{SIDE_X + v:.2f}'
    side = (f'M{x(0)},72.5 L{x(7.5)},72.5 L{x(7.5)},23 L{x(10)},20.5 L{x(23)},20.5 L{x(25.5)},23 L{x(25.5)},72.5 '
            f'L{x(33)},72.5 ' + domePoints(SIDE_X + 16.5, 72.5, 16.5, 17) + ' Z')
    return flipY(side) + ' ' + socketTopView()

ICONS = {
    'screws': {
        'socket-head-screw': socketHeadScrew(),
        'button-head-screw': buttonHeadScrew(),
    },
    'nuts': {
        'hex-nut': hexagon(50, 50, 45) + ' ' + circle(50, 50, 22),
        'square-nut': 'M10,10 L90,10 L90,90 L10,90 Z ' + circle(50, 50, 22),
    },
    'washers': {
        'washer': circle(50, 50, 45) + ' ' + circle(50, 50, 20),
    },
}

def svg(d: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">\n  <path fill-rule="evenodd" d="{d}"/>\n</svg>\n'

def arcPoints(start, rx, ry, rotation, largeArc, sweep, end, segments=32):
    """Points along an svg endpoint arc, by the center conversion of the svg spec"""
    (x1, y1), (x2, y2) = start, end
    phi = math.radians(rotation)
    cosPhi, sinPhi = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cosPhi * dx + sinPhi * dy, -sinPhi * dx + cosPhi * dy
    scale = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    numerator = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    factor = math.sqrt(max(0, numerator / (rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2)))
    if largeArc == sweep:
        factor = -factor
    cxp, cyp = factor * rx * y1p / ry, -factor * ry * x1p / rx
    cx, cy = cosPhi * cxp - sinPhi * cyp + (x1 + x2) / 2, sinPhi * cxp + cosPhi * cyp + (y1 + y2) / 2
    angle = lambda ux, uy: math.atan2(uy, ux)
    theta1 = angle((x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((-x1p - cxp) / rx, (-y1p - cyp) / ry) - theta1
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    points = []
    for i in range(1, segments + 1):
        t = theta1 + delta * i / segments
        px, py = rx * math.cos(t), ry * math.sin(t)
        points.append((cosPhi * px - sinPhi * py + cx, sinPhi * px + cosPhi * py + cy))
    return points

def pathLoops(d: str) -> list[list[tuple[float, float]]]:
    tokens = re.findall(r'[MLAZ]|-?\d*\.?\d+(?:e-?\d+)?', d)
    loops, current, i = [], [], 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command == 'M':
            if current:
                loops.append(current)
            current = [(float(tokens[i]), float(tokens[i + 1]))]
            i += 2
        elif command == 'L':
            current.append((float(tokens[i]), float(tokens[i + 1])))
            i += 2
        elif command == 'A':
            rx, ry, rotation, largeArc, sweep, x, y = [float(v) for v in tokens[i:i + 7]]
            current += arcPoints(current[-1], rx, ry, rotation, int(largeArc), int(sweep), (x, y))
            i += 7
        elif command == 'Z':
            loops.append(current)
            current = []
        else:
            raise ValueError(f'unsupported path command {command}')
    if current:
        loops.append(current)
    return loops

def svgLoops(text: str) -> tuple[list[list[tuple[float, float]]], tuple[float, float, float, float]]:
    viewBox = [float(v) for v in re.search(r'viewBox="([^"]+)"', text).group(1).replace(',', ' ').split()]
    loops = [loop for d in re.findall(r'\sd="([^"]+)"', text) for loop in pathLoops(d)]
    return loops, viewBox

def render(loops, viewBox, size: int, color: tuple[int, int, int], samples: int = 4) -> bytes:
    """Even odd fill with supersampling, transparent background, as png bytes"""
    (minX, minY, width, height) = viewBox
    scale = size / max(width, height)
    edges = []
    for loop in loops:
        for (ax, ay), (bx, by) in zip(loop, loop[1:] + loop[:1]):
            edges.append(((ax - minX) * scale, (ay - minY) * scale, (bx - minX) * scale, (by - minY) * scale))
    coverage = [[0] * size for _ in range(size)]
    for row in range(size * samples):
        y = (row + 0.5) / samples
        crossings = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay, bx, by) in edges if (ay <= y) != (by <= y))
        for start, end in zip(crossings[0::2], crossings[1::2]):
            for column in range(max(0, math.ceil(start * samples - 0.5)), min(size * samples, math.floor(end * samples - 0.5) + 1)):
                coverage[row // samples][column // samples] += 1
    raw = b''.join(
        b'\x00' + b''.join(struct.pack('BBBB', *color, min(255, round(255 * c / samples ** 2))) for c in line)
        for line in coverage
    )
    chunk = lambda kind, data: struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def writePreviews(svgPath: str):
    loops, viewBox = svgLoops(open(svgPath).read())
    folder = os.path.splitext(svgPath)[0]
    os.makedirs(folder, exist_ok=True)
    for size in PREVIEW_SIZES:
        for suffix, color in PREVIEW_COLORS.items():
            with open(os.path.join(folder, f'{size}x{size}{suffix}.png'), 'wb') as file:
                file.write(render(loops, viewBox, size, color))
            # high resolution screens pick the double size
            with open(os.path.join(folder, f'{size}x{size}@2x{suffix}.png'), 'wb') as file:
                file.write(render(loops, viewBox, size * 2, color))

def main():
    for category, icons in ICONS.items():
        os.makedirs(os.path.join(ICONS_FOLDER, category), exist_ok=True)
        for name, d in icons.items():
            with open(os.path.join(ICONS_FOLDER, category, f'{name}.svg'), 'w') as file:
                file.write(svg(d))
    for root, _, files in os.walk(ICONS_FOLDER):
        for fileName in sorted(files):
            if fileName.lower().endswith('.svg'):
                try:
                    writePreviews(os.path.join(root, fileName))
                except ValueError as err:
                    print(f'{fileName}: no previews, {err}')

if __name__ == '__main__':
    main()
