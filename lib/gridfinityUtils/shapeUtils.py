import adsk.core, adsk.fusion, traceback
import os

from . import extrudeUtils, sketchUtils
from .dim import Dim

app = adsk.core.Application.get()
ui = app.userInterface

def simpleCylinder(
    plane: adsk.core.Base,
    planeOffset: float,
    height: float,
    radius: float,
    centerBottom: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    """Plane, sketch, extrude and body are named after the cylinder"""
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(plane, adsk.core.ValueInput.createByReal(planeOffset))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    baseConstructionPlane.name = f'{name} plane'
    cylinderBaseSketch: adsk.fusion.Sketch = targetComponent.sketches.add(baseConstructionPlane)
    cylinderBaseSketch.name = f'{name} sketch'
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
        name=name,
    )
    cylinderBody = cylinderExtrude.bodies.item(0)
    cylinderBody.name = name
    return cylinderBody

def simpleBox(
    plane: adsk.core.Base,
    planeOffset: float,
    width: Dim | float,
    length: Dim | float,
    height: float,
    originPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
    originX: Dim = None,
    originY: Dim = None,
    *,
    name: str,
):
    """Plane, sketch, extrude and body are named after the box, the optional origin dims drive the corner position"""
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    boxPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    boxPlaneInput.setByOffset(
        plane,
        adsk.core.ValueInput.createByReal(planeOffset)
    )
    boxConstructionPlane = targetComponent.constructionPlanes.add(boxPlaneInput)
    boxConstructionPlane.name = f'{name} plane'
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(boxConstructionPlane)
    recSketch.name = f'{name} sketch'
    startPointOnSketch = recSketch.modelToSketchSpace(originPoint)
    startPointOnSketch.z = 0
    sketchUtils.createRectangle(width, length, startPointOnSketch, recSketch, originX, originY)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = name
    boxBody = extrude.bodies.item(0)
    boxBody.name = name
    return boxBody