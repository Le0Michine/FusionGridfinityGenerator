import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE

from .geometryUtils import boundingBoxVolume

def cutBody(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    isKeepToolBodies: bool = False,
    *,
    name: str,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineInput.isKeepToolBodies = isKeepToolBodies
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    combineFeature.name = name
    return combineFeature

def intersectBody(
    targetBody: adsk.fusion.BRepBody,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    combineFeature.name = name
    return combineFeature

def joinBodies(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    combineFeature.name = name
    return combineFeature
