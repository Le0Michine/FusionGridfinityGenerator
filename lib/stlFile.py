import struct

# Binary STL files of a mesh, each at the origin. Kept free of Fusion imports so it can be unit tested

Vertex = tuple[float, float, float]

def atOrigin(vertices: list[Vertex]) -> list[Vertex]:
    """Moved so they're centered on x and y at 0 and their bottom at z 0, as a body made on its own"""
    if len(vertices) == 0:
        return vertices
    shiftX = -(min(x for (x, _, _) in vertices) + max(x for (x, _, _) in vertices)) / 2
    shiftY = -(min(y for (_, y, _) in vertices) + max(y for (_, y, _) in vertices)) / 2
    shiftZ = -min(z for (_, _, z) in vertices)
    return [(x + shiftX, y + shiftY, z + shiftZ) for (x, y, z) in vertices]

def _normal(a: Vertex, b: Vertex, c: Vertex) -> Vertex:
    """Outward for corners counterclockwise seen from outside, zero for a sliver"""
    (ux, uy, uz) = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    (vx, vy, vz) = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    (nx, ny, nz) = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    return (nx / length, ny / length, nz / length) if length > 0 else (0.0, 0.0, 0.0)

def write(path: str, name: str, vertices: list[Vertex], triangles: list[tuple[int, int, int]]):
    """The triangles in mm, the name in the header, cut to fit its 80 bytes"""
    # readers take a header starting with solid for a text STL
    header = (name if not name.lower().startswith('solid') else f'Body {name}').encode('ascii', 'replace')[:80].ljust(80, b' ')
    with open(path, 'wb') as file:
        file.write(header)
        file.write(struct.pack('<I', len(triangles)))
        for (a, b, c) in triangles:
            corners = (vertices[a], vertices[b], vertices[c])
            file.write(struct.pack('<12fH', *_normal(*corners), *corners[0], *corners[1], *corners[2], 0))
