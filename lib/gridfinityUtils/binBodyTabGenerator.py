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
    x_position = input.origin.x - BIN_WALL_THICKNESS
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

    h1 = input.width * math.sin(input.labelAngle)
    hr1 = BIN_TAB_EDGE_FILLET_RADIUS * math.cos(input.labelAngle)
    wr1 = BIN_TAB_EDGE_FILLET_RADIUS*(1 - math.sin(input.labelAngle))
    hr2 = BIN_TAB_EDGE_FILLET_RADIUS * math.sin(input.overhangAngle)
    wr2 = BIN_TAB_EDGE_FILLET_RADIUS*(1 - math.cos(input.overhangAngle))
    w = input.width * math.cos(input.labelAngle)
    h2 = (w+wr1-wr2) / math.tan(input.overhangAngle)
    h = h1 + h2 + hr1 + hr2

    originPoint = adsk.core.Point3D.create(
        x=x_position,
        y=input.origin.y,
        z=tabTopEdgeHeight
    )

    pt1 = adsk.core.Point3D.create(
        x=x_position, 
        y=input.origin.y + BIN_WALL_THICKNESS, 
        z=tabTopEdgeHeight + BIN_WALL_THICKNESS*math.tan(input.labelAngle)
        )
    pt2 = adsk.core.Point3D.create(
        x=x_position, 
        y=input.origin.y + BIN_WALL_THICKNESS, 
        z=tabTopEdgeHeight - h - BIN_WALL_THICKNESS*math.tan(input.overhangAngle)
        )
    pt3 = adsk.core.Point3D.create(
        x=x_position, 
        y=input.origin.y - w,
        z=tabTopEdgeHeight - h1
        )
    pt4 = adsk.core.Point3D.create(
        x=x_position, 
        y=input.origin.y - w - wr1 + wr2, 
        z=tabTopEdgeHeight - h1 - hr1 - hr2
        )
    
    fillet_center_pt = adsk.core.Point3D.create(
        x=x_position, 
        y=input.origin.y - w - wr1 + const.BIN_TAB_EDGE_FILLET_RADIUS, 
        z=tabTopEdgeHeight - h1 - hr1
        )

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
        tabSketch.modelToSketchSpace(pt4),
    )
    tabOriginSketchPoint = tabSketch.sketchPoints.add(tabSketch.modelToSketchSpace(originPoint))

    arc1 = tabSketch.sketchCurves.sketchArcs.addByCenterStartEnd(
        tabSketch.modelToSketchSpace(fillet_center_pt),
        line2.endSketchPoint,
        line3.endSketchPoint
    )
    
    constraints: adsk.fusion.GeometricConstraints = tabSketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = tabSketch.sketchDimensions

    tabOriginSketchPoint.isFixed = True
    constraints.addCoincident(tabOriginSketchPoint, line2)

    dimensions.addDistanceDimension(
        tabOriginSketchPoint,
        line2.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        line2.endSketchPoint.geometry,
        True
        )
    dimensions.addDistanceDimension(
        tabOriginSketchPoint,
        line1.startSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        line1.startSketchPoint.geometry,
        True
    )
    # horizontal/vertical relative to local sketch XY coordinates
    constraints.addHorizontal(line1)    
    constraints.addCoincident(line1.startSketchPoint, line2.startSketchPoint)
    constraints.addCoincident(line1.endSketchPoint, line3.startSketchPoint)

            
    dimensions.addAngularDimension(
        line1,
        line2,
        adsk.core.Point3D.create(x_position, (pt2.y + pt3.y) / 2, (pt2.z + pt3.z) / 2),
        True,
        )
    
    dimensions.addAngularDimension(
        line3,
        line1,
        adsk.core.Point3D.create(x_position, (pt1.y + pt3.y) / 2, (pt1.z + pt3.z) / 2),
        True,
        )
    

    constraints.addTangent(arc1, line2)
    constraints.addTangent(arc1, line3)

    dimensions.addRadialDimension(
        arc1, arc1.endSketchPoint.geometry, True
    )
    
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

    if input.isTabHollow:
        binBody = targetComponent.bRepBodies.itemByName("Bin body")
        tabBodySubtract = targetComponent.features.copyPasteBodies.add(tabBody).bodies.item(0)
        tabBodyShell = targetComponent.features.copyPasteBodies.add(tabBody).bodies.item(0)

        intersectCollection = adsk.core.ObjectCollection.create()
        intersectCollection.add(binBody)
        combineUtils.intersectBody(
            tabBodyShell,
            intersectCollection,
            targetComponent,
            True
        )

        combineUtils.intersectBody(
            tabBodySubtract,
            intersectCollection,
            targetComponent,
            True
        )

        shellFeatureEntities = adsk.core.ObjectCollection.create()

        for face in tabBodyShell.faces:
            if face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType and face.evaluator.getNormalAtPoint(pt1)[1].isPerpendicularTo(
                adsk.core.Vector3D.create(pt2.x - pt1.x , pt2.y - pt1.y, pt2.z - pt1.z)
            ) and not face.evaluator.getNormalAtPoint(pt1)[1].isParallelTo(
                adsk.core.Vector3D.create(pt2.x - pt1.x , pt2.y - pt1.y, pt2.z - pt1.z).crossProduct(
                    adsk.core.Vector3D.create(pt3.x - pt1.x , pt3.y - pt1.y, pt3.z - pt1.z)
                )
            ):  
                shellFeatureEntities.add(face)

        shellFeats = targetComponent.features.shellFeatures

        shellFeatureInput = shellFeats.createInput(shellFeatureEntities, False)
        shellFeatureInput.insideThickness = adsk.core.ValueInput.createByReal(BIN_WALL_THICKNESS)
        shellFeatureInput.shellType = adsk.fusion.ShellTypes.RoundedOffsetShellType
        shellFeats.add(shellFeatureInput)

        subtractCollection = adsk.core.ObjectCollection.create()
        subtractCollection.add(tabBodyShell)

        combineUtils.cutBody(
            tabBodySubtract,
            subtractCollection,
            targetComponent
        )

        subtractCollection = adsk.core.ObjectCollection.create()
        subtractCollection.add(tabBodySubtract)

        combineUtils.cutBody(
            tabBody,
            subtractCollection,
            targetComponent,
            True
        )

        return tabBody, [tabBodySubtract]
    else:
        return tabBody, []
