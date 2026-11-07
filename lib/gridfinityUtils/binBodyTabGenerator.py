import adsk.core, adsk.fusion, traceback
import os
import math



from .const import BIN_TAB_EDGE_FILLET_RADIUS
from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from .dim import Dim, valueInput, applyTo
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def createGridfinityBinBodyTab(
    input: BinBodyTabGeneratorInput,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    """The body and all its features are named after the given name"""

    tabProfilePlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    tabProfilePlaneInput.setByOffset(
        targetComponent.yZConstructionPlane,
        valueInput(input.originX)
        )
    tabProfilePlane = targetComponent.constructionPlanes.add(tabProfilePlaneInput)
    tabProfilePlane.name = f'{name} plane'
    tabSketch: adsk.fusion.Sketch = targetComponent.sketches.add(tabProfilePlane)
    tabSketch.name = f'{name} sketch'
    with sketchUtils.deferSketchCompute(tabSketch):
        tabSketchLine = tabSketch.sketchCurves.sketchLines
        tabTopEdgeHeight = input.origin.z - input.topClearance
        actualTabWidth = input.width + BIN_TAB_EDGE_FILLET_RADIUS / math.tan((math.radians(90) - input.overhangAngle) / 2)
        actualTabHeight = actualTabWidth / math.tan(input.overhangAngle)
        line1 = tabSketchLine.addByTwoPoints(
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight)),
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight - actualTabHeight)),
        )
        line2 = tabSketchLine.addByTwoPoints(
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight)),
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y - actualTabWidth, tabTopEdgeHeight)),
        )
        line3 = tabSketchLine.addByTwoPoints(
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight - actualTabHeight)),
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y - actualTabWidth, tabTopEdgeHeight)),
        )

        constraints: adsk.fusion.GeometricConstraints = tabSketch.geometricConstraints
        dimensions: adsk.fusion.SketchDimensions = tabSketch.sketchDimensions

        # horizontal/vertical relative to local sketch XY coordinates
        constraints.addHorizontal(line1)
        constraints.addVertical(line2)
        constraints.addCoincident(line1.startSketchPoint, line2.startSketchPoint)
        constraints.addCoincident(line2.endSketchPoint, line3.endSketchPoint)
        constraints.addCoincident(line1.endSketchPoint, line3.startSketchPoint)

        # on the YZ plane sketch vertical runs along the model y and sketch horizontal along the model z
        applyTo(dimensions.addDistanceDimension(
            tabSketch.originPoint,
            line1.startSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            line1.startSketchPoint.geometry,
            True
            ).parameter, input.originY)

        applyTo(dimensions.addDistanceDimension(
            tabSketch.originPoint,
            line1.startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            line1.startSketchPoint.geometry,
            True
            ).parameter, input.originZ - Dim.length(input.topClearance))

        dimensions.addDistanceDimension(
            line2.startSketchPoint,
            line2.endSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            line2.endSketchPoint.geometry,
            True
            )
            
        dimensions.addAngularDimension(
            line1,
            line3,
            line1.endSketchPoint.geometry,
            True,
            )

    tabExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
        tabSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.length,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
        name=name,
    )
    tabBody = tabExtrudeFeature.bodies.item(0)
    tabBody.name = name

    tabTopFace = faceUtils.getTopFace(tabBody)
    roundedEdge = min([edge for edge in tabTopFace.edges if geometryUtils.isCollinearToX(edge)], key=lambda x: x.boundingBox.minPoint.y)
    fillet = filletUtils.createFillet(
        [roundedEdge],
        BIN_TAB_EDGE_FILLET_RADIUS,
        False,
        targetComponent,
        name=f'{name} edge fillet',
    )

    return tabBody
