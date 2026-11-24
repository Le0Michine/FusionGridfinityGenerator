import dataclasses

# Rectangles packed close on print beds, as many beds as they need, clear of areas each bed keeps free. Kept free of
# Fusion imports so it can be unit tested. Each bed is filled by maximal free rectangles, a rectangle going where it
# leaves the least of the free space around it, see _score

Size = tuple[float, float]
Rectangle = tuple[float, float, float, float]
# x0, y0, x1, y1
Area = tuple[float, float, float, float]

@dataclasses.dataclass
class Placement:
    bed: int
    # the rectangle's min corner on the bed, after the turn
    x: float
    y: float
    # turned a quarter, its width along y
    turned: bool
    # bigger than the bed, alone on a bed of its own
    fits: bool = True
    # away from the areas the bed keeps free
    clear: bool = True

def _score(free: Rectangle, width: float, length: float) -> tuple[float, float] | None:
    """The space left beside it on its shorter and longer side, none when it doesn't fit"""
    (_, _, freeWidth, freeLength) = free
    if width > freeWidth + 1e-9 or length > freeLength + 1e-9:
        return None
    (left, right) = sorted((freeWidth - width, freeLength - length))
    return (left, right)

def _split(free: Rectangle, used: Rectangle) -> list[Rectangle]:
    """What stays free of the free rectangle around the one used, up to four overlapping rectangles"""
    (fx, fy, fw, fl) = free
    (ux, uy, uw, ul) = used
    if ux >= fx + fw or ux + uw <= fx or uy >= fy + fl or uy + ul <= fy:
        return [free]
    parts = []
    if ux > fx:
        parts.append((fx, fy, ux - fx, fl))
    if ux + uw < fx + fw:
        parts.append((ux + uw, fy, fx + fw - ux - uw, fl))
    if uy > fy:
        parts.append((fx, fy, fw, uy - fy))
    if uy + ul < fy + fl:
        parts.append((fx, uy + ul, fw, fy + fl - uy - ul))
    return parts

def _contains(outer: Rectangle, inner: Rectangle) -> bool:
    return inner[0] >= outer[0] and inner[1] >= outer[1] \
        and inner[0] + inner[2] <= outer[0] + outer[2] and inner[1] + inner[3] <= outer[1] + outer[3]

class _Bed:
    def __init__(self, width: float, length: float):
        self.free: list[Rectangle] = [(0.0, 0.0, width, length)]

    def best(self, width: float, length: float) -> tuple[tuple[float, float], float, float, bool] | None:
        """The best spot, its score, corner and whether turned, unturned when as good"""
        found = None
        for (turned, (w, l)) in ((False, (width, length)), (True, (length, width))):
            for free in self.free:
                score = _score(free, w, l)
                if score is not None and (found is None or score < found[0]):
                    found = (score, free[0], free[1], turned)
        return found

    def use(self, used: Rectangle):
        parts = [part for free in self.free for part in _split(free, used)]
        self.free = [part for (index, part) in enumerate(parts)
            if not any(index != other and _contains(parts[other], part) and (parts[other] != part or other < index) for other in range(len(parts)))]

def _clipped(area: Area, bed: Size) -> Area | None:
    """The part of the area on the bed, none when it's off the bed"""
    clipped = (max(area[0], 0.0), max(area[1], 0.0), min(area[2], bed[0]), min(area[3], bed[1]))
    return clipped if clipped[2] > clipped[0] and clipped[3] > clipped[1] else None

