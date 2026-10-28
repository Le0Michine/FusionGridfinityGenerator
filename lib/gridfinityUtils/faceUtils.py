import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE
from . import geometryUtils


def minByArea(faces: adsk.fusion.BRepFaces):
    return min(faces, key=lambda x: x.area)

def maxByArea(faces: adsk.fusion.BRepFaces):
    return max(faces, key=lambda x: x.area)

def closestToOrigin(faces: adsk.fusion.BRepFaces):
    origin = adsk.core.Point3D.create(0, 0, 0)
    def distance(face):
        bounds = face.boundingBox
        return min(bounds.minPoint.distanceTo(origin), bounds.maxPoint.distanceTo(origin))
    return min(faces, key=distance)

def longestEdge(face: adsk.fusion.BRepFace):
    return max(face.edges, key=lambda x: x.length)

def shortestEdge(face: adsk.fusion.BRepFace):
    return min(face.edges, key=lambda x: x.length)

def isYNormal(face: adsk.fusion.BRepFace):
    return geometryUtils.isBoundingBoxFlat(face.boundingBox, 'y')

def isXNormal(face: adsk.fusion.BRepFace):
    return geometryUtils.isBoundingBoxFlat(face.boundingBox, 'x')

def isZNormal(face: adsk.fusion.BRepFace):
    return geometryUtils.isBoundingBoxFlat(face.boundingBox, 'z')


def getNormalFaceExtremes(faces: adsk.fusion.BRepFaces, axis):
    positions = []
    for face in faces:
        bounds = face.boundingBox
        minimum = getattr(bounds.minPoint, axis)
        maximum = getattr(bounds.maxPoint, axis)
        if math.isclose(minimum, maximum, abs_tol=DEFAULT_FILTER_TOLERANCE):
            positions.append((face, minimum))
    return (min(positions, key=lambda item: item[1])[0],
            max(positions, key=lambda item: item[1])[0])


def getBottomFace(body: adsk.fusion.BRepBody):
    return getNormalFaceExtremes(body.faces, 'z')[0]

def getTopFace(body: adsk.fusion.BRepBody):
    return getNormalFaceExtremes(body.faces, 'z')[1]

def getTopHorizontalEdge(edges: adsk.fusion.BRepEdges):
    horizontalEdges = [edge for edge in edges if geometryUtils.isHorizontal(edge)]
    return max(horizontalEdges, key=lambda x: x.startVertex.geometry.z)

def getBottomHorizontalEdge(edges: adsk.fusion.BRepEdges):
    horizontalEdges = [edge for edge in edges if geometryUtils.isHorizontal(edge)]
    return min(horizontalEdges, key=lambda x: x.startVertex.geometry.z)

def getVerticalEdges(
    faces: adsk.fusion.BRepFaces,
    ):
    filteredEdges: list[adsk.fusion.BRepEdge] = []
    for face in faces:
        for edge in face.edges:
            if geometryUtils.isCollinearToZ(edge):
                filteredEdges.append(edge)
    return filteredEdges
