import os
import adsk.core, adsk.fusion

from . import const, commonUtils, combineUtils
from .dim import Dim, valueInput

LABEL_STYLE_OUTLINE = 'Outline'
LABEL_STYLE_ENGRAVED = 'Engraved'
LABEL_STYLE_EMBOSSED = 'Embossed'
LABEL_STYLES = [LABEL_STYLE_OUTLINE, LABEL_STYLE_ENGRAVED, LABEL_STYLE_EMBOSSED]

LABEL_ICON_NONE = 'None'
LABEL_ICONS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'labelIcons')

# icons are grouped by type in folders, these types come first in this order, any others after them
LABEL_ICON_TYPE_ORDER = ['screws', 'nuts', 'washers']

def iconName(fileName: str) -> str:
    """hex-nut.svg shows as Hex nut"""
    return os.path.splitext(fileName)[0].replace('-', ' ').capitalize()

class LabelIcon():
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path

    @property
    def previewFolder(self) -> str:
        """Dropdown preview images, rendered by tools/labelIcons.py, empty when there are none"""
        folder = os.path.splitext(self.path)[0]
        return folder if os.path.isfile(os.path.join(folder, '16x16.png')) else ''

def listIconGroups() -> list[list[LabelIcon]]:
    """Icons grouped by type in the order shown, svg files outside a type folder come last"""
    if not os.path.isdir(LABEL_ICONS_FOLDER):
        return []
    def svgIcons(folder: str) -> list[LabelIcon]:
        fileNames = sorted(fileName for fileName in os.listdir(folder) if fileName.lower().endswith('.svg'))
        return [LabelIcon(iconName(fileName), os.path.join(folder, fileName)) for fileName in fileNames]
    types = [entry for entry in os.listdir(LABEL_ICONS_FOLDER) if os.path.isdir(os.path.join(LABEL_ICONS_FOLDER, entry))]
    types.sort(key=lambda entry: (LABEL_ICON_TYPE_ORDER.index(entry) if entry in LABEL_ICON_TYPE_ORDER else len(LABEL_ICON_TYPE_ORDER), entry))
    groups = [svgIcons(os.path.join(LABEL_ICONS_FOLDER, entry)) for entry in types] + [svgIcons(LABEL_ICONS_FOLDER)]
    return [group for group in groups if len(group) > 0]

def iconPath(name: str) -> str | None:
    return next((icon.path for group in listIconGroups() for icon in group if icon.name == name), None)

class BinLabelDefinition():
    """What goes on one label tab, the text parameter drives the text so it can be edited later"""
    def __init__(self, textParameter: adsk.fusion.UserParameter = None, iconPath: str = None):
        self.textParameter = textParameter
        self.iconPath = iconPath

    @property
    def isEmpty(self) -> bool:
        return self.textParameter is None and self.iconPath is None

class BinLabelInput():
    def __init__(self):
        self.style = LABEL_STYLE_OUTLINE
        self.isBold = True
        self.depth = const.BIN_LABEL_DEPTH
        self.definition: BinLabelDefinition = None
        # label area on the tab top face, the dims let it follow the parameters
        self.originX: Dim = None
        self.originY: Dim = None
        self.originZ: Dim = None
        self.width: float = 0
        self.length: float = 0

def _curveBounds(curves) -> tuple[float, float, float, float] | None:
    """Min and max x and y over sampled points of the given geometry curves"""
    bounds = None
    for curve in curves:
        evaluator = curve.evaluator
        (_, start, end) = evaluator.getParameterExtents()
        parameters = [start + (end - start) * i / 16 for i in range(17)]
        (_, points) = evaluator.getPointsAtParameters(parameters)
        for point in points:
            if bounds is None:
                bounds = [point.x, point.y, point.x, point.y]
            bounds = [min(bounds[0], point.x), min(bounds[1], point.y), max(bounds[2], point.x), max(bounds[3], point.y)]
    return tuple(bounds) if bounds is not None else None

def _sketchCurvesBounds(sketch: adsk.fusion.Sketch) -> tuple[float, float, float, float] | None:
    return _curveBounds([curve.geometry for curve in sketch.sketchCurves])

def _addText(
    sketch: adsk.fusion.Sketch,
    text: str,
    height: float,
    corner: adsk.core.Point3D,
    diagonal: adsk.core.Point3D,
    isBold: bool,
    isCentered: bool,
) -> adsk.fusion.SketchText:
    textInput = sketch.sketchTexts.createInput2(text, height)
    textInput.setAsMultiLine(
        corner,
        diagonal,
        adsk.core.HorizontalAlignments.CenterHorizontalAlignment if isCentered else adsk.core.HorizontalAlignments.LeftHorizontalAlignment,
        adsk.core.VerticalAlignments.MiddleVerticalAlignment,
        0,
    )
    if isBold:
        textInput.textStyle = adsk.fusion.TextStyles.TextStyleBold
    return sketch.sketchTexts.add(textInput)

