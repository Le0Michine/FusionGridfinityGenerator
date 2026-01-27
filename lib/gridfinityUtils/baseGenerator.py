import adsk.core, adsk.fusion, traceback, math
import os

from .sketchUtils import createRectangle
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from . import sketchUtils, const, edgeUtils, commonUtils, combineUtils, faceUtils, extrudeUtils, shapeUtils, geometryUtils
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def createCircleAtPointSketch(
    plane: adsk.core.Base,
    radius: float,
    circleCenterPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    circleSketch: adsk.fusion.Sketch = sketches.add(plane)
    circleCenterOnSketch = circleSketch.modelToSketchSpace(circleCenterPoint)
    dimensions: adsk.fusion.SketchDimensions = circleSketch.sketchDimensions
    sketchUtils.convertToConstruction(circleSketch.sketchCurves)
    circle = circleSketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(circleCenterOnSketch.x, circleCenterOnSketch.y, 0),
        radius,
    )
    dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y * 2, 0),
        True,
    )
    dimensions.addDistanceDimension(
        circleSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
        True
        )
    dimensions.addDistanceDimension(
        circleSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
        True
        )

    return (circleSketch, circle)

def createTabAtCircleEdgeSketch(
    plane: adsk.core.Base,
    radius: float,
    circleCenterPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    circleSketch, circle = createCircleAtPointSketch(
        plane,
        radius,
        circleCenterPoint,
        targetComponent,
    )
    circleCenterOnSketch = geometryUtils.pointToXY(circleSketch.modelToSketchSpace(circleCenterPoint))
    angularPointOnSketch = geometryUtils.pointToXY(circleSketch.modelToSketchSpace(
        adsk.core.Point3D.create(circleCenterPoint.x + radius, circleCenterPoint.y + radius, circleCenterPoint.z)
    ))
    dimensions: adsk.fusion.SketchDimensions = circleSketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = circleSketch.geometricConstraints
    sketchUtils.convertToConstruction(circleSketch.sketchCurves)
    verticalConstructionLine = circleSketch.sketchCurves.sketchLines.addByTwoPoints(
        circleCenterOnSketch,
        adsk.core.Point3D.create(circleCenterOnSketch.x, circleCenterOnSketch.y + radius, circleCenterOnSketch.z)
    )
    verticalConstructionLine.isConstruction = True
    diagonalConstructionLine = circleSketch.sketchCurves.sketchLines.addByTwoPoints(
        circleCenterOnSketch,
        angularPointOnSketch,
    )
    diagonalConstructionLine.isConstruction = True
    constraints.addVertical(verticalConstructionLine)
    dimensions.addAngularDimension(
        diagonalConstructionLine,
        verticalConstructionLine,
        angularPointOnSketch,
    )
    constraints.addCoincident(
        verticalConstructionLine.startSketchPoint,
        circle.centerSketchPoint,
    )
    constraints.addCoincident(
        verticalConstructionLine.endSketchPoint,
        circle,
    )
    constraints.addCoincident(
        diagonalConstructionLine.startSketchPoint,
        circle.centerSketchPoint,
    )
    constraints.addCoincident(
        diagonalConstructionLine.endSketchPoint,
        circle,
    )
    circle = circleSketch.sketchCurves.sketchCircles.addByCenterRadius(
        diagonalConstructionLine.endSketchPoint,
        radius / 2,
    )
    dimensions.addRadialDimension(
        circle,
        circleCenterOnSketch,
    )

    return circleSketch

def createSingleGridfinityBaseBody(
    input: BaseGeneratorInput,
    targetComponent: adsk.fusion.Component,
):
    actual_base_width = input.baseWidth
    actual_base_length = input.baseLength
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, adsk.core.ValueInput.createByReal(input.originPoint.z))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    baseConstructionPlane.name = 'Base plate construction plane'
    # create rectangle for the base
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    basePlateSketch: adsk.fusion.Sketch = sketches.add(baseConstructionPlane)
    basePlateSketch.name = 'Base plate sketch'
    createRectangle(actual_base_width, actual_base_length, basePlateSketch.modelToSketchSpace(input.originPoint), basePlateSketch)

    # extrude top section
    topSectionExtrudeDepth = adsk.core.ValueInput.createByReal(const.BIN_BASE_TOP_SECTION_HEIGH)
    topSectionExtrudeInput = extrudeFeatures.createInput(basePlateSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    topSectionExtrudeExtent = adsk.fusion.DistanceExtentDefinition.create(topSectionExtrudeDepth)
    topSectionExtrudeInput.setOneSideExtent(topSectionExtrudeExtent,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByReal(0))
    topSectionExtrudeFeature = extrudeFeatures.add(topSectionExtrudeInput)
    topSectionExtrudeFeature.name = 'Base top section extrude'
    baseBody = topSectionExtrudeFeature.bodies.item(0)
    baseBody.name = 'Base'

    # fillet on corners
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    fillet_edges = edgeUtils.selectEdgesByLength(baseBody.faces, const.BIN_BASE_TOP_SECTION_HEIGH, const.DEFAULT_FILTER_TOLERANCE)
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByReal(input.cornerFilletRadius), True)
    filletFeatures.add(filletInput).name = 'Base corner fillet'

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
    circularPatternFeatures = features.circularPatternFeatures
    cutoutBodies = adsk.core.ObjectCollection.create()

    baseBottomPlane = baseBottomExtrude.endFaces.item(0)
    baseHoleCenterPoint = adsk.core.Point3D.create(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        baseBottomPlane.boundingBox.minPoint.z
    )
    cutoutCenterPoint = adsk.core.Point3D.create(baseHoleCenterPoint.x, baseHoleCenterPoint.y, 0)
    if input.hasScrewHoles:
        screwHoleBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -const.BIN_BASE_HEIGHT,
            input.screwHolesDiameter / 2,
            cutoutCenterPoint,
            targetComponent,
        )
        cutoutBodies.add(screwHoleBody)

    # magnet cutouts
    if input.hasMagnetCutouts:
        magnetSocketBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -input.magnetCutoutsDepth,
            input.magnetCutoutsDiameter / 2,
            cutoutCenterPoint,
            targetComponent,
        )
        cutoutBodies.add(magnetSocketBody)

        if input.magnetCutoutsChamferXY > 0 and input.magnetCutoutsChamferZ > 0:
            magnetChamferExtrude = extrudeUtils.simpleDistanceExtrude(
                faceUtils.getBottomFace(magnetSocketBody),
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                input.magnetCutoutsChamferZ,
                adsk.fusion.ExtentDirections.PositiveExtentDirection,
                [magnetSocketBody],
                targetComponent,
                -input.magnetCutoutsChamferZ,
                math.atan(input.magnetCutoutsChamferXY/input.magnetCutoutsChamferZ),
            )

        # magnet tab cutouts
        if input.hasMagnetCutoutsTabs:
            magnetTabCutoutSketch = createTabAtCircleEdgeSketch(
                baseBottomPlane,
                input.magnetCutoutsDiameter / 2,
                cutoutCenterPoint,
                targetComponent,
            )
            magnetTabCutoutSketch.name = "Cutout tab sketch"

            magnetTabCutoutExtrude = extrudeUtils.simpleDistanceExtrude(
                magnetTabCutoutSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                input.magnetCutoutsDepth,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                [],
                targetComponent,
            )
            cutoutBodies.add(magnetTabCutoutExtrude.bodies.item(0))
        
        if input.hasScrewHoles and (const.BIN_BASE_HEIGHT - input.magnetCutoutsDepth) > const.BIN_MAGNET_HOLE_GROOVE_DEPTH:
            grooveBody = shapeUtils.simpleCylinder(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH,
                input.magnetCutoutsDiameter / 2,
                cutoutCenterPoint,
                targetComponent,
            )
            grooveBody.name = "Groove body"
            grooveLayer1 = shapeUtils.simpleBox(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                input.magnetCutoutsDiameter,
                input.screwHolesDiameter,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x + input.magnetCutoutsDiameter / 2, baseHoleCenterPoint.y - input.screwHolesDiameter / 2, 0),
                targetComponent,
            )
            grooveLayer1.name = "Groove layer 1 body"
            grooveLayer2 = shapeUtils.simpleBox(
                baseBottomPlane,
                -(input.magnetCutoutsDepth + const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2),
                input.screwHolesDiameter,
                input.screwHolesDiameter,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x + input.screwHolesDiameter / 2, baseHoleCenterPoint.y - input.screwHolesDiameter / 2, 0),
                targetComponent,
            )
            grooveLayer2.name = "Groove layer 2 body"
            combineUtils.intersectBody(grooveBody, commonUtils.objectCollectionFromList([grooveLayer1, grooveLayer2]), targetComponent)

            rotateGrooveBodyInput = targetComponent.features.moveFeatures.createInput2(commonUtils.objectCollectionFromList([grooveBody]))
            verticalAxisVector = adsk.core.Vector3D.create(0, 0, 1.0)
            transformRotate = adsk.core.Matrix3D.create()
            transformRotate.setToRotation(math.radians(-45), verticalAxisVector, cutoutCenterPoint)
            rotateGrooveBodyInput.defineAsFreeMove(transformRotate)
            ratateGrooveBodyFeature = targetComponent.features.moveFeatures.add(rotateGrooveBodyInput)
            ratateGrooveBodyFeature.name = "Rotate groove by 45 degree"

            cutoutBodies.add(grooveBody)


    if input.hasScrewHoles or input.hasMagnetCutouts:
        if cutoutBodies.count > 1:
            joinFeature = combineUtils.joinBodies(cutoutBodies.item(0), commonUtils.objectCollectionFromList(list(cutoutBodies)[1:]), targetComponent)
            cutoutBodies = commonUtils.objectCollectionFromList(joinFeature.bodies)

        baseXZMidPlaneInput = targetComponent.constructionPlanes.createInput()
        baseXZMidPlaneInput.setByOffset(targetComponent.xZConstructionPlane, adsk.core.ValueInput.createByReal(input.baseLength / 2 - input.xyClearance))
        baseXZMidPlane = targetComponent.constructionPlanes.add(baseXZMidPlaneInput)
        baseXZMidPlane.name = "Base XZ mid plane"
        baseXZMidPlane.isLightBulbOn = False
        baseYZMidPlaneInput = targetComponent.constructionPlanes.createInput()
        baseYZMidPlaneInput.setByOffset(targetComponent.yZConstructionPlane, adsk.core.ValueInput.createByReal(input.baseWidth / 2 - input.xyClearance))
        baseYZMidPlane = targetComponent.constructionPlanes.add(baseYZMidPlaneInput)
        baseYZMidPlane.name = "Base YZ mid plane"
        baseYZMidPlane.isLightBulbOn = False
        patternAxisInput = targetComponent.constructionAxes.createInput()
        patternAxisInput.setByTwoPlanes(
            baseXZMidPlane,
            baseYZMidPlane
        )
        baseCenterAxis = targetComponent.constructionAxes.add(patternAxisInput)
        baseCenterAxis.name = "Base center axis"
        baseCenterAxis.isLightBulbOn = False
        patternInput = circularPatternFeatures.createInput(
            cutoutBodies,
            baseCenterAxis,
        )
        patternInput.quantity = adsk.core.ValueInput.createByString("4")
        patternFeature = circularPatternFeatures.add(patternInput)
        combineUtils.cutBody(baseBody, commonUtils.objectCollectionFromList(list(cutoutBodies) + list(patternFeature.bodies)), targetComponent)

    return baseBody


