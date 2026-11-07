import adsk.core, adsk.fusion, traceback
import os

from . import sketchUtils
from .dim import Dim, valueInput

def simpleDistanceExtrude(
    profile: adsk.core.Base,
    operation: adsk.fusion.FeatureOperations,
    distance: Dim | float,
    direction: adsk.fusion.ExtentDirections,
    participantBodies: list[adsk.fusion.BRepBody],
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    extrudeInput = extrudeFeatures.createInput(profile, operation)
    extrudeInput.participantBodies = participantBodies
    extrudeExtent = adsk.fusion.DistanceExtentDefinition.create(valueInput(distance))
    extrudeInput.setOneSideExtent(
        extrudeExtent,
        direction,
        adsk.core.ValueInput.createByReal(0),
    )
    extrudeFeature = extrudeFeatures.add(extrudeInput)
    extrudeFeature.name = name
    return extrudeFeature

def createBox(
    width: Dim | float,
    length: Dim | float,
    height: Dim | float,
    targetComponent: adsk.fusion.Component,
    targetPlane: adsk.core.Base,
    *,
    name: str,
    ):
    """Sketch and extrude are named after the box"""
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(targetPlane)
    recSketch.name = f'{name} sketch'
    sketchUtils.createRectangle(width, length, recSketch.originPoint.geometry, recSketch)

    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        valueInput(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = name
    return extrude

def createBoxAtPoint(
    width: Dim | float,
    length: Dim | float,
    height: float,
    targetComponent: adsk.fusion.Component,
    originPoint: adsk.core.Point3D,
    originZ: Dim | float = None,
    *,
    name: str,
    ):
    """Box with its bottom corner at the origin point, the optional origin z drives the height of its plane.
    Plane, sketch and extrude are named after the box"""
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    boxPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    boxPlaneInput.setByOffset(
        targetComponent.xYConstructionPlane,
        valueInput(originPoint.z if originZ is None else originZ)
    )
    boxConstructionPlane = targetComponent.constructionPlanes.add(boxPlaneInput)
    boxConstructionPlane.name = f'{name} plane'
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(boxConstructionPlane)
    recSketch.name = f'{name} sketch'
    sketchUtils.createRectangle(width, length, recSketch.modelToSketchSpace(originPoint), recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = name
    return extrude
