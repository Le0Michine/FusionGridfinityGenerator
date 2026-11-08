import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, commonUtils, filletUtils, combineUtils, faceUtils, extrudeUtils, sketchUtils, baseGenerator, patternUtils, shapeUtils, geometryUtils, edgeUtils, baseplateLayout
from .baseGeneratorInput import BaseGeneratorInput
from .baseplateGeneratorInput import BaseplateGeneratorInput
from .dim import Dim, applyTo, valueInput

def createGridfinityBaseplate(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component) -> adsk.fusion.BRepBody:
    return createBaseplateBodies(input, None, targetComponent)[0]

def createGridfinityBaseplatePieces(
    input: BaseplateGeneratorInput,
    pieces: list[tuple[int, int, int, int]],
    targetComponent: adsk.fusion.Component,
) -> list[adsk.fusion.BRepBody]:
    """The plate built once and cut into pieces, given as (first column, columns, first row, rows) of whole cells.
    Bodies come in the order of the pieces"""
    return createBaseplateBodies(input, pieces, targetComponent)

def createBaseplateBodies(
    input: BaseplateGeneratorInput,
    pieces: list[tuple[int, int, int, int]] | None,
    targetComponent: adsk.fusion.Component,
) -> list[adsk.fusion.BRepBody]:
    """
    The whole plate, cut into the given pieces in place, or a single piece. Pieces end the xy clearance short of the cell
    border on the seams, the same as a plate's outer edge. Connection holes go along the seams too.
    """
    timer = commonUtils.StepTimer('Baseplate {}x{}'.format(int(input.baseplateWidth), int(input.baseplateLength)))
    features = targetComponent.features
    clearance = Dim.length(input.xyClearance)
    cutoutInput = BaseGeneratorInput()
    cutoutInput.xyClearance = input.xyClearance
    cutoutInput.originPoint = geometryUtils.createOffsetPoint(
        targetComponent.originConstructionPoint.geometry,
        byX=-cutoutInput.xyClearance * 2,
        byY=-cutoutInput.xyClearance * 2,
    )
    cutoutInput.baseWidth = input.baseWidth + Dim.length(cutoutInput.xyClearance * 2)
    cutoutInput.baseLength = input.baseLength + Dim.length(cutoutInput.xyClearance * 2)
    cutoutInput.cornerFilletRadius = input.cornerFilletRadius + cutoutInput.xyClearance
    baseBody = baseGenerator.createSingleGridfinityBaseBody(cutoutInput, targetComponent, name='Socket')

    cuttingTools: list[adsk.fusion.BRepBody] = []
    extraCutoutBodies: list[adsk.fusion.BRepBody] = []

    holeCenterPoint = adsk.core.Point3D.create(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        0
    )

    connectionHoleYTool = None
    connectionHoleXTool = None
    # cell borders between pieces
    seamColumns = sorted({firstColumn for (firstColumn, _, _, _) in pieces or [] if firstColumn > 0})
    seamRows = sorted({firstRow for (_, _, firstRow, _) in pieces or [] if firstRow > 0})

    if input.hasSkeletonizedBottom:
        centerCutoutSketch,centerCutoutSketchCircle = baseGenerator.createCircleAtPointSketch(
            faceUtils.getBottomFace(baseBody),
            input.magnetCutoutsDiameter / 2,
            holeCenterPoint,
            targetComponent,
            name='Skeleton cutout sketch',
        )
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

        # the cutout corner sits at the cell center, measured from the screw hole center which stays put.
        # Face sketch axes can be flipped but stay aligned with the model axes
        cellCenterOffsetX = input.baseWidth / 2 - Dim.length(const.DIMENSION_SCREW_HOLES_OFFSET)
        cellCenterOffsetY = input.baseLength / 2 - Dim.length(const.DIMENSION_SCREW_HOLES_OFFSET)
        if abs(centerCutoutSketch.xDirection.x) < 0.5:
            (cellCenterOffsetX, cellCenterOffsetY) = (cellCenterOffsetY, cellCenterOffsetX)
        holeCenter = screwHoleCircle.centerSketchPoint.geometry
        baseCenterOffsetX = cellCenterOffsetX.value - holeCenter.x
        baseCenterOffsetY = cellCenterOffsetY.value + holeCenter.y
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
        constraints.addTangent(arc, line6)
        dimensions.addRadialDimension(arc, arc.endSketchPoint.geometry, True)
        applyTo(dimensions.addDistanceDimension(
            screwHoleCircle.centerSketchPoint,
            line3.endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            line2.endSketchPoint.geometry
            ).parameter, cellCenterOffsetX)
        applyTo(dimensions.addDistanceDimension(
            screwHoleCircle.centerSketchPoint,
            line3.endSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            line4.endSketchPoint.geometry
            ).parameter, cellCenterOffsetY)

        centerCutoutExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
            centerCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.bottomExtensionHeight,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [],
            targetComponent,
            name='Skeleton cutout',
        )
        centerCutoutBody = centerCutoutExtrudeFeature.bodies.item(0)

        # mirroring instead of a circular pattern keeps the cutouts in the cell corners of non square bases
        cellXZMidPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        cellXZMidPlaneInput.setByOffset(targetComponent.xZConstructionPlane, valueInput(input.baseLength / 2 - clearance))
        cellXZMidPlane = targetComponent.constructionPlanes.add(cellXZMidPlaneInput)
        cellXZMidPlane.name = 'Skeleton cutout XZ mid plane'
        cellXZMidPlane.isLightBulbOn = False
        cellYZMidPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        cellYZMidPlaneInput.setByOffset(targetComponent.yZConstructionPlane, valueInput(input.baseWidth / 2 - clearance))
        cellYZMidPlane = targetComponent.constructionPlanes.add(cellYZMidPlaneInput)
        cellYZMidPlane.name = 'Skeleton cutout YZ mid plane'
        cellYZMidPlane.isLightBulbOn = False
        mirrorXInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList([centerCutoutBody]), cellYZMidPlane)
        mirrorXFeature = features.mirrorFeatures.add(mirrorXInput)
        mirrorXFeature.name = 'Skeleton cutouts mirror X'
        halfCutoutBodies = commonUtils.objectCollectionFromList([centerCutoutBody], mirrorXFeature.bodies)
        mirrorYInput = features.mirrorFeatures.createInput(halfCutoutBodies, cellXZMidPlane)
        mirrorYFeature = features.mirrorFeatures.add(mirrorYInput)
        mirrorYFeature.name = 'Skeleton cutouts mirror Y'
        # mirror results can include their sources, which a combine rejects as its own tool
        combineUtils.joinBodies(
            centerCutoutBody,
            commonUtils.objectCollectionFromList([body for body in list(halfCutoutBodies) + list(mirrorYFeature.bodies) if body != centerCutoutBody]),
            targetComponent,
            name='Skeleton cutouts join',
        )
        extraCutoutBodies.append(centerCutoutBody)
        if input.hasConnectionHoles:
            connectionHoleFaceY = min([face for face in centerCutoutBody.faces if faceUtils.isYNormal(face)], key=lambda x: x.boundingBox.minPoint.y)
            connectionHoleYTool = createConnectionHoleTool(connectionHoleFaceY, input.connectionScrewHolesDiameter / 2, input.baseLength / 2, targetComponent, name='Connection hole Y')
            connectionHoleFaceX = min([face for face in centerCutoutBody.faces if faceUtils.isXNormal(face)], key=lambda x: x.boundingBox.minPoint.x)
            connectionHoleXTool = createConnectionHoleTool(connectionHoleFaceX, input.connectionScrewHolesDiameter / 2, input.baseWidth / 2, targetComponent, name='Connection hole X')

    holeCuttingBodies: list[adsk.fusion.BRepBody] = []
    
    if input.hasExtendedBottom and input.hasMagnetCutouts:
        magnetSocketBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(baseBody),
            0,
            input.magnetCutoutsDepth,
            input.magnetCutoutsDiameter / 2,
            holeCenterPoint,
            targetComponent,
            name='Plate magnet socket',
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
            name='Plate screw hole',
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
            name='Plate screw head',
        )
        filletUtils.createChamfer(
            commonUtils.objectCollectionFromList(faceUtils.getTopFace(screwHeadBody).edges),
            (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2,
            targetComponent,
            name='Plate screw head chamfer',
        )
        holeCuttingBodies.append(screwHeadBody)

    if len(holeCuttingBodies) > 0:
        patternSpacingX = input.baseWidth - Dim.length(const.DIMENSION_SCREW_HOLES_OFFSET * 2)
        patternSpacingY = input.baseLength - Dim.length(const.DIMENSION_SCREW_HOLES_OFFSET * 2)
        magnetScrewCutoutsPattern = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(holeCuttingBodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (patternSpacingX, patternSpacingY),
            (2, 2),
            targetComponent,
            name='Plate holes pattern',
        )
        extraCutoutBodies = extraCutoutBodies + holeCuttingBodies + list(magnetScrewCutoutsPattern.bodies)

    if len(extraCutoutBodies) > 0:
        combineUtils.joinBodies(
            baseBody,
            commonUtils.objectCollectionFromList(extraCutoutBodies),
            targetComponent,
            name='Socket bottom cutouts join',
        )

    timer.step('seed socket')

    baseplateTrueWidth = input.baseWidth * input.baseplateWidth - Dim.length(input.xyClearance * 2)
    baseplateTrueLength = input.baseLength * input.baseplateLength - Dim.length(input.xyClearance * 2)

    if not connectionHoleYTool is None and not connectionHoleXTool is None:
        holeToolsXFeature = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(connectionHoleXTool.bodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (input.baseWidth, input.baseLength),
            (1, input.baseplateLength),
            targetComponent,
            name='Connection holes X pattern',
        )
        connectionHoleXToolList = list(connectionHoleXTool.bodies) + list(holeToolsXFeature.bodies)

        holeToolsYFeature = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(connectionHoleYTool.bodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (input.baseWidth, input.baseLength),
            (input.baseplateWidth, 1),
            targetComponent,
            name='Connection holes Y pattern',
        )
        connectionHoleYToolList = list(connectionHoleYTool.bodies) + list(holeToolsYFeature.bodies)

        # a tool at a cell border reaches into the cells on both sides, so one per seam holes both pieces
        for (seams, tools, isAlongX, axisName) in [
            (seamColumns, connectionHoleXToolList, True, 'X'),
            (seamRows, connectionHoleYToolList, False, 'Y'),
        ]:
            for seam in seams:
                seamPattern = patternUtils.recPattern(
                    commonUtils.objectCollectionFromList(tools),
                    (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
                    (input.baseWidth * seam, input.baseLength) if isAlongX else (input.baseWidth, input.baseLength * seam),
                    (2, 1) if isAlongX else (1, 2),
                    targetComponent,
                    name=f'Connection holes seam {axisName}{seam} pattern',
                )
                cuttingTools.extend(body for body in seamPattern.bodies if body not in tools)

        constructionPlaneXZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneXZInput.setByOffset(targetComponent.xZConstructionPlane, valueInput(input.baseLength * input.baseplateLength / 2 - clearance))
        constructionPlaneXZ = targetComponent.constructionPlanes.add(constructionPlaneXZInput)
        constructionPlaneXZ.name = 'Plate XZ mid plane'
        constructionPlaneXZ.isLightBulbOn = False

        constructionPlaneYZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneYZInput.setByOffset(targetComponent.yZConstructionPlane, valueInput(input.baseWidth * input.baseplateWidth / 2 - clearance))
        constructionPlaneYZ = targetComponent.constructionPlanes.add(constructionPlaneYZInput)
        constructionPlaneYZ.name = 'Plate YZ mid plane'
        constructionPlaneYZ.isLightBulbOn = False

        mirrorConnectionHolesYZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleXToolList), constructionPlaneYZ)
        mirrorConnectionHolesYZ = features.mirrorFeatures.add(mirrorConnectionHolesYZInput)
        mirrorConnectionHolesYZ.name = 'Connection holes X mirror'

        mirrorConnectionHolesXZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleYToolList), constructionPlaneXZ)
        mirrorConnectionHolesXZ = features.mirrorFeatures.add(mirrorConnectionHolesXZInput)
        mirrorConnectionHolesXZ.name = 'Connection holes Y mirror'

        # mirror and pattern results can include their sources
        connectionHoleRightToolList = [body for body in mirrorConnectionHolesYZ.bodies if body not in connectionHoleXToolList]
        connectionHoleTopToolList = [body for body in mirrorConnectionHolesXZ.bodies if body not in connectionHoleYToolList]
        # holes on a side with half cells would end up inside the plate, between the half cells and the whole ones
        unusedConnectionHoleTools: list[adsk.fusion.BRepBody] = []
        for (hasHalfCells, tools) in [
            (input.hasHalfCellsLeft, connectionHoleXToolList),
            (input.hasHalfCellsRight, connectionHoleRightToolList),
            (input.hasHalfCellsBottom, connectionHoleYToolList),
            (input.hasHalfCellsTop, connectionHoleTopToolList),
        ]:
            sideTools = unusedConnectionHoleTools if hasHalfCells else cuttingTools
            sideTools.extend(body for body in tools if body not in sideTools)
        for body in unusedConnectionHoleTools:
            removeFeature = features.removeFeatures.add(body)
            removeFeature.name = 'Unused connection hole remove'
    timer.step('connection holes')

    # the plate is built from socket cells each cut once by the seed socket, then patterned and joined,
    # instead of cutting a plate body with a socket body per cell
    gridHeight = const.BIN_BASE_HEIGHT + (input.bottomExtensionHeight if input.hasExtendedBottom else 0)
    # cells start below the top clearance, the same as cutting it from the whole plate
    gridTop = -max(0, input.binZClearance)
    noPadding = Dim.length(0)
    paddingLeft = input.paddingLeft if input.hasPadding else noPadding
    paddingTop = input.paddingTop if input.hasPadding else noPadding
    paddingRight = input.paddingRight if input.hasPadding else noPadding
    paddingBottom = input.paddingBottom if input.hasPadding else noPadding
    baseplateBody = createSocketCellGrid(input, baseBody, gridTop, gridHeight, targetComponent, timer)
    halfCellBodies = createHalfCellStrips(input, gridTop, gridHeight, targetComponent)
    if len(halfCellBodies) > 0:
        combineUtils.joinBodies(
            baseplateBody,
            commonUtils.objectCollectionFromList(halfCellBodies),
            targetComponent,
            name='Half cells join',
        )
        timer.step(f'half cells ({len(halfCellBodies)} cells)')
    noHalfCells = Dim.length(0)
    halfCellsLeft = input.baseWidth / 2 if input.hasHalfCellsLeft else noHalfCells
    halfCellsRight = input.baseWidth / 2 if input.hasHalfCellsRight else noHalfCells
    halfCellsBottom = input.baseLength / 2 if input.hasHalfCellsBottom else noHalfCells
    halfCellsTop = input.baseLength / 2 if input.hasHalfCellsTop else noHalfCells

    # padding past the cells. Sockets overhang their cells by the xy clearance, but only within the top
    # xy clearance depth, which the top clearance removes anyway unless it is set smaller
    cellsMinX = clearance * -1 - halfCellsLeft
    cellsMaxX = input.baseWidth * input.baseplateWidth - clearance + halfCellsRight
    cellsMinY = clearance * -1 - halfCellsBottom
    cellsMaxY = input.baseLength * input.baseplateLength - clearance + halfCellsTop
    outlineMinX = (paddingLeft + halfCellsLeft) * -1
    outlineMaxX = baseplateTrueWidth + halfCellsRight + paddingRight
    outlineMinY = (paddingBottom + halfCellsBottom) * -1
    outlineMaxY = baseplateTrueLength + halfCellsTop + paddingTop
    paddingStrips = [
        ("Padding left", outlineMinX, outlineMinY, cellsMinX, outlineMaxY),
        ("Padding right", cellsMaxX, outlineMinY, outlineMaxX, outlineMaxY),
        ("Padding bottom", cellsMinX, outlineMinY, cellsMaxX, cellsMinY),
        ("Padding top", cellsMinX, cellsMaxY, cellsMaxX, outlineMaxY),
    ]
    paddingBodies: list[adsk.fusion.BRepBody] = []
    for (name, minX, minY, maxX, maxY) in paddingStrips:
        if (maxX - minX).value > const.DEFAULT_FILTER_TOLERANCE and (maxY - minY).value > const.DEFAULT_FILTER_TOLERANCE:
            paddingBody = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                gridTop,
                maxX - minX,
                maxY - minY,
                -(gridHeight + gridTop),
                adsk.core.Point3D.create(minX.value, minY.value, 0),
                targetComponent,
                minX,
                minY,
                name=name,
            )
            paddingBodies.append(paddingBody)
    if len(paddingBodies) > 0:
        combineUtils.joinBodies(
            baseplateBody,
            commonUtils.objectCollectionFromList(paddingBodies),
            targetComponent,
            name='Padding join',
        )
        timer.step(f'padding ({len(paddingBodies)} strips)')

    # holes go in before the plate is cut into pieces, a combine cuts one body only
    if len(cuttingTools) > 0:
        combineUtils.cutBody(
            baseplateBody,
            commonUtils.objectCollectionFromList(cuttingTools),
            targetComponent,
            name='Connection holes cut',
        )
        timer.step('connection holes cut')

    # trims cells overhanging the plate edge and rounds the corners, of every piece at once
    def axisRange(first: int, count: int, total: int, baseUnit: Dim, outlineMin: Dim, outlineMax: Dim) -> tuple[Dim, Dim]:
        low = outlineMin if first == 0 else baseUnit * first
        high = outlineMax if first + count == total else baseUnit * (first + count) - clearance * 2
        return (low, high)
    pieceOutlines: list[tuple[Dim, Dim, Dim, Dim]] = []
    for (firstColumn, columns, firstRow, rows) in pieces or [(0, input.baseplateWidth, 0, input.baseplateLength)]:
        (minX, maxX) = axisRange(firstColumn, columns, input.baseplateWidth, input.baseWidth, outlineMinX, outlineMaxX)
        (minY, maxY) = axisRange(firstRow, rows, input.baseplateLength, input.baseLength, outlineMinY, outlineMaxY)
        pieceOutlines.append((minX, minY, maxX, maxY))
    trimFeature = baseGenerator.cutOutsideRoundedRectangles(
        pieceOutlines,
        input.cornerFilletRadius - input.xyClearance,
        [baseplateBody],
        targetComponent,
        name='Plate outline trim' if pieces is None else 'Plate pieces cut',
    )
    timer.step('trim to outline' if pieces is None else f'cut into {len(pieceOutlines)} pieces')

    # the cut can leave the bodies in any order, each piece is the one around its outline center.
    # The plate body itself stays one of them
    trimmedBodies = [baseplateBody] + [body for body in trimFeature.bodies if body != baseplateBody]
    plateBodies: list[adsk.fusion.BRepBody] = []
    for (minX, minY, maxX, maxY) in pieceOutlines:
        (centerX, centerY) = ((minX.value + maxX.value) / 2, (minY.value + maxY.value) / 2)
        matches = [
            body for body in trimmedBodies
            if body.boundingBox.minPoint.x < centerX < body.boundingBox.maxPoint.x and body.boundingBox.minPoint.y < centerY < body.boundingBox.maxPoint.y
        ]
        if len(matches) != 1:
            raise Exception(f'Expected one plate body around ({centerX:.2f}, {centerY:.2f}), found {len(matches)}')
        plateBodies.append(matches[0])

    def outlineChamferEdges(body: adsk.fusion.BRepBody) -> list[adsk.fusion.BRepEdge]:
        bodyBox = body.boundingBox
        def isOnOutline(edge: adsk.fusion.BRepEdge):
            edgeBox = edge.boundingBox
            return any(math.isclose(edgeValue, bodyValue, abs_tol=const.DEFAULT_FILTER_TOLERANCE) for (edgeValue, bodyValue) in [
                (edgeBox.minPoint.x, bodyBox.minPoint.x),
                (edgeBox.maxPoint.x, bodyBox.maxPoint.x),
                (edgeBox.minPoint.y, bodyBox.minPoint.y),
                (edgeBox.maxPoint.y, bodyBox.maxPoint.y),
            ])
        # the bottom face also has socket edges now, only chamfer the outline edges picked by length as before
        return [
            edge for edge in edgeUtils.selectEdgesByLength(
                [faceUtils.getBottomFace(body)],
                bodyBox.maxPoint.y - bodyBox.minPoint.y,
                const.BIN_CORNER_FILLET_RADIUS * 3,
            )
            if isOnOutline(edge)
        ]
    bottomChamferEdges = [edge for body in plateBodies for edge in outlineChamferEdges(body)]
    if len(bottomChamferEdges) > 0:
        filletUtils.createChamfer(
            commonUtils.objectCollectionFromList(bottomChamferEdges),
            0.05,
            targetComponent,
            name='Plate bottom chamfer',
        )
    timer.step('bottom chamfer')
    timer.total()

    return plateBodies

