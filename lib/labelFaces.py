import adsk.core, adsk.fusion

# The letter tops of an outline label: the outline groove cuts each letter out of the tab top face, which leaves it a
# face of its own lying in the plane of the tab top. Inside a letter like o the groove cuts out its hole as well, so in
# a plane the faces nested in an odd number of others are letters and those in an even number the tab or a hole.
# The groove floor nests the same way, in the hole of an o the floor of the groove inside the o lies in that of the
# groove around it, a letter stands out of the groove where a floor lies down in it

# the appearance letters get in Fusion, one for all bins so changing its color changes them all
LABEL_APPEARANCE_NAME = 'Gridfinity label'
LABEL_APPEARANCE_COLOR = '#202020'
# cm, faces this close lie in the same plane
PLANE_TOLERANCE = 1e-4
# cm, how far a face outline may stray from its edges
STROKE_TOLERANCE = 0.001
# points taken along an edge Fusion can't stroke
EDGE_SAMPLES = 32
# cm, a face's point is moved up by this before the ray to +x is cast from it: a point on a letter's middle line meets
# its widest points, where two edges meet, and the edges' ends differ by a rounding, so the ray could cross both
RAY_NUDGE = 1.2345e-6

Point2D = tuple[float, float]
Segment = tuple[Point2D, Point2D]

def isInside(point: Point2D, outline: list[Segment]) -> bool:
    """By the crossings of a ray to +x, the segments only have to close up, in any order"""
    (x, y) = point
    inside = False
    for ((x1, y1), (x2, y2)) in outline:
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside

def letterFlags(points: list[Point2D], outlines: list[list[Segment]]) -> list[bool]:
    """For faces of one plane, a point on each and its outer outline, which are letters: inside an odd number of the others"""
    nudged = [(x, y + RAY_NUDGE) for (x, y) in points]
    return [
        sum(1 for (other, outline) in enumerate(outlines) if other != index and isInside(point, outline)) % 2 == 1
        for (index, point) in enumerate(nudged)
    ]

def _outwardNormal(face: adsk.fusion.BRepFace) -> adsk.core.Vector3D | None:
    (isOk, normal) = face.evaluator.getNormalAtPoint(face.pointOnFace)
    return normal if isOk else None

def _planeBasis(normal: adsk.core.Vector3D) -> tuple[adsk.core.Vector3D, adsk.core.Vector3D]:
    """Two directions across the plane"""
    helper = adsk.core.Vector3D.create(1, 0, 0) if abs(normal.x) < 0.9 else adsk.core.Vector3D.create(0, 1, 0)
    u = normal.crossProduct(helper)
    u.normalize()
    v = normal.crossProduct(u)
    v.normalize()
    return (u, v)

def _project(point: adsk.core.Point3D, u: adsk.core.Vector3D, v: adsk.core.Vector3D) -> Point2D:
    return (point.x * u.x + point.y * u.y + point.z * u.z, point.x * v.x + point.y * v.y + point.z * v.z)

def _strokes(evaluator: adsk.core.CurveEvaluator3D) -> list[adsk.core.Point3D] | None:
    """The curve as a polyline, none when Fusion refuses it"""
    try:
        (isOk, start, end) = evaluator.getParameterExtents()
        if isOk:
            (isOk, points) = evaluator.getStrokes(start, end, STROKE_TOLERANCE)
            if isOk and len(points) >= 2:
                return list(points)
    except RuntimeError:
        pass
    return None

def _sampled(evaluator: adsk.core.CurveEvaluator3D) -> list[adsk.core.Point3D] | None:
    """Points along the curve one by one, short of its ends, those Fusion refuses left out"""
    try:
        (isOk, start, end) = evaluator.getParameterExtents()
    except RuntimeError:
        return None
    if not isOk:
        return None
    points = []
    for index in range(EDGE_SAMPLES + 1):
        # a hair inside, Fusion refuses the very ends of some curves
        fraction = min(max(index / EDGE_SAMPLES, 1e-6), 1 - 1e-6)
        try:
            (isOk, point) = evaluator.getPointAtParameter(start + (end - start) * fraction)
        except RuntimeError:
            continue
        if isOk:
            points.append(point)
    return points if len(points) >= 2 else None

