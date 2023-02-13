import adsk.core, adsk.fusion, traceback
import os

def createRectangle(
    width: float,
    length: float,
    sketch: adsk.fusion.Sketch,
    ):
    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = sketch.sketchDimensions
    lines: adsk.fusion.SketchLines = sketch.sketchCurves.sketchLines
    rectangleLines = lines.addTwoPointRectangle(sketch.originPoint.geometry,
        adsk.core.Point3D.create(width, length, 0))
    constraints.addHorizontal(rectangleLines.item(0))
    constraints.addVertical(rectangleLines.item(1))
    constraints.addHorizontal(rectangleLines.item(2))
    constraints.addVertical(rectangleLines.item(3))
    constraints.addCoincident(sketch.originPoint, rectangleLines.item(3))
    constraints.addCoincident(sketch.originPoint, rectangleLines.item(0))
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