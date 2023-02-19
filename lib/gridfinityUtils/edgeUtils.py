import adsk.core, adsk.fusion, traceback
import os

def matches(edge1: adsk.fusion.BRepEdge, edge2: adsk.fusion.BRepEdge):
    [_, start1, end1] = edge1.evaluator.getEndPoints()
    [_, start2, end2] = edge2.evaluator.getEndPoints()
    return (start1.isEqualToByTolerance(start2) or start1.isEqualToByTolerance(end2)) and (end1.isEqualToByTolerance(start2) or end1.isEqualToByTolerance(end2))
