import adsk.core, adsk.fusion, traceback
import os
import math
import copy

from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils
from .binBodyCutoutGenerator import createGridfinityBinBodyCutout
from .binBodyCutoutGeneratorInput import BinBodyCutoutGeneratorInput
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyGeneratorInput import BinBodyGeneratorInput, BinBodyCompartmentDefinition
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from .binBodyTabGenerator import createGridfinityBinBodyTab
from .binBodyLipGeneratorInput import BinBodyLipGeneratorInput
from .binBodyLipGenerator import createGridfinityBinBodyLip
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def uniformCompartments(countX, countY):
    compartments: list[BinBodyCompartmentDefinition] = []
    for i in range(countX):
        for j in range(countY):
            compartments.append(BinBodyCompartmentDefinition(i, j, 1, 1))
    return compartments

def createGridfinityBinBody(
    input: BinBodyGeneratorInput,
    targetComponent: adsk.fusion.Component,
) -> tuple[adsk.fusion.BRepBody, adsk.fusion.BRepBody]:

    actualBodyWidth = (input.baseWidth * input.binWidth) - input.xyClearance * 2.0
    actualBodyLength = (input.baseLength * input.binLength) - input.xyClearance * 2.0
    binHeightWithoutBase = input.binHeight - 1
    binBodyTotalHeight = binHeightWithoutBase * input.heightUnit + max(0, input.heightUnit - const.BIN_BASE_HEIGHT)
    features: adsk.fusion.Features = targetComponent.features
    binBodyExtrude = extrudeUtils.createBox(
        actualBodyWidth,
        actualBodyLength,
        binBodyTotalHeight,
        targetComponent,
        targetComponent.xYConstructionPlane
    )
    binBody = binBodyExtrude.bodies.item(0)
    binBody.name = 'Bin body'

    bodiesToMerge: list[adsk.fusion.BRepBody] = []
    bodiesToSubtract: list[adsk.fusion.BRepBody] = []

    # round corners
    filletUtils.filletEdgesByLength(
        binBodyExtrude.faces,
        input.binCornerFilletRadius,
        binBodyTotalHeight,
        targetComponent,
    ).name = 'Bin body corner fillets'

    if input.hasLip:
        lipOriginPoint = adsk.core.Point3D.create(
            0,
            0,
            binHeightWithoutBase * input.heightUnit + max(0, input.heightUnit - const.BIN_BASE_HEIGHT)
        )
        lipInput = BinBodyLipGeneratorInput()
        lipInput.baseLength = input.baseLength
        lipInput.baseWidth = input.baseWidth
        lipInput.binLength = input.binLength
        lipInput.binWidth = input.binWidth
        lipInput.hasLipNotches = input.hasLipNotches
        lipInput.xyClearance = input.xyClearance
        lipInput.binCornerFilletRadius = input.binCornerFilletRadius
        lipInput.origin = lipOriginPoint
        lipBody = createGridfinityBinBodyLip(lipInput, targetComponent)

        if input.wallThickness < const.BIN_LIP_WALL_THICKNESS:
            lipBottomChamferSize = max(const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, input.binCornerFilletRadius - input.wallThickness)
            lipBottomChamferExtrude = extrudeUtils.createBoxAtPoint(
                actualBodyWidth - input.wallThickness * 2,
                (actualBodyLength - input.wallThickness - const.BIN_LIP_WALL_THICKNESS + input.xyClearance) if input.hasScoop else (actualBodyLength - input.wallThickness * 2),
                lipBottomChamferSize,
                targetComponent,
                adsk.core.Point3D.create(
                    input.wallThickness,
                    (const.BIN_LIP_WALL_THICKNESS - input.xyClearance) if input.hasScoop else input.wallThickness,
                    lipOriginPoint.z,
                )
            )
            lipBottomChamferExtrude.name = 'Lip bottom chamfer extrude'
            filletUtils.filletEdgesByLength(
                lipBottomChamferExtrude.faces,
                lipBottomChamferSize,
                lipBottomChamferSize,
                targetComponent,
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
            chamferFeatures.add(bottomLipChamferInput)
            combineUtils.cutBody(lipBody, commonUtils.objectCollectionFromList(lipBottomChamferExtrude.bodies), targetComponent)

        bodiesToMerge.append(lipBody)

    if not input.isSolid:
        compartmentsMinX = input.wallThickness
        compartmentsMaxX = actualBodyWidth - input.wallThickness
        compartmentsMinY = (const.BIN_LIP_WALL_THICKNESS - input.xyClearance) if input.hasLip and input.hasScoop else input.wallThickness
        compartmentsMaxY = actualBodyLength - input.wallThickness

        totalCompartmentsWidth = compartmentsMaxX - compartmentsMinX
        totalCompartmentsLength = compartmentsMaxY - compartmentsMinY
        
        compartmentWidthUnit = (totalCompartmentsWidth - (input.compartmentsByX - 1) * input.wallThickness) / input.compartmentsByX
        compartmentLengthUnit = (totalCompartmentsLength - (input.compartmentsByY - 1) * input.wallThickness) / input.compartmentsByY

        for compartment in input.compartments:
            compartmentX = compartmentsMinX + compartment.positionX * (compartmentWidthUnit + input.wallThickness)
            compartmentY = compartmentsMinY + compartment.positionY * (compartmentLengthUnit + input.wallThickness)
            compartmentOriginPoint = adsk.core.Point3D.create(
                compartmentX,
                compartmentY,
                binBodyTotalHeight
            )
            compartmentWidth = compartmentWidthUnit * compartment.width + (compartment.width - 1) * input.wallThickness
            compartmentLength = compartmentLengthUnit * compartment.length + (compartment.length - 1) * input.wallThickness
            compartmentDepth = min(binBodyTotalHeight - const.BIN_COMPARTMENT_BOTTOM_THICKNESS, compartment.depth)

            compartmentTabInput = BinBodyTabGeneratorInput()
            tabOriginPoint = adsk.core.Point3D.create(
                compartmentOriginPoint.x + max(0, min(input.tabPosition, input.binWidth - input.tabLength)) * input.baseWidth,
                compartmentOriginPoint.y + compartmentLength,
                compartmentOriginPoint.z,
            )
            compartmentTabInput.origin = tabOriginPoint
            compartmentTabInput.length = max(0, min(input.tabLength, input.binWidth)) * input.baseWidth
            compartmentTabInput.width = input.tabWidth
            compartmentTabInput.overhangAngle = input.tabOverhangAngle
            compartmentTabInput.topClearance = const.BIN_TAB_TOP_CLEARANCE
            compartmentTabInput.tabMethod = input.tabMethod
            compartmentTabInput.rootThickness = input.rootThickness
            compartmentTabInput.tipThickness = input.tipThickness
            compartmentTabInput.tabFilletTop = input.tabFilletTop
            compartmentTabInput.tabFilletBottom = input.tabFilletBottom
            compartmentTabInput.tabFilletBack = input.tabFilletBack

            [compartmentMerges, compartmentCuts] = createCompartment(
                input.wallThickness,
                compartmentOriginPoint,
                compartmentWidth,
                compartmentLength,
                compartmentDepth,
                input.binCornerFilletRadius - input.wallThickness,
                input.hasScoop,
                input.scoopMaxRadius,
                input.hasTab,
                compartmentTabInput,
                targetComponent,
            )
            bodiesToSubtract = bodiesToSubtract + compartmentCuts
            bodiesToMerge = bodiesToMerge + compartmentMerges

        if len(input.compartments) > 1:
            compartmentsTopClearance = createCompartmentCutout(
                input.wallThickness,
                adsk.core.Point3D.create(
                    compartmentsMinX,
                    compartmentsMinY,
                    binBodyTotalHeight
                ),
                actualBodyWidth - input.wallThickness * 2,
                actualBodyLength - input.wallThickness - compartmentsMinY,
                const.BIN_TAB_TOP_CLEARANCE,
                input.binCornerFilletRadius - input.wallThickness,
                False,
                0,
                False,
                targetComponent,
            )
            bodiesToSubtract.append(compartmentsTopClearance)

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


def createCompartmentCutout(
        wallThickness: float,
        originPoint: adsk.core.Point3D,
        width: float,
        length: float,
        depth: float,
        cornerFilletRadius: float,
        hasScoop: bool,
        scoopMaxRadius: float,
        hasBottomFillet: bool,
        targetComponent: adsk.fusion.Component,
    ) -> adsk.fusion.BRepBody:

    innerCutoutFilletRadius = max(const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, cornerFilletRadius)
    innerCutoutInput = BinBodyCutoutGeneratorInput()
    innerCutoutInput.origin = originPoint
    innerCutoutInput.width = width
    innerCutoutInput.length = length
    innerCutoutInput.height = depth
    innerCutoutInput.hasScoop = hasScoop
    innerCutoutInput.scoopMaxRadius = scoopMaxRadius
    innerCutoutInput.filletRadius = innerCutoutFilletRadius
    innerCutoutInput.hasBottomFillet = hasBottomFillet

    return createGridfinityBinBodyCutout(innerCutoutInput, targetComponent)

def createCompartment(
        wallThickness: float,
        originPoint: adsk.core.Point3D,
        width: float,
        length: float,
        depth: float,
        cornerFilletRadius: float,
        hasScoop: bool,
        scoopMaxRadius: float,
        hasTab: bool,
        tabInput: BinBodyTabGeneratorInput,
        targetComponent: adsk.fusion.Component,
    ) -> tuple[list[adsk.fusion.BRepBody], list[adsk.fusion.BRepBody]]:

    bodiesToMerge: list[adsk.fusion.BRepBody] = []
    bodiesToSubtract: list[adsk.fusion.BRepBody] = []

    innerCutoutBody = createCompartmentCutout(
        wallThickness,
        originPoint,
        width,
        length,
        depth,
        cornerFilletRadius,
        hasScoop,
        scoopMaxRadius,
        True,
        targetComponent,
    )
    bodiesToSubtract.append(innerCutoutBody)

    # label tab
    if hasTab:
        tabBody = createGridfinityBinBodyTab(tabInput, targetComponent)

        try:
            intersectTabInput = targetComponent.features.combineFeatures.createInput(
                tabBody,
                commonUtils.objectCollectionFromList([innerCutoutBody]),
                )
            intersectTabInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
            intersectTabInput.isKeepToolBodies = True
            intersectTabFeature = targetComponent.features.combineFeatures.add(intersectTabInput)
            bodiesToMerge = bodiesToMerge + [body for body in list(intersectTabFeature.bodies) if not body.revisionId == innerCutoutBody.revisionId]
        except:
             # Fallback if intersection fails (e.g. Dimensions method might not overlap cutout exactly or logic differs)
             # Just add the tab body itself
             bodiesToMerge.append(tabBody)
    return (bodiesToMerge, bodiesToSubtract)