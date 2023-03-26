import adsk.core, adsk.fusion, traceback
import os


from .const import BIN_CORNER_FILLET_RADIUS, DEFAULT_FILTER_TOLERANCE, DIMENSION_PRINT_HELPER_GROOVE_DEPTH, DIMENSION_SCREW_HOLES_DISTANCE
from .sketchUtils import createRectangle, filterCirclesByRadius
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from . import sketchUtils, const, edgeUtils, commonUtils, combineUtils, faceUtils, extrudeUtils
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def getScrewHoleOffset(baseWidth: float, xyTolerance: float):
    return (baseWidth - DIMENSION_SCREW_HOLES_DISTANCE) / 2 - xyTolerance

def createMagnetCutoutSketch(
    plane: adsk.core.Base,
    radius: float,
    baseWidth: float,
    xyTolerance: float,
    targetComponent: adsk.fusion.Component,
    ):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    magnetCutoutSketch: adsk.fusion.Sketch = sketches.add(plane)
    dimensions: adsk.fusion.SketchDimensions = magnetCutoutSketch.sketchDimensions
    screwHoleOffset = getScrewHoleOffset(baseWidth, xyTolerance)
    sketchUtils.convertToConstruction(magnetCutoutSketch.sketchCurves)
    circle = magnetCutoutSketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(-screwHoleOffset, screwHoleOffset, 0),
        radius,
    )
    dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y * 2, 0),
        True,
    )
    dimensions.addDistanceDimension(
        magnetCutoutSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
        True
        )
    dimensions.addDistanceDimension(
        magnetCutoutSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
        True
        )

    return magnetCutoutSketch

