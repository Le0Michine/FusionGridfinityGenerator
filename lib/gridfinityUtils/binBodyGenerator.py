import adsk.core, adsk.fusion, traceback
import os
import math
import copy

from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils, patternUtils, binShape
from .binBodyCutoutGenerator import createGridfinityBinBodyCutout
from .binBodyCutoutGeneratorInput import BinBodyCutoutGeneratorInput
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyGeneratorInput import BinBodyGeneratorInput, BinBodyCompartmentDefinition
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from .binBodyTabGenerator import createGridfinityBinBodyTab, createTabHollowCuts, TabCavity, TabWallOpenings, TabHollowCuts
from .labelGenerator import BinLabelDefinition, BinLabelInput, createLabel, LABEL_STYLE_EMBOSSED, LABEL_STYLE_ENGRAVED
from .binBodyLipGeneratorInput import BinBodyLipGeneratorInput
from .binBodyLipGenerator import createGridfinityBinBodyLip
from .dim import Dim, valueInput
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def uniformCompartments(countX, countY):
    compartments: list[BinBodyCompartmentDefinition] = []
    for i in range(countX):
        for j in range(countY):
            compartments.append(BinBodyCompartmentDefinition(i, j, 1, 1))
    return compartments

def patternCompartments(entities, input, spacingX, spacingY, targetComponent, name, computeOption=None):
    pattern = patternUtils.recPatternGrid(
        commonUtils.objectCollectionFromList(entities),
        (input.compartmentsByX, input.compartmentsByY),
        (spacingX, spacingY),
        targetComponent,
        computeOption,
        name=name,
    )
    return pattern

def patternCompartmentBodies(bodies, input, spacingX, spacingY, targetComponent, name):
    if not bodies or input.compartmentsByX * input.compartmentsByY == 1:
        return bodies
    pattern = patternCompartments(bodies, input, spacingX, spacingY, targetComponent, name)
    return bodies + list(pattern.bodies)


def binBodyTopHeight(input: BinBodyGeneratorInput) -> Dim:
    """Height of the body top above the base top"""
    if input.heightUnit.value >= const.BIN_BASE_HEIGHT:
        # the first unit holds the base, only its part above the base height belongs to the body
        return input.binHeight * input.heightUnit - Dim.length(const.BIN_BASE_HEIGHT)
    return (input.binHeight - Dim.number(1)) * input.heightUnit

