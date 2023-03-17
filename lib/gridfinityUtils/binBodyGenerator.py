import adsk.core, adsk.fusion, traceback
import os
import math

from .const import BIN_BODY_BOTTOM_THICKNESS, BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CONNECTION_RECESS_DEPTH, BIN_CORNER_FILLET_RADIUS, BIN_TAB_EDGE_FILLET_RADIUS
from ...lib import fusion360utils as futil
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils, filletUtils, geometryUtils
from .binBodyCutoutGenerator import createGridfinityBinBodyCutout
from .binBodyCutoutGeneratorInput import BinBodyCutoutGeneratorInput
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyGeneratorInput import BinBodyGeneratorInput
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from .binBodyTabGenerator import createGridfinityBinBodyTab
from .binBodyLipGeneratorInput import BinBodyLipGeneratorInput
from .binBodyLipGenerator import createGridfinityBinBodyLip
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def createGridfinityBinBody(
    input: BinBodyGeneratorInput,
    targetComponent: adsk.fusion.Component,
    ):

    actualBodyWidth = (input.baseWidth * input.binWidth) - input.xyTolerance * 2.0
    actualBodyLength = (input.baseLength * input.binLength) - input.xyTolerance * 2.0
    binBodyTotalHeight = input.binHeight * input.heightUnit + max(0, input.heightUnit - const.BIN_BASE_HEIGHT)
    features: adsk.fusion.Features = targetComponent.features
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
        lipOriginPoint = adsk.core.Point3D.create(
            0,
            0,
            input.binHeight * input.heightUnit + max(0, input.heightUnit - const.BIN_BASE_HEIGHT)
        )
        lipInput = BinBodyLipGeneratorInput()
        lipInput.baseLength = input.baseLength
        lipInput.baseWidth = input.baseWidth
        lipInput.binLength = input.binLength
        lipInput.binWidth = input.binWidth
        lipInput.hasLipNotches = input.hasLipNotches
        lipInput.xyTolerance = input.xyTolerance
        lipInput.origin = lipOriginPoint
        lipBody = createGridfinityBinBodyLip(lipInput, targetComponent)

        if input.wallThickness < const.BIN_LIP_WALL_THICKNESS:
            lipBottomChamferSize = max(const.BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, const.BIN_CORNER_FILLET_RADIUS - input.wallThickness)
            lipBottomChamferExtrude = extrudeUtils.createBoxAtPoint(
                actualBodyWidth - input.wallThickness * 2,
                (actualBodyLength - input.wallThickness - const.BIN_LIP_WALL_THICKNESS) if input.hasScoop else (actualBodyLength - input.wallThickness * 2),
                lipBottomChamferSize,
                targetComponent,
                adsk.core.Point3D.create(
                    input.wallThickness,
                    const.BIN_LIP_WALL_THICKNESS if input.hasScoop else input.wallThickness,
                    lipOriginPoint.z,
                )
            )
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
        innerCutoutFilletRadius = max(BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CORNER_FILLET_RADIUS - input.wallThickness)
        innerCutoutInput = BinBodyCutoutGeneratorInput()
        innerCutoutOriginPoint = adsk.core.Point3D.create(
            input.wallThickness,
            const.BIN_LIP_WALL_THICKNESS if input.hasLip and input.hasScoop else input.wallThickness,
            binBodyTotalHeight
        )
        innerCutoutInput.origin = innerCutoutOriginPoint
        innerCutoutInput.width = actualBodyWidth - input.wallThickness * 2
        innerCutoutInput.length = (actualBodyLength - input.wallThickness - const.BIN_LIP_WALL_THICKNESS) if input.hasLip and input.hasScoop else (actualBodyLength - input.wallThickness * 2)
        innerCutoutInput.height = binBodyTotalHeight - const.BIN_BODY_BOTTOM_THICKNESS
        innerCutoutInput.hasScoop = input.hasScoop
        innerCutoutInput.hasTab = input.hasTab
        innerCutoutInput.tabLength = input.tabLength
        innerCutoutInput.tabWidth = input.tabWidth
        innerCutoutInput.tabPosition = input.tabPosition
        innerCutoutInput.tabOverhangAngle = input.tabOverhangAngle
        innerCutoutInput.filletRadius = innerCutoutFilletRadius

        innerCutoutBody = createGridfinityBinBodyCutout(innerCutoutInput, targetComponent)
        bodiesToSubtract.append(innerCutoutBody)
        
        # label tab
        if input.hasTab:
            tabInput = BinBodyTabGeneratorInput()
            tabOriginPoint = adsk.core.Point3D.create(
                max(0, min(input.tabPosition, input.binWidth - input.tabLength)) * input.baseWidth,
                actualBodyLength - input.wallThickness,
                innerCutoutInput.origin.z,
            )
            tabInput.origin = tabOriginPoint
            tabInput.length = max(0, min(input.tabLength, input.binWidth)) * input.baseWidth
            tabInput.width = input.tabWidth
            tabInput.overhangAngle = input.tabOverhangAngle
            tabBody = createGridfinityBinBodyTab(tabInput,targetComponent)
            bodiesToMerge.append(tabBody)

            intersectTabInput = targetComponent.features.combineFeatures.createInput(
                tabBody,
                commonUtils.objectCollectionFromList([innerCutoutBody]),
                )
            intersectTabInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
            intersectTabInput.isKeepToolBodies = True
            targetComponent.features.combineFeatures.add(intersectTabInput)


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
