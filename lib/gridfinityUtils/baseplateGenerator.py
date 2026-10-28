import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, commonUtils, filletUtils, combineUtils, faceUtils, extrudeUtils, sketchUtils, baseGenerator, patternUtils, shapeUtils, geometryUtils, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .baseplateGeneratorInput import BaseplateGeneratorInput

def createGridfinityBaseplate(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component):
    timer = commonUtils.StepTimer('Baseplate {}x{}'.format(int(input.baseplateWidth), int(input.baseplateLength)))
    features = targetComponent.features
    cutoutInput = BaseGeneratorInput()
    cutoutInput.xyClearance = input.xyClearance
    cutoutInput.originPoint = geometryUtils.createOffsetPoint(
        targetComponent.originConstructionPoint.geometry,
        byX=-cutoutInput.xyClearance * 2,
        byY=-cutoutInput.xyClearance * 2,
    )
    cutoutInput.baseWidth = input.baseWidth + cutoutInput.xyClearance * 2
    cutoutInput.baseLength = input.baseLength + cutoutInput.xyClearance * 2
    cutoutInput.cornerFilletRadius = input.cornerFilletRadius + cutoutInput.xyClearance
    baseBody = baseGenerator.createSingleGridfinityBaseBody(cutoutInput, targetComponent)

    cuttingTools: list[adsk.fusion.BRepBody] = []
    extraCutoutBodies: list[adsk.fusion.BRepBody] = []

    holeCenterPoint = adsk.core.Point3D.create(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        0
    )

    connectionHoleYTool = None
    connectionHoleXTool = None

    if input.hasSkeletonizedBottom:
        centerCutoutSketch,centerCutoutSketchCircle = baseGenerator.createCircleAtPointSketch(
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

        baseCenterOffsetX = input.baseWidth / 2 - input.xyClearance
        baseCenterOffsetY = input.baseLength / 2 - input.xyClearance
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

    timer.step('seed socket')

    baseplateTrueWidth = input.baseplateWidth * input.baseWidth - input.xyClearance * 2
    baseplateTrueLength = input.baseplateLength * input.baseLength - input.xyClearance * 2

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
            (input.baseLength, input.baseLength),
            (input.baseplateWidth, 1),
            targetComponent
        )
        connectionHoleYToolList = list(connectionHoleYTool.bodies) + list(holeToolsYFeature.bodies)

        constructionPlaneXZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneXZInput.setByOffset(targetComponent.xZConstructionPlane, adsk.core.ValueInput.createByReal(input.baseplateLength * input.baseLength / 2 - input.xyClearance))
        constructionPlaneXZ = targetComponent.constructionPlanes.add(constructionPlaneXZInput)
        constructionPlaneXZ.isLightBulbOn = False

        constructionPlaneYZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneYZInput.setByOffset(targetComponent.yZConstructionPlane, adsk.core.ValueInput.createByReal(input.baseplateWidth * input.baseWidth / 2 - input.xyClearance))
        constructionPlaneYZ = targetComponent.constructionPlanes.add(constructionPlaneYZInput)
        constructionPlaneYZ.isLightBulbOn = False

        mirrorConnectionHolesYZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleXToolList), constructionPlaneYZ)
        mirrorConnectionHolesYZ = features.mirrorFeatures.add(mirrorConnectionHolesYZInput)

        mirrorConnectionHolesXZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleYToolList), constructionPlaneXZ)
        mirrorConnectionHolesXZ = features.mirrorFeatures.add(mirrorConnectionHolesXZInput)

        cuttingTools = cuttingTools + list(mirrorConnectionHolesYZ.bodies) + list(mirrorConnectionHolesXZ.bodies) + connectionHoleYToolList + connectionHoleXToolList
    timer.step('connection holes')

    # the plate is built from socket cells each cut once by the seed socket, then patterned and joined,
    # instead of cutting a plate body with a socket body per cell
    gridHeight = const.BIN_BASE_HEIGHT + (input.bottomExtensionHeight if input.hasExtendedBottom else 0)
    # cells start below the top clearance, the same as cutting it from the whole plate
    gridTop = -max(0, input.binZClearance)
    paddingLeft = input.paddingLeft if input.hasPadding else 0
    paddingTop = input.paddingTop if input.hasPadding else 0
    paddingRight = input.paddingRight if input.hasPadding else 0
    paddingBottom = input.paddingBottom if input.hasPadding else 0
    baseplateBody = createSocketCellGrid(input, baseBody, gridTop, gridHeight, targetComponent, timer)

    # padding past the cells. Sockets overhang their cells by the xy clearance, but only within the top
    # xy clearance depth, which the top clearance removes anyway unless it is set smaller
    cellsMinX = -input.xyClearance
    cellsMaxX = input.baseplateWidth * input.baseWidth - input.xyClearance
    cellsMinY = -input.xyClearance
    cellsMaxY = input.baseplateLength * input.baseLength - input.xyClearance
    outlineMinX = -paddingLeft
    outlineMaxX = baseplateTrueWidth + paddingRight
    outlineMinY = -paddingBottom
    outlineMaxY = baseplateTrueLength + paddingTop
    paddingStrips = [
        ("Padding left", outlineMinX, outlineMinY, cellsMinX, outlineMaxY),
        ("Padding right", cellsMaxX, outlineMinY, outlineMaxX, outlineMaxY),
        ("Padding bottom", cellsMinX, outlineMinY, cellsMaxX, cellsMinY),
        ("Padding top", cellsMinX, cellsMaxY, cellsMaxX, outlineMaxY),
    ]
    paddingBodies: list[adsk.fusion.BRepBody] = []
    for (name, minX, minY, maxX, maxY) in paddingStrips:
        if maxX - minX > const.DEFAULT_FILTER_TOLERANCE and maxY - minY > const.DEFAULT_FILTER_TOLERANCE:
            paddingBody = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                gridTop,
                maxX - minX,
                maxY - minY,
                -(gridHeight + gridTop),
                adsk.core.Point3D.create(minX, minY, 0),
                targetComponent,
            )
            paddingBody.name = name
            paddingBodies.append(paddingBody)
    if len(paddingBodies) > 0:
        combineUtils.joinBodies(
            baseplateBody,
            commonUtils.objectCollectionFromList(paddingBodies),
            targetComponent,
        ).name = "Join padding"
        timer.step(f'padding ({len(paddingBodies)} strips)')

    # trims cells overhanging the plate edge and rounds the outer corners
    baseGenerator.cutOutsideRoundedRectangle(
        adsk.core.Point3D.create(outlineMinX, outlineMinY, 0),
        outlineMaxX - outlineMinX,
        outlineMaxY - outlineMinY,
        input.cornerFilletRadius - input.xyClearance,
        [baseplateBody],
        targetComponent,
    ).name = "Trim to plate outline"
    timer.step('trim to outline')

    bottomFace = faceUtils.getBottomFace(baseplateBody)
    plateBox = baseplateBody.boundingBox
    def isOnOutline(edge: adsk.fusion.BRepEdge):
        edgeBox = edge.boundingBox
        return any(math.isclose(edgeValue, plateValue, abs_tol=const.DEFAULT_FILTER_TOLERANCE) for (edgeValue, plateValue) in [
            (edgeBox.minPoint.x, plateBox.minPoint.x),
            (edgeBox.maxPoint.x, plateBox.maxPoint.x),
            (edgeBox.minPoint.y, plateBox.minPoint.y),
            (edgeBox.maxPoint.y, plateBox.maxPoint.y),
        ])
    # the bottom face also has socket edges now, only chamfer the outline edges picked by length as before
    bottomChamferEdges = [
        edge for edge in edgeUtils.selectEdgesByLength(
            [bottomFace],
            outlineMaxY - outlineMinY,
            const.BIN_CORNER_FILLET_RADIUS * 3,
        )
        if isOnOutline(edge)
    ]
    if len(bottomChamferEdges) > 0:
        filletUtils.createChamfer(
            commonUtils.objectCollectionFromList(bottomChamferEdges),
            0.05,
            targetComponent,
        ).name = "Bottom chamfer"
    timer.step('bottom chamfer')

    # cut everything else
    if len(cuttingTools) > 0:
        finalCut = combineUtils.cutBody(
            baseplateBody,
            commonUtils.objectCollectionFromList(cuttingTools),
            targetComponent,
        )
        finalCut.name = "Final baseplate cut"
        timer.step('final cut')
    timer.total()

    return baseplateBody