def createGridfinityBase(
    input: BaseGeneratorInput,
    targetComponent: adsk.fusion.Component,
):
    actual_base_width = input.baseWidth - input.xyTolerance * 2.0
    actual_base_length = input.baseLength - input.xyTolerance * 2.0
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # create rectangle for the base
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    base_plate_sketch: adsk.fusion.Sketch = sketches.add(targetComponent.xYConstructionPlane)
    createRectangle(actual_base_width, actual_base_length, base_plate_sketch.originPoint.geometry, base_plate_sketch)
        
    # extrude top section
    topSectionExtrudeDepth = adsk.core.ValueInput.createByReal(const.BIN_BASE_TOP_SECTION_HEIGH)
    topSectionExtrudeInput = extrudeFeatures.createInput(base_plate_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    topSectionExtrudeExtent = adsk.fusion.DistanceExtentDefinition.create(topSectionExtrudeDepth)
    topSectionExtrudeInput.setOneSideExtent(topSectionExtrudeExtent,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByReal(0))
    topSectionExtrudeFeature = extrudeFeatures.add(topSectionExtrudeInput)
    baseBody = topSectionExtrudeFeature.bodies.item(0)
    baseBody.name = 'base'

    # fillet on corners
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    fillet_edges = edgeUtils.selectEdgesByLength(baseBody.faces, const.BIN_BASE_TOP_SECTION_HEIGH, const.DEFAULT_FILTER_TOLERANCE)
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByReal(BIN_CORNER_FILLET_RADIUS), True)
    filletFeatures.add(filletInput)

    # chamfer top section
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(topSectionExtrudeFeature.endFaces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        topSectionExtrudeDepth,
        True)
    chamferFeatures.add(chamferInput)

    # extrude mid/bottom section
    baseBottomExtrude = extrudeUtils.simpleDistanceExtrude(
        topSectionExtrudeFeature.endFaces.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        const.BIN_BASE_MID_SECTION_HEIGH + const.BIN_BASE_BOTTOM_SECTION_HEIGH,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [baseBody],
        targetComponent
    )

    if input.hasBottomChamfer:
        # chamfer bottom section
        chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
        chamferInput = chamferFeatures.createInput2()
        chamfer_edges = commonUtils.objectCollectionFromList(faceUtils.getBottomFace(baseBottomExtrude.bodies.item(0)).edges)
        chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
            adsk.core.ValueInput.createByReal(const.BIN_BASE_BOTTOM_SECTION_HEIGH),
            True)
        chamferFeatures.add(chamferInput)
    
    # screw holes
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()

    screwHoleOffset = getScrewHoleOffset(input.baseWidth, input.xyTolerance)
    holeFeatures = features.holeFeatures
    if input.hasScrewHoles:
        baseTopPlane = topSectionExtrudeFeature.startFaces.item(0)
        screwHoleFeatureInput = holeFeatures.createSimpleInput(adsk.core.ValueInput.createByReal(input.screwHolesDiameter))
        screwHoleFeatureInput.setPositionByPlaneAndOffsets(
            baseTopPlane,
            adsk.core.Point3D.create(screwHoleOffset, screwHoleOffset, 0),
            baseTopPlane.edges.item(1),
            adsk.core.ValueInput.createByReal(screwHoleOffset),
            baseTopPlane.edges.item(3),
            adsk.core.ValueInput.createByReal(screwHoleOffset)
            )
        screwHoleFeatureInput.participantBodies = [baseBody]
        screwHoleFeatureInput.setAllExtent(adsk.fusion.ExtentDirections.PositiveExtentDirection)
        screwHoleFeature = holeFeatures.add(screwHoleFeatureInput)
        patternInputBodies.add(screwHoleFeature)

    # magnet cutouts
    if input.hasMagnetCutouts:
        baseBottomPlane = baseBottomExtrude.endFaces.item(0)
        magnetCutoutSketch = createMagnetCutoutSketch(baseBottomPlane, input.magnetCutoutsDiameter / 2, input.baseWidth, input.xyTolerance, targetComponent)

        magnetCutoutExtrude = extrudeUtils.simpleDistanceExtrude(
            magnetCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            input.magnetCutoutsDepth,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [baseBottomExtrude.bodies.item(0)],
            targetComponent,
        )
        patternInputBodies.add(magnetCutoutExtrude)
        
        if input.hasScrewHoles and input.magnetCutoutsDepth < const.BIN_BASE_HEIGHT:
            printHelperGrooveSketch: adsk.fusion.Sketch = sketches.add(magnetCutoutExtrude.endFaces.item(0))
            constraints: adsk.fusion.GeometricConstraints = printHelperGrooveSketch.geometricConstraints
            for curve in printHelperGrooveSketch.sketchCurves:
                curve.isConstruction = True
            sketchLines = printHelperGrooveSketch.sketchCurves.sketchLines
            sketchArcs = printHelperGrooveSketch.sketchCurves.sketchArcs
            magnetRadius = input.magnetCutoutsDiameter / 2
            screwRadius = input.screwHolesDiameter / 2
            bottomTangentLine = sketchLines.addByTwoPoints(
                adsk.core.Point3D.create(-screwHoleOffset + magnetRadius, screwHoleOffset - screwRadius, 0),
                adsk.core.Point3D.create(-screwHoleOffset - magnetRadius, screwHoleOffset - screwRadius, 0),
            )
            topTangentLine = sketchLines.addByTwoPoints(
                adsk.core.Point3D.create(-screwHoleOffset + magnetRadius, screwHoleOffset + screwRadius, 0),
                adsk.core.Point3D.create(-screwHoleOffset - magnetRadius, screwHoleOffset + screwRadius, 0),
            )
            leftTangentLine = sketchLines.addByTwoPoints(
                adsk.core.Point3D.create(-screwHoleOffset - screwRadius, screwHoleOffset - screwRadius, 0),
                adsk.core.Point3D.create(-screwHoleOffset - screwRadius, screwHoleOffset + screwRadius, 0),
            )
            rightTangentLine = sketchLines.addByTwoPoints(
                adsk.core.Point3D.create(-screwHoleOffset + screwRadius, screwHoleOffset - screwRadius, 0),
                adsk.core.Point3D.create(-screwHoleOffset + screwRadius, screwHoleOffset + screwRadius, 0),
            )
            screwHoleCircle: adsk.fusion.SketchCircle = filterCirclesByRadius(screwRadius, DEFAULT_FILTER_TOLERANCE, printHelperGrooveSketch.sketchCurves.sketchCircles)[0]
            screwHoleCircle.isConstruction = False
            magnetCutoutCircle: adsk.fusion.SketchCircle = filterCirclesByRadius(magnetRadius, DEFAULT_FILTER_TOLERANCE, printHelperGrooveSketch.sketchCurves.sketchCircles)[0]
            startArc = sketchArcs.addByCenterStartSweep(
                magnetCutoutCircle.centerSketchPoint,
                bottomTangentLine.startSketchPoint,
                1
                )
            endArc = sketchArcs.addByCenterStartSweep(
                magnetCutoutCircle.centerSketchPoint,
                topTangentLine.endSketchPoint,
                1
                )
            constraints.addCoincident(startArc.endSketchPoint, topTangentLine.startSketchPoint)
            constraints.addCoincident(endArc.endSketchPoint, bottomTangentLine.endSketchPoint)
            constraints.addConcentric(screwHoleCircle, startArc)
            constraints.addConcentric(screwHoleCircle, endArc)
            constraints.addTangent(screwHoleCircle, bottomTangentLine)
            constraints.addTangent(screwHoleCircle, topTangentLine)
            constraints.addCoincident(topTangentLine.startSketchPoint, magnetCutoutCircle)
            constraints.addCoincident(topTangentLine.endSketchPoint, magnetCutoutCircle)
            constraints.addHorizontal(bottomTangentLine)
            constraints.addHorizontal(topTangentLine)
            constraints.addCoincident(leftTangentLine.startSketchPoint, bottomTangentLine)
            constraints.addCoincident(rightTangentLine.startSketchPoint, bottomTangentLine)
            constraints.addCoincident(leftTangentLine.endSketchPoint, topTangentLine)
            constraints.addCoincident(rightTangentLine.endSketchPoint, topTangentLine)

            innerGrooveProfiles = []
            outerGrooveProfiles = []

            for profile in printHelperGrooveSketch.profiles:
                loop = profile.profileLoops[0]
                hadScrewHoleCircle = False

                for curve in loop.profileCurves:
                    if curve.sketchEntity == screwHoleCircle:
                        hadScrewHoleCircle = True
                    if curve.sketchEntity == startArc or curve.sketchEntity == endArc:
                        outerGrooveProfiles.append(profile)
                        hadScrewHoleCircle = False
                        break
                
                if hadScrewHoleCircle:
                    innerGrooveProfiles.append(profile)
                    
            printHelperOuterGrooveCutInput = extrudeFeatures.createInput(
                commonUtils.objectCollectionFromList(outerGrooveProfiles),
                adsk.fusion.FeatureOperations.CutFeatureOperation,
                )
            printHelperOuterGrooveCutExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(DIMENSION_PRINT_HELPER_GROOVE_DEPTH))
            printHelperOuterGrooveCutInput.setOneSideExtent(
                printHelperOuterGrooveCutExtent,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                adsk.core.ValueInput.createByReal(0),
            )
            printHelperOuterGrooveCutInput.participantBodies = [baseBottomExtrude.bodies.item(0)]
            printHelperOuterGrooveCut = extrudeFeatures.add(printHelperOuterGrooveCutInput)

            patternInputBodies.add(printHelperOuterGrooveCut)

            printHelperInnerGrooveCutInput = extrudeFeatures.createInput(
                commonUtils.objectCollectionFromList(innerGrooveProfiles),
                adsk.fusion.FeatureOperations.CutFeatureOperation,
                )
            printHelperInnerGrooveCutExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(DIMENSION_PRINT_HELPER_GROOVE_DEPTH * 2))
            printHelperInnerGrooveCutInput.setOneSideExtent(
                printHelperInnerGrooveCutExtent,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                adsk.core.ValueInput.createByReal(0),
            )
            printHelperInnerGrooveCutInput.participantBodies = [baseBottomExtrude.bodies.item(0)]
            printHelperInnerGrooveCut = extrudeFeatures.add(printHelperInnerGrooveCutInput)

            patternInputBodies.add(printHelperInnerGrooveCut)

    if input.hasScrewHoles or input.hasMagnetCutouts:
        patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
            targetComponent.xConstructionAxis,
            adsk.core.ValueInput.createByReal(2),
            adsk.core.ValueInput.createByReal(DIMENSION_SCREW_HOLES_DISTANCE),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        patternInput.directionTwoEntity = targetComponent.yConstructionAxis
        patternInput.quantityTwo = adsk.core.ValueInput.createByReal(2)
        patternInput.distanceTwo = adsk.core.ValueInput.createByReal(DIMENSION_SCREW_HOLES_DISTANCE)
        rectangularPatternFeatures.add(patternInput)

    return baseBody