def createGridfinityBinBody(
    input: BinBodyGeneratorInput,
    targetComponent: adsk.fusion.Component,
) -> tuple[adsk.fusion.BRepBody, adsk.fusion.BRepBody]:

    bodyWidth = input.baseWidth * input.binWidth - Dim.length(input.xyClearance * 2)
    bodyLength = input.baseLength * input.binLength - Dim.length(input.xyClearance * 2)
    wall = Dim.length(input.wallThickness)
    # everything sitting on the bin top uses this dim, so it follows the height parameters
    binBodyTotalHeight = binBodyTopHeight(input)
    features: adsk.fusion.Features = targetComponent.features
    binBodyExtrude = extrudeUtils.createBox(
        bodyWidth,
        bodyLength,
        binBodyTotalHeight,
        targetComponent,
        targetComponent.xYConstructionPlane,
        name='Bin body',
    )
    binBody = binBodyExtrude.bodies.item(0)
    binBody.name = 'Bin body'

    bodiesToMerge: list[adsk.fusion.BRepBody] = []
    bodiesToSubtract: list[adsk.fusion.BRepBody] = []
    # hollow tabs are cut once joined, the walls behind them close the hollows
    tabHollowCuts: list[adsk.fusion.BRepBody] = []

    # round corners
    filletUtils.filletEdgesByLength(
        binBodyExtrude.faces,
        input.binCornerFilletRadius,
        binBodyTotalHeight.value,
        targetComponent,
        name='Bin body corner fillets',
    )

    if input.hasLip:
        lipOriginPoint = adsk.core.Point3D.create(0, 0, binBodyTotalHeight.value)
        lipInput = BinBodyLipGeneratorInput()
        lipInput.baseLength = input.baseLength
        lipInput.baseWidth = input.baseWidth
        lipInput.binLength = input.binLength
        lipInput.binWidth = input.binWidth
        lipInput.hasLipNotches = input.hasLipNotches
        lipInput.xyClearance = input.xyClearance
        lipInput.binCornerFilletRadius = input.binCornerFilletRadius
        lipInput.origin = lipOriginPoint
        lipInput.originZ = binBodyTotalHeight
        lipInput.shapeCells = input.shapeCells
        lipBody = createGridfinityBinBodyLip(lipInput, targetComponent)

        if input.wallThickness < const.BIN_LIP_WALL_THICKNESS and input.shapeCells is not None:
            # the inside of the walls widening at 45 degrees into the lip, so it doesn't overhang the cavity
            combineUtils.cutBody(
                lipBody,
                commonUtils.objectCollectionFromList([createShapeLipBottomChamfer(input, binBodyTotalHeight, targetComponent)]),
                targetComponent,
                name='Lip bottom chamfer cut',
            )
        elif input.wallThickness < const.BIN_LIP_WALL_THICKNESS:
            lipBottomChamferSize = max(const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, input.binCornerFilletRadius - input.wallThickness)
            lipBottomChamferExtrude = extrudeUtils.createBoxAtPoint(
                bodyWidth - wall * 2,
                (bodyLength - wall - Dim.length(const.BIN_LIP_WALL_THICKNESS - input.xyClearance)) if input.hasScoop else (bodyLength - wall * 2),
                lipBottomChamferSize,
                targetComponent,
                adsk.core.Point3D.create(
                    input.wallThickness,
                    (const.BIN_LIP_WALL_THICKNESS - input.xyClearance) if input.hasScoop else input.wallThickness,
                    lipOriginPoint.z,
                ),
                binBodyTotalHeight,
                name='Lip bottom chamfer box',
            )
            filletUtils.filletEdgesByLength(
                lipBottomChamferExtrude.faces,
                lipBottomChamferSize,
                lipBottomChamferSize,
                targetComponent,
                name='Lip bottom chamfer box fillets',
            )
            lipBottomChamferExtrudeTopFace = faceUtils.getTopFace(lipBottomChamferExtrude.bodies.item(0))
            scoopSideEdge = min([edge for edge in lipBottomChamferExtrudeTopFace.edges if geometryUtils.isCollinearToX(edge)], key=lambda x: x.boundingBox.minPoint.y)

            edgesToChamfer = list(scoopSideEdge.tangentiallyConnectedEdges)[3:] if input.hasScoop else scoopSideEdge.tangentiallyConnectedEdges
            chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
            bottomLipChamferInput = chamferFeatures.createInput2()
            bottomLipChamferEdges = commonUtils.objectCollectionFromList(edgesToChamfer)
            bottomLipChamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                bottomLipChamferEdges,
                adsk.core.ValueInput.createByReal(lipBottomChamferSize),
                False)
            chamferFeatures.add(bottomLipChamferInput).name = 'Lip bottom chamfer'
            combineUtils.cutBody(lipBody, commonUtils.objectCollectionFromList(lipBottomChamferExtrude.bodies), targetComponent, name='Lip bottom chamfer cut')

        bodiesToMerge.append(lipBody)

    if not input.isSolid:
        compartmentsMinX = wall
        compartmentsMaxX = bodyWidth - wall
        compartmentsMinY = Dim.length(const.BIN_LIP_WALL_THICKNESS - input.xyClearance) if input.hasLip and input.hasScoop else wall
        compartmentsMaxY = bodyLength - wall

        totalCompartmentsWidth = compartmentsMaxX - compartmentsMinX
        totalCompartmentsLength = compartmentsMaxY - compartmentsMinY

        compartmentWidthUnit = (totalCompartmentsWidth - wall * (input.compartmentsByX - 1)) / input.compartmentsByX
        compartmentLengthUnit = (totalCompartmentsLength - wall * (input.compartmentsByY - 1)) / input.compartmentsByY

        def compartmentPlacement(compartment: BinBodyCompartmentDefinition) -> tuple[Dim, Dim, Dim, Dim]:
            """X, y, width and length of the compartment cavity"""
            return (
                compartmentsMinX + (compartmentWidthUnit + wall) * compartment.positionX,
                compartmentsMinY + (compartmentLengthUnit + wall) * compartment.positionY,
                compartmentWidthUnit * compartment.width + wall * (compartment.width - 1),
                compartmentLengthUnit * compartment.length + wall * (compartment.length - 1),
            )

        def tabPlacement(compartmentX: Dim, compartmentY: Dim, compartmentLength: Dim) -> tuple[Dim, Dim, Dim]:
            """X and y of the tab's back top corner, along the compartment's back wall, and its length"""
            return (
                compartmentX + input.baseWidth * max(0, min(input.tabPosition, input.binWidth - input.tabLength)),
                compartmentY + compartmentLength,
                input.baseWidth * max(0, min(input.tabLength, input.binWidth)),
            )

        useCompartmentPattern = input.isUniformCompartments and len(input.compartments) > 1
        compartmentsToBuild = input.compartments[:1] if useCompartmentPattern else input.compartments
        for compartmentIndex, compartment in enumerate(compartmentsToBuild):
            compartmentName = 'Compartment' if len(compartmentsToBuild) == 1 else f'Compartment {compartmentIndex + 1}'
            (compartmentX, compartmentY, compartmentWidth, compartmentLength) = compartmentPlacement(compartment)
            # full depth compartments keep their floor thickness, shallower ones keep their depth from the top
            fullCompartmentDepth = binBodyTotalHeight - Dim.length(const.BIN_COMPARTMENT_BOTTOM_THICKNESS)
            compartmentDepth = fullCompartmentDepth if compartment.depth >= fullCompartmentDepth.value else compartment.depth

            compartmentTabInput = BinBodyTabGeneratorInput()
            (tabOriginX, tabOriginY, tabLength) = tabPlacement(compartmentX, compartmentY, compartmentLength)
            compartmentTabInput.origin = adsk.core.Point3D.create(tabOriginX.value, tabOriginY.value, binBodyTotalHeight.value)
            compartmentTabInput.originX = tabOriginX
            compartmentTabInput.originY = tabOriginY
            compartmentTabInput.originZ = binBodyTotalHeight
            compartmentTabInput.length = tabLength
            compartmentTabInput.width = input.tabWidth
            compartmentTabInput.overhangAngle = input.tabOverhangAngle
            compartmentTabInput.labelAngle = input.tabTopAngle
            compartmentTabInput.topClearance = tabTopClearance(input.labelStyle)
            # a hollow tab of a single compartment is opened through the outer walls of the bin, with more compartments
            # the hollows are left closed
            tabOpenings = None
            if input.isTabHollow and len(input.compartments) == 1:
                tabOpenings = TabWallOpenings(
                    input.wallThickness * 2,
                    back=True,
                    minXSide=input.isTabOpenThroughSides,
                    maxXSide=input.isTabOpenThroughSides,
                )

            [compartmentMerges, compartmentCuts, compartmentHollowCuts] = createCompartment(
                input.wallThickness,
                compartmentX,
                compartmentY,
                binBodyTotalHeight,
                compartmentWidth,
                compartmentLength,
                compartmentDepth,
                input.binCornerFilletRadius - input.wallThickness,
                input.hasScoop,
                input.scoopMaxRadius,
                input.hasTab,
                compartmentTabInput,
                hollowTabWallThickness(input.wallThickness, input.labelStyle) if input.isTabHollow else None,
                tabOpenings,
                targetComponent,
                name=compartmentName,
            )
            if useCompartmentPattern:
                # These cavities are identical and disjoint, so copy their cut faces instead
                # of creating every cutter body and asking Combine to intersect them all.
                # Optimized compute assumes every instance meets the same surrounding geometry;
                # revisit if uniform compartments ever stop being identical.
                # Patterning a cut feature requires design history, which entry.py enforces.
                seedCut = combineUtils.cutBody(
                    binBody, commonUtils.objectCollectionFromList(compartmentCuts), targetComponent, name='Compartment cut')
                patternCompartments(
                    [seedCut], input,
                    compartmentWidthUnit + wall,
                    compartmentLengthUnit + wall,
                    targetComponent, 'Compartment cuts pattern',
                    adsk.fusion.PatternComputeOptions.OptimizedPatternCompute,
                )
                compartmentCuts = []
                compartmentMerges = patternCompartmentBodies(
                    compartmentMerges, input,
                    compartmentWidthUnit + wall,
                    compartmentLengthUnit + wall,
                    targetComponent, 'Label tabs pattern',
                )
                compartmentHollowCuts = TabHollowCuts(hollow=patternCompartmentBodies(
                    compartmentHollowCuts.hollow, input,
                    compartmentWidthUnit + wall,
                    compartmentLengthUnit + wall,
                    targetComponent, 'Label tab hollows pattern',
                ))
            bodiesToSubtract.extend(compartmentCuts)
            tabHollowCuts.extend(compartmentHollowCuts.all())
            bodiesToMerge.extend(compartmentMerges)

        if len(input.compartments) > 1:
            compartmentsTopClearance = createCompartmentCutout(
                input.wallThickness,
                compartmentsMinX,
                compartmentsMinY,
                binBodyTotalHeight,
                bodyWidth - wall * 2,
                bodyLength - wall - compartmentsMinY,
                const.BIN_TAB_TOP_CLEARANCE,
                input.binCornerFilletRadius - input.wallThickness,
                False,
                0,
                False,
                targetComponent,
                name='Compartments top clearance',
            )
            bodiesToSubtract.append(compartmentsTopClearance)

    if len(bodiesToSubtract) > 0:
        combineUtils.cutBody(
            binBody,
            commonUtils.objectCollectionFromList(bodiesToSubtract),
            targetComponent,
            name='Bin body cutouts cut',
        )
    if len(bodiesToMerge) > 0:
        combineUtils.joinBodies(
            binBody,
            commonUtils.objectCollectionFromList(bodiesToMerge),
            targetComponent,
            name='Bin body lip and tabs join',
        )
    if len(tabHollowCuts) > 0:
        combineUtils.cutBody(
            binBody,
            commonUtils.objectCollectionFromList(tabHollowCuts),
            targetComponent,
            name='Label tab hollows cut',
        )

    if not input.isSolid and input.hasTab:
        # every compartment gets its own label, also where the tabs come from a pattern
        for compartmentIndex, compartment in enumerate(input.compartments):
            if compartment.label is None or compartment.label.isEmpty:
                continue
            (compartmentX, compartmentY, compartmentWidth, compartmentLength) = compartmentPlacement(compartment)
            (tabOriginX, tabOriginY, tabLength) = tabPlacement(compartmentX, compartmentY, compartmentLength)
            # tabs are trimmed to their compartment
            labelMinX = tabOriginX if tabOriginX.value >= compartmentX.value else compartmentX
            tabMaxX = tabOriginX + tabLength
            compartmentMaxX = compartmentX + compartmentWidth
            labelMaxX = tabMaxX if tabMaxX.value <= compartmentMaxX.value else compartmentMaxX
            createTabLabel(
                compartment.label,
                input.labelStyle,
                input.isLabelBold,
                labelMinX,
                labelMaxX,
                tabOriginY,
                input.tabWidth,
                binBodyTotalHeight,
                binBody,
                targetComponent,
                input.tabTopAngle,
                name='Label' if len(input.compartments) == 1 else f'Compartment {compartmentIndex + 1} label',
            )

    return binBody

