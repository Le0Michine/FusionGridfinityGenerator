from contextlib import contextmanager
import math
import adsk.core, adsk.fusion, traceback
import os

from . import const
from .dim import Dim, valueOf, applyTo

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
    width: Dim | float,
    length: Dim | float,
    startPoint: adsk.core.Point3D,
    sketch: adsk.fusion.Sketch,
    startX: Dim = None,
    startY: Dim = None,
):
    """Constrained rectangle, the optional start dims drive its distance from the sketch origin"""
    with deferSketchCompute(sketch):
        lines: adsk.fusion.SketchLines = sketch.sketchCurves.sketchLines
        rectangleLines = lines.addTwoPointRectangle(
            startPoint,
            adsk.core.Point3D.create(startPoint.x + valueOf(width), startPoint.y + valueOf(length), 0)
        )
        constrainRectangle(sketch, rectangleLines, width, length, startX, startY)
        return rectangleLines

def addFrame(sketch: adsk.fusion.Sketch, minX: float, minY: float, maxX: float, maxY: float) -> adsk.fusion.SketchLineList:
    """
    Frame around an outline given in model coordinates, as far again past it on every side, for cuts that take the region
    between frame and outline. It stays clear of the outline when parameters grow it up to twice its size.
    Drawn as createRectangle with its corner dimensioned from the sketch origin, so the sketch stays fully constrained.
    A bare addTwoPointRectangle only got horizontal and vertical from Fusion and left position and size free.
    """
    margin = max(maxX - minX, maxY - minY)
    corner = sketch.modelToSketchSpace(adsk.core.Point3D.create(minX - margin, minY - margin, 0))
    corner.z = 0
    return createRectangle(
        Dim.length(maxX - minX + 2 * margin),
        Dim.length(maxY - minY + 2 * margin),
        corner,
        sketch,
        Dim.length(corner.x),
        Dim.length(corner.y),
    )

def constrainRectangle(
    sketch: adsk.fusion.Sketch,
    rectangleLines,
    width: Dim | float = None,
    length: Dim | float = None,
    startX: Dim = None,
    startY: Dim = None,
):
    """
    The lines of a rectangle as addTwoPointRectangle orders them, from the start corner along X first, kept a rectangle
    and dimensioned so the sketch is fully constrained. The dims drive their dimensions, those left out keep the
    rectangle as it is
    """
    def applyDim(dimension: adsk.fusion.SketchDimension, value: Dim | float):
        if value is not None:
            applyTo(dimension.parameter, value)

    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = sketch.sketchDimensions
    constraints.addHorizontal(rectangleLines.item(0))
    constraints.addVertical(rectangleLines.item(1))
    constraints.addHorizontal(rectangleLines.item(2))
    constraints.addVertical(rectangleLines.item(3))
    if rectangleLines.item(0).startSketchPoint.geometry.isEqualTo(sketch.originPoint.geometry):
        constraints.addCoincident(sketch.originPoint, rectangleLines.item(3))
        constraints.addCoincident(sketch.originPoint, rectangleLines.item(0))
    else:
        # sketch distance dimensions are unsigned, coordinates left or below the origin need the magnitude
        applyDim(dimensions.addDistanceDimension(
            sketch.originPoint,
            rectangleLines.item(0).startSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            rectangleLines.item(0).startSketchPoint.geometry,
            True,
        ), startY.abs() if startY is not None else None)
        applyDim(dimensions.addDistanceDimension(
            sketch.originPoint,
            rectangleLines.item(3).startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            rectangleLines.item(3).startSketchPoint.geometry,
            True,
        ), startX.abs() if startX is not None else None)
    applyDim(dimensions.addDistanceDimension(rectangleLines.item(0).startSketchPoint,
        rectangleLines.item(0).endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        rectangleLines.item(0).endSketchPoint.geometry), width)
    applyDim(dimensions.addDistanceDimension(rectangleLines.item(1).startSketchPoint,
        rectangleLines.item(1).endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        rectangleLines.item(1).endSketchPoint.geometry), length)

def constrainTextBox(sketch: adsk.fusion.Sketch, sketchText: adsk.fusion.SketchText):
    """
    Holds a multi-line text's box where it is drawn. The box keeps its corners square itself, more than one side made
    vertical or horizontal over-constrains it. A vertical side then each side's offset from the sketch origin
    """
    boxLines = list(adsk.fusion.MultiLineTextDefinition.cast(sketchText.definition).rectangleLines)
    sketch.geometricConstraints.addVertical(boxLines[3])
    for line in boxLines:
        sketch.sketchDimensions.addOffsetDimension(line, sketch.originPoint, line.startSketchPoint.geometry, True)

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
