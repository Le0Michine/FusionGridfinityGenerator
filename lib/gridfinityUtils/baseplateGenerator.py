import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, commonUtils, filletUtils, combineUtils, faceUtils, extrudeUtils, sketchUtils, baseGenerator, patternUtils, shapeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .baseplateGeneratorInput import BaseplateGeneratorInput

def createGridfinityBaseplate(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component):
    features = targetComponent.features
    cutoutInput = BaseGeneratorInput()
    cutoutInput.originPoint = targetComponent.originConstructionPoint.geometry
    cutoutInput.baseWidth = input.baseWidth
    cutoutInput.baseLength = input.baseLength
    cutoutInput.xyTolerance = input.xyTolerance
    baseBody = baseGenerator.createBaseWithClearance(cutoutInput, targetComponent)

    cuttingTools: list[adsk.fusion.BRepBody] = [baseBody]
    extraCutoutBodies: list[adsk.fusion.BRepBody] = []

    holeCenterPoint = adsk.core.Point3D.create(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyTolerance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyTolerance,
        0
    )

    connectionHoleYTool = None
    connectionHoleXTool = None

    if input.hasSkeletonizedBottom:
        centerCutoutSketch = baseGenerator.createCircleAtPointSketch(
            faceUtils.getBottomFace(baseBody),
            input.magnetCutoutsDiameter / 2,
            holeCenterPoint,
            targetComponent
        )
        centerCutoutSketch.name = "center bottom cutout"
        sketchUtils.convertToConstruction(centerCutoutSketch.sketchCurves)
        sketchCurves = centerCutoutSketch.sketchCurves
        dimensions = centerCutoutSketch.sketchDimensions
        constraints = centerCutoutSketch.geometricConstraints
        sketchLines = sketchCurves.sketchLines
        screwHoleCircle = sketchCurves.sketchCircles.item(0)
        arcStartingPoint = screwHoleCircle.centerSketchPoint.geometry.asVector()
        arcStartingPoint.add(adsk.core.Vector3D.create(0, max(input.magnetCutoutsDiameter, input.screwHeadCutoutDiameter) / 2 + 0.1, 0))
        arc = sketchCurves.sketchArcs.addByCenterStartSweep(
            screwHoleCircle.centerSketchPoint,
            arcStartingPoint.asPoint(),
            math.radians(90),
        )

        verticalEdgeLine = min([line for line in sketchLines if sketchUtils.isVertical(line)], key=lambda x: abs(x.startSketchPoint.geometry.x))
        horizontalEdgeLine = min([line for line in sketchLines if sketchUtils.isHorizontal(line)], key=lambda x: abs(x.startSketchPoint.geometry.y))

        baseCenterOffsetX = input.baseWidth / 2 - input.xyTolerance
        baseCenterOffsetY = input.baseLength / 2 - input.xyTolerance
        line1 = sketchLines.addByTwoPoints(arc.startSketchPoint, adsk.core.Point3D.create(verticalEdgeLine.startSketchPoint.geometry.x, arc.startSketchPoint.geometry.y, 0))
        line2 = sketchLines.addByTwoPoints(line1.endSketchPoint, adsk.core.Point3D.create(line1.endSketchPoint.geometry.x, baseCenterOffsetY, 0))
        line3 = sketchLines.addByTwoPoints(line2.endSketchPoint, adsk.core.Point3D.create(-baseCenterOffsetX, baseCenterOffsetY, 0))
        line4 = sketchLines.addByTwoPoints(line3.endSketchPoint, adsk.core.Point3D.create(line3.endSketchPoint.geometry.x, horizontalEdgeLine.startSketchPoint.geometry.y, 0))
        line5 = sketchLines.addByTwoPoints(line4.endSketchPoint, adsk.core.Point3D.create(arc.endSketchPoint.geometry.x, line4.endSketchPoint.geometry.y, 0))
        line6 = sketchLines.addByTwoPoints(line5.endSketchPoint, arc.endSketchPoint)
        
        constraints.addCoincident(line1.endSketchPoint, verticalEdgeLine)
        constraints.addCoincident(line6.startSketchPoint, horizontalEdgeLine)
        constraints.addCoincident(screwHoleCircle.centerSketchPoint, arc.centerSketchPoint)
        constraints.addHorizontal(line1)
        constraints.addPerpendicular(line1, line2)
        constraints.addPerpendicular(line2, line3)
        constraints.addPerpendicular(line3, line4)
        constraints.addPerpendicular(line4, line5)
        constraints.addPerpendicular(line5, line6)
        constraints.addTangent(arc, line1)
        constraints.addEqual(line1, line6)
        constraints.addEqual(line2, line5)
        dimensions.addRadialDimension(arc, arc.endSketchPoint.geometry, True)
        dimensions.addDistanceDimension(
            arc.endSketchPoint,
            line3.endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            line2.endSketchPoint.geometry
            )

        centerCutoutExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
            centerCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.bottomExtensionHeight,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [],
            targetComponent,
        )

        constructionAxisInput: adsk.fusion.ConstructionAxisInput = targetComponent.constructionAxes.createInput()
        constructionAxisInput.setByNormalToFaceAtPoint(
            faceUtils.getBottomFace(baseBody),
            line3.endSketchPoint,
        )
        constructionAxis = targetComponent.constructionAxes.add(constructionAxisInput)
        constructionAxis.isLightBulbOn = False

        centerCutoutPattern = patternUtils.circPattern(
            commonUtils.objectCollectionFromList(centerCutoutExtrudeFeature.bodies),
            constructionAxis,
            4,
            targetComponent,
        )
        centerCutoutBody = centerCutoutExtrudeFeature.bodies.item(0)
        combineUtils.joinBodies(
            centerCutoutBody,
            commonUtils.objectCollectionFromList([body for body in list(centerCutoutPattern.bodies) if not body.name == centerCutoutBody.name]),
            targetComponent,
        )
        extraCutoutBodies.append(centerCutoutBody)
        if input.hasConnectionHoles:
            connectionHoleFaceY = min([face for face in centerCutoutBody.faces if faceUtils.isYNormal(face)], key=lambda x: x.boundingBox.minPoint.y)
            connectionHoleYTool = createConnectionHoleTool(connectionHoleFaceY, input.connectionScrewHolesDiameter / 2, input.baseWidth / 2, targetComponent)
            connectionHoleFaceX = min([face for face in centerCutoutBody.faces if faceUtils.isXNormal(face)], key=lambda x: x.boundingBox.minPoint.x)
            connectionHoleXTool = createConnectionHoleTool(connectionHoleFaceX, input.connectionScrewHolesDiameter / 2, input.baseWidth / 2, targetComponent)

    holeCuttingBodies: list[adsk.fusion.BRepBody] = []
    
    if input.hasExtendedBottom and input.hasMagnetCutouts:
        magnetSocketBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(baseBody),
            0,
            input.magnetCutoutsDepth,
            input.magnetCutoutsDiameter / 2,
            holeCenterPoint,
            targetComponent,
        )
        holeCuttingBodies.append(magnetSocketBody)
    
    if input.hasExtendedBottom and input.hasScrewHoles:
        screwHoleBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(baseBody),
            0,
            input.bottomExtensionHeight,
            input.screwHolesDiameter / 2,
            holeCenterPoint,
            targetComponent,
        )
        holeCuttingBodies.append(screwHoleBody)

        screwHeadHeight = const.DIMENSION_SCREW_HEAD_CUTOUT_OFFSET_HEIGHT + (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2
        screwHeadBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(screwHoleBody),
            -screwHeadHeight,
            screwHeadHeight,
            input.screwHeadCutoutDiameter / 2,
            holeCenterPoint,
            targetComponent,
        )
        filletUtils.createChamfer(
            commonUtils.objectCollectionFromList(faceUtils.getTopFace(screwHeadBody).edges),
            (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2,
            targetComponent,
        )
        holeCuttingBodies.append(screwHeadBody)

    if len(holeCuttingBodies) > 0:
        patternSpacingX = input.baseWidth - const.DIMENSION_SCREW_HOLES_OFFSET * 2
        patternSpacingY = input.baseLength - const.DIMENSION_SCREW_HOLES_OFFSET * 2
        magnetScrewCutoutsPattern = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(holeCuttingBodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (patternSpacingX, patternSpacingY),
            (2, 2),
            targetComponent
        )
        extraCutoutBodies = extraCutoutBodies + holeCuttingBodies + list(magnetScrewCutoutsPattern.bodies)

    if len(extraCutoutBodies) > 0:
        combineUtils.joinBodies(
            baseBody,
            commonUtils.objectCollectionFromList(extraCutoutBodies),
            targetComponent,
        )
    
    # replicate base in rectangular pattern
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()
    patternInputBodies.add(baseBody)
    patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
        targetComponent.xConstructionAxis,
        adsk.core.ValueInput.createByReal(input.baseplateWidth),
        adsk.core.ValueInput.createByReal(input.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = adsk.core.ValueInput.createByReal(input.baseplateLength)
    patternInput.distanceTwo = adsk.core.ValueInput.createByReal(input.baseWidth)
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    cuttingTools = cuttingTools + list(rectangularPattern.bodies)

    # create baseplate body
    binInterfaceBody = shapeUtils.simpleBox(
        targetComponent.xYConstructionPlane,
        0,
        input.baseplateWidth * input.baseWidth,
        input.baseplateLength * input.baseWidth,
        -const.BIN_BASE_HEIGHT,
        adsk.core.Point3D.create(-input.xyTolerance, -input.xyTolerance, 0),
        targetComponent,
    )

    if input.binZClearance > 0:
        binZClearance = extrudeUtils.simpleDistanceExtrude(
            faceUtils.getTopFace(binInterfaceBody),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.binZClearance,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
        )
        binZClearance.name = "flatten top side"
        binZClearance.bodies.item(0).name = "top negative volume"
        cuttingTools.append(binZClearance.bodies.item(0))

    cornerFillet = filletUtils.filletEdgesByLength(
        binInterfaceBody.faces,
        const.BIN_CORNER_FILLET_RADIUS,
        const.BIN_BASE_HEIGHT,
        targetComponent,
        )
    cornerFillet.name = "round outer corners"
    
    if input.hasExtendedBottom:
        baseplateBottomLayer = extrudeUtils.simpleDistanceExtrude(
            faceUtils.getBottomFace(binInterfaceBody),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.bottomExtensionHeight,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [],
            targetComponent,
        )
        baseplateBottomLayerBody = baseplateBottomLayer.bodies.item(0)
        combineUtils.joinBodies(binInterfaceBody, commonUtils.objectCollectionFromList([baseplateBottomLayerBody]), targetComponent)

    bottomChamfer = filletUtils.chamferEdgesByLength(
        [faceUtils.getBottomFace(binInterfaceBody)],
        0.05,
        input.baseplateLength * input.baseWidth,
        const.BIN_CORNER_FILLET_RADIUS * 3,
        targetComponent,
    )
    bottomChamfer.name = "bottom shamfer"

    if not connectionHoleYTool is None and not connectionHoleXTool is None:
        holeToolsXFeature = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(connectionHoleXTool.bodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (input.baseWidth, input.baseLength),
            (1, input.baseplateLength),
            targetComponent
        )
        connectionHoleXToolList = list(connectionHoleXTool.bodies) + list(holeToolsXFeature.bodies)

        holeToolsYFeature = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(connectionHoleYTool.bodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (input.baseWidth, input.baseLength),
            (input.baseplateWidth, 1),
            targetComponent
        )
        connectionHoleYToolList = list(connectionHoleYTool.bodies) + list(holeToolsYFeature.bodies)

        constructionPlaneXZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneXZInput.setByOffset(targetComponent.xZConstructionPlane, adsk.core.ValueInput.createByReal(input.baseplateLength * input.baseLength / 2 - input.xyTolerance))
        constructionPlaneXZ = targetComponent.constructionPlanes.add(constructionPlaneXZInput)
        constructionPlaneXZ.isLightBulbOn = False

        constructionPlaneYZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneYZInput.setByOffset(targetComponent.yZConstructionPlane, adsk.core.ValueInput.createByReal(input.baseplateWidth * input.baseWidth / 2 - input.xyTolerance))
        constructionPlaneYZ = targetComponent.constructionPlanes.add(constructionPlaneYZInput)
        constructionPlaneYZ.isLightBulbOn = False

        mirrorConnectionHolesYZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleXToolList), constructionPlaneYZ)
        mirrorConnectionHolesYZ = features.mirrorFeatures.add(mirrorConnectionHolesYZInput)

        mirrorConnectionHolesXZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleYToolList), constructionPlaneXZ)
        mirrorConnectionHolesXZ = features.mirrorFeatures.add(mirrorConnectionHolesXZInput)

        cuttingTools = cuttingTools + list(mirrorConnectionHolesYZ.bodies) + list(mirrorConnectionHolesXZ.bodies) + connectionHoleYToolList + connectionHoleXToolList


    # cut everything
    toolBodies = commonUtils.objectCollectionFromList(cuttingTools)
    finalCut = combineUtils.cutBody(
        binInterfaceBody,
        toolBodies,
        targetComponent,
    )
    finalCut.name = "final baseplate cut"

    return binInterfaceBody

