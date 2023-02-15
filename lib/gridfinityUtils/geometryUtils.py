import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE

def isHorizontal(entity: adsk.fusion.BRepEdge):
    return math.isclose(entity.boundingBox.maxPoint.z, entity.boundingBox.minPoint.z, abs_tol=DEFAULT_FILTER_TOLERANCE)
