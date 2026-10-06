import adsk.core, adsk.fusion, traceback
import os, math

from . import extrudeUtils, sketchUtils

app = adsk.core.Application.get()
ui = app.userInterface

def simpleCylinder(
    plane: adsk.core.Base,
    planeOffset: float,
    height: float,
    radius: float,
    centerBottom: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(plane, adsk.core.ValueInput.createByReal(planeOffset))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    cylinderBaseSketch: adsk.fusion.Sketch = targetComponent.sketches.add(baseConstructionPlane)
    cylinderBaseSketch.name = "Simple cylinder sketch"
    dimensions: adsk.fusion.SketchDimensions = cylinderBaseSketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = cylinderBaseSketch.geometricConstraints
    centerOnSketch = cylinderBaseSketch.modelToSketchSpace(centerBottom)
    centerOnSketch.z = 0

    circle = cylinderBaseSketch.sketchCurves.sketchCircles.addByCenterRadius(
        centerOnSketch,
        radius,
    )
    dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x + 1, circle.centerSketchPoint.geometry.y + 1, 0),
        True,
    )
    if centerOnSketch.isEqualTo(cylinderBaseSketch.originPoint.geometry):
        constraints.addCoincident(cylinderBaseSketch.originPoint, circle.centerSketchPoint)
    else:
        dimensions.addDistanceDimension(
            cylinderBaseSketch.originPoint,
            circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
            True
        )
        dimensions.addDistanceDimension(
            cylinderBaseSketch.originPoint,
            circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
            True
        )
    
    cylinderExtrude = extrudeUtils.simpleDistanceExtrude(
        cylinderBaseSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        height,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    cylinderExtrude.name = "Simple cylinder extrude"
    return cylinderExtrude.bodies.item(0)

def refinedMagnetHoleBody(
    plane: adsk.core.Base,
    planeOffset: float,
    pocketRadius: float,
    pocketDepth: float,
    slotEdgePoint: adsk.core.Point3D,
    centerPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    """Create a refined magnet hole cutout body (grizzie17's Gridfinity Refined design).

    The pocket is a keyhole shape drawn as a single closed profile: a semicircular
    pocket connected to a rectangular slot extending to the base edge.

    Arguments:
        plane: the base bottom face
        planeOffset: offset from the bottom face to the TOP of the pocket
            (negative = into the base, typically -(floor thickness))
        pocketRadius: radius of the circular magnet pocket
        pocketDepth: depth of the pocket (magnet height minus tolerance)
        slotEdgePoint: the point on the base edge where the slot exits,
            in model space (center of the slot width at the edge)
        centerPoint: center of the magnet pocket in model space
    """
    constructionPlaneInput = targetComponent.constructionPlanes.createInput()
    constructionPlaneInput.setByOffset(plane, adsk.core.ValueInput.createByReal(planeOffset))
    constructionPlane = targetComponent.constructionPlanes.add(constructionPlaneInput)

    sketch: adsk.fusion.Sketch = targetComponent.sketches.add(constructionPlane)
    sketch.name = "Refined magnet hole sketch"

    ctr = sketch.modelToSketchSpace(centerPoint)
    ctr.z = 0
    edge = sketch.modelToSketchSpace(slotEdgePoint)
    edge.z = 0

    # Compute slot direction (center → edge) and perpendicular in sketch space
    dx = edge.x - ctr.x
    dy = edge.y - ctr.y
    length = math.sqrt(dx * dx + dy * dy)
    dirX = dx / length
    dirY = dy / length
    perpX = -dirY
    perpY = dirX
    r = pocketRadius

    # Keyhole as a single closed profile:
    #   - Semicircular arc on the far side (away from slot)
    #   - Two parallel lines forming the slot sides
    #   - A closing line at the base edge
    arcStart = adsk.core.Point3D.create(ctr.x + perpX * r, ctr.y + perpY * r, 0)
    arcMid = adsk.core.Point3D.create(ctr.x - dirX * r, ctr.y - dirY * r, 0)
    arcEnd = adsk.core.Point3D.create(ctr.x - perpX * r, ctr.y - perpY * r, 0)

    edgeTop = adsk.core.Point3D.create(edge.x + perpX * r, edge.y + perpY * r, 0)
    edgeBottom = adsk.core.Point3D.create(edge.x - perpX * r, edge.y - perpY * r, 0)

    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines

    arcs.addByThreePoints(arcStart, arcMid, arcEnd)
    lines.addByTwoPoints(arcEnd, edgeBottom)
    lines.addByTwoPoints(edgeBottom, edgeTop)
    lines.addByTwoPoints(edgeTop, arcStart)

    pocketExtrude = extrudeUtils.simpleDistanceExtrude(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        -pocketDepth,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    pocketExtrude.name = "Refined magnet pocket extrude"
    return pocketExtrude.bodies.item(0)


def refinedPokeThrough(
    plane: adsk.core.Base,
    planeOffset: float,
    depth: float,
    pokeRadius: float,
    slotEdgePoint: adsk.core.Point3D,
    centerPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    """Create a poke-through slot for magnet removal with a toothpick.

    Draws a stadium/oblong shape (two semicircles connected by lines) positioned
    on the OPPOSITE side of the pocket from the insertion slot (toward the base
    interior). This lets you push the magnet out from behind with a toothpick.

    Positions match the OpenSCAD reference: near end at ~3.4mm from center,
    far end at ~6.93mm from center, in the direction away from the base edge.
    """
    constructionPlaneInput = targetComponent.constructionPlanes.createInput()
    constructionPlaneInput.setByOffset(plane, adsk.core.ValueInput.createByReal(planeOffset))
    constructionPlane = targetComponent.constructionPlanes.add(constructionPlaneInput)

    sketch: adsk.fusion.Sketch = targetComponent.sketches.add(constructionPlane)
    sketch.name = "Refined poke-through sketch"

    ctr = sketch.modelToSketchSpace(centerPoint)
    ctr.z = 0
    edge = sketch.modelToSketchSpace(slotEdgePoint)
    edge.z = 0

    # Direction from center AWAY from the edge (toward base interior)
    # This is the opposite of the slot direction
    dx = ctr.x - edge.x
    dy = ctr.y - edge.y
    length = math.sqrt(dx * dx + dy * dy)
    dirX = dx / length
    dirY = dy / length
    perpX = -dirY
    perpY = dirX

    # Position the poke-through slot along the interior direction,
    # matching OpenSCAD: near end at 3.4mm, far end at 6.93mm from center
    # As fractions of the center-to-edge distance (8mm):
    nearFrac = 0.425
    farFrac = 0.866
    nearCenter = adsk.core.Point3D.create(
        ctr.x + dirX * length * nearFrac, ctr.y + dirY * length * nearFrac, 0,
    )
    farCenter = adsk.core.Point3D.create(
        ctr.x + dirX * length * farFrac, ctr.y + dirY * length * farFrac, 0,
    )

    pr = pokeRadius

    # Stadium shape: two semicircles connected by two lines
    # Near semicircle (closer to pocket center)
    nearArcStart = adsk.core.Point3D.create(nearCenter.x + perpX * pr, nearCenter.y + perpY * pr, 0)
    nearArcMid = adsk.core.Point3D.create(nearCenter.x - dirX * pr, nearCenter.y - dirY * pr, 0)
    nearArcEnd = adsk.core.Point3D.create(nearCenter.x - perpX * pr, nearCenter.y - perpY * pr, 0)

    # Far semicircle (toward base interior)
    farArcStart = adsk.core.Point3D.create(farCenter.x - perpX * pr, farCenter.y - perpY * pr, 0)
    farArcMid = adsk.core.Point3D.create(farCenter.x + dirX * pr, farCenter.y + dirY * pr, 0)
    farArcEnd = adsk.core.Point3D.create(farCenter.x + perpX * pr, farCenter.y + perpY * pr, 0)

    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines

    arcs.addByThreePoints(nearArcStart, nearArcMid, nearArcEnd)
    lines.addByTwoPoints(nearArcEnd, farArcStart)
    arcs.addByThreePoints(farArcStart, farArcMid, farArcEnd)
    lines.addByTwoPoints(farArcEnd, nearArcStart)

    pokeExtrude = extrudeUtils.simpleDistanceExtrude(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        -depth,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    pokeExtrude.name = "Refined poke-through extrude"
    return pokeExtrude.bodies.item(0)


def simpleBox(
    plane: adsk.core.Base,
    planeOffset: float,
    width: float,
    length: float,
    height: float,
    originPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    boxPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    boxPlaneInput.setByOffset(
        plane,
        adsk.core.ValueInput.createByReal(planeOffset)
    )
    boxConstructionPlane = targetComponent.constructionPlanes.add(boxPlaneInput)
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(boxConstructionPlane)
    recSketch.name = "Simple box sketch"
    startPointOnSketch = recSketch.modelToSketchSpace(originPoint)
    startPointOnSketch.z = 0
    sketchUtils.createRectangle(width, length, startPointOnSketch, recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = "Simple box extrude"
    return extrude.bodies.item(0)