def createGridfinityBaseplateFill(
    input: BaseplateGeneratorInput,
    layout: baseplateLayout.FillLayout,
    targetComponent: adsk.fusion.Component,
    pieceGap: float = 0,
) -> list[tuple[baseplateLayout.FillPiece, adsk.fusion.BRepBody]]:
    """
    Baseplate pieces of a fill layout, built once as a plate of the whole grid with the input padding and half cells
    on its outer sides, then cut into the pieces in place. Each piece is cut the xy clearance short of the cell border
    on the seams, like a plate's outer edge.
    The piece gap spreads the pieces further apart, e.g. to tell them apart in the preview.
    """
    input.baseplateWidth = layout.x.cells
    input.baseplateLength = layout.y.cells
    input.hasPadding = True
    bodies = createGridfinityBaseplatePieces(
        input,
        [(piece.cellOffsetX, piece.cellsX, piece.cellOffsetY, piece.cellsY) for piece in layout.pieces],
        targetComponent,
    )
    if pieceGap > 0:
        for (piece, body) in zip(layout.pieces, bodies):
            if piece.column > 0 or piece.row > 0:
                moveBodiesBy(
                    [body],
                    Dim.length(pieceGap * piece.column),
                    Dim.length(pieceGap * piece.row),
                    targetComponent,
                    name=f'Piece {piece.column + 1}-{piece.row + 1} spread',
                )
    return list(zip(layout.pieces, bodies))