def pack(sizes: list[Size], bed: Size, spacing: float, kept: list[Area] = ()) -> list[Placement]:
    """
    Where each rectangle goes, in the order given, the biggest packed first, each on the first bed it fits. Rectangles
    keep the spacing between them and from the areas kept free on every bed, not from the bed's edges. One bigger than
    the bed, turned or not, gets a bed of its own, one that only fits over a kept area a bed where it isn't clear
    """
    (bedWidth, bedLength) = bed
    areas = [area for area in (_clipped(area, bed) for area in kept) if area is not None]
    def newBed(isKept: bool) -> _Bed:
        packed = _Bed(bedWidth + spacing, bedLength + spacing)
        for (x0, y0, x1, y1) in areas if isKept else []:
            # rectangles are padded on their far sides, so the area is on its near ones
            packed.use((x0, y0, x1 - x0 + spacing, y1 - y0 + spacing))
        return packed
    beds: list[_Bed] = []
    clear: list[bool] = []
    placements: list[Placement | None] = [None] * len(sizes)
    order = sorted(range(len(sizes)), key=lambda index: (-max(sizes[index]), -sizes[index][0] * sizes[index][1], index))
    for index in order:
        (width, length) = sizes[index]
        # the spacing after each rectangle, which the bed's far edges get too
        (paddedWidth, paddedLength) = (width + spacing, length + spacing)
        fitsAsIs = width <= bedWidth + 1e-9 and length <= bedLength + 1e-9
        fitsTurned = length <= bedWidth + 1e-9 and width <= bedLength + 1e-9
        if not fitsAsIs and not fitsTurned:
            beds.append(_Bed(0, 0))
            clear.append(True)
            placements[index] = Placement(len(beds) - 1, 0.0, 0.0, False, False)
            continue
        spot = None
        for (bedIndex, packed) in enumerate(beds):
            found = packed.best(paddedWidth, paddedLength)
            if found is not None:
                spot = (bedIndex, found)
                break
        if spot is None:
            beds.append(newBed(True))
            clear.append(True)
            found = beds[-1].best(paddedWidth, paddedLength)
            if found is None:
                # no room beside the kept areas, the bed is all its own
                beds[-1] = newBed(False)
                clear[-1] = False
                found = beds[-1].best(paddedWidth, paddedLength)
            spot = (len(beds) - 1, found)
        (bedIndex, (_, x, y, turned)) = spot
        beds[bedIndex].use((x, y, paddedLength, paddedWidth) if turned else (x, y, paddedWidth, paddedLength))
        placements[index] = Placement(bedIndex, x, y, turned)
    return [dataclasses.replace(placement, clear=clear[placement.bed]) for placement in placements]

def centered(sizes: list[Size], placements: list[Placement], bed: Size) -> list[Placement]:
    """Each bed's rectangles moved together so they're in the middle of the bed, one bigger than its bed too"""
    moved = list(placements)
    for bedIndex in set(placement.bed for placement in placements):
        indices = [index for (index, placement) in enumerate(placements) if placement.bed == bedIndex]
        extents = []
        for index in indices:
            placement = placements[index]
            (width, length) = sizes[index][::-1] if placement.turned else sizes[index]
            extents.append((placement.x, placement.y, placement.x + width, placement.y + length))
        shiftX = (bed[0] - min(extent[0] for extent in extents) - max(extent[2] for extent in extents)) / 2
        shiftY = (bed[1] - min(extent[1] for extent in extents) - max(extent[3] for extent in extents)) / 2
        for index in indices:
            moved[index] = dataclasses.replace(placements[index], x=placements[index].x + shiftX, y=placements[index].y + shiftY)
    return moved

def bedCount(placements: list[Placement]) -> int:
    return max((placement.bed for placement in placements), default=-1) + 1

def _isClear(sizes: list[Size], placements: list[Placement], areas: list[Area], spacing: float) -> list[bool]:
    """Whether each rectangle keeps the spacing from every area"""
    result = []
    for (size, placement) in zip(sizes, placements):
        (width, length) = size[::-1] if placement.turned else size
        (x0, y0, x1, y1) = (placement.x, placement.y, placement.x + width, placement.y + length)
        result.append(not any(
            x0 < area[2] + spacing - 1e-9 and x1 > area[0] - spacing + 1e-9 and y0 < area[3] + spacing - 1e-9 and y1 > area[1] - spacing + 1e-9
            for area in areas
        ))
    return result

def _bands(areas: list[Area], bed: Size, axis: int) -> list[Area]:
    """
    Each area widened to a band across the bed, at the edge it's nearest to and mirrored at the opposite edge: whatever
    lies between the bands stays between them when centered, see centered
    """
    length = bed[axis]
    bands = []
    for area in areas:
        (low, high) = (area[axis], area[axis + 2])
        depth = high if low <= length - high else length - low
        if axis == 0:
            bands += [(0.0, 0.0, depth, bed[1]), (length - depth, 0.0, length, bed[1])]
        else:
            bands += [(0.0, 0.0, bed[0], depth), (0.0, length - depth, bed[0], length)]
    return bands

def _grown(areas: list[Area], byX: float, byY: float) -> list[Area]:
    return [(x0 - byX, y0 - byY, x1 + byX, y1 + byY) for (x0, y0, x1, y1) in areas]

# how often a plate is packed again around areas grown by how far centering moved its bodies
CENTERING_TRIES = 4

