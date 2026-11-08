import adsk.core, adsk.fusion

from . import commonUtils, patternUtils, sketchUtils, wallCreases
from .baseGenerator import cellLineDim
from .baseGeneratorInput import BaseGeneratorInput
from .dim import Dim, applyTo

_AXES = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}

def _dimensionCoordinate(sketch: adsk.fusion.Sketch, point: adsk.fusion.SketchPoint, axis: str, value: Dim):
    """Drives a model coordinate of a point of a sketch on a principal plane, whichever sketch axis it lies along"""
    vector = _AXES[axis]
    xDirection = sketch.xDirection
    isAlongSketchX = abs(xDirection.x * vector[0] + xDirection.y * vector[1] + xDirection.z * vector[2]) > 0.99
    if abs(value.value) < 1e-6:
        # a zero distance can't be dimensioned, the point lines up with the origin instead
        if isAlongSketchX:
            sketch.geometricConstraints.addVerticalPoints(sketch.originPoint, point)
        else:
            sketch.geometricConstraints.addHorizontalPoints(sketch.originPoint, point)
        return
    geometry = point.geometry
    # sketch distance dimensions are unsigned
    applyTo(sketch.sketchDimensions.addDistanceDimension(
        sketch.originPoint,
        point,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation if isAlongSketchX else adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(geometry.x / 2, geometry.y / 2, 0),
        True,
    ).parameter, value if value.value >= 0 else value * -1)

def _ensureAligned(sketch: adsk.fusion.Sketch, line: adsk.fusion.SketchLine):
    """Horizontal or vertical constraint on a line drawn along a sketch axis, Fusion may have added it by itself"""
    alignedTypes = [adsk.fusion.HorizontalConstraint.classType(), adsk.fusion.VerticalConstraint.classType()]
    if any(constraint.objectType in alignedTypes for constraint in line.geometricConstraints):
        return
    start = line.startSketchPoint.geometry
    end = line.endSketchPoint.geometry
    if abs(start.y - end.y) < abs(start.x - end.x):
        sketch.geometricConstraints.addHorizontal(line)
    else:
        sketch.geometricConstraints.addVertical(line)

def _closedPolygon(sketch: adsk.fusion.Sketch, corners: list[tuple[adsk.core.Point3D, dict[str, Dim]]]):
    """
    Lines through the model points, each corner dimensioned with its model coordinates. Lines along an axis are
    constrained to it instead, only one of the corners they join gets that coordinate dimensioned
    """
    lines: list[adsk.fusion.SketchLine] = []
    sketchLines = sketch.sketchCurves.sketchLines
    points = []
    for (modelPoint, _) in corners:
        point = sketch.modelToSketchSpace(modelPoint)
        point.z = 0
        points.append(point)
    for (index, point) in enumerate(points):
        start = lines[-1].endSketchPoint if len(lines) > 0 else point
        end = lines[0].startSketchPoint if index == len(points) - 1 else points[index + 1]
        lines.append(sketchLines.addByTwoPoints(start, end))

    # corners joined by lines along an axis share that coordinate, it's dimensioned once per group
    groups: dict[str, list[int]] = {}
    for axis in corners[0][1]:
        groups[axis] = list(range(len(corners)))
    for (index, line) in enumerate(lines):
        nextIndex = (index + 1) % len(corners)
        for (axis, owners) in groups.items():
            if abs(corners[index][1][axis].value - corners[nextIndex][1][axis].value) > 1e-9:
                continue
            _ensureAligned(sketch, line)
            (keep, merge) = sorted([owners[index], owners[nextIndex]])
            groups[axis] = [keep if owner == merge else owner for owner in owners]
            owners = groups[axis]
    for (index, (line, (_, coordinates))) in enumerate(zip(lines, corners)):
        for (axis, value) in coordinates.items():
            if groups[axis][index] == index:
                _dimensionCoordinate(sketch, line.startSketchPoint, axis, value)

