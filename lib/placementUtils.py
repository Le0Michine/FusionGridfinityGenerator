import adsk.core, adsk.fusion
import math

from . import tagUtils

# fraction of a grid cell, keeps bodies sitting exactly on cell borders from spilling into neighbours
GRID_SNAP_TOLERANCE = 0.001

def extentToCells(
    extent: tuple[float, float, float, float],
    cellWidth: float,
    cellLength: float,
) -> tuple[int, int, int, int]:
    """Grid cells covered by an XY extent (minX, minY, maxX, maxY), end exclusive"""
    (minX, minY, maxX, maxY) = extent
    return (
        math.floor(minX / cellWidth + GRID_SNAP_TOLERANCE),
        math.floor(minY / cellLength + GRID_SNAP_TOLERANCE),
        math.ceil(maxX / cellWidth - GRID_SNAP_TOLERANCE),
        math.ceil(maxY / cellLength - GRID_SNAP_TOLERANCE),
    )

def cellsOverlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def findFreeGridOffset(
    footprint: tuple[int, int, int, int],
    occupied: list[tuple[int, int, int, int]],
    cellWidth: float = 1,
    cellLength: float = 1,
) -> tuple[int, int]:
    """Non-negative grid offset moving footprint clear of occupied cells, greedily picking the spot
    whose footprint center is closest to the origin. Ties go to lower rows, then lower columns."""
    # past these offsets the footprint clears every occupied cell, so the closest free spot is within them
    limitX = max([0] + [cells[2] - footprint[0] for cells in occupied])
    limitY = max([0] + [cells[3] - footprint[1] for cells in occupied])
    centerX = (footprint[0] + footprint[2]) / 2
    centerY = (footprint[1] + footprint[3]) / 2
    def distanceToOrigin(offset: tuple[int, int]):
        return ((offset[0] + centerX) * cellWidth) ** 2 + ((offset[1] + centerY) * cellLength) ** 2
    candidates = sorted(
        ((x, y) for x in range(limitX + 1) for y in range(limitY + 1)),
        key=lambda offset: (distanceToOrigin(offset), offset[1], offset[0]),
    )
    for (x, y) in candidates:
        shifted = (footprint[0] + x, footprint[1] + y, footprint[2] + x, footprint[3] + y)
        if not any(cellsOverlap(shifted, cells) for cells in occupied):
            return (x, y)
    return (limitX, 0)

def getOccupiedExtents(
    design: adsk.fusion.Design,
    tagName: str,
    legacyNamePrefix: str,
) -> list[tuple[float, float, float, float]]:
    """World XY extents of every placed instance of tagged bodies, plus untagged ones from before tagging"""
    bodies = [body for (body, _) in tagUtils.findTaggedBodies(design, tagName)]
    for component in design.allComponents:
        for body in component.bRepBodies:
            if body.name.startswith(legacyNamePrefix) and body.attributes.itemByName(tagUtils.TAG_GROUP, tagName) is None:
                bodies.append(body)

    root = design.rootComponent
    extents = []
    for body in bodies:
        if body.parentComponent == root:
            instances = [body]
        else:
            instances = [body.createForAssemblyContext(occurrence) for occurrence in root.allOccurrencesByComponent(body.parentComponent)]
        for instance in instances:
            box = instance.boundingBox
            extents.append((box.minPoint.x, box.minPoint.y, box.maxPoint.x, box.maxPoint.y))
    return extents

def findPlacement(
    design: adsk.fusion.Design,
    tagName: str,
    legacyNamePrefix: str,
    extent: tuple[float, float, float, float],
    cellWidth: float,
    cellLength: float,
) -> tuple[float, float]:
    """XY offset placing an item with the given extent at the origin into a free grid spot"""
    occupied = [extentToCells(occupiedExtent, cellWidth, cellLength) for occupiedExtent in getOccupiedExtents(design, tagName, legacyNamePrefix)]
    (x, y) = findFreeGridOffset(extentToCells(extent, cellWidth, cellLength), occupied, cellWidth, cellLength)
    return (x * cellWidth, y * cellLength)

def moveBodies(
    bodies: list[adsk.fusion.BRepBody],
    offsetX: float,
    offsetY: float,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.MoveFeature:
    moveFeatures = targetComponent.features.moveFeatures
    bodiesToMove = adsk.core.ObjectCollection.create()
    for body in bodies:
        bodiesToMove.add(body)
    moveInput = moveFeatures.createInput2(bodiesToMove)
    moveInput.defineAsTranslateXYZ(
        adsk.core.ValueInput.createByReal(offsetX),
        adsk.core.ValueInput.createByReal(offsetY),
        adsk.core.ValueInput.createByReal(0),
        True,
    )
    return moveFeatures.add(moveInput)