def moveBodiesBy(
    bodies: list[adsk.fusion.BRepBody],
    offsetX: Dim,
    offsetY: Dim,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> adsk.fusion.MoveFeature:
    moveFeatures = targetComponent.features.moveFeatures
    moveInput = moveFeatures.createInput2(commonUtils.objectCollectionFromList(bodies))
    moveInput.defineAsTranslateXYZ(
        valueInput(offsetX),
        valueInput(offsetY),
        adsk.core.ValueInput.createByReal(0),
        True,
    )
    moveFeature = moveFeatures.add(moveInput)
    moveFeature.name = name
    return moveFeature

def createHalfCellStrips(
    input: BaseplateGeneratorInput,
    gridTop: float,
    gridHeight: float,
    targetComponent: adsk.fusion.Component,
) -> list[adsk.fusion.BRepBody]:
    """
    Rows of half cells along the sides asked for. Cells are only halved across the row, so they line up with
    the whole cells and take bins half a unit wide as well as half size ones, only the corners are halved both ways.
    Half cells have no magnet or screw holes, there is no room for them in the standard spots.
    """
    halfWidth = input.baseWidth / 2
    halfLength = input.baseLength / 2
    noOffset = Dim.length(0)
    columnCell = (halfWidth, input.baseLength)
    rowCell = (input.baseWidth, halfLength)
    cornerCell = (halfWidth, halfLength)
    leftX = halfWidth * -1
    rightX = input.baseWidth * input.baseplateWidth
    bottomY = halfLength * -1
    topY = input.baseLength * input.baseplateLength
    strips = [
        (name, cellSize, originX, originY, countX, countY)
        for (hasHalfCells, name, cellSize, originX, originY, countX, countY) in [
            (input.hasHalfCellsLeft, 'Half cells left', columnCell, leftX, noOffset, 1, input.baseplateLength),
            (input.hasHalfCellsRight, 'Half cells right', columnCell, rightX, noOffset, 1, input.baseplateLength),
            (input.hasHalfCellsBottom, 'Half cells bottom', rowCell, noOffset, bottomY, input.baseplateWidth, 1),
            (input.hasHalfCellsTop, 'Half cells top', rowCell, noOffset, topY, input.baseplateWidth, 1),
            (input.hasHalfCellsLeft and input.hasHalfCellsBottom, 'Half cell bottom left', cornerCell, leftX, bottomY, 1, 1),
            (input.hasHalfCellsRight and input.hasHalfCellsBottom, 'Half cell bottom right', cornerCell, rightX, bottomY, 1, 1),
            (input.hasHalfCellsLeft and input.hasHalfCellsTop, 'Half cell top left', cornerCell, leftX, topY, 1, 1),
            (input.hasHalfCellsRight and input.hasHalfCellsTop, 'Half cell top right', cornerCell, rightX, topY, 1, 1),
        ]
        if hasHalfCells
    ]

    stripBodies: list[adsk.fusion.BRepBody] = []
    for (shapeName, cellSize) in [('Half width', columnCell), ('Half length', rowCell), ('Half corner', cornerCell)]:
        shapeStrips = [strip for strip in strips if strip[1] is cellSize]
        if len(shapeStrips) == 0:
            continue
        cellBody = createSocketCellSeed(input, cellSize[0], cellSize[1], gridTop, gridHeight, targetComponent, name=f'{shapeName} socket')
        for (index, (name, _, originX, originY, countX, countY)) in enumerate(shapeStrips):
            # copies are taken while the seed cell is still at the origin, the last strip moves the seed itself
            if index < len(shapeStrips) - 1:
                copyFeature = targetComponent.features.copyPasteBodies.add(cellBody)
                copyFeature.name = f'{name} cell copy'
                stripCell = copyFeature.bodies.item(0)
            else:
                stripCell = cellBody
            moveBodiesBy([stripCell], originX, originY, targetComponent, name=f'{name} placement')
            stripBodies.append(stripCell)
            if countX * countY > 1:
                stripPattern = patternUtils.recPatternGrid(
                    commonUtils.objectCollectionFromList([stripCell]),
                    (countX, countY),
                    cellSize,
                    targetComponent,
                    name=f'{name} pattern',
                )
                # pattern bodies include the source body, which a combine rejects as its own tool
                stripBodies.extend(body for body in stripPattern.bodies if body != stripCell)
    return stripBodies

def createSocketCellSeed(
    input: BaseplateGeneratorInput,
    cellWidth: Dim,
    cellLength: Dim,
    gridTop: float,
    gridHeight: float,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> adsk.fusion.BRepBody:
    """A plain socket cell of the given size at the origin, cell and socket named after the given name"""
    socketInput = BaseGeneratorInput()
    socketInput.xyClearance = input.xyClearance
    socketInput.originPoint = geometryUtils.createOffsetPoint(
        targetComponent.originConstructionPoint.geometry,
        byX=-input.xyClearance * 2,
        byY=-input.xyClearance * 2,
    )
    socketInput.baseWidth = cellWidth + Dim.length(input.xyClearance * 2)
    socketInput.baseLength = cellLength + Dim.length(input.xyClearance * 2)
    socketInput.cornerFilletRadius = input.cornerFilletRadius + input.xyClearance
    socketBody = baseGenerator.createSingleGridfinityBaseBody(socketInput, targetComponent, name=name)
    cellBody = shapeUtils.simpleBox(
        targetComponent.xYConstructionPlane,
        gridTop,
        cellWidth,
        cellLength,
        -(gridHeight + gridTop),
        adsk.core.Point3D.create(-input.xyClearance, -input.xyClearance, 0),
        targetComponent,
        name=f'{name} cell',
    )
    combineUtils.cutBody(
        cellBody,
        commonUtils.objectCollectionFromList([socketBody]),
        targetComponent,
        name=f'{name} cell cut',
    )
    return cellBody

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
        name='Socket cell',
    )
    combineUtils.cutBody(
        cellBody,
        commonUtils.objectCollectionFromList([socketBody]),
        targetComponent,
        name='Socket cell cut',
    )
    timer.step('socket cell')

    if input.baseplateWidth * input.baseplateLength > 1:
        cellCopies = patternUtils.recPatternGrid(
            commonUtils.objectCollectionFromList([cellBody]),
            (input.baseplateWidth, input.baseplateLength),
            (input.baseWidth, input.baseLength),
            targetComponent,
            name='Socket cell grid',
        )
        # pattern bodies include the source body, which a combine rejects as its own tool
        copyBodies = [body for body in cellCopies.bodies if body != cellBody]
        timer.step(f'socket cell grid ({len(copyBodies)} copies)')
        combineUtils.joinBodies(
            cellBody,
            commonUtils.objectCollectionFromList(copyBodies),
            targetComponent,
            name='Socket cells join',
        )
        timer.step('join socket cells')
    return cellBody

def createConnectionHoleTool(connectionHoleFace: adsk.fusion.BRepFace, diameter: float, depth: Dim | float, targetComponent: adsk.fusion.Component, *, name: str):
    connectionHoleSketch: adsk.fusion.Sketch = targetComponent.sketches.add(connectionHoleFace)
    connectionHoleSketch.name = f'{name} sketch'
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
        name=name,
    )
    return connectionHoleTool