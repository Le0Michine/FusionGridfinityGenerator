import adsk.core, adsk.fusion, traceback
import os
import math

from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils, binGrid, patternUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyLipGeneratorInput import BinBodyLipGeneratorInput
from .dim import Dim, valueInput, applyTo

app = adsk.core.Application.get()
ui = app.userInterface

def createShapeLipSocket(
    input: BinBodyLipGeneratorInput,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.BRepBody:
    """
    The lip cutout of a shaped bin, a foot following the outline the feet of a bin of the same shape stacked on top
    sit in. Like the plain one it starts a clearance outside the cell lines, the 45 degree top section is a tapered
    extrude, so its corners stay concentric with the bin's all the way down
    """
    grid = baseGenerator.shapeGridInput(input.baseWidth, input.baseLength, input.xyClearance, input.shapeCellsPerFoot)
    planeInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(input.originZ + Dim.length(const.BIN_BASE_HEIGHT)))
    plane = targetComponent.constructionPlanes.add(planeInput)
    plane.name = 'Lip cutout plane'
    (sketch, _) = baseGenerator.createShapeOutlineSketch(
        input.shapeCells,
        grid,
        -input.xyClearance,
        plane,
        targetComponent,
        name='Lip cutout',
    )
    topSection = extrudeUtils.taperedExtrude(
        sketch.profiles.item(0),
        const.BIN_BASE_TOP_SECTION_HEIGH,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        targetComponent,
        name='Lip cutout top section',
    )
    socket = topSection.bodies.item(0)
    socket.name = 'Lip cutout'
    extrudeUtils.simpleDistanceExtrude(
        topSection.endFaces.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        const.BIN_BASE_MID_SECTION_HEIGH + const.BIN_BASE_BOTTOM_SECTION_HEIGH,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [socket],
        targetComponent,
        name='Lip cutout bottom section',
    )
    return socket

def createShapeLipMiddleCutout(
    input: BinBodyLipGeneratorInput,
    height: float,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.BRepBody:
    """Inside of the lip wall of a shaped bin, between the notches"""
    grid = baseGenerator.shapeGridInput(input.baseWidth, input.baseLength, input.xyClearance, input.shapeCellsPerFoot)
    planeInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(input.originZ))
    plane = targetComponent.constructionPlanes.add(planeInput)
    plane.name = 'Lip middle cutout plane'
    (sketch, _) = baseGenerator.createShapeOutlineSketch(
        input.shapeCells,
        grid,
        input.wallThickness,
        plane,
        targetComponent,
        const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS,
        name='Lip middle cutout',
    )
    cutout = extrudeUtils.simpleDistanceExtrude(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        height,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
        name='Lip middle cutout',
    )
    return cutout.bodies.item(0)

