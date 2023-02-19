import adsk.core, adsk.fusion, traceback
import os
import math

from .commonUtils import objectCollectionFromList

from . import faceUtils

def createFillet(
    edges: list[adsk.fusion.BRepEdge],
    radius: float,
    isTangentChain: bool,
    targetComponent: adsk.fusion.Component,
    ):
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    filletInput.isTangentChain = True
    filletEdges = objectCollectionFromList(edges)
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(
        filletEdges,
        adsk.core.ValueInput.createByReal(radius),
        isTangentChain)
    return filletFeatures.add(filletInput)