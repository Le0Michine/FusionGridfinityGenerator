import adsk.core, adsk.fusion, traceback
import os

from . import const

def matches(edge1: adsk.fusion.BRepEdge, edge2: adsk.fusion.BRepEdge):
    [_, start1, end1] = edge1.evaluator.getEndPoints()
    [_, start2, end2] = edge2.evaluator.getEndPoints()
    tol = const.DEFAULT_FILTER_TOLERANCE
    return (start1.isEqualToByTolerance(start2, tol) or start1.isEqualToByTolerance(end2, tol)) and (end1.isEqualToByTolerance(start2, tol) or end1.isEqualToByTolerance(end2, tol))