def tabTopClearance(labelStyle: str) -> float:
    """Embossed labels stand on a tab lowered by their depth, so they keep the tab's clearance"""
    return const.BIN_TAB_TOP_CLEARANCE + (const.BIN_LABEL_DEPTH if labelStyle == LABEL_STYLE_EMBOSSED else 0)

def hollowTabWallThickness(wallThickness: float, labelStyle: str) -> float:
    """Hollow tabs take the wall thickness, thick enough for an engraved label not to cut through"""
    if labelStyle == LABEL_STYLE_ENGRAVED:
        return max(wallThickness, const.BIN_LABEL_DEPTH + const.BIN_TAB_HOLLOW_MIN_SKIN)
    return wallThickness

def createTabLabel(
        definition: BinLabelDefinition,
        style: str,
        isBold: bool,
        minX: Dim,
        maxX: Dim,
        tabOriginY: Dim,
        tabWidth: float,
        tabOriginZ: Dim,
        targetBody: adsk.fusion.BRepBody,
        targetComponent: adsk.fusion.Component,
        tabTopAngle: float = 0,
        *,
        name: str,
    ):
    """Label on the top face of a tab with its back top corner at the tab origin y and z, between the given x.
    On a tilted top the label is as long as the slope, so it still covers the tab width once turned down"""
    labelLength = tabWidth / math.cos(tabTopAngle)
    labelInput = BinLabelInput()
    labelInput.style = style
    labelInput.isBold = isBold
    labelInput.definition = definition
    labelInput.originX = minX
    labelInput.originY = tabOriginY - Dim.length(labelLength)
    labelInput.originZ = tabOriginZ - Dim.length(tabTopClearance(style))
    labelInput.width = (maxX - minX).value
    labelInput.length = labelLength
    labelInput.tiltAngle = tabTopAngle
    return createLabel(labelInput, targetBody, targetComponent, name=name)


