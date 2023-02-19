import math
import adsk.core, adsk.fusion, traceback
import os

from .const import DEFAULT_FILTER_TOLERANCE


def minByArea(faces: adsk.fusion.BRepFaces):
    return min(faces, key=lambda x: x.area)

def maxByArea(faces: adsk.fusion.BRepFaces):
    return max(faces, key=lambda x: x.area)

def closestToOrigin(faces: adsk.fusion.BRepFaces):
    origin = adsk.core.Point3D.create(0, 0, 0)
    return min(faces, key=lambda x: min(x.boundingBox.minPoint.distanceTo(origin), x.boundingBox.maxPoint.distanceTo(origin)))

def longestEdge(face: adsk.fusion.BRepFace):
    return max(face.edges, key=lambda x: x.length)

def shortestEdge(face: adsk.fusion.BRepFace):
    return min(face.edges, key=lambda x: x.length)

def isYNormal(face: adsk.fusion.BRepFace):
    return math.isclose(face.boundingBox.minPoint.y, face.boundingBox.maxPoint.y, abs_tol=DEFAULT_FILTER_TOLERANCE)

def isXNormal(face: adsk.fusion.BRepFace):
    return math.isclose(face.boundingBox.minPoint.x, face.boundingBox.maxPoint.x, abs_tol=DEFAULT_FILTER_TOLERANCE)

def isZNormal(face: adsk.fusion.BRepFace):
    return math.isclose(face.boundingBox.minPoint.z, face.boundingBox.maxPoint.z, abs_tol=DEFAULT_FILTER_TOLERANCE)