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
    innerCutoutSketch.name = 'Inner cutout sketch'
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
    innerCutout.name = 'Inner cutout extrude'
    innerCutoutBody = innerCutout.bodies.item(0)
    innerCutoutBody.name = 'Inner cutout'

    # scoop
    scoopBothSides = input.hasScoop and input.scoopBothSides
    if input.hasScoop:
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopEdges = [faceUtils.getBottomHorizontalEdge(innerCutoutScoopFace.edges)]
        scoopMaxRadius = min(input.scoopMaxRadius, input.height) if min(input.scoopMaxRadius, input.height) >= input.filletRadius else input.filletRadius
        if scoopBothSides:
            scoopEdges.append(faceUtils.getBottomHorizontalEdge(innerCutoputScoopOppositeFace.edges))
            # two opposite scoops can't be wider than the cutout, otherwise the fillets would overlap
            scoopMaxRadius = min(scoopMaxRadius, input.length / 2)
        filletUtils.createFillet(
            scoopEdges,
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
    # when the scoop goes along both sides the opposite edge is already rounded by it
    if input.hasBottomFillet and not scoopBothSides:
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
