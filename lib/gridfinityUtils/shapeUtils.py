import adsk.core, adsk.fusion, traceback
import os

from . import extrudeUtils, sketchUtils

app = adsk.core.Application.get()
ui = app.userInterface

def simpleCylinder(
    plane: adsk.core.Base,
    planeOffset: float,
    height: float,
    radius: float,
    centerBottom: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(plane, adsk.core.ValueInput.createByReal(planeOffset))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    cylinderBaseSketch: adsk.fusion.Sketch = targetComponent.sketches.add(baseConstructionPlane)
    dimensions: adsk.fusion.SketchDimensions = cylinderBaseSketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = cylinderBaseSketch.geometricConstraints
    centerOnSketch = cylinderBaseSketch.modelToSketchSpace(centerBottom)
    centerOnSketch.z = 0

    circle = cylinderBaseSketch.sketchCurves.sketchCircles.addByCenterRadius(
        centerOnSketch,
        radius,
    )
    dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x + 1, circle.centerSketchPoint.geometry.y + 1, 0),
        True,
    )
    if centerOnSketch.isEqualTo(cylinderBaseSketch.originPoint.geometry):
        constraints.addCoincident(cylinderBaseSketch.originPoint, circle.centerSketchPoint)
    else:
        dimensions.addDistanceDimension(
            cylinderBaseSketch.originPoint,
            circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
            True
        )
        dimensions.addDistanceDimension(
            cylinderBaseSketch.originPoint,
            circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
            True
        )
    
    cylinderExtrude = extrudeUtils.simpleDistanceExtrude(
        cylinderBaseSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        height,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    return cylinderExtrude.bodies.item(0)

def simpleBox(
    plane: adsk.core.Base,
    planeOffset: float,
    width: float,
    length: float,
    height: float,
    originPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    boxPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    boxPlaneInput.setByOffset(
        plane,
        adsk.core.ValueInput.createByReal(planeOffset)
    )
    boxConstructionPlane = targetComponent.constructionPlanes.add(boxPlaneInput)
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(boxConstructionPlane)
    startPointOnSketch = recSketch.modelToSketchSpace(originPoint)
    startPointOnSketch.z = 0
    sketchUtils.createRectangle(width, length, startPointOnSketch, recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    return extrude.bodies.item(0)