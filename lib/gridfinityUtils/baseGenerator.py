import adsk.core, adsk.fusion, traceback, math
import copy
from typing import Callable
import os

from .sketchUtils import createRectangle
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from .dim import Dim, valueInput, applyTo
from . import sketchUtils, const, edgeUtils, commonUtils, combineUtils, faceUtils, extrudeUtils, shapeUtils, geometryUtils, patternUtils, binShape, binGrid
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def createCircleAtPointSketch(
    plane: adsk.core.Base,
    radius: float,
    circleCenterPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    circleSketch: adsk.fusion.Sketch = sketches.add(plane)
    circleSketch.name = name
    circleCenterOnSketch = circleSketch.modelToSketchSpace(circleCenterPoint)
    dimensions: adsk.fusion.SketchDimensions = circleSketch.sketchDimensions
    sketchUtils.convertToConstruction(circleSketch.sketchCurves)
    circle = circleSketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(circleCenterOnSketch.x, circleCenterOnSketch.y, 0),
        radius,
    )
    dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y * 2, 0),
        True,
    )
    dimensions.addDistanceDimension(
        circleSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
        True
        )
    dimensions.addDistanceDimension(
        circleSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
        True
        )

    return (circleSketch, circle)

def createTabAtCircleEdgeSketch(
    plane: adsk.core.Base,
    radius: float,
    circleCenterPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    circleSketch, circle = createCircleAtPointSketch(
        plane,
        radius,
        circleCenterPoint,
        targetComponent,
        name=name,
    )
    circleCenterOnSketch = geometryUtils.pointToXY(circleSketch.modelToSketchSpace(circleCenterPoint))
    angularPointOnSketch = geometryUtils.pointToXY(circleSketch.modelToSketchSpace(
        adsk.core.Point3D.create(circleCenterPoint.x + radius, circleCenterPoint.y + radius, circleCenterPoint.z)
    ))
    dimensions: adsk.fusion.SketchDimensions = circleSketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = circleSketch.geometricConstraints
    sketchUtils.convertToConstruction(circleSketch.sketchCurves)
    verticalConstructionLine = circleSketch.sketchCurves.sketchLines.addByTwoPoints(
        circleCenterOnSketch,
        adsk.core.Point3D.create(circleCenterOnSketch.x, circleCenterOnSketch.y + radius, circleCenterOnSketch.z)
    )
    verticalConstructionLine.isConstruction = True
    diagonalConstructionLine = circleSketch.sketchCurves.sketchLines.addByTwoPoints(
        circleCenterOnSketch,
        angularPointOnSketch,
    )
    diagonalConstructionLine.isConstruction = True
    constraints.addVertical(verticalConstructionLine)
    dimensions.addAngularDimension(
        diagonalConstructionLine,
        verticalConstructionLine,
        angularPointOnSketch,
    )
    constraints.addCoincident(
        verticalConstructionLine.startSketchPoint,
        circle.centerSketchPoint,
    )
    constraints.addCoincident(
        verticalConstructionLine.endSketchPoint,
        circle,
    )
    constraints.addCoincident(
        diagonalConstructionLine.startSketchPoint,
        circle.centerSketchPoint,
    )
    constraints.addCoincident(
        diagonalConstructionLine.endSketchPoint,
        circle,
    )
    circle = circleSketch.sketchCurves.sketchCircles.addByCenterRadius(
        diagonalConstructionLine.endSketchPoint,
        radius / 2,
    )
    dimensions.addRadialDimension(
        circle,
        circleCenterOnSketch,
    )

    return circleSketch

def createSingleGridfinityBaseBody(
    input: BaseGeneratorInput,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    """The body and all its features are named after the given name"""
    actual_base_width = input.baseWidth
    actual_base_length = input.baseLength
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(input.originZ))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    baseConstructionPlane.name = f'{name} plane'
    # create rectangle for the base
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    basePlateSketch: adsk.fusion.Sketch = sketches.add(baseConstructionPlane)
    basePlateSketch.name = f'{name} sketch'
    createRectangle(actual_base_width, actual_base_length, basePlateSketch.modelToSketchSpace(input.originPoint), basePlateSketch)

    # extrude top section
    topSectionExtrudeDepth = adsk.core.ValueInput.createByReal(const.BIN_BASE_TOP_SECTION_HEIGH)
    topSectionExtrudeInput = extrudeFeatures.createInput(basePlateSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    topSectionExtrudeExtent = adsk.fusion.DistanceExtentDefinition.create(topSectionExtrudeDepth)
    topSectionExtrudeInput.setOneSideExtent(topSectionExtrudeExtent,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByReal(0))
    topSectionExtrudeFeature = extrudeFeatures.add(topSectionExtrudeInput)
    topSectionExtrudeFeature.name = f'{name} top section'
    baseBody = topSectionExtrudeFeature.bodies.item(0)
    baseBody.name = name

    # fillet on corners
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    fillet_edges = edgeUtils.selectEdgesByLength(baseBody.faces, const.BIN_BASE_TOP_SECTION_HEIGH, const.DEFAULT_FILTER_TOLERANCE)
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByReal(input.cornerFilletRadius), True)
    filletFeatures.add(filletInput).name = f'{name} corner fillet'

    # chamfer top section
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(topSectionExtrudeFeature.endFaces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        topSectionExtrudeDepth,
        True)
    chamferFeatures.add(chamferInput).name = f'{name} top chamfer'

    # extrude mid/bottom section
    baseBottomExtrude = extrudeUtils.simpleDistanceExtrude(
        topSectionExtrudeFeature.endFaces.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        const.BIN_BASE_MID_SECTION_HEIGH + const.BIN_BASE_BOTTOM_SECTION_HEIGH,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [baseBody],
        targetComponent,
        name=f'{name} bottom section',
    )

    if input.hasBottomChamfer:
        # chamfer bottom section
        chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
        chamferInput = chamferFeatures.createInput2()
        chamfer_edges = commonUtils.objectCollectionFromList(faceUtils.getBottomFace(baseBottomExtrude.bodies.item(0)).edges)
        chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
            adsk.core.ValueInput.createByReal(const.BIN_BASE_BOTTOM_SECTION_HEIGH),
            True)
        chamferFeatures.add(chamferInput).name = f'{name} bottom chamfer'
    
    # screw holes
    cutoutBodies = adsk.core.ObjectCollection.create()

    baseBottomPlane = baseBottomExtrude.endFaces.item(0)
    baseHoleCenterPoint = adsk.core.Point3D.create(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        baseBottomPlane.boundingBox.minPoint.z
    )
    cutoutCenterPoint = adsk.core.Point3D.create(baseHoleCenterPoint.x, baseHoleCenterPoint.y, 0)
    if input.hasScrewHoles:
        screwHoleBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -const.BIN_BASE_HEIGHT,
            input.screwHolesDiameter / 2,
            cutoutCenterPoint,
            targetComponent,
            name=f'{name} screw hole',
        )
        cutoutBodies.add(screwHoleBody)

    # magnet cutouts
    if input.hasMagnetCutouts:
        magnetSocketBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -input.magnetCutoutsDepth,
            input.magnetCutoutsDiameter / 2,
            cutoutCenterPoint,
            targetComponent,
            name=f'{name} magnet socket',
        )
        cutoutBodies.add(magnetSocketBody)

        # magnet tab cutouts
        if input.hasMagnetCutoutsTabs:
            magnetTabCutoutSketch = createTabAtCircleEdgeSketch(
                baseBottomPlane,
                input.magnetCutoutsDiameter / 2,
                cutoutCenterPoint,
                targetComponent,
                name=f'{name} magnet tab sketch',
            )

            magnetTabCutoutExtrude = extrudeUtils.simpleDistanceExtrude(
                magnetTabCutoutSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                input.magnetCutoutsDepth,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                [],
                targetComponent,
                name=f'{name} magnet tab',
            )
            cutoutBodies.add(magnetTabCutoutExtrude.bodies.item(0))
        
        if input.hasScrewHoles and (const.BIN_BASE_HEIGHT - input.magnetCutoutsDepth) > const.BIN_MAGNET_HOLE_GROOVE_DEPTH:
            grooveBody = shapeUtils.simpleCylinder(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH,
                input.magnetCutoutsDiameter / 2,
                cutoutCenterPoint,
                targetComponent,
                name=f'{name} groove',
            )
            grooveLayer1 = shapeUtils.simpleBox(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                input.magnetCutoutsDiameter,
                input.screwHolesDiameter,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x + input.magnetCutoutsDiameter / 2, baseHoleCenterPoint.y - input.screwHolesDiameter / 2, 0),
                targetComponent,
                name=f'{name} groove layer 1',
            )
            grooveLayer2 = shapeUtils.simpleBox(
                baseBottomPlane,
                -(input.magnetCutoutsDepth + const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2),
                input.screwHolesDiameter,
                input.screwHolesDiameter,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x + input.screwHolesDiameter / 2, baseHoleCenterPoint.y - input.screwHolesDiameter / 2, 0),
                targetComponent,
                name=f'{name} groove layer 2',
            )
            combineUtils.intersectBody(grooveBody, commonUtils.objectCollectionFromList([grooveLayer1, grooveLayer2]), targetComponent, name=f'{name} groove shape')

            rotateGrooveBodyInput = targetComponent.features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([grooveBody]))
            verticalAxisVector = adsk.core.Vector3D.create(0, 0, 1.0)
            transformRotate = adsk.core.Matrix3D.create()
            transformRotate.setToRotation(math.radians(-45), verticalAxisVector, cutoutCenterPoint)
            rotateGrooveBodyInput.defineAsFreeMove(transformRotate)
            ratateGrooveBodyFeature = targetComponent.features.moveFeatures.add(rotateGrooveBodyInput)
            ratateGrooveBodyFeature.name = f'{name} groove rotation'

            cutoutBodies.add(grooveBody)


    if input.hasScrewHoles or input.hasMagnetCutouts:
        if cutoutBodies.count > 1:
            joinFeature = combineUtils.joinBodies(cutoutBodies.item(0), commonUtils.objectCollectionFromList(list(cutoutBodies)[1:]), targetComponent, name=f'{name} holes join')
            cutoutBodies = commonUtils.objectCollectionFromList(joinFeature.bodies)

        baseXZMidPlaneInput = targetComponent.constructionPlanes.createInput()
        baseXZMidPlaneInput.setByOffset(targetComponent.xZConstructionPlane, valueInput(input.baseLength / 2 - Dim.length(input.xyClearance)))
        baseXZMidPlane = targetComponent.constructionPlanes.add(baseXZMidPlaneInput)
        baseXZMidPlane.name = f'{name} XZ mid plane'
        baseXZMidPlane.isLightBulbOn = False
        baseYZMidPlaneInput = targetComponent.constructionPlanes.createInput()
        baseYZMidPlaneInput.setByOffset(targetComponent.yZConstructionPlane, valueInput(input.baseWidth / 2 - Dim.length(input.xyClearance)))
        baseYZMidPlane = targetComponent.constructionPlanes.add(baseYZMidPlaneInput)
        baseYZMidPlane.name = f'{name} YZ mid plane'
        baseYZMidPlane.isLightBulbOn = False
        # mirroring instead of a circular pattern keeps the holes in the corners of non square bases,
        # and the tabs and grooves still face the base center
        mirrorXInput = features.mirrorFeatures.createInput(cutoutBodies, baseYZMidPlane)
        mirrorXFeature = features.mirrorFeatures.add(mirrorXInput)
        mirrorXFeature.name = f'{name} holes mirror X'
        holeBodies = commonUtils.objectCollectionFromList(cutoutBodies, mirrorXFeature.bodies)
        mirrorYInput = features.mirrorFeatures.createInput(holeBodies, baseXZMidPlane)
        mirrorYFeature = features.mirrorFeatures.add(mirrorYInput)
        mirrorYFeature.name = f'{name} holes mirror Y'
        # the collection skips bodies listed twice, in case mirror results include their sources
        combineUtils.cutBody(baseBody, commonUtils.objectCollectionFromList(holeBodies, mirrorYFeature.bodies), targetComponent, name=f'{name} holes cut')

    return baseBody


