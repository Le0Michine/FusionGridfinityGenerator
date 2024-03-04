import adsk.core, adsk.fusion, traceback, math
import os


from .const import BIN_CORNER_FILLET_RADIUS, DEFAULT_FILTER_TOLERANCE, DIMENSION_PRINT_HELPER_GROOVE_DEPTH
from .sketchUtils import createRectangle, filterCirclesByRadius
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from . import sketchUtils, const, edgeUtils, commonUtils, combineUtils, faceUtils, extrudeUtils, shapeUtils
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

    return circleSketch

def createGridfinityBase(
    input: BaseGeneratorInput,
    targetComponent: adsk.fusion.Component,
):
    actual_base_width = input.baseWidth - input.xyClearance * 2.0
    actual_base_length = input.baseLength - input.xyClearance * 2.0
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, adsk.core.ValueInput.createByReal(input.originPoint.z))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    # create rectangle for the base
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    basePlateSketch: adsk.fusion.Sketch = sketches.add(baseConstructionPlane)
    rectangleOrigin = basePlateSketch.modelToSketchSpace(input.originPoint)
    createRectangle(actual_base_width, actual_base_length,rectangleOrigin, basePlateSketch)

    # extrude top section
    topSectionExtrudeDepth = adsk.core.ValueInput.createByReal(const.BIN_BASE_TOP_SECTION_HEIGH)
    topSectionExtrudeInput = extrudeFeatures.createInput(basePlateSketch.profiles.item(0),
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
    cutoutBodies = adsk.core.ObjectCollection.create()

    baseBottomPlane = baseBottomExtrude.endFaces.item(0)
    baseHoleCenterPoint = adsk.core.Point3D.create(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        baseBottomPlane.boundingBox.minPoint.z
    )
    if input.hasScrewHoles:
        screwHoleBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -const.BIN_BASE_HEIGHT,
            input.screwHolesDiameter / 2,
            adsk.core.Point3D.create(baseHoleCenterPoint.x, baseHoleCenterPoint.y, 0),
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
            adsk.core.Point3D.create(baseHoleCenterPoint.x, baseHoleCenterPoint.y, 0),
            targetComponent,
        )
        cutoutBodies.add(magnetSocketBody)

        # magnet tab cutouts
        if input.hasMagnetCutoutsTabs:
            patternTabCutoutBodies = adsk.core.ObjectCollection.create()
            tabRadius = input.magnetCutoutsDiameter / 4
            tabOffset = math.sqrt(2) * tabRadius
            magnetTabCutoutSketch = createCircleAtPointSketch(
                baseBottomPlane,
                tabRadius,
                adsk.core.Point3D.create(
                    baseHoleCenterPoint.x + tabOffset,
                    baseHoleCenterPoint.y + tabOffset,
                    0
                ),
                targetComponent
            )

            magnetTabCutoutExtrude = extrudeUtils.simpleDistanceExtrude(
                magnetTabCutoutSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.CutFeatureOperation,
                input.magnetCutoutsDepth,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                [baseBottomExtrude.bodies.item(0)],
                targetComponent,
            )
            patternTabCutoutBodies.add(magnetTabCutoutExtrude)
        
        if input.hasScrewHoles and (const.BIN_BASE_HEIGHT - input.magnetCutoutsDepth) > const.BIN_MAGNET_HOLE_GROOVE_DEPTH:
            grooveBody = shapeUtils.simpleCylinder(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH,
                input.magnetCutoutsDiameter / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x, baseHoleCenterPoint.y, 0),
                targetComponent,
            )
            grooveLayer1 = shapeUtils.simpleBox(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                input.magnetCutoutsDiameter,
                input.screwHolesDiameter,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x + input.magnetCutoutsDiameter / 2, baseHoleCenterPoint.y - input.screwHolesDiameter / 2, 0),
                targetComponent,
            )
            grooveLayer2 = shapeUtils.simpleBox(
                baseBottomPlane,
                -(input.magnetCutoutsDepth + const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2),
                input.screwHolesDiameter,
                input.screwHolesDiameter,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                adsk.core.Point3D.create(baseHoleCenterPoint.x + input.screwHolesDiameter / 2, baseHoleCenterPoint.y - input.screwHolesDiameter / 2, 0),
                targetComponent,
            )
            combineUtils.intersectBody(grooveBody, commonUtils.objectCollectionFromList([grooveLayer1, grooveLayer2]), targetComponent)

            cutoutBodies.add(grooveBody)


    if input.hasScrewHoles or input.hasMagnetCutouts:
        patternSpacingX = input.baseWidth - const.DIMENSION_SCREW_HOLES_OFFSET * 2
        patternSpacingY = input.baseLength - const.DIMENSION_SCREW_HOLES_OFFSET * 2
        
        if cutoutBodies.count > 1:
            joinFeature = combineUtils.joinBodies(cutoutBodies.item(0), commonUtils.objectCollectionFromList(list(cutoutBodies)[1:]), targetComponent)
            cutoutBodies = commonUtils.objectCollectionFromList(joinFeature.bodies)
        patternInput = rectangularPatternFeatures.createInput(cutoutBodies,
            targetComponent.xConstructionAxis,
            adsk.core.ValueInput.createByReal(2),
            adsk.core.ValueInput.createByReal(patternSpacingX),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        patternInput.directionTwoEntity = targetComponent.yConstructionAxis
        patternInput.quantityTwo = adsk.core.ValueInput.createByReal(2)
        patternInput.distanceTwo = adsk.core.ValueInput.createByReal(patternSpacingY)
        patternFeature = rectangularPatternFeatures.add(patternInput)
        combineUtils.cutBody(baseBody, commonUtils.objectCollectionFromList(list(cutoutBodies) + list(patternFeature.bodies)), targetComponent)

        if input.hasMagnetCutoutsTabs:
            patternTabInput = rectangularPatternFeatures.createInput(patternTabCutoutBodies,
                targetComponent.xConstructionAxis,
                adsk.core.ValueInput.createByReal(2),
                adsk.core.ValueInput.createByReal(patternSpacingX - input.magnetCutoutsDiameter + tabOffset),
                adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
            patternTabInput.directionTwoEntity = targetComponent.yConstructionAxis
            patternTabInput.quantityTwo = adsk.core.ValueInput.createByReal(2)
            patternTabInput.distanceTwo = adsk.core.ValueInput.createByReal(patternSpacingY  - input.magnetCutoutsDiameter + tabOffset)
            rectangularPatternFeatures.add(patternTabInput)

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