def createConnectionHoleTool(connectionHoleFace: adsk.fusion.BRepFace, diameter: float, depth: float, targetComponent: adsk.fusion.Component):
    connectionHoleSketch: adsk.fusion.Sketch = targetComponent.sketches.add(connectionHoleFace)
    connectionHoleSketch.name = "side connector hole"
    sketchCurves = connectionHoleSketch.sketchCurves
    dimensions = connectionHoleSketch.sketchDimensions
    constraints = connectionHoleSketch.geometricConstraints
    sketchUtils.convertToConstruction(sketchCurves)
    [sketchHorizontalEdge1, sketchHorizontalEdge2] = [line for line in sketchCurves.sketchLines if sketchUtils.isHorizontal(line)]
    line1 = sketchCurves.sketchLines.addByTwoPoints(sketchHorizontalEdge1.startSketchPoint.geometry, sketchHorizontalEdge2.endSketchPoint.geometry)
    line1.isConstruction = True
    constraints.addMidPoint(line1.startSketchPoint, sketchHorizontalEdge1)
    constraints.addMidPoint(line1.endSketchPoint, sketchHorizontalEdge2)
    
    circle = sketchCurves.sketchCircles.addByCenterRadius(
        connectionHoleSketch.originPoint.geometry,
        diameter
    )
    constraints.addMidPoint(circle.centerSketchPoint, line1)
    dimensions.addRadialDimension(circle, line1.startSketchPoint.geometry, True)
    connectionHoleTool = extrudeUtils.simpleDistanceExtrude(
        connectionHoleSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        depth,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    return connectionHoleTool