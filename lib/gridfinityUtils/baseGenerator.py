import adsk.core, adsk.fusion, traceback
import os


from .const import BASE_TOTAL_HEIGHT, BIN_CORNER_FILLET_RADIUS, DEFAULT_FILTER_TOLERANCE, DIMENSION_PRINT_HELPER_GROOVE_DEPTH, DIMENSION_SCREW_HOLES_DISTANCE
from .sketchUtils import createRectangle, filterCirclesByRadius
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.extrudeUtils import simpleDistanceExtrude
from . import sketchUtils, const
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def getScrewHoleOffset(baseWidth: float):
    return (baseWidth - DIMENSION_SCREW_HOLES_DISTANCE) / 2

def createMagnetCutoutSketch(
    plane: adsk.core.Base,
    radius: float,
    baseWidth: float,
    targetComponent: adsk.fusion.Component,
    ):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    magnetCutoutSketch: adsk.fusion.Sketch = sketches.add(plane)
    dimensions: adsk.fusion.SketchDimensions = magnetCutoutSketch.sketchDimensions
    screwHoleOffset = getScrewHoleOffset(baseWidth)
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
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # create rectangle for the base
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    base_plate_sketch: adsk.fusion.Sketch = sketches.add(targetComponent.xYConstructionPlane)
    createRectangle(actual_base_width, actual_base_width, base_plate_sketch.originPoint.geometry, base_plate_sketch)
        
    # extrude
    topExtrudeDepth = adsk.core.ValueInput.createByReal(0.23)
    topExtrudeInput = extrudeFeatures.createInput(base_plate_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    topExtrudeExtent = adsk.fusion.DistanceExtentDefinition.create(topExtrudeDepth)
    topExtrudeInput.setOneSideExtent(topExtrudeExtent,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByReal(0))
    topExtrudeFeature = extrudeFeatures.add(topExtrudeInput)
    baseBody = topExtrudeFeature.bodies.item(0)
    baseBody.name = 'base'

    # fillet
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    fillet_edges = adsk.core.ObjectCollection.create()
    faces: adsk.fusion.BRepFaces = baseBody.faces
    for i in range(0, 4):
        fillet_edges.add(faces.item(i).edges.item(1))
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByReal(BIN_CORNER_FILLET_RADIUS), True)
    filletFeatures.add(filletInput)

    # chamfer
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(topExtrudeFeature.endFaces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        topExtrudeDepth,
        True)
    chamferFeatures.add(chamferInput)

    # extrude again
    topExtrudeDepth = adsk.core.ValueInput.createByReal(0.27)
    baseBottomExtrude = extrudeFeatures.addSimple(
        faces.item(8),
        topExtrudeDepth,
        adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # chamfer again
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(baseBottomExtrude.endFaces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        adsk.core.ValueInput.createByReal(0.08),
        True)
    chamferFeatures.add(chamferInput)
    
    # screw holes
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()

    screwHoleOffset = getScrewHoleOffset(input.baseWidth)
    holeFeatures = features.holeFeatures
    if input.hasScrewHoles:
        baseTopPlane = topExtrudeFeature.startFaces.item(0)
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
        magnetCutoutSketch = createMagnetCutoutSketch(baseBottomPlane, input.magnetCutoutsDiameter / 2, input.baseWidth, targetComponent)

        magnetCutoutExtrude = simpleDistanceExtrude(
            magnetCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            input.magnetCutoutsDepth,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [baseBottomExtrude.bodies.item(0)],
            targetComponent,
        )
        patternInputBodies.add(magnetCutoutExtrude)
        
        if input.hasScrewHoles and input.magnetCutoutsDepth < const.BASE_TOTAL_HEIGHT:
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
            screwHoleCircle: adsk.fusion.SketchCircle = filterCirclesByRadius(screwRadius, DEFAULT_FILTER_TOLERANCE, printHelperGrooveSketch.sketchCurves.sketchCircles)[0]
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

            printHelperGrooveCutInput = extrudeFeatures.createInput(
                printHelperGrooveSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.CutFeatureOperation,
                )
            printHelperGrooveCutExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(DIMENSION_PRINT_HELPER_GROOVE_DEPTH))
            printHelperGrooveCutInput.setOneSideExtent(
                printHelperGrooveCutExtent,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                adsk.core.ValueInput.createByReal(0),
            )
            printHelperGrooveCutInput.participantBodies = [baseBottomExtrude.bodies.item(0)]
            printHelperGrooveCut = extrudeFeatures.add(printHelperGrooveCutInput)

            patternInputBodies.add(printHelperGrooveCut)


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