def createSingleBaseBodyWithClearance(input: BaseGeneratorInput, targetComponent: adsk.fusion.Component):
    """
    deprecated:: produced inconsistent results where fillets on the corners would not align properly with outer radius
    """
    features = targetComponent.features
    # create base
    baseBody = createSingleGridfinityBaseBody(input, targetComponent)

    # offset side faces
    offsetFacesInput = features.offsetFeatures.createInput(
        commonUtils.objectCollectionFromList([face for face in list(baseBody.faces) if not faceUtils.isZNormal(face)]),
        adsk.core.ValueInput.createByReal(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        False
    )
    offsetFacesFeature = features.offsetFeatures.add(offsetFacesInput)
    offsetFacesFeature.name = "bin base side faces"

    # original solid body might be included into feature bodies array, find created surfaces using isSolid flag
    offsetSurfaceBodies = [body for body in list(offsetFacesFeature.bodies) if not body.isSolid][0]
    offsetSurfaceBodies.name = "bin base side faces"

    extentEdge = faceUtils.getTopHorizontalEdge(offsetSurfaceBodies.edges)
    extendClearanceSurfaceFeatureInput = features.extendFeatures.createInput(
        commonUtils.objectCollectionFromList([extentEdge]),
        adsk.core.ValueInput.createByReal(input.xyClearance * 2),
        adsk.fusion.SurfaceExtendTypes.NaturalSurfaceExtendType,
        True
    )
    extendFeature = features.extendFeatures.add(extendClearanceSurfaceFeatureInput)

    # thicken faces to add clearance
    thickenFaces = commonUtils.objectCollectionFromList(offsetFacesFeature.faces, extendFeature.faces);
    thickenFeatureInput = features.thickenFeatures.createInput(
        thickenFaces,
        adsk.core.ValueInput.createByReal(input.xyClearance),
        False,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        False,
    )
    thickenFeaure = features.thickenFeatures.add(thickenFeatureInput)
    thickenFeaure.name = "clearance"
    thickenFeaure.bodies.item(0).name = "bin base clearance layer"
    features.removeFeatures.add(offsetSurfaceBodies)

    # thickened body would go beyond the bottom face, use bounding box to make bottom flat
    clearanceBoundingBox = extrudeUtils.createBoxAtPoint(
        input.baseWidth,
        input.baseLength,
        -const.BIN_BASE_HEIGHT,
        targetComponent,
        adsk.core.Point3D.create(input.originPoint.x - input.xyClearance, input.originPoint.y - input.xyClearance, input.originPoint.z),
        )
    clearanceBoundingBox.name = "clearance bounding box"
    clearanceBoundingBox.bodies.item(0).name = "clearance bounding box"
    combineFeatureInput = features.combineFeatures.createInput(
        thickenFeaure.bodies.item(0),
        commonUtils.objectCollectionFromList(clearanceBoundingBox.bodies)
    )
    combineFeatureInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    features.combineFeatures.add(combineFeatureInput)
    combineUtils.joinBodies(baseBody, commonUtils.objectCollectionFromList(thickenFeaure.bodies), targetComponent)
    return baseBody

def createBaseBodyPattern(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetComponent: adsk.fusion.Component,
):
    baseBody = createSingleGridfinityBaseBody(baseConfiguration, targetComponent)
    features = targetComponent.features
    # replicate base in a rectangular pattern
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()
    patternInputBodies.add(baseBody)
    patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
        targetComponent.xConstructionAxis,
        adsk.core.ValueInput.createByReal(basesXCount),
        adsk.core.ValueInput.createByReal(baseConfiguration.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = adsk.core.ValueInput.createByReal(basesYCount)
    patternInput.distanceTwo = adsk.core.ValueInput.createByReal(baseConfiguration.baseLength)
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    return list(rectangularPattern.bodies) + [baseBody]

def cutBaseClearance(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetComponent: adsk.fusion.Component,
):
    actual_base_width = baseConfiguration.baseWidth * basesXCount - baseConfiguration.xyClearance * 2
    actual_base_length = baseConfiguration.baseLength * basesYCount - baseConfiguration.xyClearance * 2
    features = targetComponent.features
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, adsk.core.ValueInput.createByReal(baseConfiguration.originPoint.z))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    baseClearanceCutSketch: adsk.fusion.Sketch = sketches.add(baseConstructionPlane)
    baseClearanceCutSketch.name = "Base clearance cut sketch"
    innerRectangle = createRectangle(
        actual_base_width,
        actual_base_length,
        adsk.core.Point3D.create(
            baseConfiguration.originPoint.x + baseConfiguration.xyClearance,
            baseConfiguration.originPoint.y + baseConfiguration.xyClearance,
            baseConfiguration.originPoint.z,
        ),
        baseClearanceCutSketch
    )
    sketchArcs = baseClearanceCutSketch.sketchCurves.sketchArcs
    geometricConstraints = baseClearanceCutSketch.geometricConstraints
    sketchDimensions = baseClearanceCutSketch.sketchDimensions

    [side1, side2, side3, side4] = list(innerRectangle)
    filletRadius = baseConfiguration.cornerFilletRadius - baseConfiguration.xyClearance
    fillet1 = sketchArcs.addFillet(side1, side1.endSketchPoint.geometry, side2, side2.startSketchPoint.geometry, filletRadius)
    fillet2 = sketchArcs.addFillet(side2, side2.endSketchPoint.geometry, side3, side3.startSketchPoint.geometry, filletRadius)
    fillet3 = sketchArcs.addFillet(side3, side3.endSketchPoint.geometry, side4, side4.startSketchPoint.geometry, filletRadius)
    fillet4 = sketchArcs.addFillet(side4, side4.endSketchPoint.geometry, side1, side1.startSketchPoint.geometry, filletRadius)

    geometricConstraints.addEqual(fillet1, fillet2)
    geometricConstraints.addEqual(fillet2, fillet3)
    geometricConstraints.addEqual(fillet3, fillet4)
    sketchDimensions.addRadialDimension(fillet1, fillet1.startSketchPoint.geometry)

    baseClearanceCutSketch.offset(commonUtils.objectCollectionFromList([fillet1, fillet2, fillet3, fillet4, side1, side2, side3, side4]), baseConfiguration.originPoint, 1)

    cuttingProfile = min(list(baseClearanceCutSketch.profiles), key=lambda x: x.boundingBox.minPoint.x)
    clearanceCutExtrudeInput = features.extrudeFeatures.createInput(
        cuttingProfile,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    clearanceCutExtrudeInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
    )
    clearanceCutExtrudeInput.participantBodies = list(targetComponent.bRepBodies)
    clearanceCutExtrude = features.extrudeFeatures.add(clearanceCutExtrudeInput)
    clearanceCutExtrude.name = "Base side clearance cut"