def createShapeLipBottomChamfer(
    input: BinBodyGeneratorInput,
    topZ: Dim,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.BRepBody:
    """The inside of the walls of a shaped bin from the body top, narrowing at 45 degrees into the lip"""
    grid = baseGenerator.shapeGridInput(input.baseWidth, input.baseLength, input.xyClearance)
    offset = input.xyClearance + input.wallThickness
    # as tall as the plain bin's, its outer corners' radius, a hair less, the taper would close the corner arcs to a point
    height = compartmentCutoutFilletRadius(binShape.cornerRadius(True, grid.cornerFilletRadius, offset)) - 0.001
    planeInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(topZ))
    plane = targetComponent.constructionPlanes.add(planeInput)
    plane.name = 'Lip bottom chamfer plane'
    (sketch, _) = baseGenerator.createShapeOutlineSketch(
        input.shapeCells,
        grid,
        offset,
        plane,
        targetComponent,
        const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS,
        name='Lip bottom chamfer',
    )
    chamfer = extrudeUtils.taperedExtrude(
        sketch.profiles.item(0),
        height,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        targetComponent,
        name='Lip bottom chamfer',
    )
    return chamfer.bodies.item(0)

def createShapeCavity(
    cells: list[tuple[int, int]],
    baseConfiguration: BaseGeneratorInput,
    wallThickness: float,
    topZ: Dim,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> adsk.fusion.BRepBody:
    """
    Cavity of a shaped bin, the outline moved in by the clearance and the wall from the top down to the floor,
    rounded along the bottom like a plain bin's compartment. Its outer corners are concentric with the bin's,
    see baseGenerator.createShapeOutlineSketch
    """
    planeInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(topZ))
    plane = targetComponent.constructionPlanes.add(planeInput)
    plane.name = f'{name} plane'
    offset = baseConfiguration.xyClearance + wallThickness
    # a plain bin's compartment corners don't go below the bottom fillet either, see compartmentCutoutFilletRadius
    (sketch, _) = baseGenerator.createShapeOutlineSketch(
        cells,
        baseConfiguration,
        offset,
        plane,
        targetComponent,
        const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS,
        name=name,
    )
    cavityExtrude = extrudeUtils.simpleDistanceExtrude(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        topZ - Dim.length(const.BIN_COMPARTMENT_BOTTOM_THICKNESS),
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        [],
        targetComponent,
        name=name,
    )
    cavity = cavityExtrude.bodies.item(0)
    cavity.name = name
    # the same radius along the floor as up the outer corners, so they meet in a round corner like a plain bin's
    floorRadius = compartmentCutoutFilletRadius(binShape.cornerRadius(True, baseConfiguration.cornerFilletRadius, offset))
    filletUtils.createFillet(
        list(faceUtils.getBottomFace(cavity).edges),
        floorRadius,
        True,
        targetComponent,
        name=f'{name} bottom fillet',
    )
    return cavity

