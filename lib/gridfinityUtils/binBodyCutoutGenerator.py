import adsk.core, adsk.fusion, traceback
import os
import math

from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyCutoutGeneratorInput import BinBodyCutoutGeneratorInput
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def getInnerCutoutScoopFace(
    innerCutout: adsk.fusion.BRepBody
    ) -> tuple[adsk.fusion.BRepFace, adsk.fusion.BRepFace]:
    innerCutoutYNormalFaces = [face for face in innerCutout.faces if faceUtils.isYNormal(face)]
    scoopFace = min(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    oppositeFace = max(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    return (scoopFace, oppositeFace)

def createGridfinityBinBodyCutout(
    input: BinBodyCutoutGeneratorInput,
    targetComponent: adsk.fusion.Component,
):

    cutoutPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    cutoutPlaneInput.setByOffset(
        targetComponent.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(input.origin.z)
    )
    cutoutConstructionPlane = targetComponent.constructionPlanes.add(cutoutPlaneInput)
    innerCutoutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(cutoutConstructionPlane)
    innerCutoutSketch.name = "inner cutout sketch"
    sketchUtils.createRectangle(
        input.width,
        input.length,
        adsk.core.Point3D.create(input.origin.x, input.origin.y, 0),
        innerCutoutSketch,
    )

    innerCutout = extrudeUtils.simpleDistanceExtrude(
        innerCutoutSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.height,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        [],
        targetComponent,
    )
    innerCutoutBody = innerCutout.bodies.item(0)
    innerCutoutBody.name = 'inner cutout'

    # scoop
    if input.hasScoop:
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopEdge = faceUtils.getBottomHorizontalEdge(innerCutoutScoopFace.edges)
        scoopMaxRadius = min(input.scoopMaxRadius, input.height) if min(input.scoopMaxRadius, input.height) >= input.filletRadius else input.filletRadius
        filletUtils.createFillet(
            [scoopEdge],
            scoopMaxRadius,
            False,
            targetComponent
        )
    # fillet inner cutout
    [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
    innerCutoutVerticalFaces = faceUtils.getVerticalEdges(innerCutoutBody.faces)
    filletUtils.createFillet(
        innerCutoutVerticalFaces,
        input.filletRadius,
        True,
        targetComponent
    )
    if input.hasBottomFillet:
        # recalculate faces after fillet
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopOppositeEdge = faceUtils.getBottomHorizontalEdge(innerCutoputScoopOppositeFace.edges)

        filletUtils.createFillet(
            [scoopOppositeEdge],
            input.filletRadius,
            True,
            targetComponent
        )

    return innerCutoutBody
