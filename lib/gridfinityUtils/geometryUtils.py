import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE

def isBoundingBoxFlat(box: adsk.core.BoundingBox3D, axes):
    minimum, maximum = box.minPoint, box.maxPoint
    return all(math.isclose(getattr(minimum, axis), getattr(maximum, axis),
                            abs_tol=DEFAULT_FILTER_TOLERANCE) for axis in axes)


def isHorizontal(entity: adsk.fusion.BRepEdge):
    return isBoundingBoxFlat(entity.boundingBox, 'z')

def isCollinearToZ(entity: adsk.fusion.BRepEdge):
    return isBoundingBoxFlat(entity.boundingBox, 'xy')

def isCollinearToX(entity: adsk.fusion.BRepEdge):
    return isBoundingBoxFlat(entity.boundingBox, 'zy')

def isCollinearToY(entity: adsk.fusion.BRepEdge):
    return isBoundingBoxFlat(entity.boundingBox, 'zx')

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