def _fillBed(sizes: list[Size], bed: Size, spacing: float, areas: list[Area]) -> list[Placement]:
    """
    What goes on one bed, centered, and where, the first rectangles that fit, clear of the areas when they can be.
    The slicers center a plate's bodies on the bed as a group, so the bodies have to be clear once centered: they're
    packed around the areas, around them grown by how far centering moved the bodies, or between bands across the bed,
    see _bands, whichever takes the most of the bed. Placements of the rectangles that don't go on this bed have
    bed -1
    """
    def onFirstBed(blocked: list[Area]) -> list[Placement]:
        placements = pack(sizes, bed, spacing, blocked)
        first = [index for (index, placement) in enumerate(placements) if placement.bed == 0]
        moved = centered([sizes[index] for index in first], [placements[index] for index in first], bed)
        result = [dataclasses.replace(placement, bed=-1) for placement in placements]
        for (index, placement) in zip(first, moved):
            result[index] = placement
        clear = _isClear(sizes, result, areas, spacing)
        return [dataclasses.replace(placement, clear=isClear or not placement.fits) for (placement, isClear) in zip(result, clear)]
    def isClear(placements: list[Placement]) -> bool:
        return all(placement.clear for placement in placements if placement.bed == 0)
    def used(placements: list[Placement]) -> float:
        return sum(size[0] * size[1] for (size, placement) in zip(sizes, placements) if placement.bed == 0)
    first = onFirstBed(areas)
    if not areas or isClear(first):
        return first
    tries = []
    (byX, byY) = (0.0, 0.0)
    placements = first
    for _ in range(CENTERING_TRIES):
        # the bodies moved toward the areas by up to the centering's shift, the areas grow by as much
        before = pack(sizes, bed, spacing, _grown(areas, byX, byY))
        shifts = [(after.x - packed.x, after.y - packed.y) for (packed, after) in zip(before, placements) if after.bed == 0 and packed.bed == 0]
        if not shifts:
            break
        byX += abs(shifts[0][0])
        byY += abs(shifts[0][1])
        placements = onFirstBed(_grown(areas, byX, byY))
        tries.append(placements)
        if isClear(placements):
            break
    tries += [onFirstBed(_bands(areas, bed, axis)) for axis in (0, 1)]
    found = [placements for placements in tries if isClear(placements) and used(placements) > 0]
    # without a way to keep them clear, they're packed around the areas, the slicer moves them on one
    return max(found, key=used) if found else first

def arrangeGroups(boxes: list[Area], groups: list[list[int]], bed: Size, spacing: float, margin: float, kept: list[Area] = ()) -> list[Placement]:
    """
    Bodies that go together, as the letters of an inlaid label with their bin, arranged as one: the box around each
    group of indices into boxes is arranged, see arrange, and its bodies keep where they are in it, turned with it.
    Boxes are x0, y0, x1, y1 as the bodies lie, a placement for each, in their order
    """
    groupBoxes = [
        (min(boxes[index][0] for index in group), min(boxes[index][1] for index in group),
         max(boxes[index][2] for index in group), max(boxes[index][3] for index in group))
        for group in groups
    ]
    groupPlacements = arrange([(x1 - x0, y1 - y0) for (x0, y0, x1, y1) in groupBoxes], bed, spacing, margin, kept)
    placements: list[Placement | None] = [None] * len(boxes)
    for (group, (groupX0, groupY0, _, groupY1), placement) in zip(groups, groupBoxes, groupPlacements):
        for index in group:
            (x0, y0, _, y1) = boxes[index]
            # a quarter turned counterclockwise, x and y become -y and x, the box's corner goes with the group's
            (offsetX, offsetY) = (groupY1 - y1, x0 - groupX0) if placement.turned else (x0 - groupX0, y0 - groupY0)
            placements[index] = dataclasses.replace(placement, x=placement.x + offsetX, y=placement.y + offsetY)
    return placements

def arrange(sizes: list[Size], bed: Size, spacing: float, margin: float, kept: list[Area] = ()) -> list[Placement]:
    """
    Packed and centered on the bed less the margin along its edges, clear of the areas kept free once the slicer
    centers each plate, see pack and _fillBed, corners from the bed's. Bodies that can't be kept clear are packed around
    the areas and centered, those that end up on an area are not clear
    """
    inner = (max(bed[0] - 2 * margin, 0.0), max(bed[1] - 2 * margin, 0.0))
    areas = [area for area in ((x0 - margin, y0 - margin, x1 - margin, y1 - margin) for (x0, y0, x1, y1) in kept) for area in [_clipped(area, inner)] if area is not None]
    if not areas:
        placements = centered(sizes, pack(sizes, inner, spacing), inner)
    else:
        placements: list[Placement | None] = [None] * len(sizes)
        remaining = list(range(len(sizes)))
        bedIndex = 0
        while remaining:
            filled = _fillBed([sizes[index] for index in remaining], inner, spacing, areas)
            for (index, placement) in zip(remaining, filled):
                if placement.bed == 0:
                    placements[index] = dataclasses.replace(placement, bed=bedIndex)
            remaining = [index for (index, placement) in zip(remaining, filled) if placement.bed != 0]
            bedIndex += 1
    return [dataclasses.replace(placement, x=placement.x + margin, y=placement.y + margin) for placement in placements]
