"""
Bin footprints made of base grid cells, like tetris pieces: which cells a bin covers and the outline around them.
Cells are (x, y) pairs with x along the bin width and y along its length, both from the front left corner.
"""

# 4-neighbours, a shape is held together by shared sides, cells touching at a corner only aren't connected
_NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

ERROR_EMPTY = 'Pick at least one cell'
ERROR_NOT_CONNECTED = 'All cells must form one piece, joined along their sides'
ERROR_HOLES = 'Shapes with holes are not supported yet'

def rectangle(columns: int, rows: int) -> list[tuple[int, int]]:
    return [(x, y) for x in range(columns) for y in range(rows)]

def normalizeShape(cells, columns: int, rows: int) -> list[tuple[int, int]]:
    """Cells within the grid, each once, sorted by column then row. Untrusted entries, e.g. from the drawing, are dropped"""
    result = set()
    for cell in cells or []:
        try:
            (x, y) = (int(cell[0]), int(cell[1]))
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        if 0 <= x < columns and 0 <= y < rows:
            result.add((x, y))
    return sorted(result)

def isRectangle(cells, columns: int, rows: int) -> bool:
    """Every cell of the grid, a plain bin"""
    return set(normalizeShape(cells, columns, rows)) == set(rectangle(columns, rows))

def isConnected(cells) -> bool:
    remaining = set(cells)
    if len(remaining) == 0:
        return False
    stack = [remaining.pop()]
    while stack:
        (x, y) = stack.pop()
        for (dx, dy) in _NEIGHBOURS:
            neighbour = (x + dx, y + dy)
            if neighbour in remaining:
                remaining.remove(neighbour)
                stack.append(neighbour)
    return len(remaining) == 0

def hasHoles(cells) -> bool:
    """
    Empty cells closed in by the shape. Empty space only leaks out along sides too, so two cells touching at a corner
    with empty cells beside them close one of those in, the walls would have nothing between them there
    """
    filled = set(cells)
    if len(filled) == 0:
        return False
    minX = min(x for (x, _) in filled) - 1
    maxX = max(x for (x, _) in filled) + 1
    minY = min(y for (_, y) in filled) - 1
    maxY = max(y for (_, y) in filled) + 1
    outside = {(minX, minY)}
    stack = [(minX, minY)]
    while stack:
        (x, y) = stack.pop()
        for (dx, dy) in _NEIGHBOURS:
            neighbour = (x + dx, y + dy)
            if minX <= neighbour[0] <= maxX and minY <= neighbour[1] <= maxY and neighbour not in filled and neighbour not in outside:
                outside.add(neighbour)
                stack.append(neighbour)
    empty = (maxX - minX + 1) * (maxY - minY + 1) - len(filled)
    return len(outside) < empty

def shapeError(cells) -> str | None:
    """Why a shape can't be built, none when it can"""
    cells = set(cells)
    if len(cells) == 0:
        return ERROR_EMPTY
    if not isConnected(cells):
        return ERROR_NOT_CONNECTED
    if hasHoles(cells):
        return ERROR_HOLES
    return None

def outline(cells) -> list[tuple[int, int, bool]]:
    """
    Corners around a valid shape in grid units, counterclockwise from the lowest corner of the leftmost column.
    Each is (x, y, isConvex), convex corners point out of the shape, the others are inner corners like the one of an L
    """
    filled = set(cells)
    # sides of the cells facing outwards, directed so the shape is on their left
    edges: dict[tuple[int, int], tuple[int, int]] = {}
    for (x, y) in filled:
        if (x, y - 1) not in filled:
            edges[(x, y)] = (x + 1, y)
        if (x + 1, y) not in filled:
            edges[(x + 1, y)] = (x + 1, y + 1)
        if (x, y + 1) not in filled:
            edges[(x + 1, y + 1)] = (x, y + 1)
        if (x - 1, y) not in filled:
            edges[(x, y + 1)] = (x, y)
    start = min(edges)
    points = [start]
    point = edges[start]
    while point != start:
        points.append(point)
        point = edges[point]
    # only the points where the outline turns
    corners = []
    for (index, point) in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        incoming = (point[0] - previous[0], point[1] - previous[1])
        outgoing = (following[0] - point[0], following[1] - point[1])
        turn = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
        if turn != 0:
            corners.append((point[0], point[1], turn > 0))
    return corners

def wallJunctions(cells) -> list[tuple[int, int]]:
    """
    Grid points along the outline where feet meet under the outer wall, each needs a pocket curving up the gap
    between them, see baseGenerator.cutWallJunctionPockets. That's every point along a side and every inner corner,
    the wall bulges over the gap there too. Outer corners have a single foot under them
    """
    corners = outline(cells)
    junctions = []
    for (index, (x, y, isConvex)) in enumerate(corners):
        if not isConvex:
            junctions.append((x, y))
        (nextX, nextY, _) = corners[(index + 1) % len(corners)]
        (dx, dy) = (_sign(nextX - x), _sign(nextY - y))
        steps = abs(nextX - x) + abs(nextY - y)
        junctions += [(x + dx * step, y + dy * step) for step in range(1, steps)]
    return sorted(junctions)

def innerCornerOpenings(cells) -> dict[tuple[int, int], tuple[int, int]]:
    """
    Inner corners of the outline with the direction of the empty cell beside them, (-1, -1) for the one left and
    in front of the corner. A pocket there has no foot to curve around on that side
    """
    filled = set(cells)
    openings = {}
    for (x, y, isConvex) in outline(cells):
        if isConvex:
            continue
        for (dx, dy) in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            # cells meeting at a grid point start there or one before it
            if (x + min(dx, 0), y + min(dy, 0)) not in filled:
                openings[(x, y)] = (dx, dy)
    return openings

def insetOutline(corners: list[tuple[int, int, bool]], unitWidth: float, unitLength: float, offset: float) -> list[tuple[float, float, bool]]:
    """
    The outline scaled to the base units and moved inwards by the offset all around, the clearance for the outside
    of the bin, plus the wall thickness for the inside. Every side keeps its direction, so a corner moves along both sides it joins
    """
    result = []
    count = len(corners)
    for (index, (x, y, isConvex)) in enumerate(corners):
        (previousX, previousY, _) = corners[index - 1]
        (nextX, nextY, _) = corners[(index + 1) % count]
        # the inside is left of a counterclockwise side, its normal pointing there is the direction turned a quarter left
        normals = [_leftNormal(x - previousX, y - previousY), _leftNormal(nextX - x, nextY - y)]
        result.append((
            x * unitWidth + offset * (normals[0][0] + normals[1][0]),
            y * unitLength + offset * (normals[0][1] + normals[1][1]),
            isConvex,
        ))
    return result

def _leftNormal(dx: float, dy: float) -> tuple[int, int]:
    return (-_sign(dy), _sign(dx))

def _sign(value: float) -> int:
    return (value > 0) - (value < 0)

def cornerRadius(isConvex: bool, cellCornerRadius: float, offset: float) -> float:
    """
    Radius of a corner of the outline moved in by the offset, see insetOutline. Every corner is centred where a bin's
    corner is, the cell corner radius in from the cell lines, so a bin filling an inner corner's notch keeps an even
    gap to it: outer corners get smaller as the outline moves in, inner ones bigger, by the offset both
    """
    return cellCornerRadius - offset if isConvex else cellCornerRadius + offset
