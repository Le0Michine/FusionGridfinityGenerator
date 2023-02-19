import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE

from .geometryUtils import boundingBoxVolume

def trimBodyByMaxBBVolume(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineInput.isKeepToolBodies = True
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    maxBBVolumeBody = max(combineFeature.bodies, key=lambda x: boundingBoxVolume(x.boundingBox))
    for body in list(combineFeature.bodies):
        if not math.isclose(boundingBoxVolume(maxBBVolumeBody.boundingBox), boundingBoxVolume(body.boundingBox), abs_tol=DEFAULT_FILTER_TOLERANCE):
            targetComponent.features.removeFeatures.add(body)

    return maxBBVolumeBody

def cutBody(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    return combineFeature

def joinBodies(
    targetBody: adsk.fusion.BRepBodies,
    toolBodies: adsk.core.ObjectCollection,
    targetComponent: adsk.fusion.Component,
    ):
    combineInput = targetComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combineFeature = targetComponent.features.combineFeatures.add(combineInput)
    return combineFeature