def createSocketCellGrid(
    input: BaseplateGeneratorInput,
    socketBody: adsk.fusion.BRepBody,
    gridTop: float,
    gridHeight: float,
    targetComponent: adsk.fusion.Component,
    timer: commonUtils.StepTimer,
) -> adsk.fusion.BRepBody:
    """
    The grid area cut by every socket, from one cell cut by the seed socket, patterned and joined.
    A cell only needs its own socket: sockets are symmetric around their cell center and convex in every
    horizontal section, so whatever a neighbouring socket reaches into a cell lies within the cell's own socket.
    """
    cellBody = shapeUtils.simpleBox(
        targetComponent.xYConstructionPlane,
        gridTop,
        input.baseWidth,
        input.baseLength,
        -(gridHeight + gridTop),
        adsk.core.Point3D.create(-input.xyClearance, -input.xyClearance, 0),
        targetComponent,
    )
    cellBody.name = "Socket cell"
    combineUtils.cutBody(
        cellBody,
        commonUtils.objectCollectionFromList([socketBody]),
        targetComponent,
    ).name = "Socket cell cut"
    timer.step('socket cell')

    if input.baseplateWidth * input.baseplateLength > 1:
        cellCopies = patternUtils.recPatternGrid(
            commonUtils.objectCollectionFromList([cellBody]),
            (input.baseplateWidth, input.baseplateLength),
            (input.baseWidth, input.baseLength),
            targetComponent,
        )
        cellCopies.name = "Socket cell grid"
        # pattern bodies include the source body, which a combine rejects as its own tool
        copyBodies = [body for body in cellCopies.bodies if body != cellBody]
        timer.step(f'socket cell grid ({len(copyBodies)} copies)')
        combineUtils.joinBodies(
            cellBody,
            commonUtils.objectCollectionFromList(copyBodies),
            targetComponent,
        ).name = "Join socket cells"
        timer.step('join socket cells')
    return cellBody

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