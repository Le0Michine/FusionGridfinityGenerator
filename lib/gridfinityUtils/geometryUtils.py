import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE

def isHorizontal(entity: adsk.fusion.BRepEdge):
    return math.isclose(entity.boundingBox.maxPoint.z, entity.boundingBox.minPoint.z, abs_tol=DEFAULT_FILTER_TOLERANCE)

def isCollinearToZ(entity: adsk.fusion.BRepEdge):
    return math.isclose(entity.boundingBox.maxPoint.x, entity.boundingBox.minPoint.x, abs_tol=DEFAULT_FILTER_TOLERANCE) and math.isclose(entity.boundingBox.maxPoint.y, entity.boundingBox.minPoint.y, abs_tol=DEFAULT_FILTER_TOLERANCE)

def isCollinearToX(entity: adsk.fusion.BRepEdge):
    return math.isclose(entity.boundingBox.maxPoint.z, entity.boundingBox.minPoint.z, abs_tol=DEFAULT_FILTER_TOLERANCE) and math.isclose(entity.boundingBox.maxPoint.y, entity.boundingBox.minPoint.y, abs_tol=DEFAULT_FILTER_TOLERANCE)

def isCollinearToY(entity: adsk.fusion.BRepEdge):
    return math.isclose(entity.boundingBox.maxPoint.z, entity.boundingBox.minPoint.z, abs_tol=DEFAULT_FILTER_TOLERANCE) and math.isclose(entity.boundingBox.maxPoint.x, entity.boundingBox.minPoint.x, abs_tol=DEFAULT_FILTER_TOLERANCE)

def boundingBoxVolume(box: adsk.core.BoundingBox3D):
    dimensions = box.maxPoint.asVector()
    dimensions.subtract(box.minPoint.asVector())
    [x, y, z] = dimensions.asArray()
    return abs(x * y * z);

def createOffsetPoint(originalPoint: adsk.core.Point3D, byX = 0, byY = 0, byZ = 0):
    return adsk.core.Point3D.create(
        originalPoint.x + byX,
        originalPoint.y + byY,
        originalPoint.z + byZ,
    )

def pointToXY(point: adsk.core.Point3D):
    return adsk.core.Point3D.create(point.x, point.y, 0)
