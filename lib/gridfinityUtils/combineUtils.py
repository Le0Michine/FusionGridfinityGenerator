import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE

from .geometryUtils import boundingBoxVolume

def cutBody(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    keepToolBodies: bool = False
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineInput.isKeepToolBodies = keepToolBodies
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    return combineFeature

def intersectBody(
    targetBody: adsk.fusion.BRepBody,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    keepToolBodies: bool = False,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    combineInput.isKeepToolBodies = keepToolBodies
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    return combineFeature

def joinBodies(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    keepToolBodies: bool = False,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combineInput.isKeepToolBodies = keepToolBodies
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    return combineFeature
