import math
import adsk.core, adsk.fusion, traceback
import os

from . import const

def isVertical(line: adsk.fusion.SketchLine):
    return math.isclose(line.startSketchPoint.geometry.x, line.endSketchPoint.geometry.x, abs_tol=const.DEFAULT_FILTER_TOLERANCE)

def isHorizontal(line: adsk.fusion.SketchLine):
    return math.isclose(line.startSketchPoint.geometry.y, line.endSketchPoint.geometry.y, abs_tol=const.DEFAULT_FILTER_TOLERANCE)

def createRectangle(
    width: float,
    length: float,
    startPoint: adsk.core.Point3D,
    sketch: adsk.fusion.Sketch,
):
    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = sketch.sketchDimensions
    lines: adsk.fusion.SketchLines = sketch.sketchCurves.sketchLines
    rectangleLines = lines.addTwoPointRectangle(
        startPoint,
        adsk.core.Point3D.create(startPoint.x + width, startPoint.y + length, 0)
    )
    constraints.addHorizontal(rectangleLines.item(0))
    constraints.addVertical(rectangleLines.item(1))
    constraints.addHorizontal(rectangleLines.item(2))
    constraints.addVertical(rectangleLines.item(3))
    if startPoint.isEqualTo(sketch.originPoint.geometry):
        constraints.addCoincident(sketch.originPoint, rectangleLines.item(3))
        constraints.addCoincident(sketch.originPoint, rectangleLines.item(0))
    else:
        dimensions.addDistanceDimension(
            sketch.originPoint,
            rectangleLines.item(0).startSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            rectangleLines.item(0).startSketchPoint.geometry,
            True,
            )    
        dimensions.addDistanceDimension(
            sketch.originPoint,
            rectangleLines.item(3).startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            rectangleLines.item(3).startSketchPoint.geometry,
            True,
            )    
    dimensions.addDistanceDimension(rectangleLines.item(0).startSketchPoint,
        rectangleLines.item(0).endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        rectangleLines.item(0).endSketchPoint.geometry)
    dimensions.addDistanceDimension(rectangleLines.item(1).startSketchPoint,
        rectangleLines.item(1).endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        rectangleLines.item(1).endSketchPoint.geometry)

def filterCirclesByRadius(
    radius: float,
    tolerance: float,
    sketchCircles: adsk.fusion.SketchCircles,
):
    filteredCircles = []
    for circle in sketchCircles:
        if abs (circle.radius - radius) < tolerance:
            filteredCircles.append(circle)
        
    return filteredCircles

def createOffsetProfileSketch(
    planarEntity: adsk.core.Base,
    offsetValue: float,
    targetComponent: adsk.fusion.Component,
):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    sketch: adsk.fusion.Sketch = sketches.add(planarEntity)
    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    curvesList: list[adsk.fusion.SketchCurve] = []
    for curve in sketch.sketchCurves:
        curvesList.append(curve)
        curve.isConstruction = True
    constraints.addOffset(curvesList,
        adsk.core.ValueInput.createByReal(offsetValue),
        sketch.sketchCurves.sketchLines.item(0).startSketchPoint.geometry)

    return sketch

def convertToConstruction(curves: adsk.fusion.SketchCurves):
    for curve in curves:
        curve.isConstruction = True
