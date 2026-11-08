import math
from dataclasses import dataclass

# keeps sizes that exactly match the bed or a whole number of cells from being rejected by float noise
FIT_TOLERANCE = 1e-6

class FillLayoutError(ValueError):
    pass

# where the grid goes along an axis, the padding takes the rest of the space
ALIGN_START = 'start'
ALIGN_CENTER = 'center'
ALIGN_END = 'end'

@dataclass(frozen=True)
class AxisLayout:
    cells: int
    paddingStart: float
    paddingEnd: float
    # a row of half cells past the whole ones, between them and the padding
    hasHalfCellsStart: bool
    hasHalfCellsEnd: bool
    # cells of each piece along the axis, from the axis start
    pieces: tuple[int, ...]

    def startExtent(self, baseUnit: float) -> float:
        """How far the plate reaches past the whole cells at the start, apart from the xy clearance"""
        return self.paddingStart + (baseUnit / 2 if self.hasHalfCellsStart else 0)

    def endExtent(self, baseUnit: float) -> float:
        return self.paddingEnd + (baseUnit / 2 if self.hasHalfCellsEnd else 0)

@dataclass(frozen=True)
class FillPiece:
    column: int
    row: int
    cellOffsetX: int
    cellOffsetY: int
    cellsX: int
    cellsY: int
    isLeftEdge: bool
    isRightEdge: bool
    isBottomEdge: bool
    isTopEdge: bool

@dataclass(frozen=True)
class FillLayout:
    x: AxisLayout
    y: AxisLayout
    # pieces are laid on the bed turned by 90 degrees
    isBedRotated: bool
    pieces: tuple[FillPiece, ...]

def fitAxis(span: float, baseUnit: float, xyClearance: float, alignment: str, useHalfCells: bool) -> tuple[int, float, float, bool, bool]:
    """Most whole cells a plate spanning the given length holds, then a row of half cells if asked for and it fits,
    on the side the grid isn't pushed to. Returns the cells, the padding on both ends and where the half cells go.
    A plate without padding is its cells less the xy clearance on both sides"""
    cells = math.floor((span + xyClearance * 2) / baseUnit + FIT_TOLERANCE)
    leftover = span - (cells * baseUnit - xyClearance * 2)
    (hasHalfCellsStart, hasHalfCellsEnd) = (False, False)
    if useHalfCells and leftover + FIT_TOLERANCE >= baseUnit / 2:
        leftover -= baseUnit / 2
        if alignment == ALIGN_END:
            hasHalfCellsStart = True
        else:
            hasHalfCellsEnd = True
    leftover = max(0, leftover)
    if alignment == ALIGN_START:
        (paddingStart, paddingEnd) = (0, leftover)
    elif alignment == ALIGN_END:
        (paddingStart, paddingEnd) = (leftover, 0)
    else:
        (paddingStart, paddingEnd) = (leftover / 2, leftover / 2)
    return (cells, paddingStart, paddingEnd, hasHalfCellsStart, hasHalfCellsEnd)

def splitAxis(cells: int, startExtent: float, endExtent: float, baseUnit: float, xyClearance: float, bedSize: float) -> tuple[int, ...] | None:
    """Fewest pieces fitting the bed, cells spread as evenly as possible with the bigger pieces in the middle,
    as the edge pieces also carry what the plate reaches past the whole cells. Inner piece sides have no padding,
    so like a plain plate they stay the xy clearance short of the cell border and pieces keep the same gap between them as bins"""
    for count in range(1, cells + 1):
        def capacity(index: int) -> int:
            extra = (startExtent if index == 0 else 0) + (endExtent if index == count - 1 else 0) - xyClearance * 2
            return math.floor((bedSize - extra) / baseUnit + FIT_TOLERANCE)
        capacities = [capacity(index) for index in range(count)]
        if min(capacities) < 1 or sum(capacities) < cells:
            continue
        sizes = [1] * count
        center = (count - 1) / 2
        for _ in range(cells - count):
            index = min(
                (index for index in range(count) if sizes[index] < capacities[index]),
                key=lambda index: (sizes[index], abs(index - center), index),
            )
            sizes[index] += 1
        return tuple(sizes)
    return None

def layoutAxis(span: float, baseUnit: float, xyClearance: float, alignment: str, useHalfCells: bool, bedSize: float) -> AxisLayout | None:
    (cells, paddingStart, paddingEnd, hasHalfCellsStart, hasHalfCellsEnd) = fitAxis(span, baseUnit, xyClearance, alignment, useHalfCells)
    unsplit = AxisLayout(cells, paddingStart, paddingEnd, hasHalfCellsStart, hasHalfCellsEnd, ())
    pieces = splitAxis(cells, unsplit.startExtent(baseUnit), unsplit.endExtent(baseUnit), baseUnit, xyClearance, bedSize)
    return None if pieces is None else AxisLayout(cells, paddingStart, paddingEnd, hasHalfCellsStart, hasHalfCellsEnd, pieces)

