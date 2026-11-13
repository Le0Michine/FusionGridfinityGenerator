import adsk.core, adsk.fusion, traceback
import os
import math

from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils, binShape
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyLipGeneratorInput import BinBodyLipGeneratorInput
from .dim import Dim, valueInput

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

    if input.hasLipNotches:
        lipCutoutInput = BaseGeneratorInput()
        lipCutoutInput.originPoint = geometryUtils.createOffsetPoint(
            input.origin,
            byX=-input.xyClearance * 2,
            byY=-input.xyClearance * 2,
            byZ=const.BIN_BASE_HEIGHT
        )
        lipCutoutInput.originZ = input.originZ + Dim.length(const.BIN_BASE_HEIGHT)
        lipCutoutInput.baseWidth = input.baseWidth + Dim.length(input.xyClearance * 2)
        lipCutoutInput.baseLength = input.baseLength + Dim.length(input.xyClearance * 2)
        lipCutoutInput.xyClearance = input.xyClearance
        lipCutoutInput.hasBottomChamfer = False
        lipCutoutInput.cornerFilletRadius = input.binCornerFilletRadius + input.xyClearance * 2
        # one per foot of a bin stacked on top, half ones included
        lipCutoutBodies = baseGenerator.createFootGrid(
            lipCutoutInput,
            input.binWidth,
            input.binLength,
            targetComponent,
            input.baseWidth,
            input.baseLength,
            name='Lip notch cutout',
        )

    if input.hasLipNotches and input.shapeCells is not None:
        # notches go by feet, the outline may be in half cells
        lipCutoutBodies = baseGenerator.keepBodiesInCells(
            lipCutoutBodies,
            binShape.mergeCells(input.shapeCells, input.shapeCellsPerFoot),
            baseGenerator.shapeGridInput(input.baseWidth, input.baseLength, input.xyClearance),
            targetComponent,
            name='Lip notch outside shape remove',
        )
        bodiesToSubtract.append(createShapeLipMiddleCutout(input, lipBodyHeight, targetComponent))
    elif input.hasLipNotches:
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

    elif input.shapeCells is not None:
        lipCutoutBodies.append(createShapeLipSocket(input, targetComponent))
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