def createBaseWithClearance(input: BaseGeneratorInput, targetComponent: adsk.fusion.Component):
    features = targetComponent.features
    # create base
    baseBody = createGridfinityBase(input, targetComponent)

    # offset side faces
    offsetFacesInput = features.offsetFeatures.createInput(
        commonUtils.objectCollectionFromList([face for face in list(baseBody.faces) if not faceUtils.isZNormal(face)]),
        adsk.core.ValueInput.createByReal(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        False
    )
    offsetFacesFeature = features.offsetFeatures.add(offsetFacesInput)
    offsetFacesFeature.name = "bin base side faces"
    offsetFacesFeature.bodies.item(0).name = "bin base side faces"

    extentEdge = faceUtils.getTopHorizontalEdge(offsetFacesFeature.bodies.item(0).edges)
    extendClearanceSurfaceFeatureInput = features.extendFeatures.createInput(
        commonUtils.objectCollectionFromList([extentEdge]),
        adsk.core.ValueInput.createByReal(input.xyTolerance * 2),
        adsk.fusion.SurfaceExtendTypes.NaturalSurfaceExtendType,
        True
    )
    features.extendFeatures.add(extendClearanceSurfaceFeatureInput)

    # thicken faces to add clearance
    thickenFeatureInput = features.thickenFeatures.createInput(
        commonUtils.objectCollectionFromList(offsetFacesFeature.faces),
        adsk.core.ValueInput.createByReal(input.xyTolerance),
        False,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        False,
    )
    thickenFeaure = features.thickenFeatures.add(thickenFeatureInput)
    thickenFeaure.name = "clearance"
    thickenFeaure.bodies.item(0).name = "bin base clearance layer"
    features.removeFeatures.add(offsetFacesFeature.bodies.item(0))

    # thickened body would go beyond the bottom face, use bounding box to make bottom flat
    clearanceBoundingBox = extrudeUtils.createBox(
        input.baseWidth,
        input.baseLength,
        -const.BIN_BASE_HEIGHT,
        targetComponent,
        targetComponent.xYConstructionPlane,
        )
    clearanceBoundingBox.name = "clearance bounding box"
    clearanceBoundingBox.bodies.item(0).name = "clearance bounding box"
    # move body to allow for clearance
    moveInput = features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([clearanceBoundingBox.bodies.item(0)]))
    moveInput.defineAsTranslateXYZ(
        adsk.core.ValueInput.createByReal(-input.xyTolerance),
        adsk.core.ValueInput.createByReal(-input.xyTolerance),
        adsk.core.ValueInput.createByReal(0),
        True
    )
    clearanceAlignment = features.moveFeatures.add(moveInput)
    clearanceAlignment.name = "align for xy clearance"
    combineFeatureInput = features.combineFeatures.createInput(
        thickenFeaure.bodies.item(0),
        commonUtils.objectCollectionFromList(clearanceBoundingBox.bodies)
    )
    combineFeatureInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    features.combineFeatures.add(combineFeatureInput)
    combineUtils.joinBodies(baseBody, commonUtils.objectCollectionFromList(thickenFeaure.bodies), targetComponent)
    return baseBody