def computeFillLayout(
    areaWidth: float,
    areaLength: float,
    fitTolerance: float,
    bedWidth: float,
    bedLength: float,
    bedMargin: float,
    baseWidth: float,
    baseLength: float,
    xyClearance: float,
    alignmentX: str = ALIGN_CENTER,
    alignmentY: str = ALIGN_CENTER,
    useHalfCells: bool = False,
) -> FillLayout:
    """Grid filling the area less the fit tolerance, aligned as asked and split into pieces fitting the print bed.
    The bed is tried both ways round, the one needing fewer pieces wins"""
    spanX = areaWidth - fitTolerance
    spanY = areaLength - fitTolerance
    if fitAxis(spanX, baseWidth, xyClearance, alignmentX, False)[0] < 1 or fitAxis(spanY, baseLength, xyClearance, alignmentY, False)[0] < 1:
        raise FillLayoutError('The area is too small to fit a single cell')
    usableWidth = bedWidth - bedMargin * 2
    usableLength = bedLength - bedMargin * 2

    candidates: list[tuple[AxisLayout, AxisLayout, bool]] = []
    for (bedX, bedY, isBedRotated) in [(usableWidth, usableLength, False), (usableLength, usableWidth, True)]:
        x = layoutAxis(spanX, baseWidth, xyClearance, alignmentX, useHalfCells, bedX)
        y = layoutAxis(spanY, baseLength, xyClearance, alignmentY, useHalfCells, bedY)
        if x is not None and y is not None:
            candidates.append((x, y, isBedRotated))
    if len(candidates) == 0:
        raise FillLayoutError('The print bed is too small to fit a single cell with the side padding')
    (x, y, isBedRotated) = min(candidates, key=lambda candidate: len(candidate[0].pieces) * len(candidate[1].pieces))

    pieces = []
    for (row, cellsY) in enumerate(y.pieces):
        for (column, cellsX) in enumerate(x.pieces):
            pieces.append(FillPiece(
                column=column,
                row=row,
                cellOffsetX=sum(x.pieces[:column]),
                cellOffsetY=sum(y.pieces[:row]),
                cellsX=cellsX,
                cellsY=cellsY,
                isLeftEdge=column == 0,
                isRightEdge=column == len(x.pieces) - 1,
                isBottomEdge=row == 0,
                isTopEdge=row == len(y.pieces) - 1,
            ))
    return FillLayout(x, y, isBedRotated, tuple(pieces))

def pieceShapeKey(piece: FillPiece) -> tuple:
    """Pieces with the same key are identical, what a piece has past its whole cells only depends on its edges"""
    return (piece.cellsX, piece.cellsY, piece.isLeftEdge, piece.isRightEdge, piece.isBottomEdge, piece.isTopEdge)

def pieceOutline(layout: FillLayout, piece: FillPiece, baseWidth: float, baseLength: float, xyClearance: float) -> tuple[float, float, float, float]:
    """XY extent (minX, minY, maxX, maxY) of an assembled piece, in the generator coordinates where a plate without
    padding starts at the origin. Like such a plate, a piece is the xy clearance short of its cells on both sides"""
    def axisOutline(axis: AxisLayout, cellOffset: int, cells: int, baseUnit: float, isStartEdge: bool, isEndEdge: bool) -> tuple[float, float]:
        start = cellOffset * baseUnit - (axis.startExtent(baseUnit) if isStartEdge else 0)
        end = (cellOffset + cells) * baseUnit - xyClearance * 2 + (axis.endExtent(baseUnit) if isEndEdge else 0)
        return (start, end)
    (minX, maxX) = axisOutline(layout.x, piece.cellOffsetX, piece.cellsX, baseWidth, piece.isLeftEdge, piece.isRightEdge)
    (minY, maxY) = axisOutline(layout.y, piece.cellOffsetY, piece.cellsY, baseLength, piece.isBottomEdge, piece.isTopEdge)
    return (minX, minY, maxX, maxY)

def layoutOutline(layout: FillLayout, baseWidth: float, baseLength: float, xyClearance: float) -> tuple[float, float, float, float]:
    """XY extent of the whole assembled fill, in the same coordinates as the pieces"""
    outlines = [pieceOutline(layout, piece, baseWidth, baseLength, xyClearance) for piece in layout.pieces]
    return (
        min(outline[0] for outline in outlines),
        min(outline[1] for outline in outlines),
        max(outline[2] for outline in outlines),
        max(outline[3] for outline in outlines),
    )