def createLipNotch(
    junctionX: Dim,
    junctionY: Dim,
    input: BinBodyLipGeneratorInput,
    targetComponent: adsk.fusion.Component,
    openSide: tuple[int, int] = None,
) -> adsk.fusion.BRepBody:
    """
    The part of the lip socket where two feet of a bin stacked on top meet, a box around the grid junction less
    the socket corners of the feet around it. Taken out of the socket, it leaves the lip standing between the feet.
    The cones are concentric with the bin corners, like the socket's own they narrow at 45 degrees through its top
    section and go straight down below it. The open side, see baseGenerator.createWallJunctionPocketCutter, has no foot
    """
    features = targetComponent.features
    # fed as expressions, so the formulas stay readable in the model
    clearance = Dim.length(input.xyClearance).asExpression()
    # the bin corners are the bin corner radius in from the outline, a clearance in from the grid lines
    cornerCenterOffset = Dim.length(input.binCornerFilletRadius).asExpression() + clearance
    topSectionHeight = Dim.length(const.BIN_BASE_TOP_SECTION_HEIGH)
    lowerSectionsHeight = Dim.length(const.BIN_BASE_MID_SECTION_HEIGH + const.BIN_BASE_BOTTOM_SECTION_HEIGH)
    # the socket starts a clearance outside the grid lines, its corners narrow by the top section height
    coneSketchRadius = cornerCenterOffset + clearance - topSectionHeight
    # first foot corner center, the box corner and the source cone of the pattern
    cornerCenterX = junctionX - cornerCenterOffset
    cornerCenterY = junctionY - cornerCenterOffset

    # where the socket's top section ends, box and cones start there
    notchPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    notchPlaneZ = input.originZ + lowerSectionsHeight
    notchPlaneInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(notchPlaneZ))
    notchPlane = targetComponent.constructionPlanes.add(notchPlaneInput)
    notchPlane.name = 'Lip notch plane'

    boxSketch: adsk.fusion.Sketch = targetComponent.sketches.add(notchPlane)
    boxSketch.name = 'Lip notch sketch'
    boxCornerOnSketch = boxSketch.modelToSketchSpace(adsk.core.Point3D.create(
        cornerCenterX.value,
        cornerCenterY.value,
        notchPlaneZ.value,
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
    # down to the lip bottom and past the socket top, where neighbouring cones overlap, they only touch at the top
    # without a clearance and combine can't handle that
    boxExtrudeInput = features.extrudeFeatures.createInput(boxSketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    boxExtrudeInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(valueInput(topSectionHeight * 1.5)),
        adsk.fusion.DistanceExtentDefinition.create(valueInput(lowerSectionsHeight)),
    )
    boxExtrude = features.extrudeFeatures.add(boxExtrudeInput)
    boxExtrude.name = 'Lip notch box'
    notchBody = boxExtrude.bodies.item(0)
    notchBody.name = 'Lip notch'

    # one cone per foot corner around the junction, the outer ones only clip what lies outside the bin
    coneSketch: adsk.fusion.Sketch = targetComponent.sketches.add(notchPlane)
    coneSketch.name = 'Lip notch cone sketch'
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
    coneHeight = topSectionHeight * 2
    coneExtrudeInput = features.extrudeFeatures.createInput(coneSketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    coneExtrudeInput.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(valueInput(coneHeight)),
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        adsk.core.ValueInput.createByString('45 deg'),
    )
    coneExtrude = features.extrudeFeatures.add(coneExtrudeInput)
    coneExtrude.name = 'Lip notch cone'
    coneBody = coneExtrude.bodies.item(0)
    coneBox = coneBody.boundingBox
    if coneBox.maxPoint.x - coneBox.minPoint.x < coneSketchRadius.value * 2 + coneHeight.value:
        # taper went inwards, flip it so the cone widens upwards like the socket corner it follows
        coneExtrude.taperAngleOne.expression = '-45 deg'
    # straight below like the socket, past the box bottom so they don't share it
    extrudeUtils.simpleDistanceExtrude(
        coneExtrude.startFaces.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        lowerSectionsHeight + topSectionHeight,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [coneBody],
        targetComponent,
        name='Lip notch cone bottom',
    )

    conePattern = patternUtils.recPatternGrid(
        commonUtils.objectCollectionFromList([coneBody]),
        (2, 2),
        (cornerCenterOffset * 2, cornerCenterOffset * 2),
        targetComponent,
        name='Lip notch cones pattern',
    )
    # pattern bodies include the source cone, the collection skips the duplicate
    coneBodies = list(conePattern.bodies) + [coneBody]
    if openSide is not None:
        def isOnOpenSide(body: adsk.fusion.BRepBody) -> bool:
            box = body.boundingBox
            return ((box.minPoint.x + box.maxPoint.x) / 2 - junctionX.value) * openSide[0] > 0 \
                and ((box.minPoint.y + box.maxPoint.y) / 2 - junctionY.value) * openSide[1] > 0
        for body in [body for body in coneBodies if isOnOpenSide(body)]:
            features.removeFeatures.add(body).name = 'Lip notch open side cone remove'
        coneBodies = [body for body in coneBodies if not isOnOpenSide(body)]

    combineUtils.cutBody(notchBody, commonUtils.objectCollectionFromList(coneBodies), targetComponent, name='Lip notch shape')
    return notchBody

def createLipNotches(
    input: BinBodyLipGeneratorInput,
    targetComponent: adsk.fusion.Component,
) -> list[adsk.fusion.BRepBody]:
    """A notch where feet of a bin stacked on top meet along the walls, one made and placed like the wall junction pockets"""
    if input.shapeCells is not None:
        return baseGenerator.placeAtShapeWallJunctions(
            lambda x, y, openSide: createLipNotch(x, y, input, targetComponent, openSide),
            baseGenerator.shapeGridInput(input.baseWidth, input.baseLength, input.xyClearance, input.shapeCellsPerFoot),
            input.shapeCells,
            targetComponent,
            (binGrid.footLines(input.binWidth, input.shapeCellsPerFoot), binGrid.footLines(input.binLength, input.shapeCellsPerFoot)),
            name='Lip notch',
        )
    # the grid starts a clearance before the lip outline
    gridOrigin = geometryUtils.createOffsetPoint(input.origin, byX=-input.xyClearance, byY=-input.xyClearance)
    return baseGenerator.placeAtWallJunctions(
        lambda x, y: createLipNotch(x, y, input, targetComponent),
        gridOrigin,
        input.baseWidth,
        input.baseLength,
        input.binWidth,
        input.binLength,
        targetComponent,
        name='Lip notch',
    )

def createGridfinityBinBodyLip(
    input: BinBodyLipGeneratorInput,
    targetComponent: adsk.fusion.Component,
):
    actualLipBodyWidth = input.baseWidth * input.binWidth - Dim.length(input.xyClearance * 2)
    actualLipBodyLength = input.baseLength * input.binLength - Dim.length(input.xyClearance * 2)
    lipBodyHeight = const.BIN_LIP_EXTRA_HEIGHT
    features: adsk.fusion.Features = targetComponent.features

    lipBodyExtrude = extrudeUtils.createBoxAtPoint(
        actualLipBodyWidth,
        actualLipBodyLength,
        lipBodyHeight,
        targetComponent,
        input.origin,
        input.originZ,
        name='Lip body',
    )
    lipBody = lipBodyExtrude.bodies.item(0)
    lipBody.name = 'Lip body'

    bodiesToSubtract: list[adsk.fusion.BRepBody] = []

    # round corners
    filletUtils.filletEdgesByLength(
        lipBodyExtrude.faces,
        input.binCornerFilletRadius,
        lipBodyHeight,
        targetComponent,
        name='Lip body corner fillets',
    )

    lipCutoutBodies: list[adsk.fusion.BRepBody] = []
    lipCutoutPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    lipCutoutPlaneInput.setByOffset(
        lipBodyExtrude.endFaces.item(0),
        adsk.core.ValueInput.createByReal(0)
    )

    if input.shapeCells is not None:
        lipCutout = createShapeLipSocket(input, targetComponent)
    else:
        lipCutoutInput = BaseGeneratorInput()
        lipCutoutInput.originPoint = geometryUtils.createOffsetPoint(
            input.origin,
            byX=-input.xyClearance * 2,
            byY=-input.xyClearance * 2,
            byZ=const.BIN_BASE_HEIGHT
        )
        lipCutoutInput.originZ = input.originZ + Dim.length(const.BIN_BASE_HEIGHT)
        lipCutoutInput.baseWidth = input.baseWidth * input.binWidth + Dim.length(input.xyClearance * 2)
        lipCutoutInput.baseLength = input.baseLength * input.binLength + Dim.length(input.xyClearance * 2)
        lipCutoutInput.xyClearance = input.xyClearance
        lipCutoutInput.hasBottomChamfer = False
        lipCutoutInput.cornerFilletRadius = input.binCornerFilletRadius + input.xyClearance * 2
        lipCutout = baseGenerator.createSingleGridfinityBaseBody(lipCutoutInput, targetComponent, name='Lip cutout')
    lipCutoutBodies.append(lipCutout)

    if input.hasLipNotches:
        # the lip is left a wall, standing up to its full width where feet of a bin stacked on top meet
        notches = createLipNotches(input, targetComponent)
        if len(notches) > 0:
            combineUtils.cutBody(lipCutout, commonUtils.objectCollectionFromList(notches), targetComponent, name='Lip notches cut')
        if input.shapeCells is not None:
            bodiesToSubtract.append(createShapeLipMiddleCutout(input, lipBodyHeight, targetComponent))
        else:
            lipMiddleCutoutOrigin = geometryUtils.createOffsetPoint(
                input.origin,
                byX=input.wallThickness - input.xyClearance,
                byY=input.wallThickness - input.xyClearance,
            )
            lipMidCutout = extrudeUtils.createBoxAtPoint(
                actualLipBodyWidth - Dim.length(input.wallThickness * 2 - input.xyClearance * 2),
                actualLipBodyLength - Dim.length(input.wallThickness * 2 - input.xyClearance * 2),
                lipBodyHeight,
                targetComponent,
                lipMiddleCutoutOrigin,
                input.originZ,
                name='Lip middle cutout',
            )
            filletUtils.filletEdgesByLength(
                lipMidCutout.faces,
                input.binCornerFilletRadius - input.wallThickness + input.xyClearance,
                lipBodyHeight,
                targetComponent,
                name='Lip middle cutout fillets',
            )
            bodiesToSubtract.append(lipMidCutout.bodies.item(0))

    if const.BIN_LIP_TOP_RECESS_HEIGHT > const.DEFAULT_FILTER_TOLERANCE:
        lipCutoutConstructionPlane = targetComponent.constructionPlanes.add(lipCutoutPlaneInput)
        lipCutoutConstructionPlane.name = 'Lip top chamfer plane'
        topChamferSketch: adsk.fusion.Sketch = targetComponent.sketches.add(lipCutoutConstructionPlane)
        topChamferSketch.name = 'Lip top chamfer sketch'
        sketchUtils.createRectangle(
            actualLipBodyWidth,
            actualLipBodyLength,
            topChamferSketch.modelToSketchSpace(adsk.core.Point3D.create(0, 0, topChamferSketch.origin.z)),
            topChamferSketch,
        )
        topChamferNegativeVolume = extrudeUtils.simpleDistanceExtrude(
            topChamferSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            const.BIN_LIP_TOP_RECESS_HEIGHT,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
            name='Lip top chamfer',
        )
        bodiesToSubtract.append(topChamferNegativeVolume.bodies.item(0))
    bodiesToSubtract = bodiesToSubtract + lipCutoutBodies

    combineUtils.cutBody(
        lipBody,
        commonUtils.objectCollectionFromList(bodiesToSubtract),
        targetComponent,
        name='Lip cutouts cut',
    )

    return lipBody
