import adsk.core, adsk.fusion, traceback
import os
import math

from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyCutoutGeneratorInput import BinBodyCutoutGeneratorInput
from .dim import Dim, valueInput
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def getInnerCutoutScoopFace(
    innerCutout: adsk.fusion.BRepBody
    ) -> tuple[adsk.fusion.BRepFace, adsk.fusion.BRepFace]:
    return faceUtils.getNormalFaceExtremes(innerCutout.faces, 'y')

def createGridfinityBinBodyCutout(
    input: BinBodyCutoutGeneratorInput,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    """The body and all its features are named after the given name"""

    cutoutPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    cutoutPlaneInput.setByOffset(
        targetComponent.xYConstructionPlane,
        valueInput(input.originZ)
    )
    cutoutConstructionPlane = targetComponent.constructionPlanes.add(cutoutPlaneInput)
    cutoutConstructionPlane.name = f'{name} plane'
    innerCutoutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(cutoutConstructionPlane)
    innerCutoutSketch.name = f'{name} sketch'
    sketchUtils.createRectangle(
        input.width,
        input.length,
        adsk.core.Point3D.create(input.origin.x, input.origin.y, 0),
        innerCutoutSketch,
        startX=input.originX,
        startY=input.originY,
    )

    innerCutout = extrudeUtils.simpleDistanceExtrude(
        innerCutoutSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.height,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        [],
        targetComponent,
        name=name,
    )
    innerCutoutBody = innerCutout.bodies.item(0)
    innerCutoutBody.name = name

    # scoop
    if input.hasScoop:
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopEdge = faceUtils.getBottomHorizontalEdge(innerCutoutScoopFace.edges)
        # a margin less deep than the cutout at most and as round as its corners at least, an expression of the cutout
        # depth so it still fits once the height unit changes, see const.BIN_SCOOP_TOP_MARGIN
        scoopMaxRadius = Dim.max(
            Dim.min(Dim.length(input.scoopMaxRadius), Dim.asLength(input.height) - Dim.length(const.BIN_SCOOP_TOP_MARGIN)),
            Dim.length(input.filletRadius),
        )
        filletUtils.createFillet(
            [scoopEdge],
            scoopMaxRadius,
            False,
            targetComponent,
            name=f'{name} scoop',
        )
    # fillet inner cutout
    innerCutoutVerticalFaces = faceUtils.getVerticalEdges(innerCutoutBody.faces)
    filletUtils.createFillet(
        innerCutoutVerticalFaces,
        input.filletRadius,
        True,
        targetComponent,
        name=f'{name} corner fillets',
    )
    if input.hasBottomFillet:
        # recalculate faces after fillet
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopOppositeEdge = faceUtils.getBottomHorizontalEdge(innerCutoputScoopOppositeFace.edges)

        filletUtils.createFillet(
            [scoopOppositeEdge],
            input.filletRadius,
            True,
            targetComponent,
            name=f'{name} bottom fillet',
        )

    return innerCutoutBody