def compartmentCutoutFilletRadius(cornerFilletRadius: float) -> float:
    return max(const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, cornerFilletRadius)

def createCompartmentCutout(
        wallThickness: float,
        originX: Dim,
        originY: Dim,
        originZ: Dim,
        width: Dim,
        length: Dim,
        depth: Dim | float,
        cornerFilletRadius: float,
        hasScoop: bool,
        scoopMaxRadius: float,
        hasBottomFillet: bool,
        targetComponent: adsk.fusion.Component,
        *,
        name: str,
    ) -> adsk.fusion.BRepBody:

    innerCutoutFilletRadius = compartmentCutoutFilletRadius(cornerFilletRadius)
    innerCutoutInput = BinBodyCutoutGeneratorInput()
    innerCutoutInput.origin = adsk.core.Point3D.create(originX.value, originY.value, originZ.value)
    innerCutoutInput.originX = originX
    innerCutoutInput.originY = originY
    innerCutoutInput.originZ = originZ
    innerCutoutInput.width = width
    innerCutoutInput.length = length
    innerCutoutInput.height = depth
    innerCutoutInput.hasScoop = hasScoop
    innerCutoutInput.scoopMaxRadius = scoopMaxRadius
    innerCutoutInput.filletRadius = innerCutoutFilletRadius
    innerCutoutInput.hasBottomFillet = hasBottomFillet

    return createGridfinityBinBodyCutout(innerCutoutInput, targetComponent, name=name)

