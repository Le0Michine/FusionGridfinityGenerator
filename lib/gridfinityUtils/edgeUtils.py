import adsk.core, adsk.fusion, traceback
import os
import math

from . import const

def matches(edge1: adsk.fusion.BRepEdge, edge2: adsk.fusion.BRepEdge):
    [_, start1, end1] = edge1.evaluator.getEndPoints()
    [_, start2, end2] = edge2.evaluator.getEndPoints()
    tol = const.DEFAULT_FILTER_TOLERANCE
    return (start1.isEqualToByTolerance(start2, tol) or start1.isEqualToByTolerance(end2, tol)) and (end1.isEqualToByTolerance(start2, tol) or end1.isEqualToByTolerance(end2, tol))

def selectEdgesByLength(
    faces: adsk.fusion.BRepFaces,
    filterEdgeLength: float,
    filterEdgeTolerance: float,
    ):
    filteredEdges = adsk.core.ObjectCollection.create()
    for face in faces:
        for edge in face.edges:
            if math.isclose(edge.length, filterEdgeLength, abs_tol=filterEdgeTolerance):
                filteredEdges.add(edge)
    return filteredEdges

def excludeEdges(edges: list[adsk.fusion.BRepEdge], toExclude: list[adsk.fusion.BRepEdge]):
    toExcludeIds = [edge.tempId for edge in toExclude]
    return [edge for edge in edges if not edge.tempId in toExcludeIds]

def getConnectedEdges(edge: adsk.fusion.BRepEdge, edges: list[adsk.fusion.BRepEdge]):
    """Returns edges from the list which share a vertex with the given edge, the edge itself is excluded"""
    tol = const.DEFAULT_FILTER_TOLERANCE
    [_, start, end] = edge.evaluator.getEndPoints()
    connectedEdges: list[adsk.fusion.BRepEdge] = []
    for other in edges:
        if other.tempId == edge.tempId:
            continue
        [_, otherStart, otherEnd] = other.evaluator.getEndPoints()
        for point in [start, end]:
            if point.isEqualToByTolerance(otherStart, tol) or point.isEqualToByTolerance(otherEnd, tol):
                connectedEdges.append(other)
                break
    return connectedEdges
