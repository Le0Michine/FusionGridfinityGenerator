import adsk.core, adsk.fusion, traceback
import os
import math

from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyLipGeneratorInput import BinBodyLipGeneratorInput

app = adsk.core.Application.get()
ui = app.userInterface

def getInnerCutoutScoopFace(
    innerCutout: adsk.fusion.BRepBody
) -> tuple[adsk.fusion.BRepFace, adsk.fusion.BRepFace]:
    innerCutoutYNormalFaces = [face for face in innerCutout.faces if faceUtils.isYNormal(face)]
    scoopFace = min(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    oppositeFace = max(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    return (scoopFace, oppositeFace)

def createGridfinityBinBodyLip(
    input: BinBodyLipGeneratorInput,
    targetComponent: adsk.fusion.Component,
):
    actualLipBodyWidth = (input.baseWidth * input.binWidth) + input.paddingLeft + input.paddingRight - input.xyClearance * 2.0
    actualLipBodyLength = (input.baseLength * input.binLength) + input.paddingTop + input.paddingBottom - input.xyClearance * 2.0
    lipBodyHeight = const.BIN_LIP_EXTRA_HEIGHT
    features: adsk.fusion.Features = targetComponent.features

    lipBodyExtrude = extrudeUtils.createBoxAtPoint(
        actualLipBodyWidth,
        actualLipBodyLength,
        lipBodyHeight,
        targetComponent,
        input.origin
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
    ).name = 'Lip body corner fillets'

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
        lipCutoutInput.baseWidth = input.baseWidth + input.paddingLeft + input.paddingRight + input.xyClearance * 2
        lipCutoutInput.baseLength = input.baseLength + input.paddingTop + input.paddingBottom + input.xyClearance * 2
        lipCutoutInput.xyClearance = input.xyClearance
        lipCutoutInput.hasBottomChamfer = False
        lipCutoutInput.cornerFilletRadius = input.binCornerFilletRadius + input.xyClearance * 2
        lipCutout = baseGenerator.createSingleGridfinityBaseBody(lipCutoutInput, targetComponent)
        lipCutout.name = "Lip cutout"
        lipCutoutBodies.append(lipCutout)

        patternInputBodies = adsk.core.ObjectCollection.create()
        patternInputBodies.add(lipCutout)
        patternInput = features.rectangularPatternFeatures.createInput(patternInputBodies,
            targetComponent.xConstructionAxis,
            adsk.core.ValueInput.createByReal(input.binWidth),
            adsk.core.ValueInput.createByReal(input.baseWidth),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        patternInput.directionTwoEntity = targetComponent.yConstructionAxis
        patternInput.quantityTwo = adsk.core.ValueInput.createByReal(input.binLength)
        patternInput.distanceTwo = adsk.core.ValueInput.createByReal(input.baseLength)
        rectangularPattern = features.rectangularPatternFeatures.add(patternInput)
        lipCutoutBodies = lipCutoutBodies + list(rectangularPattern.bodies)

        lipMiddleCutoutOrigin = geometryUtils.createOffsetPoint(
            input.origin,
            byX=input.wallThickness - input.xyClearance,
            byY=input.wallThickness - input.xyClearance,
        )
        lipMidCutout = extrudeUtils.createBoxAtPoint(
            actualLipBodyWidth - input.wallThickness * 2 + input.xyClearance * 2,
            actualLipBodyLength - input.wallThickness * 2 + input.xyClearance * 2,
            lipBodyHeight,
            targetComponent,
            lipMiddleCutoutOrigin,
        )
        lipMidCutout.name = 'Lip middle cutout'
        filletUtils.filletEdgesByLength(
            lipMidCutout.faces,
            input.binCornerFilletRadius - input.wallThickness + input.xyClearance,
            lipBodyHeight,
            targetComponent,
        )
        bodiesToSubtract.append(lipMidCutout.bodies.item(0))

    else:
        lipCutoutInput = BaseGeneratorInput()
        lipCutoutInput.originPoint = geometryUtils.createOffsetPoint(
            input.origin,
            byX=-input.xyClearance * 2,
            byY=-input.xyClearance * 2,
            byZ=const.BIN_BASE_HEIGHT
        )
        lipCutoutInput.baseWidth = input.baseWidth * input.binWidth + input.paddingLeft + input.paddingRight + input.xyClearance * 2
        lipCutoutInput.baseLength = input.baseLength * input.binLength + input.paddingTop + input.paddingBottom + input.xyClearance * 2
        lipCutoutInput.xyClearance = input.xyClearance
        lipCutoutInput.hasBottomChamfer = False
        lipCutoutInput.cornerFilletRadius = input.binCornerFilletRadius + input.xyClearance * 2
        lipCutout = baseGenerator.createSingleGridfinityBaseBody(lipCutoutInput, targetComponent)
        lipCutout.name = 'Lip cutout'
        lipCutoutBodies.append(lipCutout)

    if const.BIN_LIP_TOP_RECESS_HEIGHT > const.DEFAULT_FILTER_TOLERANCE:
        lipCutoutConstructionPlane = targetComponent.constructionPlanes.add(lipCutoutPlaneInput)
        lipCutoutConstructionPlane.name = "top lip edge plane"
        topChamferSketch: adsk.fusion.Sketch = targetComponent.sketches.add(lipCutoutConstructionPlane)
        topChamferSketch.name = "Lip top chamfer"
        sketchUtils.createRectangle(
            actualLipBodyWidth,
            actualLipBodyLength,
            topChamferSketch.modelToSketchSpace(adsk.core.Point3D.create(-input.paddingLeft, -input.paddingBottom, topChamferSketch.origin.z)),
            topChamferSketch,
        )
        topChamferNegativeVolume = extrudeUtils.simpleDistanceExtrude(
            topChamferSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            const.BIN_LIP_TOP_RECESS_HEIGHT,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
        )
        topChamferNegativeVolume.name = "Lip top chamfer cut"
        bodiesToSubtract.append(topChamferNegativeVolume.bodies.item(0))
    bodiesToSubtract = bodiesToSubtract + lipCutoutBodies

    combineUtils.cutBody(
        lipBody,
        commonUtils.objectCollectionFromList(bodiesToSubtract),
        targetComponent
    )

    return lipBody
