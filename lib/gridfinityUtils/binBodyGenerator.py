import adsk.core, adsk.fusion, traceback
import os
import math
import copy

from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils, patternUtils
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


def patternWallCuts(cuts, input, spacingX, spacingY, targetComponent, toLastColumn: bool, toLastRow: bool, name: str, isAlongWall: bool = True):
    """Takes the wall cuts of the front left pattern seed to the outer wall they open, the back one along the last row
    and the sides along the first or last column, then along that wall unless they only open a corner"""
    if not cuts:
        return cuts
    features = targetComponent.features
    moveX = spacingX * (input.compartmentsByX - 1) if toLastColumn and input.compartmentsByX > 1 else None
    moveY = spacingY * (input.compartmentsByY - 1) if toLastRow and input.compartmentsByY > 1 else None
    if moveX is not None or moveY is not None:
        moveInput = features.moveFeatures.createInput2(commonUtils.objectCollectionFromList(cuts))
        moveInput.defineAsTranslateXYZ(
            valueInput(moveX if moveX is not None else Dim.length(0)),
            valueInput(moveY if moveY is not None else Dim.length(0)),
            adsk.core.ValueInput.createByReal(0),
            True,
        )
        moveFeature = features.moveFeatures.add(moveInput)
        moveFeature.name = f'{name} to the wall'
    # the back wall runs along x, the sides along y
    counts = (input.compartmentsByX, 1) if toLastRow else (1, input.compartmentsByY)
    if counts == (1, 1) or not isAlongWall:
        return cuts
    pattern = patternUtils.recPatternGrid(
        commonUtils.objectCollectionFromList(cuts),
        counts,
        (spacingX, spacingY),
        targetComponent,
        name=f'{name} pattern',
    )
    return cuts + [body for body in pattern.bodies if body not in cuts]

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
        lipBody = createGridfinityBinBodyLip(lipInput, targetComponent)

        if input.wallThickness < const.BIN_LIP_WALL_THICKNESS:
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
            # hollow tabs are opened through the outer walls of the bin they meet, the pattern seed gets cuts to move there
            tabOpenings = None
            if input.isTabHollow:
                tabOpenings = TabWallOpenings(
                    input.wallThickness * 2,
                    back=useCompartmentPattern or compartment.positionY + compartment.length >= input.compartmentsByY,
                    minXSide=input.isTabOpenThroughSides and (useCompartmentPattern or compartment.positionX == 0),
                    maxXSide=input.isTabOpenThroughSides and (useCompartmentPattern or compartment.positionX + compartment.width >= input.compartmentsByX),
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
                spacing = (compartmentWidthUnit + wall, compartmentLengthUnit + wall)
                compartmentHollowCuts = TabHollowCuts(
                    hollow=patternCompartmentBodies(compartmentHollowCuts.hollow, input, *spacing, targetComponent, 'Label tab hollows pattern'),
                    back=patternWallCuts(compartmentHollowCuts.back, input, *spacing, targetComponent, False, True, 'Label tab back openings'),
                    minXSide=patternWallCuts(compartmentHollowCuts.minXSide, input, *spacing, targetComponent, False, False, 'Label tab left openings'),
                    maxXSide=patternWallCuts(compartmentHollowCuts.maxXSide, input, *spacing, targetComponent, True, False, 'Label tab right openings'),
                    minXCorner=patternWallCuts(compartmentHollowCuts.minXCorner, input, *spacing, targetComponent, False, True, 'Label tab left corner opening', isAlongWall=False),
                    maxXCorner=patternWallCuts(compartmentHollowCuts.maxXCorner, input, *spacing, targetComponent, True, True, 'Label tab right corner opening', isAlongWall=False),
                )
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
