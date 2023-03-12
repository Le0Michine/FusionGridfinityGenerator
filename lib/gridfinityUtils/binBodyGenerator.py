import adsk.core, adsk.fusion, traceback
import os
import math



from .const import BIN_BODY_BOTTOM_THICKNESS, BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CONNECTION_RECESS_DEPTH, BIN_CORNER_FILLET_RADIUS, BIN_SCOOP_MAX_RADIUS, BIN_TAB_EDGE_FILLET_RADIUS, BIN_TAB_WIDTH, DEFAULT_FILTER_TOLERANCE
from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

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
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # create rectangle for the body
    binBodyExtrude = extrudeUtils.createBox(
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

    if input.hasLip:
        lipCutoutBodies: list[adsk.fusion.BRepBody] = []
        lipCutoutPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        lipCutoutPlaneInput.setByOffset(
            binBodyExtrude.endFaces.item(0),
            adsk.core.ValueInput.createByReal(0)
        )
        lipCutoutConstructionPlane = targetComponent.constructionPlanes.add(lipCutoutPlaneInput)

        if input.hasLipNotches:
            lipCutoutInput = BaseGeneratorInput()
            lipCutoutInput.baseWidth = input.baseWidth
            lipCutoutInput.baseLength = input.baseWidth
            lipCutoutInput.xyTolerance = input.xyTolerance
            lipCutoutInput.hasBottomChamfer = False
            lipCutout = baseGenerator.createBaseWithClearance(lipCutoutInput, targetComponent)
            lipCutout.name = "lip cutout"
            lipCutoutBodies.append(lipCutout)

            patternInputBodies = adsk.core.ObjectCollection.create()
            patternInputBodies.add(lipCutout)
            patternInput = features.rectangularPatternFeatures.createInput(patternInputBodies,
                targetComponent.xConstructionAxis,
                adsk.core.ValueInput.createByReal(input.binWidth),
                adsk.core.ValueInput.createByReal(input.baseWidth),
                adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
            patternInput.directionTwoEntity = targetComponent.yConstructionAxis
            patternInput.quantityTwo = adsk.core.ValueInput.createByReal(input.binLength)
            patternInput.distanceTwo = adsk.core.ValueInput.createByReal(input.baseLength)
            rectangularPattern = features.rectangularPatternFeatures.add(patternInput)
            lipCutoutBodies = lipCutoutBodies + list(rectangularPattern.bodies)

            lipMidCutoutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(lipCutoutConstructionPlane)
            sketchUtils.createRectangle(
                input.baseWidth * input.binWidth - const.BIN_BASE_TOP_SECTION_HEIGH * 2,
                input.baseLength * input.binLength - const.BIN_BASE_TOP_SECTION_HEIGH * 2,
                adsk.core.Point3D.create(-input.baseWidth * input.binWidth / 2 + const.BIN_BASE_TOP_SECTION_HEIGH, -input.baseWidth * input.binLength / 2 + const.BIN_BASE_TOP_SECTION_HEIGH, 0),
                lipMidCutoutSketch,
            )
            lipMidCutout = extrudeUtils.simpleDistanceExtrude(
                lipMidCutoutSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                const.BIN_BASE_HEIGHT,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                [],
                targetComponent,
            )
            # fillet on corners
            filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
            filletInput = filletFeatures.createInput()
            filletInput.isRollingBallCorner = True
            fillet_edges = edgeUtils.selectEdgesByLength(lipMidCutout.bodies.item(0).faces, const.BIN_BASE_HEIGHT, const.DEFAULT_FILTER_TOLERANCE)
            filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByReal(const.BIN_CORNER_FILLET_RADIUS - const.BIN_BASE_TOP_SECTION_HEIGH + const.BIN_XY_TOLERANCE), True)
            filletFeatures.add(filletInput)
            bodiesToSubtract.append(lipMidCutout.bodies.item(0))

        else:
            lipCutoutInput = BaseGeneratorInput()
            lipCutoutInput.baseWidth = input.baseWidth * input.binWidth
            lipCutoutInput.baseLength = input.baseLength * input.binLength
            lipCutoutInput.xyTolerance = input.xyTolerance
            lipCutoutInput.hasBottomChamfer = False
            lipCutout = baseGenerator.createBaseWithClearance(lipCutoutInput, targetComponent)
            lipCutout.name = "lip cutout"
            lipCutoutBodies.append(lipCutout)

        topChamferSketch: adsk.fusion.Sketch = targetComponent.sketches.add(lipCutoutConstructionPlane)
        sketchUtils.createRectangle(
            actualBodyWidth,
            actualBodyLength,
            adsk.core.Point3D.create(-actualBodyWidth / 2, -actualBodyLength / 2, 0),
            topChamferSketch,
        )
        topChamferNegativeVolume = extrudeUtils.simpleDistanceExtrude(
            topChamferSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            const.BIN_LIP_TOP_RECESS_HEIGHT,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            [],
            targetComponent,
        )
        bodiesToSubtract.append(topChamferNegativeVolume.bodies.item(0))
        
        # move up
        moveInput = features.moveFeatures.createInput2(commonUtils.objectCollectionFromList(lipCutoutBodies))
        moveInput.defineAsTranslateXYZ(
            adsk.core.ValueInput.createByReal(0),
            adsk.core.ValueInput.createByReal(0),
            adsk.core.ValueInput.createByReal((input.binHeight + 1) * input.heightUnit),
            True
        )
        lipCutoutHeightAlignment = features.moveFeatures.add(moveInput)
        lipCutoutHeightAlignment.name = "move to the top"
        bodiesToSubtract = bodiesToSubtract + lipCutoutBodies

    if not input.isSolid:
        cutoutPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        cutoutPlaneInput.setByOffset(
            binBodyExtrude.endFaces.item(0),
            adsk.core.ValueInput.createByReal(-BIN_CONNECTION_RECESS_DEPTH if input.hasLip else 0)
        )
        cutoutConstructionPlane = targetComponent.constructionPlanes.add(cutoutPlaneInput)
        offset = (const.BIN_LIP_WALL_THICKNESS - input.wallThickness) if input.hasLip else -input.wallThickness
        innerCutoutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(cutoutConstructionPlane)
        sketchUtils.createRectangle(
            actualBodyWidth - input.wallThickness * 2,
            actualBodyLength - input.wallThickness * 2,
            adsk.core.Point3D.create(-actualBodyWidth / 2 + input.wallThickness, -actualBodyLength / 2 + input.wallThickness, 0),
            innerCutoutSketch,
        )

        innerCutout = extrudeUtils.simpleDistanceExtrude(
            innerCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            binBodyTotalHeight - BIN_BODY_BOTTOM_THICKNESS - (BIN_CONNECTION_RECESS_DEPTH if input.hasLip else 0),
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
            scoopEdge = faceUtils.getBottomHorizontalEdge(innerCutoutScoopFace.edges)
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
        scoopOppositeEdge = faceUtils.getBottomHorizontalEdge(innerCutoputScoopOppositeFace.edges)

        filletUtils.createFillet(
            [scoopOppositeEdge],
            innerCutoutFilletRadius,
            True,
            targetComponent
        )

        if input.hasLip and offset > 0:
            extrudeUtils.simpleDistanceExtrude(
                faceUtils.getTopFace(innerCutoutBody),
                adsk.fusion.FeatureOperations.JoinFeatureOperation,
                innerCutoutFilletRadius - offset,
                adsk.fusion.ExtentDirections.PositiveExtentDirection,
                [innerCutoutBody],
                targetComponent,
            )
            [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
            topEdge = faceUtils.getTopHorizontalEdge(innerCutoutScoopFace.edges)
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

            tabExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
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
