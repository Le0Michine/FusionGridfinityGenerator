import logging
import adsk.core, adsk.fusion, traceback
import os
import math



from .const import BIN_TAB_EDGE_FILLET_RADIUS, BIN_WALL_THICKNESS, BIN_XY_CLEARANCE
from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
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

def createGridfinityBinBodyTab(
    input: BinBodyTabGeneratorInput,
    targetComponent: adsk.fusion.Component,
):  
    x_position = input.origin.x - BIN_WALL_THICKNESS # + BIN_XY_CLEARANCE/2
    tabProfilePlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    tabProfilePlaneInput.setByOffset(
        targetComponent.yZConstructionPlane,
        adsk.core.ValueInput.createByReal(x_position)
        )
    tabProfilePlane = targetComponent.constructionPlanes.add(tabProfilePlaneInput)
    tabSketch: adsk.fusion.Sketch = targetComponent.sketches.add(tabProfilePlane)
    tabSketch.name = "label tab sketch"
    tabSketchLine = tabSketch.sketchCurves.sketchLines
    tabTopEdgeHeight = input.origin.z - input.topClearance

    h1 = input.width * math.sin(math.radians(input.labelAngle))
    w = input.width * math.cos(math.radians(input.labelAngle))
    h2 = w / math.tan(input.overhangAngle)
    h = h1 + h2

    logging.info(input.labelAngle)
    logging.info(math.degrees(input.overhangAngle ))

    pt1 = adsk.core.Point3D.create(x_position, input.origin.y + BIN_WALL_THICKNESS, tabTopEdgeHeight)
    pt2 = adsk.core.Point3D.create(x_position, input.origin.y + BIN_WALL_THICKNESS, tabTopEdgeHeight - h)
    pt3 = adsk.core.Point3D.create(x_position, input.origin.y - w, tabTopEdgeHeight - h1)
    logging.info(input.labelAngle)
    logging.info(input.overhangAngle)

    line1 = tabSketchLine.addByTwoPoints(
        tabSketch.modelToSketchSpace(pt1),
        tabSketch.modelToSketchSpace(pt2),
    )
    line2 = tabSketchLine.addByTwoPoints(
        tabSketch.modelToSketchSpace(pt1),
        tabSketch.modelToSketchSpace(pt3),
    )
    line3 = tabSketchLine.addByTwoPoints(
        tabSketch.modelToSketchSpace(pt2),
        tabSketch.modelToSketchSpace(pt3),
    )

    constraints: adsk.fusion.GeometricConstraints = tabSketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = tabSketch.sketchDimensions

    # horizontal/vertical relative to local sketch XY coordinates
    constraints.addHorizontal(line1)
    
    
    # constraints.addVertical(line2)
    constraints.addCoincident(line1.startSketchPoint, line2.startSketchPoint)
    constraints.addCoincident(line2.endSketchPoint, line3.endSketchPoint)
    constraints.addCoincident(line1.endSketchPoint, line3.startSketchPoint)

    # tabSketchArcs = tabSketch.sketchCurves.sketchArcs
    # tabSketchArcs.addFillet(line2, pt2, line3, pt2, BIN_TAB_EDGE_FILLET_RADIUS)
    line2.startSketchPoint.isFixed = True
    tabSizeDim = dimensions.addDistanceDimension(
        line2.startSketchPoint,
        line2.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        line2.endSketchPoint.geometry,
        True
        )
    # tabSizeDim.value = input.width
            
    labelAngleDim = dimensions.addAngularDimension(
        line1,
        line2,
        adsk.core.Point3D.create(x_position, (pt2.y + pt3.y) / 2, (pt2.z + pt3.z) / 2),
        True,
        )
    # labelAngleDim.value = math.radians(input.labelAngle)

    labelOverhangAngleDim = dimensions.addAngularDimension(
        line1,
        line3,
        adsk.core.Point3D.create(x_position, (pt1.y + pt3.y) / 2, (pt1.z + pt3.z) / 2),
        True,
        )
    # labelOverhangAngleDim.value = input.overhangAngle

    tabExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
        tabSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.length - BIN_XY_CLEARANCE * 2,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    tabBody = tabExtrudeFeature.bodies.item(0)
    tabBody.name = 'label tab'

    # tabTopFace = faceUtils.getTopFace(tabBody)
    # roundedEdge = min([edge for edge in tabTopFace.edges if geometryUtils.isCollinearToX(edge)], key=lambda x: x.boundingBox.minPoint.y)
    # fillet = filletUtils.createFillet(
    #     [roundedEdge],
    #     BIN_TAB_EDGE_FILLET_RADIUS,
    #     False,
    #     targetComponent
    # )
    # fillet.name = 'label tab fillet'

    tabBodySubtract = targetComponent.features.copyPasteBodies.add(tabBody).bodies.item(0)
    tabBodyShell = targetComponent.features.copyPasteBodies.add(tabBody).bodies.item(0)

    shellFeatureEntities = adsk.core.ObjectCollection.create()
    # shellFeatureEntities.add(tabBodyShell)
    for face in tabBodyShell.faces:
        if face.evaluator.getNormalAtPoint(pt1)[1].isPerpendicularTo(
            adsk.core.Vector3D.create(pt2.x - pt1.x , pt2.y - pt1.y, pt2.z - pt1.z)
        ) and not face.evaluator.getNormalAtPoint(pt1)[1].isParallelTo(
            adsk.core.Vector3D.create(pt2.x - pt1.x , pt2.y - pt1.y, pt2.z - pt1.z).crossProduct(
                adsk.core.Vector3D.create(pt3.x - pt1.x , pt3.y - pt1.y, pt3.z - pt1.z)
            )
        ):  
            logging.info(face)
            shellFeatureEntities.add(face)
    logging.info(shellFeatureEntities)
    logging.info(shellFeatureEntities.count)

    shellFeats = targetComponent.features.shellFeatures

    shellFeatureInput = shellFeats.createInput(shellFeatureEntities, False)
    shellFeatureInput.insideThickness = adsk.core.ValueInput.createByReal(BIN_WALL_THICKNESS)
    shellFeatureInput.shellType = adsk.fusion.ShellTypes.SharpOffsetShellType

    shellFeature = shellFeats.add(shellFeatureInput)

    subtractCollection = adsk.core.ObjectCollection.create()
    subtractCollection.add(tabBodyShell)

    combineUtils.cutBody(
        tabBodySubtract,
        subtractCollection,
        targetComponent
    )

    
    subtractCollection = adsk.core.ObjectCollection.create()
    subtractCollection.add(tabBodySubtract)
    
    combineInput = targetComponent.features.combineFeatures.createInput(tabBody, subtractCollection)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineInput.isKeepToolBodies = True
    targetComponent.features.combineFeatures.add(combineInput)
    

    # for face in tabBodySubtract.faces:
    #     if face.evaluator.getNormalAtPoint(pt1)[1].isPerpendicularTo(
    #         adsk.core.Vector3D.create(pt2.x, pt2.y, pt2.z)
    #     ):  
    #         offset = -BIN_WALL_THICKNESS
    #     else:
    #         offset = BIN_WALL_THICKNESS
    #     offsetFaceEntities = adsk.core.ObjectCollection.create()
    #     offsetFaceEntities.add(face)

    #     offsetFaceInput = targetComponent.features.offsetFeatures.createInput(
    #         offsetFaceEntities,
    #         adsk.core.ValueInput.createByReal(offset),
    #         adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    #     )
    #     targetComponent.features.offsetFeatures.add(offsetFaceInput)

   

    return tabBody, tabBodySubtract