def _createSideFolds(
    side: wallCreases.WallSide,
    count: int,
    grid: BaseGeneratorInput,
    wallOffset: float,
    depth: float,
    bottomZ: float,
    topZ: Dim,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> list[adsk.fusion.BRepBody]:
    features = targetComponent.features
    origin = grid.originPoint
    along = side.axis
    across = 'y' if along == 'x' else 'x'
    alongUnit = (grid.baseWidth if along == 'x' else grid.baseLength).asExpression()
    acrossUnit = (grid.baseLength if along == 'x' else grid.baseWidth).asExpression()
    alongOrigin = origin.x if along == 'x' else origin.y
    acrossOrigin = origin.y if along == 'x' else origin.x
    cornerRadius = grid.cornerFilletRadius

    def modelPoint(alongValue: float, acrossValue: float, z: float) -> adsk.core.Point3D:
        if along == 'x':
            return adsk.core.Point3D.create(alongValue, acrossValue, z)
        return adsk.core.Point3D.create(acrossValue, alongValue, z)

    # the wall face and the ridge pressed in from it
    wall = cellLineDim(acrossUnit, side.line, acrossOrigin + side.inward * wallOffset)
    ridge = cellLineDim(acrossUnit, side.line, acrossOrigin + side.inward * (wallOffset + depth))
    # panels share the flat part of the side, the corner arcs end the corner radius from the grid points on both faces of the wall
    start = cellLineDim(alongUnit, side.start, alongOrigin + cornerRadius)
    cells = side.end - side.start
    length = (alongUnit * cells if cells != 1 else alongUnit) - Dim.length(cornerRadius * 2)
    width = length / count if count > 1 else length
    triangle = width * wallCreases.TRIANGLE_WIDTH_RATIO
    bottom = Dim.length(bottomZ)
    ridgeZ = bottom + (topZ - bottom) * wallCreases.RIDGE_HEIGHT_RATIO

    # across the wall, the fold from the panel bottom in to the ridge and out to its top, as long as the side
    gableSketch: adsk.fusion.Sketch = targetComponent.sketches.add(
        targetComponent.yZConstructionPlane if along == 'x' else targetComponent.xZConstructionPlane
    )
    gableSketch.name = f'{name} profile sketch'
    with sketchUtils.deferSketchCompute(gableSketch):
        _closedPolygon(gableSketch, [
            (modelPoint(0, wall.value, bottom.value), {across: wall, 'z': bottom}),
            (modelPoint(0, ridge.value, ridgeZ.value), {across: ridge, 'z': ridgeZ}),
            (modelPoint(0, wall.value, topZ.value), {across: wall, 'z': topZ}),
        ])
    gableInput = features.extrudeFeatures.createInput(gableSketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    gableInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
    )
    gableExtrude = features.extrudeFeatures.add(gableInput)
    gableExtrude.name = f'{name} profile'

    # along the wall, the first panel's fold from its ends in to the ridge, as tall as the profile
    panelSketch: adsk.fusion.Sketch = targetComponent.sketches.add(targetComponent.xYConstructionPlane)
    panelSketch.name = f'{name} panel sketch'
    with sketchUtils.deferSketchCompute(panelSketch):
        _closedPolygon(panelSketch, [
            (modelPoint(start.value, wall.value, 0), {along: start, across: wall}),
            (modelPoint((start + triangle).value, ridge.value, 0), {along: start + triangle, across: ridge}),
            (modelPoint((start + width - triangle).value, ridge.value, 0), {along: start + width - triangle, across: ridge}),
            (modelPoint((start + width).value, wall.value, 0), {along: start + width, across: wall}),
        ])
    panelExtrude = features.extrudeFeatures.addSimple(
        panelSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(100),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    panelExtrude.name = f'{name} panel'
    fold = panelExtrude.bodies.item(0)
    fold.name = name

    # where both meet the panel folds in along its creases
    intersectInput = features.combineFeatures.createInput(fold, commonUtils.objectCollectionFromList([gableExtrude.bodies.item(0)]))
    intersectInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    features.combineFeatures.add(intersectInput).name = f'{name} shape'

    if count == 1:
        return [fold]
    pattern = patternUtils.recPattern(
        commonUtils.objectCollectionFromList([fold]),
        (
            targetComponent.xConstructionAxis if along == 'x' else targetComponent.yConstructionAxis,
            targetComponent.yConstructionAxis if along == 'x' else targetComponent.xConstructionAxis,
        ),
        (width, acrossUnit),
        (count, 1),
        targetComponent,
        name=f'{name} pattern',
    )
    # pattern bodies include the source fold, collections made of these skip the duplicate
    return list(pattern.bodies) + [fold]

def createCreaseFolds(
    sides: list[tuple[wallCreases.WallSide, int]],
    grid: BaseGeneratorInput,
    wallOffset: float,
    depth: float,
    bottomZ: float,
    topZ: Dim,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> list[adsk.fusion.BRepBody]:
    """
    The folds of the creased walls, see wallCreases, against a wall face the offset in from the cell lines, the depth
    deep towards the inside. Cut from the outer face they dent the wall, joined to the inner face they keep the
    wall thickness behind the dent. Panels run from the bottom to the top height, the top follows its parameters
    """
    bodies = []
    for (index, (side, count)) in enumerate(sides):
        bodies += _createSideFolds(side, count, grid, wallOffset, depth, bottomZ, topZ, targetComponent, name=f'{name} {index + 1}')
    return bodies