def createCompartment(
        wallThickness: float,
        originX: Dim,
        originY: Dim,
        originZ: Dim,
        width: Dim,
        length: Dim,
        depth: Dim | float,
        cornerFilletRadius: float,
        hasScoop: bool,
        scoopMaxRadius: float,
        hasTab: bool,
        tabInput: BinBodyTabGeneratorInput,
        tabHollowWallThickness: float | None,
        tabOpenings: TabWallOpenings | None,
        targetComponent: adsk.fusion.Component,
        *,
        name: str,
    ) -> tuple[list[adsk.fusion.BRepBody], list[adsk.fusion.BRepBody], TabHollowCuts]:
    """Bodies to join, bodies to cut, then with a hollow wall thickness, bodies hollowing out the tab once joined
    and opening it through the walls given"""

    bodiesToMerge: list[adsk.fusion.BRepBody] = []
    bodiesToSubtract: list[adsk.fusion.BRepBody] = []
    hollowCuts = TabHollowCuts()

    innerCutoutBody = createCompartmentCutout(
        wallThickness,
        originX,
        originY,
        originZ,
        width,
        length,
        depth,
        cornerFilletRadius,
        hasScoop,
        scoopMaxRadius,
        True,
        targetComponent,
        name=f'{name} cavity',
    )
    bodiesToSubtract.append(innerCutoutBody)

    # label tab
    if hasTab:
        tabBody = createGridfinityBinBodyTab(tabInput, targetComponent, name=f'{name} label tab')

        intersectTabInput = targetComponent.features.combineFeatures.createInput(
            tabBody,
            commonUtils.objectCollectionFromList([innerCutoutBody]),
            )
        intersectTabInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
        intersectTabInput.isKeepToolBodies = True
        intersectTabFeature = targetComponent.features.combineFeatures.add(intersectTabInput)
        intersectTabFeature.name = f'{name} label tab trim'
        tabBodies = [body for body in list(intersectTabFeature.bodies) if not body.revisionId == innerCutoutBody.revisionId]
        if tabHollowWallThickness is not None and len(tabBodies) > 0:
            # the tab is trimmed to the compartment
            tabMinX = tabInput.originX if tabInput.originX.value >= originX.value else originX
            tabMaxX = tabInput.originX + tabInput.length
            maxX = originX + width
            tabMaxX = tabMaxX if tabMaxX.value <= maxX.value else maxX
            hollowCuts = createTabHollowCuts(
                tabInput,
                tabMinX,
                tabMaxX,
                tabHollowWallThickness,
                innerCutoutBody,
                TabCavity(originX, maxX, originY + length, compartmentCutoutFilletRadius(cornerFilletRadius)),
                tabOpenings,
                targetComponent,
                name=f'{name} label tab',
            )
        bodiesToMerge = bodiesToMerge + tabBodies
    return (bodiesToMerge, bodiesToSubtract, hollowCuts)
