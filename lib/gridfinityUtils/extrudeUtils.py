import adsk.core, adsk.fusion, traceback
import os

from . import sketchUtils

def simpleDistanceExtrude(
    profile: adsk.core.Base,
    operation: adsk.fusion.FeatureOperations,
    distance: float,
    direction: adsk.fusion.ExtentDirections,
    participantBodies: list[adsk.fusion.BRepBody],
    targetComponent: adsk.fusion.Component,
    offset: float = 0.0,
    taperAngle: float = 0.0,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    extrudeInput = extrudeFeatures.createInput(profile, operation)
    extrudeInput.participantBodies = participantBodies
    if offset != 0:
        startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(offset))
        extrudeInput.startExtent = startExtent
    extrudeExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(distance))
    extrudeInput.setOneSideExtent(
        extrudeExtent,
        direction,
        adsk.core.ValueInput.createByReal(taperAngle),
    )
    extrudeFeature = extrudeFeatures.add(extrudeInput)
    return extrudeFeature

def createBox(
    width: float,
    length: float,
    height: float,
    targetComponent: adsk.fusion.Component,
    targetPlane: adsk.core.Base,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(targetPlane)
    recSketch.name = 'Simple box sketch'
    sketchUtils.createRectangle(width, length, recSketch.originPoint.geometry, recSketch)

    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = 'Simple box extrude'
    return extrude

def createBoxAtPoint(
    width: float,
    length: float,
    height: float,
    targetComponent: adsk.fusion.Component,
    originPoint: adsk.core.Point3D,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    boxPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    boxPlaneInput.setByOffset(
        targetComponent.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(originPoint.z)
    )
    boxConstructionPlane = targetComponent.constructionPlanes.add(boxPlaneInput)
    boxConstructionPlane.name = 'Simple box at point construction plane'
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(boxConstructionPlane)
    recSketch.name = 'Simple box at point sketch'
    sketchUtils.createRectangle(width, length, recSketch.modelToSketchSpace(originPoint), recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = 'Simple box at point extrude'
    return extrude
