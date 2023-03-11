import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, commonUtils, filletUtils, combineUtils, faceUtils, extrudeUtils, sketchUtils, baseGenerator, patternUtils, geometryUtils
from .binBodyGenerator import createBox
from .baseGenerator import createGridfinityBase
from .baseGeneratorInput import BaseGeneratorInput
from .baseplateGeneratorInput import BaseplateGeneratorInput

def createGridfinityBaseplate(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component):
    features = targetComponent.features
    baseGeneratorInput = BaseGeneratorInput()
    baseGeneratorInput.baseWidth = input.baseWidth
    baseGeneratorInput.xyTolerance = input.xyTolerance
    baseBody = createGridfinityBase(baseGeneratorInput, targetComponent)

    cuttingTools: list[adsk.fusion.BRepBody] = [baseBody]
    extraCutoutBodies: list[adsk.fusion.BRepBody] = []

    if input.hasSkeletonizedBottom:
        centerCutoutSketch = baseGenerator.createMagnetCutoutSketch(faceUtils.getBottomFace(baseBody), input.magnetCutoutsDiameter / 2, input.baseWidth, targetComponent)
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

        baseCenterOffset = input.baseWidth / 2
        line1 = sketchLines.addByTwoPoints(arc.startSketchPoint, adsk.core.Point3D.create(verticalEdgeLine.startSketchPoint.geometry.x, arc.startSketchPoint.geometry.y, 0))
        line2 = sketchLines.addByTwoPoints(line1.endSketchPoint, adsk.core.Point3D.create(line1.endSketchPoint.geometry.x, baseCenterOffset, 0))
        line3 = sketchLines.addByTwoPoints(line2.endSketchPoint, adsk.core.Point3D.create(-baseCenterOffset, baseCenterOffset, 0))
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
            input.bottomExtensionHeight+1,
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
            commonUtils.objectCollectionFromList(centerCutoutPattern.bodies),
            targetComponent,
        )
        extraCutoutBodies.append(centerCutoutBody)

        if input.hasConnectionHoles:
            connectionHoleFace = min([face for face in centerCutoutBody.faces if faceUtils.isYNormal(face)], key=lambda x: x.boundingBox.minPoint.y)
            connectionHoleSketch: adsk.fusion.Sketch = targetComponent.sketches.add(connectionHoleFace)
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
                input.connectionScrewHolesDiameter / 2
            )
            constraints.addMidPoint(circle.centerSketchPoint, line1)
            dimensions.addRadialDimension(circle, line1.startSketchPoint.geometry, True)
            connectionHoleTool = extrudeUtils.simpleDistanceExtrude(
                connectionHoleSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                input.baseWidth / 2,
                adsk.fusion.ExtentDirections.PositiveExtentDirection,
                [],
                targetComponent,
            )
            connectionHolePattern = patternUtils.circPattern(
                commonUtils.objectCollectionFromList(connectionHoleTool.bodies),
                constructionAxis,
                4,
                targetComponent,
            )
            extraCutoutBodies = extraCutoutBodies + list(connectionHoleTool.bodies) + list(connectionHolePattern.bodies)


    holeCuttingBodies: list[adsk.fusion.BRepBody] = []
    
    if input.hasMagnetCutouts:
        magnetCutoutSketch = baseGenerator.createMagnetCutoutSketch(faceUtils.getBottomFace(baseBody), input.magnetCutoutsDiameter / 2, input.baseWidth, targetComponent)
        magnetCutout = extrudeUtils.simpleDistanceExtrude(
            magnetCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.magnetCutoutsDepth,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [],
            targetComponent,
        )
        holeCuttingBodies.append(magnetCutout.bodies.item(0))
    
    if input.hasScrewHoles:
        screwHoleSketch = baseGenerator.createMagnetCutoutSketch(faceUtils.getBottomFace(baseBody), input.screwHolesDiameter / 2, input.baseWidth, targetComponent)
        screwHoleFeature = extrudeUtils.simpleDistanceExtrude(
            screwHoleSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.bottomExtensionHeight,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [],
            targetComponent,
        )
        holeCuttingBodies.append(screwHoleFeature.bodies.item(0))

        screwHeadSketch = baseGenerator.createMagnetCutoutSketch(screwHoleFeature.endFaces.item(0), input.screwHeadCutoutDiameter / 2, input.baseWidth, targetComponent)
        screwHeadCutoutFeature = extrudeUtils.simpleDistanceExtrude(
            screwHeadSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            const.DIMENSION_SCREW_HEAD_CUTOUT_OFFSET_HEIGHT + (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
        )
        filletUtils.createChamfer(
            commonUtils.objectCollectionFromList(screwHeadCutoutFeature.endFaces.item(0).edges),
            (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2,
            targetComponent,
        )
        holeCuttingBodies.append(screwHeadCutoutFeature.bodies.item(0))

    if len(holeCuttingBodies) > 0:
        magnetScrewCutoutsPattern = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(holeCuttingBodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (const.DIMENSION_SCREW_HOLES_DISTANCE, const.DIMENSION_SCREW_HOLES_DISTANCE),
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
    binInterfaceExtrude = createBox(
        input.baseplateWidth * input.baseWidth,
        input.baseplateLength * input.baseWidth,
        -const.BASE_TOTAL_HEIGHT,
        targetComponent,
        targetComponent.xYConstructionPlane,
        )
    binInterfaceBody = binInterfaceExtrude.bodies.item(0)

    if input.binZClearance > 0:
        binZClearance = extrudeUtils.simpleDistanceExtrude(
            binInterfaceExtrude.startFaces.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.binZClearance,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
        )
        cuttingTools.append(binZClearance.bodies.item(0))

    filletUtils.filletEdgesByLength(
        binInterfaceExtrude.faces,
        const.BIN_CORNER_FILLET_RADIUS,
        const.BASE_TOTAL_HEIGHT,
        targetComponent,
        )
    
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

    filletUtils.chamferEdgesByLength(
        [faceUtils.getBottomFace(binInterfaceBody)],
        0.05,
        input.baseplateLength * input.baseWidth,
        const.BIN_CORNER_FILLET_RADIUS * 3,
        targetComponent,
    )

    # cut everything
    toolBodies = commonUtils.objectCollectionFromList(cuttingTools)
    combineUtils.cutBody(
        binInterfaceBody,
        toolBodies,
        targetComponent,
    )

    return binInterfaceBody
