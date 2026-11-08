import adsk.core, adsk.fusion, traceback, math
import os

from .sketchUtils import createRectangle
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from .dim import Dim, valueInput, applyTo
from . import sketchUtils, const, edgeUtils, commonUtils, combineUtils, faceUtils, extrudeUtils, shapeUtils, geometryUtils, patternUtils
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
):
    baseBody = createSingleGridfinityBaseBody(baseConfiguration, targetComponent, name='Foot')
    features = targetComponent.features
    # replicate base in a rectangular pattern
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()
    patternInputBodies.add(baseBody)
    patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
        targetComponent.xConstructionAxis,
        valueInput(basesXCount),
        valueInput(baseConfiguration.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = valueInput(basesYCount)
    patternInput.distanceTwo = valueInput(baseConfiguration.baseLength)
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    rectangularPattern.name = 'Feet pattern'
    return list(rectangularPattern.bodies) + [baseBody]

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
) -> adsk.fusion.BRepBody:
    """Negative volume curving up the gap where two feet meet at an outer wall, continuing the 45 degree
    chamfers of the foot corners above their top until they close the gap. The cones are concentric with the
    foot corners and start where the clearance trim meets the chamfer, a clearance below the feet top"""
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

    combineUtils.cutBody(pocketBody, commonUtils.objectCollectionFromList(coneBodies), targetComponent, name='Wall junction pocket shape')
    return pocketBody

def cutWallJunctionPockets(
    baseConfiguration: BaseGeneratorInput,
    basesXCount: int,
    basesYCount: int,
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.CombineFeature:
    """Curves up the gaps between feet along all outer walls instead of leaving flat overhangs there"""
    origin = baseConfiguration.originPoint
    baseWidth = baseConfiguration.baseWidth.asExpression()
    baseLength = baseConfiguration.baseLength.asExpression()

    # cutters are symmetric, so one row of them serves both opposite walls
    cutters: list[adsk.fusion.BRepBody] = []
    frontCutter = createWallJunctionPocketCutter(
        Dim.length(origin.x) + baseWidth,
        Dim.length(origin.y),
        origin.z,
        baseConfiguration.cornerFilletRadius,
        baseConfiguration.xyClearance,
        targetComponent,
    )
    if basesYCount > 1:
        # the first left wall junction is always one base back and up from the first front one
        if basesXCount > 1:
            copyFeature = targetComponent.features.copyPasteBodies.add(frontCutter)
            copyFeature.name = 'Wall junction pocket copy'
            sideCutter = copyFeature.bodies.item(0)
        else:
            sideCutter = frontCutter
        moveInput = targetComponent.features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([sideCutter]))
        moveInput.defineAsTranslateXYZ(
            valueInput(baseWidth * -1),
            valueInput(baseLength),
            valueInput(0),
            True,
        )
        targetComponent.features.moveFeatures.add(moveInput).name = 'Wall junction pocket move to left wall'
        pattern = patternUtils.recPatternGrid(
            commonUtils.objectCollectionFromList([sideCutter]),
            (2, basesYCount - 1),
            (baseWidth * basesXCount, baseLength),
            targetComponent,
            name='Wall junction pockets left and right pattern',
        )
        # pattern bodies include the source cutter, the collection skips the duplicate
        cutters += list(pattern.bodies) + [sideCutter]
    if basesXCount > 1:
        pattern = patternUtils.recPatternGrid(
            commonUtils.objectCollectionFromList([frontCutter]),
            (basesXCount - 1, 2),
            (baseWidth, baseLength * basesYCount),
            targetComponent,
            name='Wall junction pockets front and back pattern',
        )
        cutters += list(pattern.bodies) + [frontCutter]

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