def createBaseBodyPattern(
    baseConfiguration: BaseGeneratorInput,
    basesXCount: Dim | int,
    basesYCount: Dim | int,
    targetComponent: adsk.fusion.Component,
    spacingX: Dim = None,
    spacingY: Dim = None,
    *,
    name: str = 'Foot',
):
    """Feet the spacing apart, the base size by default. Bodies and features are named after the given name"""
    baseBody = createSingleGridfinityBaseBody(baseConfiguration, targetComponent, name=name)
    features = targetComponent.features
    # replicate base in a rectangular pattern
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()
    patternInputBodies.add(baseBody)
    patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
        targetComponent.xConstructionAxis,
        valueInput(basesXCount),
        valueInput(spacingX if spacingX is not None else baseConfiguration.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = valueInput(basesYCount)
    patternInput.distanceTwo = valueInput(spacingY if spacingY is not None else baseConfiguration.baseLength)
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    rectangularPattern.name = f'{name} pattern'
    return list(rectangularPattern.bodies) + [baseBody]

def createFootGrid(
    baseConfiguration: BaseGeneratorInput,
    columns: float,
    rows: float,
    targetComponent: adsk.fusion.Component,
    spacingX: Dim = None,
    spacingY: Dim = None,
    *,
    name: str = 'Foot',
) -> list[adsk.fusion.BRepBody]:
    """
    A foot per grid cell of a bin the columns by rows cells big, the spacing apart, the base size by default.
    A half cell left over makes a row of half feet along the far side, see binGrid. They are halved across the row
    only, like the half cells of a baseplate, so they line up with the whole ones, the corner one is halved both ways.
    Half feet are as much smaller as half the spacing and have no holes, there is no room for them in the standard spots
    """
    spacingX = spacingX if spacingX is not None else baseConfiguration.baseWidth
    spacingY = spacingY if spacingY is not None else baseConfiguration.baseLength
    (wholeX, hasHalfX) = binGrid.splitHalf(columns)
    (wholeY, hasHalfY) = binGrid.splitHalf(rows)
    bodies: list[adsk.fusion.BRepBody] = []
    if wholeX > 0 and wholeY > 0:
        bodies += createBaseBodyPattern(baseConfiguration, wholeX, wholeY, targetComponent, spacingX, spacingY, name=name)

    halfWidth = baseConfiguration.baseWidth - spacingX / 2
    halfLength = baseConfiguration.baseLength - spacingY / 2
    halfX = spacingX * wholeX if wholeX != 1 else spacingX
    halfY = spacingY * wholeY if wholeY != 1 else spacingY
    noOffset = Dim.length(0)
    for (hasHalf, label, width, length, offsetX, offsetY, countX, countY) in [
        (hasHalfX, 'half width', halfWidth, baseConfiguration.baseLength, halfX, noOffset, 1, wholeY),
        (hasHalfY, 'half length', baseConfiguration.baseWidth, halfLength, noOffset, halfY, wholeX, 1),
        (hasHalfX and hasHalfY, 'half corner', halfWidth, halfLength, halfX, halfY, 1, 1),
    ]:
        if not hasHalf or countX * countY == 0:
            continue
        halfInput = copy.copy(baseConfiguration)
        halfInput.baseWidth = width
        halfInput.baseLength = length
        halfInput.hasScrewHoles = False
        halfInput.hasMagnetCutouts = False
        halfInput.hasMagnetCutoutsTabs = False
        halfBody = createSingleGridfinityBaseBody(halfInput, targetComponent, name=f'{name} {label}')
        bodies.append(halfBody)
        if offsetX.value > 0 or offsetY.value > 0:
            moveInput = targetComponent.features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([halfBody]))
            moveInput.defineAsTranslateXYZ(valueInput(offsetX), valueInput(offsetY), adsk.core.ValueInput.createByReal(0), True)
            targetComponent.features.moveFeatures.add(moveInput).name = f'{name} {label} placement'
        if countX * countY > 1:
            pattern = patternUtils.recPatternGrid(
                commonUtils.objectCollectionFromList([halfBody]),
                (countX, countY),
                (spacingX, spacingY),
                targetComponent,
                name=f'{name} {label} pattern',
            )
            # pattern bodies include the source body, which a combine rejects as its own tool
            bodies += [body for body in pattern.bodies if body != halfBody]
    return bodies