def _edgePoints(edge: adsk.fusion.BRepEdge) -> list[adsk.core.Point3D]:
    """
    The edge as a polyline. Fusion refuses some edges of text, a closed one as the outside of an o is a whole letter's
    outline, so its curve is tried as well and points taken one by one
    """
    points = _strokes(edge.evaluator) or _strokes(edge.geometry.evaluator) or _sampled(edge.evaluator)
    if points is not None:
        return points
    from .gridfinityUtils import commonUtils
    commonUtils.debugLog(f'label face edge of {edge.length * 10:.2f} mm not traced, only its ends used')
    return [edge.startVertex.geometry, edge.endVertex.geometry]

def _outerOutline(face: adsk.fusion.BRepFace, u: adsk.core.Vector3D, v: adsk.core.Vector3D) -> list[Segment]:
    segments = []
    for loop in face.loops:
        if not loop.isOuter:
            continue
        for edge in loop.edges:
            projected = [_project(point, u, v) for point in _edgePoints(edge)]
            segments += zip(projected, projected[1:])
    return segments

def outlineLetterFaces(body: adsk.fusion.BRepBody) -> list[adsk.fusion.BRepFace]:
    """The letter and icon tops of the outline labels on the body, faces looking up nested in their plane, see letterFlags"""
    planes: dict[tuple, list[tuple[adsk.fusion.BRepFace, adsk.core.Vector3D]]] = {}
    for face in body.faces:
        if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
            continue
        normal = _outwardNormal(face)
        if normal is None or normal.z <= 0:
            continue
        normal.normalize()
        point = face.pointOnFace
        offset = normal.x * point.x + normal.y * point.y + normal.z * point.z
        key = (round(normal.x, 4), round(normal.y, 4), round(normal.z, 4), round(offset / PLANE_TOLERANCE))
        planes.setdefault(key, []).append((face, normal))

    letters = []
    for faces in planes.values():
        if len(faces) < 2:
            continue
        (u, v) = _planeBasis(faces[0][1])
        points = [_project(face.pointOnFace, u, v) for (face, _) in faces]
        outlines = [_outerOutline(face, u, v) for (face, _) in faces]
        letters += [face for ((face, normal), isLetter) in zip(faces, letterFlags(points, outlines)) if isLetter and _isRaised(face, normal)]
    return letters

def _isRaised(face: adsk.fusion.BRepFace, normal: adsk.core.Vector3D) -> bool:
    """Whether the faces around it go down from it, as the groove walls around a letter, or up, as around a groove floor"""
    point = face.pointOnFace
    for loop in face.loops:
        if not loop.isOuter:
            continue
        for edge in loop.edges:
            for neighbor in edge.faces:
                if neighbor != face:
                    beside = neighbor.pointOnFace
                    return (beside.x - point.x) * normal.x + (beside.y - point.y) * normal.y + (beside.z - point.z) * normal.z < 0
    return False

def labelAppearance(design: adsk.fusion.Design) -> adsk.core.Appearance:
    """The design's label appearance, copied from Fusion's plastics the first time, its color can be changed after"""
    from .ui import viewportPictures
    appearance = viewportPictures.appearanceNamed(design.appearances, LABEL_APPEARANCE_NAME)
    if appearance is None:
        base = viewportPictures.firstLibraryAppearance(viewportPictures.COLOR_BASE_PREFIXES)
        appearance = design.appearances.addByCopy(base, LABEL_APPEARANCE_NAME)
        viewportPictures.setColor(appearance, LABEL_APPEARANCE_COLOR)
    return appearance

def paintLetterFaces(design: adsk.fusion.Design, body: adsk.fusion.BRepBody) -> int:
    """Colors the letter tops of the outline labels on the body in Fusion, returns how many faces"""
    faces = outlineLetterFaces(body)
    if len(faces) == 0:
        return 0
    appearance = labelAppearance(design)
    for face in faces:
        face.appearance = appearance
    return len(faces)