def _measureText(sketch: adsk.fusion.Sketch, text: str, height: float, isBold: bool) -> tuple[float, float] | None:
    """Width and height of the letters at the given text height, measured on a throwaway text
    with a box wide enough not to wrap"""
    origin = adsk.core.Point3D.create(0, 0, 0)
    probe = _addText(sketch, text, height, origin, adsk.core.Point3D.create(height * len(text) * 10, height * 10, 0), isBold, False)
    bounds = _curveBounds(probe.asCurves())
    probe.deleteMe()
    return None if bounds is None else (bounds[2] - bounds[0], bounds[3] - bounds[1])

def _iconProfiles(sketch: adsk.fusion.Sketch) -> list[adsk.fusion.Profile]:
    """Filled regions of the icon, profiles nested an odd number of times are its holes"""
    profiles = list(sketch.profiles)
    def contains(outer: adsk.fusion.Profile, inner: adsk.fusion.Profile) -> bool:
        a = outer.boundingBox
        b = inner.boundingBox
        tolerance = const.DEFAULT_FILTER_TOLERANCE
        return outer != inner \
            and a.minPoint.x <= b.minPoint.x + tolerance and a.minPoint.y <= b.minPoint.y + tolerance \
            and a.maxPoint.x >= b.maxPoint.x - tolerance and a.maxPoint.y >= b.maxPoint.y - tolerance \
            and (a.maxPoint.x - a.minPoint.x) * (a.maxPoint.y - a.minPoint.y) > (b.maxPoint.x - b.minPoint.x) * (b.maxPoint.y - b.minPoint.y)
    return [profile for profile in profiles if sum(1 for other in profiles if contains(other, profile)) % 2 == 0]

def _importMeasured(sketch: adsk.fusion.Sketch, path: str, x: float, y: float, scale: float, keep: bool = False) -> tuple[float, float, float, float] | None:
    """Bounds of the svg imported at the given position and scale, removed again unless kept"""
    sketch.importSVG(path, x, y, scale)
    bounds = _sketchCurvesBounds(sketch)
    if not keep:
        for curve in list(sketch.sketchCurves):
            if curve.isValid:
                curve.deleteMe()
    return bounds

def _iconAspect(sketch: adsk.fusion.Sketch, path: str) -> float | None:
    """Width of the drawn icon per unit of its height"""
    bounds = _importMeasured(sketch, path, 0, 0, 1)
    if bounds is None or bounds[3] - bounds[1] <= 0:
        return None
    return (bounds[2] - bounds[0]) / (bounds[3] - bounds[1])

def _importIcon(sketch: adsk.fusion.Sketch, path: str, minX: float, minY: float, height: float):
    """Imports the svg scaled to the given height with its bottom left corner at the given point.
    How the svg units and import position map to the sketch isn't documented, so the svg is imported
    to measure both and then imported where it belongs"""
    bounds = _importMeasured(sketch, path, 0, 0, 1)
    if bounds is None:
        return
    scale = height / (bounds[3] - bounds[1])
    scaled = _importMeasured(sketch, path, 0, 0, scale)
    # the position moves the import by a unit step in each direction, one way or the other
    stepped = _importMeasured(sketch, path, 1, 1, scale)
    directionX = 1 if stepped[0] >= scaled[0] else -1
    directionY = 1 if stepped[1] >= scaled[1] else -1
    targetMinX = minX
    targetMinY = minY
    placed = _importMeasured(sketch, path, (targetMinX - scaled[0]) * directionX, (targetMinY - scaled[1]) * directionY, scale, keep=True)
    commonUtils.debugLog(f'icon {os.path.basename(path)} placed at {placed[0]:.3f}, {placed[1]:.3f}, expected {targetMinX:.3f}, {targetMinY:.3f}')