def footCenters(
    baseWidth: Dim,
    baseLength: Dim,
    xyClearance: float,
    columns: float,
    rows: float,
    offsetX: Dim = None,
    offsetY: Dim = None,
) -> list[tuple[int, int, Dim, Dim]]:
    """cellCenters of the feet of createFootGrid, the half ones included"""
    centers = []
    for (column, (startX, sizeX)) in enumerate(binGrid.footSpans(columns)):
        for (row, (startY, sizeY)) in enumerate(binGrid.footSpans(rows)):
            x = baseWidth * (startX + sizeX / 2) - Dim.length(xyClearance)
            y = baseLength * (startY + sizeY / 2) - Dim.length(xyClearance)
            centers.append((
                column,
                row,
                x + offsetX if offsetX is not None else x,
                y + offsetY if offsetY is not None else y,
            ))
    return centers

def cutOutsideRoundedRectangles(
    rectangles: list[tuple[Dim, Dim, Dim, Dim]],
    filletRadius: float,
    targetBodies: list[adsk.fusion.BRepBody],
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> adsk.fusion.ExtrudeFeature:
    """Cuts everything outside the rounded rectangles (minX, minY, maxX, maxY) from the target bodies, through their
    full height, in one cut. Bodies spanning several rectangles split along the gaps between them.
    The rectangle dims drive their position and size. Sketch and cut are named after the given name"""
    features = targetComponent.features
    cutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(targetComponent.xYConstructionPlane)
    cutSketch.name = f'{name} sketch'
    sketchArcs = cutSketch.sketchCurves.sketchArcs
    geometricConstraints = cutSketch.geometricConstraints
    fillets = []
    for (minX, minY, maxX, maxY) in rectangles:
        cornerPoint = cutSketch.modelToSketchSpace(adsk.core.Point3D.create(minX.value, minY.value, 0))
        cornerPoint.z = 0
        [side1, side2, side3, side4] = list(createRectangle(maxX - minX, maxY - minY, cornerPoint, cutSketch, minX, minY))
        fillets.append(sketchArcs.addFillet(side1, side1.endSketchPoint.geometry, side2, side2.startSketchPoint.geometry, filletRadius))
        fillets.append(sketchArcs.addFillet(side2, side2.endSketchPoint.geometry, side3, side3.startSketchPoint.geometry, filletRadius))
        fillets.append(sketchArcs.addFillet(side3, side3.endSketchPoint.geometry, side4, side4.startSketchPoint.geometry, filletRadius))
        fillets.append(sketchArcs.addFillet(side4, side4.endSketchPoint.geometry, side1, side1.startSketchPoint.geometry, filletRadius))
    # one radius for every corner
    for fillet in fillets[1:]:
        geometricConstraints.addEqual(fillets[0], fillet)
    cutSketch.sketchDimensions.addRadialDimension(fillets[0], fillets[0].startSketchPoint.geometry)

    # a frame around all the rectangles, its region less the rectangles is cut. It is as far again past them on every side,
    # so it keeps clear of them when parameters grow the plate
    allMinX = min(rectangle[0].value for rectangle in rectangles)
    allMinY = min(rectangle[1].value for rectangle in rectangles)
    allMaxX = max(rectangle[2].value for rectangle in rectangles)
    allMaxY = max(rectangle[3].value for rectangle in rectangles)
    margin = max(allMaxX - allMinX, allMaxY - allMinY)
    frameCorner1 = cutSketch.modelToSketchSpace(adsk.core.Point3D.create(allMinX - margin, allMinY - margin, 0))
    frameCorner2 = cutSketch.modelToSketchSpace(adsk.core.Point3D.create(allMaxX + margin, allMaxY + margin, 0))
    (frameCorner1.z, frameCorner2.z) = (0, 0)
    cutSketch.sketchCurves.sketchLines.addTwoPointRectangle(frameCorner1, frameCorner2)

    def area(profile: adsk.fusion.Profile) -> float:
        box = profile.boundingBox
        return (box.maxPoint.x - box.minPoint.x) * (box.maxPoint.y - box.minPoint.y)
    cuttingProfile = max(list(cutSketch.profiles), key=area)
    cutExtrudeInput = features.extrudeFeatures.createInput(
        cuttingProfile,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    cutExtrudeInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
    )
    # the target component can be the root of a part design, which also holds unrelated bodies
    cutExtrudeInput.participantBodies = targetBodies
    cutExtrude = features.extrudeFeatures.add(cutExtrudeInput)
    cutExtrude.name = name
    return cutExtrude

def cellCenters(
    baseWidth: Dim,
    baseLength: Dim,
    xyClearance: float,
    columns: range,
    rows: range,
    offsetX: Dim = None,
    offsetY: Dim = None,
) -> list[tuple[int, int, Dim, Dim]]:
    """Column, row and XY center of grid cells. Bins and baseplates share the grid, cells start a clearance
    before the origin, the optional offsets follow the moves placing the bodies"""
    centers = []
    for column in columns:
        for row in rows:
            x = baseWidth * (column + 0.5) - Dim.length(xyClearance)
            y = baseLength * (row + 0.5) - Dim.length(xyClearance)
            centers.append((
                column,
                row,
                x + offsetX if offsetX is not None else x,
                y + offsetY if offsetY is not None else y,
            ))
    return centers

def createCellJointOrigins(
    centers: list[tuple[int, int, Dim, Dim]],
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> list[adsk.fusion.JointOrigin]:
    """
    Joint origins at the base bottom of the given cell centers, Z up, the bottom of bin feet and of baseplate
    sockets alike, so a joint between the two seats a bin in its socket.
    They sit on sketch points dimensioned from the origin, so they follow the base unit parameters. Sketches
    don't follow moves of bodies, so these are made after the bodies are placed, with the placement in the centers.
    """
    planeInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(targetComponent.xYConstructionPlane, adsk.core.ValueInput.createByReal(-const.BIN_BASE_HEIGHT))
    plane = targetComponent.constructionPlanes.add(planeInput)
    plane.name = f'{name} plane'
    plane.isLightBulbOn = False
    sketch: adsk.fusion.Sketch = targetComponent.sketches.add(plane)
    sketch.name = f'{name} sketch'
    points: list[tuple[int, int, adsk.fusion.SketchPoint]] = []
    with sketchUtils.deferSketchCompute(sketch):
        dimensions = sketch.sketchDimensions
        for (column, row, x, y) in centers:
            pointOnSketch = sketch.modelToSketchSpace(adsk.core.Point3D.create(x.value, y.value, -const.BIN_BASE_HEIGHT))
            pointOnSketch.z = 0
            point = sketch.sketchPoints.add(pointOnSketch)
            # distance dimensions are unsigned
            for (orientation, distance, textPoint) in [
                (adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation, x, adsk.core.Point3D.create(pointOnSketch.x / 2, pointOnSketch.y, 0)),
                (adsk.fusion.DimensionOrientations.VerticalDimensionOrientation, y, adsk.core.Point3D.create(pointOnSketch.x, pointOnSketch.y / 2, 0)),
            ]:
                applyTo(
                    dimensions.addDistanceDimension(sketch.originPoint, point, orientation, textPoint, False).parameter,
                    distance if distance.value >= 0 else distance * -1,
                )
            points.append((column, row, point))
    sketch.isVisible = False

    jointOrigins = []
    for (column, row, point) in points:
        jointOriginInput = targetComponent.jointOrigins.createInput(adsk.fusion.JointGeometry.createByPoint(point))
        jointOrigin = targetComponent.jointOrigins.add(jointOriginInput)
        jointOrigin.name = f'{name} {column + 1}-{row + 1}'
        jointOrigins.append(jointOrigin)
    return jointOrigins

def cutBaseClearance(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetBodies: list[adsk.fusion.BRepBody],
    targetComponent: adsk.fusion.Component,
):
    actual_base_width = baseConfiguration.baseWidth * basesXCount - Dim.length(baseConfiguration.xyClearance * 2)
    actual_base_length = baseConfiguration.baseLength * basesYCount - Dim.length(baseConfiguration.xyClearance * 2)
    cutOutsideRoundedRectangle(
        adsk.core.Point3D.create(
            baseConfiguration.originPoint.x + baseConfiguration.xyClearance,
            baseConfiguration.originPoint.y + baseConfiguration.xyClearance,
            baseConfiguration.originPoint.z,
        ),
        actual_base_width,
        actual_base_length,
        baseConfiguration.cornerFilletRadius - baseConfiguration.xyClearance,
        targetBodies,
        targetComponent,
        name='Outer clearance trim',
    )

def createWallJunctionPocketCutter(
    junctionX: Dim,
    junctionY: Dim,
    junctionZ: float,
    cornerRadius: float,
    xyClearance: float,
    targetComponent: adsk.fusion.Component,
    openSide: tuple[int, int] = None,
) -> adsk.fusion.BRepBody:
    """Negative volume curving up the gap where two feet meet at an outer wall, continuing the 45 degree
    chamfers of the foot corners above their top until they close the gap. The cones are concentric with the
    foot corners and start where the clearance trim meets the chamfer, a clearance below the feet top.
    The open side, x and y directions of an empty cell at an inner corner, has no foot to curve around. Its cone
    would hug the rounded wall there and close the pocket right above the feet, so it's left out"""
    features = targetComponent.features
    # fed as expressions, so the formulas stay readable in the model
    cornerCenterOffset = Dim.length(cornerRadius).asExpression()
    clearance = Dim.length(xyClearance).asExpression()
    coneSketchRadius = cornerCenterOffset - clearance
    # cones around the corner centers meet above the junction once they reach offset * sqrt(2)
    pocketRise = cornerCenterOffset * Dim.number(math.sqrt(2), 'sqrt(2)') - coneSketchRadius
    coneSketchHeight = Dim.length(junctionZ) - clearance
    # first foot corner center, the box corner and the source cone of the pattern
    cornerCenterX = junctionX - cornerCenterOffset
    cornerCenterY = junctionY - cornerCenterOffset

    # box and cones share the plane, starting with the cones keeps them apart at the bottom, at the feet top
    # neighbouring cones touch in a point which combine can't handle
    pocketPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    pocketPlaneInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(coneSketchHeight))
    pocketPlane = targetComponent.constructionPlanes.add(pocketPlaneInput)
    pocketPlane.name = 'Wall junction pocket plane'

    boxSketch: adsk.fusion.Sketch = targetComponent.sketches.add(pocketPlane)
    boxSketch.name = 'Wall junction pocket sketch'
    boxCornerOnSketch = boxSketch.modelToSketchSpace(adsk.core.Point3D.create(
        cornerCenterX.value,
        cornerCenterY.value,
        coneSketchHeight.value,
    ))
    boxCornerOnSketch.z = 0
    sketchUtils.createRectangle(
        cornerCenterOffset * 2,
        cornerCenterOffset * 2,
        boxCornerOnSketch,
        boxSketch,
        startX=cornerCenterX,
        startY=cornerCenterY,
    )
    # taller than the pocket, so its top closes inside the box instead of touching the box top in a point
    boxExtrude = features.extrudeFeatures.addSimple(
        boxSketch.profiles.item(0),
        valueInput(pocketRise * 1.5),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    boxExtrude.name = 'Wall junction pocket box'
    pocketBody = boxExtrude.bodies.item(0)
    pocketBody.name = 'Wall junction pocket'

    # one cone per foot corner around the junction, the outer ones only clip what lies outside the bin
    coneSketch: adsk.fusion.Sketch = targetComponent.sketches.add(pocketPlane)
    coneSketch.name = 'Wall junction pocket cone sketch'
    with sketchUtils.deferSketchCompute(coneSketch):
        dimensions: adsk.fusion.SketchDimensions = coneSketch.sketchDimensions
        coneCircle = coneSketch.sketchCurves.sketchCircles.addByCenterRadius(boxCornerOnSketch, coneSketchRadius.value)
        applyTo(dimensions.addDiameterDimension(
            coneCircle,
            adsk.core.Point3D.create(boxCornerOnSketch.x + coneSketchRadius.value, boxCornerOnSketch.y + coneSketchRadius.value, 0),
        ).parameter, coneSketchRadius * 2)
        # sketch distance dimensions are unsigned, coordinates left or below the origin need the magnitude
        applyTo(dimensions.addDistanceDimension(
            coneSketch.originPoint,
            coneCircle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            adsk.core.Point3D.create(boxCornerOnSketch.x, 0, 0),
        ).parameter, cornerCenterX.abs())
        applyTo(dimensions.addDistanceDimension(
            coneSketch.originPoint,
            coneCircle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            adsk.core.Point3D.create(0, boxCornerOnSketch.y, 0),
        ).parameter, cornerCenterY.abs())

    # past the box top, so the cone fully covers it
    coneHeight = pocketRise * 2.5
    coneExtrudeInput = features.extrudeFeatures.createInput(coneSketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    coneExtrudeInput.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(valueInput(coneHeight)),
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        adsk.core.ValueInput.createByString('45 deg'),
    )
    coneExtrude = features.extrudeFeatures.add(coneExtrudeInput)
    coneExtrude.name = 'Wall junction pocket cone'
    coneBody = coneExtrude.bodies.item(0)
    coneBox = coneBody.boundingBox
    if coneBox.maxPoint.x - coneBox.minPoint.x < coneSketchRadius.value * 2 + coneHeight.value:
        # taper went inwards, flip it so the cone widens upwards like the chamfer it continues
        coneExtrude.taperAngleOne.expression = '-45 deg'

    conePattern = patternUtils.recPatternGrid(
        commonUtils.objectCollectionFromList([coneBody]),
        (2, 2),
        (cornerCenterOffset * 2, cornerCenterOffset * 2),
        targetComponent,
        name='Wall junction pocket cones pattern',
    )
    # pattern bodies include the source cone, the collection skips the duplicate
    coneBodies = list(conePattern.bodies) + [coneBody]
    if openSide is not None:
        def isOnOpenSide(body: adsk.fusion.BRepBody) -> bool:
            box = body.boundingBox
            return ((box.minPoint.x + box.maxPoint.x) / 2 - junctionX.value) * openSide[0] > 0 \
                and ((box.minPoint.y + box.maxPoint.y) / 2 - junctionY.value) * openSide[1] > 0
        openCones = [body for body in coneBodies if isOnOpenSide(body)]
        for body in openCones:
            features.removeFeatures.add(body).name = 'Wall junction pocket open side cone remove'
        coneBodies = [body for body in coneBodies if not isOnOpenSide(body)]

    combineUtils.cutBody(pocketBody, commonUtils.objectCollectionFromList(coneBodies), targetComponent, name='Wall junction pocket shape')
    return pocketBody

def placeAtWallJunctions(
    createAt: Callable[[Dim, Dim], adsk.fusion.BRepBody],
    origin: adsk.core.Point3D,
    baseWidth: Dim,
    baseLength: Dim,
    columns: float,
    rows: float,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> list[adsk.fusion.BRepBody]:
    """A body at every point along the outer walls where feet meet, made once at the first junction of the front
    wall and patterned along the walls. It has to be symmetric across the wall to serve both opposite ones.
    Feet meet on every grid line from the origin, a half cell left over adds one more before its half feet, see createFootGrid"""
    baseWidth = baseWidth.asExpression()
    baseLength = baseLength.asExpression()
    junctionsX = math.ceil(columns - 1e-6) - 1
    junctionsY = math.ceil(rows - 1e-6) - 1
    if junctionsX <= 0 and junctionsY <= 0:
        return []

    bodies: list[adsk.fusion.BRepBody] = []
    frontBody = createAt(Dim.length(origin.x) + baseWidth, Dim.length(origin.y))
    if junctionsY > 0:
        # the first left wall junction is always one base back and up from the first front one
        if junctionsX > 0:
            copyFeature = targetComponent.features.copyPasteBodies.add(frontBody)
            copyFeature.name = f'{name} copy'
            sideBody = copyFeature.bodies.item(0)
        else:
            sideBody = frontBody
        moveInput = targetComponent.features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([sideBody]))
        moveInput.defineAsTranslateXYZ(
            valueInput(baseWidth * -1),
            valueInput(baseLength),
            valueInput(0),
            True,
        )
        targetComponent.features.moveFeatures.add(moveInput).name = f'{name} move to left wall'
        pattern = patternUtils.recPatternGrid(
            commonUtils.objectCollectionFromList([sideBody]),
            (2, junctionsY),
            (baseWidth * columns, baseLength),
            targetComponent,
            name=f'{name}s left and right pattern',
        )
        # pattern bodies include the source body, the collection skips the duplicate
        bodies += list(pattern.bodies) + [sideBody]
    if junctionsX > 0:
        pattern = patternUtils.recPatternGrid(
            commonUtils.objectCollectionFromList([frontBody]),
            (junctionsX, 2),
            (baseWidth, baseLength * rows),
            targetComponent,
            name=f'{name}s front and back pattern',
        )
        bodies += list(pattern.bodies) + [frontBody]
    return bodies

def cutWallJunctionPockets(
    baseConfiguration: BaseGeneratorInput,
    columns: float,
    rows: float,
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.CombineFeature:
    """Curves up the gaps between feet along all outer walls instead of leaving flat overhangs there, see placeAtWallJunctions"""
    origin = baseConfiguration.originPoint
    # cutters are symmetric, so one row of them serves both opposite walls
    cutters = placeAtWallJunctions(
        lambda x, y: createWallJunctionPocketCutter(
            x,
            y,
            origin.z,
            baseConfiguration.cornerFilletRadius,
            baseConfiguration.xyClearance,
            targetComponent,
        ),
        origin,
        baseConfiguration.baseWidth,
        baseConfiguration.baseLength,
        columns,
        rows,
        targetComponent,
        name='Wall junction pocket',
    )
    return combineUtils.cutBody(targetBody, commonUtils.objectCollectionFromList(cutters), targetComponent, name='Wall junction pockets cut')

def cutOutsideRoundedRectangle(
    cornerPoint: adsk.core.Point3D,
    width: Dim | float,
    length: Dim | float,
    filletRadius: float,
    targetBodies: list[adsk.fusion.BRepBody],
    targetComponent: adsk.fusion.Component,
    cornerX: Dim = None,
    cornerY: Dim = None,
    *,
    name: str,
) -> adsk.fusion.ExtrudeFeature:
    """Cuts everything outside a rounded rectangle from the target bodies, through their full height.
    The optional corner dims drive the corner position. Plane, sketch and cut are named after the given name"""
    features = targetComponent.features
    cutConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    cutConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, adsk.core.ValueInput.createByReal(cornerPoint.z))
    cutConstructionPlane = targetComponent.constructionPlanes.add(cutConstructionPlaneInput)
    cutConstructionPlane.name = f'{name} plane'
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    cutSketch: adsk.fusion.Sketch = sketches.add(cutConstructionPlane)
    cutSketch.name = f'{name} sketch'
    innerRectangle = createRectangle(
        width,
        length,
        cornerPoint,
        cutSketch,
        cornerX,
        cornerY,
    )
    sketchArcs = cutSketch.sketchCurves.sketchArcs
    geometricConstraints = cutSketch.geometricConstraints
    sketchDimensions = cutSketch.sketchDimensions

    [side1, side2, side3, side4] = list(innerRectangle)
    fillet1 = sketchArcs.addFillet(side1, side1.endSketchPoint.geometry, side2, side2.startSketchPoint.geometry, filletRadius)
    fillet2 = sketchArcs.addFillet(side2, side2.endSketchPoint.geometry, side3, side3.startSketchPoint.geometry, filletRadius)
    fillet3 = sketchArcs.addFillet(side3, side3.endSketchPoint.geometry, side4, side4.startSketchPoint.geometry, filletRadius)
    fillet4 = sketchArcs.addFillet(side4, side4.endSketchPoint.geometry, side1, side1.startSketchPoint.geometry, filletRadius)

    geometricConstraints.addEqual(fillet1, fillet2)
    geometricConstraints.addEqual(fillet2, fillet3)
    geometricConstraints.addEqual(fillet3, fillet4)
    sketchDimensions.addRadialDimension(fillet1, fillet1.startSketchPoint.geometry)

    # offset outwards, towards a point past the rectangle corner
    outsidePoint = adsk.core.Point3D.create(cornerPoint.x - 1, cornerPoint.y - 1, 0)
    cutSketch.offset(commonUtils.objectCollectionFromList([fillet1, fillet2, fillet3, fillet4, side1, side2, side3, side4]), outsidePoint, 1)

    cuttingProfile = min(list(cutSketch.profiles), key=lambda x: x.boundingBox.minPoint.x)
    cutExtrudeInput = features.extrudeFeatures.createInput(
        cuttingProfile,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    cutExtrudeInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
    )
    # the target component can be the root of a part design, which also holds unrelated bodies
    cutExtrudeInput.participantBodies = targetBodies
    cutExtrude = features.extrudeFeatures.add(cutExtrudeInput)
    cutExtrude.name = name
    return cutExtrude
def shapeGridInput(baseWidth: Dim, baseLength: Dim, xyClearance: float, cellsPerFoot: int = 1) -> BaseGeneratorInput:
    """
    The base grid of a bin, for shape outlines and picking cells, cells start a clearance before the origin.
    Its cells are the base size, or the given part of it for an outline in half cells, see binGrid.outlineCellsPerFoot
    """
    grid = BaseGeneratorInput()
    grid.originPoint = adsk.core.Point3D.create(-xyClearance, -xyClearance, 0)
    grid.baseWidth = baseWidth / cellsPerFoot if cellsPerFoot != 1 else baseWidth
    grid.baseLength = baseLength / cellsPerFoot if cellsPerFoot != 1 else baseLength
    grid.xyClearance = xyClearance
    return grid

def keepBodiesInCells(
    bodies: list[adsk.fusion.BRepBody],
    cells: list[tuple[int, int]],
    baseConfiguration: BaseGeneratorInput,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> list[adsk.fusion.BRepBody]:
    """Bodies centred over one of the cells, the others are removed. Cells start at the base origin point.
    Bodies listed twice are taken once, pattern results may include their source"""
    origin = baseConfiguration.originPoint
    filled = set(cells)
    kept = []
    seen = set()
    for body in bodies:
        if body.revisionId in seen:
            continue
        seen.add(body.revisionId)
        box = body.boundingBox
        column = math.floor(((box.minPoint.x + box.maxPoint.x) / 2 - origin.x) / baseConfiguration.baseWidth.value)
        row = math.floor(((box.minPoint.y + box.maxPoint.y) / 2 - origin.y) / baseConfiguration.baseLength.value)
        if (column, row) in filled:
            kept.append(body)
        else:
            targetComponent.features.removeFeatures.add(body).name = name
    return kept

def cellLineDim(baseUnit: Dim, index: int, shift: float) -> Dim:
    """Coordinate of a grid line moved by the shift, the grid line counted from the origin in base units"""
    line = baseUnit * index if index != 1 else baseUnit
    if abs(shift) < 1e-9:
        return line if index != 0 else Dim.length(0)
    return line + Dim.length(shift) if index != 0 else Dim.length(shift)

def createShapeOutlineSketch(
    cells: list[tuple[int, int]],
    baseConfiguration: BaseGeneratorInput,
    offset: float,
    plane: adsk.core.Base,
    targetComponent: adsk.fusion.Component,
    minConvexRadius: float = 0,
    *,
    name: str,
) -> tuple[adsk.fusion.Sketch, list[tuple[float, float, bool]]]:
    """
    Outline of the cells moved in by the offset from the cell lines, with the corners it has in model coordinates.
    Corners are rounded around where a bin's corner is, see binShape.cornerRadius, so the outer ones match a plain
    bin and inner ones keep an even gap to a bin filling the notch. Outer corners stay at least the given radius.
    Sides are dimensioned with the base units, the sketch follows their parameters
    """
    origin = baseConfiguration.originPoint
    baseWidth = baseConfiguration.baseWidth.asExpression()
    baseLength = baseConfiguration.baseLength.asExpression()
    gridCorners = binShape.outline(cells)
    corners = [
        (origin.x + x, origin.y + y, isConvex)
        for (x, y, isConvex) in binShape.insetOutline(gridCorners, baseConfiguration.baseWidth.value, baseConfiguration.baseLength.value, offset)
    ]

    sketch: adsk.fusion.Sketch = targetComponent.sketches.add(plane)
    sketch.name = f'{name} sketch'
    lines: list[adsk.fusion.SketchLine] = []
    with sketchUtils.deferSketchCompute(sketch):
        constraints = sketch.geometricConstraints
        dimensions = sketch.sketchDimensions
        sketchLines = sketch.sketchCurves.sketchLines
        points = []
        for (x, y, _) in corners:
            point = sketch.modelToSketchSpace(adsk.core.Point3D.create(x, y, 0))
            point.z = 0
            points.append(point)
        for (index, point) in enumerate(points):
            start = lines[-1].endSketchPoint if len(lines) > 0 else point
            end = lines[0].startSketchPoint if index == len(points) - 1 else points[index + 1]
            lines.append(sketchLines.addByTwoPoints(start, end))
        for (index, line) in enumerate(lines):
            (gridX, gridY, _) = gridCorners[index]
            (nextGridX, nextGridY, _) = gridCorners[(index + 1) % len(gridCorners)]
            isHorizontal = gridY == nextGridY
            if isHorizontal:
                constraints.addHorizontal(line)
                # the inside is above a side running right, a cell line plus the offset, or below one running left
                distance = cellLineDim(baseLength, gridY, origin.y + (offset if nextGridX > gridX else -offset))
            else:
                constraints.addVertical(line)
                distance = cellLineDim(baseWidth, gridX, origin.x + (offset if nextGridY < gridY else -offset))
            if abs(distance.value) < 1e-6:
                constraints.addCoincident(sketch.originPoint, line)
                continue
            textPoint = line.startSketchPoint.geometry
            # sketch distance dimensions are unsigned
            applyTo(dimensions.addDistanceDimension(
                sketch.originPoint,
                line.startSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation if isHorizontal else adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(textPoint.x / 2, textPoint.y / 2, 0),
                True,
            ).parameter, distance if distance.value >= 0 else distance * -1)

    # one radius for the outer corners and one for the inner ones
    sketchArcs = sketch.sketchCurves.sketchArcs
    fillets: dict[bool, list[adsk.fusion.SketchArc]] = {True: [], False: []}
    for (index, (_, _, isConvex)) in enumerate(corners):
        incoming = lines[index - 1]
        outgoing = lines[index]
        radius = binShape.cornerRadius(isConvex, baseConfiguration.cornerFilletRadius, offset)
        fillets[isConvex].append(sketchArcs.addFillet(
            incoming,
            incoming.endSketchPoint.geometry,
            outgoing,
            outgoing.startSketchPoint.geometry,
            max(radius, minConvexRadius) if isConvex else radius,
        ))
    for group in fillets.values():
        for fillet in group[1:]:
            sketch.geometricConstraints.addEqual(group[0], fillet)
        if len(group) > 0:
            sketch.sketchDimensions.addRadialDimension(group[0], group[0].startSketchPoint.geometry)
    return (sketch, corners)

def cutOutsideShape(
    cells: list[tuple[int, int]],
    baseConfiguration: BaseGeneratorInput,
    targetBodies: list[adsk.fusion.BRepBody],
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> adsk.fusion.ExtrudeFeature:
    """Cuts everything outside the outline of the cells, a clearance in from the cell lines, through the full height
    of the target bodies, see createShapeOutlineSketch"""
    features = targetComponent.features
    (cutSketch, corners) = createShapeOutlineSketch(
        cells,
        baseConfiguration,
        baseConfiguration.xyClearance,
        targetComponent.xYConstructionPlane,
        targetComponent,
        name=name,
    )

    # a frame around the outline, as far again past it on every side, its region less the outline is cut
    minX = min(x for (x, _, _) in corners)
    minY = min(y for (_, y, _) in corners)
    maxX = max(x for (x, _, _) in corners)
    maxY = max(y for (_, y, _) in corners)
    margin = max(maxX - minX, maxY - minY)
    frameCorner1 = cutSketch.modelToSketchSpace(adsk.core.Point3D.create(minX - margin, minY - margin, 0))
    frameCorner2 = cutSketch.modelToSketchSpace(adsk.core.Point3D.create(maxX + margin, maxY + margin, 0))
    (frameCorner1.z, frameCorner2.z) = (0, 0)
    cutSketch.sketchCurves.sketchLines.addTwoPointRectangle(frameCorner1, frameCorner2)

    def area(profile: adsk.fusion.Profile) -> float:
        box = profile.boundingBox
        return (box.maxPoint.x - box.minPoint.x) * (box.maxPoint.y - box.minPoint.y)
    cuttingProfile = max(list(cutSketch.profiles), key=area)
    cutExtrudeInput = features.extrudeFeatures.createInput(
        cuttingProfile,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    cutExtrudeInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
    )
    # the target component can be the root of a part design, which also holds unrelated bodies
    cutExtrudeInput.participantBodies = targetBodies
    cutExtrude = features.extrudeFeatures.add(cutExtrudeInput)
    cutExtrude.name = name
    return cutExtrude

def placeAtShapeWallJunctions(
    createAt: Callable[[Dim, Dim, tuple[int, int] | None], adsk.fusion.BRepBody],
    baseConfiguration: BaseGeneratorInput,
    cells: list[tuple[int, int]],
    targetComponent: adsk.fusion.Component,
    footLines: tuple[set[int], set[int]] = None,
    *,
    name: str,
) -> list[adsk.fusion.BRepBody]:
    """
    placeAtWallJunctions for any shape, a body at every point of the outline where feet meet, see binShape.wallJunctions.
    Inner corners get their own bodies, made with the direction of the empty cell beside them, see binShape.innerCornerOpenings.
    With the grid lines where feet meet, see binGrid.footLines, an outline in half cells only gets them on those
    """
    junctions = binShape.wallJunctions(cells)
    if footLines is not None:
        junctions = [(x, y) for (x, y) in junctions if x in footLines[0] and y in footLines[1]]
    if len(junctions) == 0:
        return []
    openings = binShape.innerCornerOpenings(cells)
    sides = [point for point in junctions if point not in openings]
    origin = baseConfiguration.originPoint
    baseWidth = baseConfiguration.baseWidth.asExpression()
    baseLength = baseConfiguration.baseLength.asExpression()

    def gridOffset(baseUnit: Dim, count: int) -> Dim | float:
        if count == 0:
            return 0
        return baseUnit * count if count != 1 else baseUnit

    bodies = []
    if len(sides) > 0:
        # one body at the origin, copied and moved by base units to each junction. Every feature keeps a reference
        # of its own body, the bodies of a pattern with some removed lose theirs once it's recomputed, after the base
        # units change
        source = createAt(Dim.length(origin.x), Dim.length(origin.y), None)
        for (index, (x, y)) in enumerate(sorted(sides)):
            if index == len(sides) - 1:
                body = source
            else:
                copyFeature = targetComponent.features.copyPasteBodies.add(source)
                copyFeature.name = f'{name} copy'
                body = copyFeature.bodies.item(0)
            if (x, y) != (0, 0):
                moveInput = targetComponent.features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([body]))
                moveInput.defineAsTranslateXYZ(
                    valueInput(gridOffset(baseWidth, x)),
                    valueInput(gridOffset(baseLength, y)),
                    valueInput(0),
                    True,
                )
                targetComponent.features.moveFeatures.add(moveInput).name = f'{name} move to {x}, {y}'
            bodies.append(body)

    for ((x, y), openSide) in openings.items():
        bodies.append(createAt(
            Dim.length(origin.x) + (baseWidth * x if x != 1 else baseWidth),
            Dim.length(origin.y) + (baseLength * y if y != 1 else baseLength),
            openSide,
        ))
    return bodies

def cutShapeWallJunctionPockets(
    baseConfiguration: BaseGeneratorInput,
    cells: list[tuple[int, int]],
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
    footLines: tuple[set[int], set[int]] = None,
) -> adsk.fusion.CombineFeature | None:
    """
    cutWallJunctionPockets for any shape, see placeAtShapeWallJunctions. Pockets at inner corners are open towards
    the empty cell, see createWallJunctionPocketCutter
    """
    origin = baseConfiguration.originPoint
    cutters = placeAtShapeWallJunctions(
        lambda x, y, openSide: createWallJunctionPocketCutter(
            x,
            y,
            origin.z,
            baseConfiguration.cornerFilletRadius,
            baseConfiguration.xyClearance,
            targetComponent,
            openSide,
        ),
        baseConfiguration,
        cells,
        targetComponent,
        footLines,
        name='Wall junction pocket',
    )
    if len(cutters) == 0:
        return None
    return combineUtils.cutBody(targetBody, commonUtils.objectCollectionFromList(cutters), targetComponent, name='Wall junction pockets cut')
