"""
Bin sizes in base units, whole or ending in a half. A half grid bin stands on half size feet all over. Otherwise
a half left over gets a row of half feet along the far side, halved across the row only like the half cells of a
baseplate, see baseGenerator.createFootGrid
"""

import math

_TOLERANCE = 1e-6

def isHalfStep(size: float) -> bool:
    """Whole or ending in a half"""
    return abs(size * 2 - round(size * 2)) < _TOLERANCE

def isWhole(size: float) -> bool:
    return abs(size - round(size)) < _TOLERANCE

def splitHalf(cells: float) -> tuple[int, bool]:
    """Whole cells and whether a half one is left over"""
    whole = math.floor(cells + _TOLERANCE)
    return (whole, cells - whole > _TOLERANCE)

def feetPerUnit(isHalfGrid: bool) -> int:
    """Feet along a base unit"""
    return 2 if isHalfGrid else 1

def outlineDivisions(width: float, length: float, isHalfGrid: bool) -> int:
    """
    Grid cells per base unit of the bin outline, for its shape and creases. Half cells when the grid or a size has
    halves, so the outline still runs along cell lines
    """
    return 2 if isHalfGrid or not (isWhole(width) and isWhole(length)) else 1

def footSpans(cells: float) -> list[tuple[float, float]]:
    """Start and size of the feet along a side the given grid cells long, a half one last"""
    (whole, hasHalf) = splitHalf(cells)
    spans = [(float(index), 1.0) for index in range(whole)]
    if hasHalf:
        spans.append((float(whole), 0.5))
    return spans

def outlineCellsPerFoot(width: float, length: float, isHalfGrid: bool) -> int:
    """
    Cells of the outline grid along a whole foot, two for a whole grid bin ending in a half, its half feet take one.
    A shape is drawn in feet, see binShape.footShapeToOutline
    """
    return outlineDivisions(width, length, isHalfGrid) // feetPerUnit(isHalfGrid)

def footLines(cells: float, cellsPerFoot: int) -> set[int]:
    """Lines of the outline grid where feet meet or the grid ends, along a side the given feet long"""
    total = round(cells * cellsPerFoot)
    return {min(index * cellsPerFoot, total) for index in range(math.ceil(cells - _TOLERANCE) + 1)}

def formatSize(size: float) -> str:
    """2 or 2.5, as the dialog shows it"""
    return f'{round(size * 2) / 2:g}'