def createLabel(
    input: BinLabelInput,
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> adsk.fusion.BRepBody:
    """Icon at the left as tall as the letters of the text after it, standing on their bottom, text alone is centered. Built as a separate body at the current label spot and
    moved by how far the parametric spot is from it, then cut from or joined to the target body.
    Planes, sketches and features are named after the given name"""
    features = targetComponent.features
    labelPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    labelPlaneInput.setByOffset(targetComponent.xYConstructionPlane, valueInput(input.originZ))
    labelPlane = targetComponent.constructionPlanes.add(labelPlaneInput)
    labelPlane.name = f'{name} plane'
    labelPlane.isLightBulbOn = False

    margin = const.BIN_LABEL_MARGIN
    contentMinX = input.originX.value + const.BIN_LABEL_SIDE_MARGIN
    contentMinY = input.originY.value + margin
    contentWidth = input.width - const.BIN_LABEL_SIDE_MARGIN * 2
    contentHeight = input.length - margin * 2
    profiles = adsk.core.ObjectCollection.create()
    iconPath = input.definition.iconPath
    textParameter = input.definition.textParameter
    text = textParameter.textValue if textParameter is not None else ''
    gap = const.BIN_LABEL_ICON_GAP if iconPath is not None else 0

    iconAspect = 0
    if iconPath is not None:
        iconSketch: adsk.fusion.Sketch = targetComponent.sketches.add(labelPlane)
        iconSketch.name = f'{name} icon sketch'
        iconAspect = _iconAspect(iconSketch, iconPath) or 1

    # the icon is as tall as the letters, so both grow and shrink together. Letters start as tall as
    # the label allows, then everything scales down until the icon, gap and text fit the label width
    iconSize = contentHeight * const.BIN_LABEL_TEXT_HEIGHT_RATIO
    textWidth = 0
    if len(text) > 0:
        textSketch: adsk.fusion.Sketch = targetComponent.sketches.add(labelPlane)
        textSketch.name = f'{name} text sketch'
        textHeight = contentHeight
        measured = _measureText(textSketch, text, textHeight, input.isBold)
        if measured is not None and measured[1] > 0:
            (measuredWidth, measuredHeight) = measured
            iconShare = measuredHeight * iconAspect
            scale = min(
                contentHeight * const.BIN_LABEL_TEXT_HEIGHT_RATIO / measuredHeight,
                (contentWidth - gap) / (measuredWidth + iconShare),
            )
            textHeight *= scale
            textWidth = measuredWidth * scale
            iconSize = measuredHeight * scale
    elif iconPath is not None:
        iconSize = min(contentHeight, contentWidth / iconAspect)

    # an icon starts at the side with the text after it, text alone is centered
    groupMinX = contentMinX
    iconMinY = contentMinY + (contentHeight - iconSize) / 2

    if len(text) > 0:
        textMinX = groupMinX + (iconSize * iconAspect + gap if iconPath is not None else 0)
        sketchText = _addText(
            textSketch,
            text,
            textHeight,
            adsk.core.Point3D.create(textMinX, contentMinY, 0),
            adsk.core.Point3D.create(contentMinX + contentWidth, contentMinY + contentHeight, 0),
            input.isBold,
            iconPath is None,
        )
        sketchText.textParameter.expression = textParameter.name
        profiles.add(sketchText)
        # the icon stands on the bottom of the letters as they came out
        letterBounds = _curveBounds(sketchText.asCurves())
        if letterBounds is not None:
            iconMinY = letterBounds[1]

    if iconPath is not None:
        _importIcon(iconSketch, iconPath, groupMinX, iconMinY, iconSize)
        for profile in _iconProfiles(iconSketch):
            profiles.add(profile)

    if profiles.count == 0:
        return None

    isEmbossed = input.style == LABEL_STYLE_EMBOSSED
    def extrudeLabel(isThin: bool) -> adsk.fusion.ExtrudeFeature:
        extrudeInput = features.extrudeFeatures.createInput(profiles, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extrudeInput.setOneSideExtent(
            adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(input.depth)),
            adsk.fusion.ExtentDirections.PositiveExtentDirection if isEmbossed else adsk.fusion.ExtentDirections.NegativeExtentDirection,
        )
        if isThin:
            extrudeInput.setThinExtrude(
                adsk.fusion.ThinExtrudeWallLocation.Center,
                adsk.core.ValueInput.createByReal(const.BIN_LABEL_OUTLINE_THICKNESS),
            )
        return features.extrudeFeatures.add(extrudeInput)
    if input.style == LABEL_STYLE_OUTLINE:
        try:
            labelExtrude = extrudeLabel(True)
        except RuntimeError as err:
            commonUtils.debugLog(f'{name}: outline extrude failed, engraving instead, {err}')
            labelExtrude = extrudeLabel(False)
    else:
        labelExtrude = extrudeLabel(False)
    labelExtrude.name = name
    labelBodies = list(labelExtrude.bodies)
    for body in labelBodies:
        body.name = name

    # the label is laid out at the current spot, the move follows the parameters from there
    shiftX = input.originX - Dim.length(input.originX.value)
    shiftY = input.originY - Dim.length(input.originY.value)
    if shiftX.isExpression or shiftY.isExpression:
        moveInput = features.moveFeatures.createInput2(commonUtils.objectCollectionFromList(labelBodies))
        moveInput.defineAsTranslateXYZ(valueInput(shiftX), valueInput(shiftY), adsk.core.ValueInput.createByReal(0), True)
        moveFeature = features.moveFeatures.add(moveInput)
        moveFeature.name = f'{name} placement'

    if isEmbossed:
        combineUtils.joinBodies(targetBody, commonUtils.objectCollectionFromList(labelBodies), targetComponent, name=f'{name} join')
    else:
        combineUtils.cutBody(targetBody, commonUtils.objectCollectionFromList(labelBodies), targetComponent, name=f'{name} cut')
    commonUtils.debugLog(f'{name}: {input.style.lower()}, text parameter {textParameter.name if textParameter is not None else None}, icon {input.definition.iconPath}')
    return targetBody
