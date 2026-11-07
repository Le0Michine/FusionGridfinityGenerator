import adsk.core, adsk.fusion, traceback
import os
import math

from . import edgeUtils, faceUtils, commonUtils, const

def createFillet(
    edges: list[adsk.fusion.BRepEdge],
    radius: float,
    isTangentChain: bool,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    ):
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    filletInput.isTangentChain = True
    filletEdges = commonUtils.objectCollectionFromList(edges)
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(
        filletEdges,
        adsk.core.ValueInput.createByReal(radius),
        isTangentChain)
    filletFeature = filletFeatures.add(filletInput)
    filletFeature.name = name
    return filletFeature

def filletEdgesByLength(
    faces: adsk.fusion.BRepFaces,
    radius: float,
    filterEdgeLength: float,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    ):
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    bottomFilletInput = filletFeatures.createInput()
    bottomFilletInput.isRollingBallCorner = True
    bottomFilletEdges = edgeUtils.selectEdgesByLength(faces, filterEdgeLength, const.DEFAULT_FILTER_TOLERANCE)
    bottomFilletInput.edgeSetInputs.addConstantRadiusEdgeSet(bottomFilletEdges, adsk.core.ValueInput.createByReal(radius), True)
    filletFeature = filletFeatures.add(bottomFilletInput)
    filletFeature.name = name
    return filletFeature

def chamferEdgesByLength(
    faces: adsk.fusion.BRepFaces,
    distance: float,
    filterEdgeLength: float,
    filterEdgeTolerance: float,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    chamferEdges = edgeUtils.selectEdgesByLength(faces, filterEdgeLength, filterEdgeTolerance)
    return createChamfer(
        chamferEdges,
        distance,
        targetComponent,
        name=name,
    )

def createChamfer(
    edges: adsk.core.ObjectCollection,
    distance: float,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    features: adsk.fusion.Features = targetComponent.features
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        edges,
        adsk.core.ValueInput.createByReal(distance),
        True)
    chamferFeature = chamferFeatures.add(chamferInput)
    chamferFeature.name = name
    return chamferFeature