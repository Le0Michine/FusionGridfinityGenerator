from contextlib import contextmanager
import math
import adsk.core, adsk.fusion, traceback
import os

from . import const

def isVertical(line: adsk.fusion.SketchLine):
    return math.isclose(line.startSketchPoint.geometry.x, line.endSketchPoint.geometry.x, abs_tol=const.DEFAULT_FILTER_TOLERANCE)

def isHorizontal(line: adsk.fusion.SketchLine):
    return math.isclose(line.startSketchPoint.geometry.y, line.endSketchPoint.geometry.y, abs_tol=const.DEFAULT_FILTER_TOLERANCE)

@contextmanager
def deferSketchCompute(sketch):
    """Batch construction of a new sketch before any feature depends on it."""
    wasDeferred = sketch.isComputeDeferred
    try:
        sketch.isComputeDeferred = True
        yield
    finally:
        sketch.isComputeDeferred = wasDeferred


def createRectangle(
    width: float,
    length: float,
    startPoint: adsk.core.Point3D,
    sketch: adsk.fusion.Sketch,
    widthExpr: str = None,
    lengthExpr: str = None,
    startXExpr: str = None,
    startYExpr: str = None,
):
    """Constrained rectangle, the optional expressions drive its dimensions instead of plain values"""
    def applyExpression(dimension: adsk.fusion.SketchDimension, expression: str):
        if expression is not None:
            dimension.parameter.expression = expression

    with deferSketchCompute(sketch):
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
            applyExpression(dimensions.addDistanceDimension(
                sketch.originPoint,
                rectangleLines.item(0).startSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                rectangleLines.item(0).startSketchPoint.geometry,
                True,
            ), startYExpr)
            applyExpression(dimensions.addDistanceDimension(
                sketch.originPoint,
                rectangleLines.item(3).startSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                rectangleLines.item(3).startSketchPoint.geometry,
                True,
            ), startXExpr)
        applyExpression(dimensions.addDistanceDimension(rectangleLines.item(0).startSketchPoint,
            rectangleLines.item(0).endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            rectangleLines.item(0).endSketchPoint.geometry), widthExpr)
        applyExpression(dimensions.addDistanceDimension(rectangleLines.item(1).startSketchPoint,
            rectangleLines.item(1).endSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            rectangleLines.item(1).endSketchPoint.geometry), lengthExpr)
        return rectangleLines

def lengthExpression(value: float) -> str:
    """Internal length in cm as a millimeter literal for parameter expressions"""
    return f'{round(value * 10, 6):g} mm'

def distanceExpression(expression: str) -> str:
    """Sketch distance dimensions are unsigned, coordinates left or below the origin need the magnitude"""
    return f'abs({expression})'

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
