import adsk.core, adsk.fusion, traceback
import os

def simpleDistanceExtrude(
    profile: adsk.core.Base,
    operation: adsk.fusion.FeatureOperations,
    distance: float,
    direction: adsk.fusion.ExtentDirections,
    targetComponent: adsk.fusion.Component,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures

    participatingBodies = []
    for body in targetComponent.bRepBodies:
        participatingBodies.append(body)
    extrudeInput = extrudeFeatures.createInput(profile, operation)
    extrudeInput.participantBodies = participatingBodies
    extrudeExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(distance))
    extrudeInput.setOneSideExtent(
        extrudeExtent,
        direction,
        adsk.core.ValueInput.createByReal(0),
    )
    extrudeFeature = extrudeFeatures.add(extrudeInput)
    return extrudeFeature
