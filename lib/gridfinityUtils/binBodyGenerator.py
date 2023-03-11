import adsk.core, adsk.fusion, traceback
import os
import math



from .const import BIN_BODY_BOTTOM_THICKNESS, BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CONNECTION_RECESS_DEPTH, BIN_CORNER_FILLET_RADIUS, BIN_SCOOP_MAX_RADIUS, BIN_TAB_EDGE_FILLET_RADIUS, BIN_TAB_WIDTH, DEFAULT_FILTER_TOLERANCE
from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils
from ...lib.gridfinityUtils.extrudeUtils import simpleDistanceExtrude
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface


def createBox(
    width: float,
    length: float,
    height: float,
    targetComponent: adsk.fusion.Component,
    targetPlane: adsk.core.Base,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(targetPlane)
    sketchUtils.createRectangle(width, length, recSketch.originPoint.geometry, recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    return extrude

def getVerticalEdges(
    faces: adsk.fusion.BRepFaces,
    ):
    filteredEdges: list[adsk.fusion.BRepEdge] = []
    for face in faces:
        for edge in face.edges:
            if geometryUtils.isVertical(edge):
                filteredEdges.append(edge)
    return filteredEdges

def excludeEdges(edges: list[adsk.fusion.BRepEdge], toExclude: list[adsk.fusion.BRepEdge]):
    toExcludeIds = [edge.tempId for edge in toExclude]
    return [edge for edge in edges if not edge.tempId in toExcludeIds]

def getInnerCutoutScoopFace(
    innerCutout: adsk.fusion.BRepBody
    ) -> tuple[adsk.fusion.BRepFace, adsk.fusion.BRepFace]:
    innerCutoutYNormalFaces = [face for face in innerCutout.faces if faceUtils.isYNormal(face)]
    scoopFace = min(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    oppositeFace = max(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    return (scoopFace, oppositeFace)

def createGridfinityBinBody(
    input: BinBodyGeneratorInput,
    targetComponent: adsk.fusion.Component,
    ):

    actualBodyWidth = (input.baseWidth * input.binWidth) - input.xyTolerance * 2.0
    actualBodyLength = (input.baseWidth * input.binLength) - input.xyTolerance * 2.0
    binBodyTotalHeight = input.binHeight * input.heightUnit + max(0, input.heightUnit - const.BIN_BASE_HEIGHT) + (const.BIN_LIP_EXTRA_HEIGHT if input.hasLip else 0)
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # create rectangle for the body
    binBodyExtrude = createBox(
        actualBodyWidth,
        actualBodyLength,
        binBodyTotalHeight,
        targetComponent,
        targetComponent.xYConstructionPlane
    )
    binBody = binBodyExtrude.bodies.item(0)
    binBody.name = 'bin body'

    bodiesToMerge: list[adsk.fusion.BRepBody] = []
    bodiesToSubtract: list[adsk.fusion.BRepBody] = []

    # round corners
    filletUtils.filletEdgesByLength(
        binBodyExtrude.faces,
        BIN_CORNER_FILLET_RADIUS,
        binBodyTotalHeight,
        targetComponent,
    )

    bottomCutoutFace: adsk.fusion.BRepFace = binBodyExtrude.endFaces.item(0);
    currentDepth = 0.0
    if input.hasLip:
        # sketch on top
        binBodyOpeningSketch = sketchUtils.createOffsetProfileSketch(
            bottomCutoutFace,
            -const.BIN_LIP_WALL_THICKNESS,
            targetComponent,
        )
        # extrude inside
        lipCutout = simpleDistanceExtrude(
            binBodyOpeningSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            BIN_CONNECTION_RECESS_DEPTH,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [binBody],
            targetComponent,
        )
        # top chamfer
        chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
        topLipChamferInput = chamferFeatures.createInput2()
        topLipChamferEdges = adsk.core.ObjectCollection.create()
        # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
        topLipChamferEdges.add(faceUtils.getTopHorizontalEdge(lipCutout.faces.item(0)))
        topLipChamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(topLipChamferEdges,
            adsk.core.ValueInput.createByReal(const.BIN_LIP_WALL_THICKNESS),
            True)
        chamferFeatures.add(topLipChamferInput)

        bottomCutoutFace = lipCutout.endFaces.item(0)
        currentDepth += BIN_CONNECTION_RECESS_DEPTH

    if not input.isSolid:
        offset = (const.BIN_LIP_WALL_THICKNESS - input.wallThickness) if input.hasLip else -input.wallThickness
        innerCutoutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(bottomCutoutFace)
        sketchUtils.convertToConstruction(innerCutoutSketch.sketchCurves)
        sketchUtils.createRectangle(
            actualBodyWidth - input.wallThickness,
            actualBodyLength - input.wallThickness,
            adsk.core.Point3D.create(input.wallThickness, input.wallThickness, 0),
            innerCutoutSketch,
        )

        innerCutout = simpleDistanceExtrude(
            innerCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            binBodyTotalHeight - BIN_BODY_BOTTOM_THICKNESS - currentDepth,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
        )
        innerCutoutBody = innerCutout.bodies.item(0)
        innerCutoutBody.name = 'inner cutout'
        bodiesToSubtract.append(innerCutoutBody)

        innerCutoutFilletRadius = max(BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CORNER_FILLET_RADIUS - input.wallThickness)

        # scoop
        if input.hasScoop:
            if input.hasLip and offset > 0:
                [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
                # with scoop need to align one of the walls with the lip
                extrudeInput = extrudeFeatures.createInput(
                    innerCutoutScoopFace,
                    adsk.fusion.FeatureOperations.CutFeatureOperation,
                )
                extrudeExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(offset))
                extrudeInput.setOneSideExtent(
                    extrudeExtent,
                    adsk.fusion.ExtentDirections.NegativeExtentDirection,
                )
                extrudeInput.participantBodies = [innerCutoutBody]
                extrudeFeatures.add(extrudeInput)
            [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
            scoopEdge = faceUtils.getBottomHorizontalEdge(innerCutoutScoopFace)
            scoopRadius = min(BIN_SCOOP_MAX_RADIUS, binBodyTotalHeight)
            filletUtils.createFillet(
                [scoopEdge],
                scoopRadius,
                False,
                targetComponent
            )
        # fillet inner cutout
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        innerCutoutVerticalFaces = getVerticalEdges(innerCutoutBody.faces)
        filletUtils.createFillet(
            innerCutoutVerticalFaces,
            innerCutoutFilletRadius,
            True,
            targetComponent
        )
        # recalculate faces after fillet
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopOppositeEdge = faceUtils.getBottomHorizontalEdge(innerCutoputScoopOppositeFace)

        filletUtils.createFillet(
            [scoopOppositeEdge],
            innerCutoutFilletRadius,
            True,
            targetComponent
        )

        if input.hasLip and offset > 0:
            simpleDistanceExtrude(
                faceUtils.getTopFace(innerCutoutBody),
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                innerCutoutFilletRadius - offset,
                adsk.fusion.ExtentDirections.PositiveExtentDirection,
                [innerCutoutBody],
                targetComponent,
            )
            [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
            topEdge = faceUtils.getTopHorizontalEdge(innerCutoutScoopFace)
            topEdgesWithConnectedFilletEdges = [topEdge.tangentiallyConnectedEdges[1], topEdge.tangentiallyConnectedEdges[-1], topEdge]
            edgesToChamfer = excludeEdges(list(faceUtils.getTopFace(innerCutoutBody).edges), topEdgesWithConnectedFilletEdges)
            if not input.hasScoop:
                edgesToChamfer = edgesToChamfer + topEdgesWithConnectedFilletEdges
            # bottom lip chamfer, no lip if main wall thicker or same size as the lip
            chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
            bottomLipChamferInput = chamferFeatures.createInput2()
            bottomLipChamferEdges = commonUtils.objectCollectionFromList(edgesToChamfer)
            bottomLipChamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                bottomLipChamferEdges,
                adsk.core.ValueInput.createByReal(innerCutoutFilletRadius),
                False)
            chamferFeatures.add(bottomLipChamferInput)
        
        # label tab
        if input.hasTab:
            tabProfilePlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
            actualTabLength = max(0, min(input.tabLength, input.binWidth)) * input.baseWidth
            actualTabPosition = max(0, min(input.tabPosition, input.binWidth - input.tabLength)) * input.baseWidth
            tabProfilePlaneInput.setByOffset(
                targetComponent.yZConstructionPlane,
                adsk.core.ValueInput.createByReal(actualTabPosition)
                )
            tabProfilePlane = targetComponent.constructionPlanes.add(tabProfilePlaneInput)
            tabSketch: adsk.fusion.Sketch = targetComponent.sketches.add(tabProfilePlane)
            tabSketchLine = tabSketch.sketchCurves.sketchLines
            tabTopEdgeHeight = binBodyTotalHeight - BIN_CONNECTION_RECESS_DEPTH if input.hasLip else binBodyTotalHeight
            tabYOffset = input.wallThickness + const.BIN_LIP_WALL_THICKNESS if input.hasLip else 0
            actualTabWidth = tabYOffset + BIN_TAB_WIDTH
            actualTabHeight = actualTabWidth / math.tan(input.tabOverhangAngle)
            line1 = tabSketchLine.addByTwoPoints(
                tabSketch.modelToSketchSpace(adsk.core.Point3D.create(actualTabPosition, actualBodyLength, tabTopEdgeHeight)),
                tabSketch.modelToSketchSpace(adsk.core.Point3D.create(actualTabPosition, actualBodyLength, tabTopEdgeHeight - actualTabHeight)),
            )
            line2 = tabSketchLine.addByTwoPoints(
                tabSketch.modelToSketchSpace(adsk.core.Point3D.create(actualTabPosition, actualBodyLength, tabTopEdgeHeight)),
                tabSketch.modelToSketchSpace(adsk.core.Point3D.create(actualTabPosition, actualBodyLength - actualTabWidth, tabTopEdgeHeight)),
            )
            line3 = tabSketchLine.addByTwoPoints(
                tabSketch.modelToSketchSpace(adsk.core.Point3D.create(actualTabPosition, actualBodyLength, tabTopEdgeHeight - actualTabHeight)),
                tabSketch.modelToSketchSpace(adsk.core.Point3D.create(actualTabPosition, actualBodyLength - actualTabWidth, tabTopEdgeHeight)),
            )

            constraints: adsk.fusion.GeometricConstraints = tabSketch.geometricConstraints
            dimensions: adsk.fusion.SketchDimensions = tabSketch.sketchDimensions

            # horizontal/vertical relative to local sketch XY coordinates
            constraints.addHorizontal(line1)
            constraints.addVertical(line2)
            constraints.addCoincident(line1.startSketchPoint, line2.startSketchPoint)
            constraints.addCoincident(line2.endSketchPoint, line3.endSketchPoint)
            constraints.addCoincident(line1.endSketchPoint, line3.startSketchPoint)

            dimensions.addDistanceDimension(
                tabSketch.originPoint,
                line1.startSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                line1.startSketchPoint.geometry,
                True
                )

            dimensions.addDistanceDimension(
                tabSketch.originPoint,
                line1.startSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                line1.startSketchPoint.geometry,
                True
                )

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

            tabExtrudeFeature = simpleDistanceExtrude(
                tabSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                actualTabLength,
                adsk.fusion.ExtentDirections.PositiveExtentDirection,
                [],
                targetComponent,
            )
            tabBody = tabExtrudeFeature.bodies.item(0)
            tabBody.name = 'label tab'
            bodiesToMerge.append(tabBody)

            intersectTabInput = targetComponent.features.combineFeatures.createInput(
                tabBody,
                commonUtils.objectCollectionFromList([binBody]),
                )
            intersectTabInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
            intersectTabInput.isKeepToolBodies = True
            targetComponent.features.combineFeatures.add(intersectTabInput)
            tabTopFace = faceUtils.getTopFace(tabBody)
            # get longest edge to apply fillet, relying on fillets left by intersection to shorten other edge
            longestTopTabEdge = max(tabTopFace.edges, key=lambda x: x.length)
            filletUtils.createFillet(
                [longestTopTabEdge],
                BIN_TAB_EDGE_FILLET_RADIUS,
                False,
                targetComponent
            )

        if len(bodiesToSubtract) > 0:
            combineUtils.cutBody(
                binBody,
                commonUtils.objectCollectionFromList(bodiesToSubtract),
                targetComponent
            )
        if len(bodiesToMerge) > 0:
            combineUtils.joinBodies(
                binBody,
                commonUtils.objectCollectionFromList(bodiesToMerge),
                targetComponent
            )

    return binBody
