import adsk.core, adsk.fusion, traceback
import copy
from dataclasses import dataclass, field
import os
import math



from .const import BIN_TAB_EDGE_FILLET_RADIUS
from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from .dim import Dim, valueInput, applyTo
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def tabFilletAllowance(overhangAngle: float, labelAngle: float) -> float:
    """How much wider the profile is than the tab, the front edge is rounded off between the top and the overhang"""
    tipAngle = math.radians(90) - overhangAngle + labelAngle
    return BIN_TAB_EDGE_FILLET_RADIUS / math.tan(tipAngle / 2)

def tabProfileSize(width: float, overhangAngle: float, labelAngle: float) -> tuple[float, float, float]:
    """Width, height at the wall and top drop of the tab profile. The top runs down from the wall towards the front
    by the label angle, the profile is widened for the tab to keep its width after the front edge fillet"""
    profileWidth = width + tabFilletAllowance(overhangAngle, labelAngle)
    topDrop = profileWidth * math.tan(labelAngle)
    return (profileWidth, profileWidth / math.tan(overhangAngle) + topDrop, topDrop)

def createGridfinityBinBodyTab(
    input: BinBodyTabGeneratorInput,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
):
    """The body and all its features are named after the given name"""

    tabProfilePlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    tabProfilePlaneInput.setByOffset(
        targetComponent.yZConstructionPlane,
        valueInput(input.originX)
        )
    tabProfilePlane = targetComponent.constructionPlanes.add(tabProfilePlaneInput)
    tabProfilePlane.name = f'{name} plane'
    tabSketch: adsk.fusion.Sketch = targetComponent.sketches.add(tabProfilePlane)
    tabSketch.name = f'{name} sketch'
    with sketchUtils.deferSketchCompute(tabSketch):
        tabSketchLine = tabSketch.sketchCurves.sketchLines
        tabTopEdgeHeight = input.origin.z - input.topClearance
        (actualTabWidth, actualTabHeight, tabTopDrop) = tabProfileSize(input.width, input.overhangAngle, input.labelAngle)
        line1 = tabSketchLine.addByTwoPoints(
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight)),
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight - actualTabHeight)),
        )
        line2 = tabSketchLine.addByTwoPoints(
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight)),
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y - actualTabWidth, tabTopEdgeHeight - tabTopDrop)),
        )
        line3 = tabSketchLine.addByTwoPoints(
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y, tabTopEdgeHeight - actualTabHeight)),
            tabSketch.modelToSketchSpace(adsk.core.Point3D.create(input.origin.x, input.origin.y - actualTabWidth, tabTopEdgeHeight - tabTopDrop)),
        )

        constraints: adsk.fusion.GeometricConstraints = tabSketch.geometricConstraints
        dimensions: adsk.fusion.SketchDimensions = tabSketch.sketchDimensions

        # horizontal/vertical relative to local sketch XY coordinates
        constraints.addHorizontal(line1)
        if input.labelAngle == 0:
            constraints.addVertical(line2)
        else:
            dimensions.addDistanceDimension(
                line2.startSketchPoint,
                line2.endSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                line2.endSketchPoint.geometry,
                True
                )
        constraints.addCoincident(line1.startSketchPoint, line2.startSketchPoint)
        constraints.addCoincident(line2.endSketchPoint, line3.endSketchPoint)
        constraints.addCoincident(line1.endSketchPoint, line3.startSketchPoint)

        # on the YZ plane sketch vertical runs along the model y and sketch horizontal along the model z
        applyTo(dimensions.addDistanceDimension(
            tabSketch.originPoint,
            line1.startSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            line1.startSketchPoint.geometry,
            True
            ).parameter, input.originY)

        applyTo(dimensions.addDistanceDimension(
            tabSketch.originPoint,
            line1.startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            line1.startSketchPoint.geometry,
            True
            ).parameter, input.originZ - Dim.length(input.topClearance))

        dimensions.addDistanceDimension(
            line2.startSketchPoint,
            line2.endSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            line2.endSketchPoint.geometry,
            True
            )
            
        dimensions.addAngularDimension(
            line1,
            line3,
            line1.endSketchPoint.geometry,
            True,
            )

    tabExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
        tabSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.length,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
        name=name,
    )
    tabBody = tabExtrudeFeature.bodies.item(0)
    tabBody.name = name

    # the front edge, where the top meets the overhang, the top face isn't horizontal on a tilted tab
    roundedEdge = min([edge for edge in tabBody.edges if geometryUtils.isCollinearToX(edge)], key=lambda x: x.boundingBox.minPoint.y)
    fillet = filletUtils.createFillet(
        [roundedEdge],
        BIN_TAB_EDGE_FILLET_RADIUS,
        False,
        targetComponent,
        name=f'{name} edge fillet',
    )

    return tabBody

@dataclass(frozen=True)
class TabCavity:
    """The cavity a tab sits in, its x range, the y of the wall behind the tab and the radius of its rounded corners"""
    minX: Dim
    maxX: Dim
    backY: Dim
    cornerRadius: float

@dataclass(frozen=True)
class TabWallOpenings:
    """Walls a hollow tab is opened through, this deep from their inner face. Sides are only opened where the tab meets them"""
    depth: float
    back: bool = False
    minXSide: bool = False
    maxXSide: bool = False

@dataclass
class TabHollowCuts:
    """Bodies to cut out of a joined tab, the hollow and the openings through each wall around it"""
    hollow: list[adsk.fusion.BRepBody] = field(default_factory=list)
    back: list[adsk.fusion.BRepBody] = field(default_factory=list)
    # the sides take the back wall at the corners along with them
    minXSide: list[adsk.fusion.BRepBody] = field(default_factory=list)
    maxXSide: list[adsk.fusion.BRepBody] = field(default_factory=list)

    def all(self) -> list[adsk.fusion.BRepBody]:
        return self.hollow + self.back + self.minXSide + self.maxXSide

def createTabHollowCuts(
    tabInput: BinBodyTabGeneratorInput,
    minX: Dim,
    maxX: Dim,
    skinThickness: float,
    cavityBody: adsk.fusion.BRepBody,
    cavity: TabCavity,
    openings: TabWallOpenings | None,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
) -> TabHollowCuts:
    """Bodies hollowing out a joined tab running between the given x, cut after the join so the wall behind the tab
    closes the hollow. It's a smaller tab keeping a skin thick top and overhang, trimmed to the cavity the tab is in.
    Its ends only keep a skin where the tab ends inside the cavity, a cavity side wall closes it like the back wall does.
    Openings carry the hollow on through the walls, the back one kept to where the wall is flat, as an opening running
    into the rounded cavity corners would leave slivers along them, the corners are opened along with the sides"""
    cuts = TabHollowCuts()
    (profileWidth, profileHeight, _) = tabProfileSize(tabInput.width, tabInput.overhangAngle, tabInput.labelAngle)
    # the hollow profile is the tab profile with its top and overhang moved in by the skin, the same shape scaled down
    topInset = skinThickness / math.cos(tabInput.labelAngle)
    bottomInset = skinThickness / math.sin(tabInput.overhangAngle)
    hollowHeight = profileHeight - topInset - bottomInset
    hollowWidth = profileWidth * hollowHeight / profileHeight - tabFilletAllowance(tabInput.overhangAngle, tabInput.labelAngle)
    tolerance = const.DEFAULT_FILTER_TOLERANCE
    isOnMinXSide = minX.value <= cavity.minX.value + tolerance
    isOnMaxXSide = maxX.value >= cavity.maxX.value - tolerance
    hollowMinX = minX if isOnMinXSide else minX + Dim.length(skinThickness)
    hollowMaxX = maxX if isOnMaxXSide else maxX - Dim.length(skinThickness)
    hollowLength = hollowMaxX - hollowMinX
    if hollowHeight <= 0 or hollowWidth <= 0 or hollowLength.value <= 0:
        return cuts

    hollowInput = copy.copy(tabInput)
    hollowInput.originX = hollowMinX
    hollowInput.origin = adsk.core.Point3D.create(hollowMinX.value, tabInput.origin.y, tabInput.origin.z)
    hollowInput.length = hollowLength
    hollowInput.width = hollowWidth
    hollowInput.topClearance = tabInput.topClearance + topInset
    hollowBody = createGridfinityBinBodyTab(hollowInput, targetComponent, name=f'{name} hollow')

    features = targetComponent.features
    hollowTrimInput = features.combineFeatures.createInput(hollowBody, commonUtils.objectCollectionFromList([cavityBody]))
    hollowTrimInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    hollowTrimInput.isKeepToolBodies = True
    hollowTrim = features.combineFeatures.add(hollowTrimInput)
    hollowTrim.name = f'{name} hollow trim'
    cuts.hollow = [body for body in list(hollowTrim.bodies) if not body.revisionId == cavityBody.revisionId]
    if openings is None or len(cuts.hollow) == 0:
        return cuts

    margin = 0.1
    tabOriginY = tabInput.originY.value
    hollowTop = tabInput.origin.z - hollowInput.topClearance
    hollowBottomAtOrigin = tabInput.origin.z - tabInput.topClearance - profileHeight + bottomInset
    def overhangZ(y: float) -> float:
        return hollowBottomAtOrigin - (y - tabOriginY) / math.tan(tabInput.overhangAngle)
    # a shallow cavity's floor can cut the hollow short, openings following the overhang would run on below it
    # and through the bottom of the walls, so such a hollow is left closed
    hollowMinZ = min(body.boundingBox.minPoint.z for body in cuts.hollow)
    if hollowMinZ > overhangZ(cavity.backY.value) + tolerance:
        return cuts

    depth = Dim.length(openings.depth)
    isMinXSideOpened = openings.minXSide and isOnMinXSide
    isMaxXSideOpened = openings.maxXSide and isOnMaxXSide
    # openings carry the hollow on through the walls, following its top and overhang. A hollow profile running back to
    # a given y is the hollow one cut back or carried on to it, so it's made the same way as the tab
    def createHollowProfile(profileMinX: Dim, profileMaxX: Dim, backY: Dim, profileName: str) -> adsk.fusion.BRepBody:
        top = hollowTop + (backY.value - tabOriginY) * math.tan(tabInput.labelAngle)
        height = top - overhangZ(backY.value)
        profileWidth = height / (1 / math.tan(tabInput.overhangAngle) + math.tan(tabInput.labelAngle))
        profileInput = copy.copy(hollowInput)
        profileInput.originX = profileMinX
        profileInput.originY = backY
        profileInput.origin = adsk.core.Point3D.create(profileMinX.value, backY.value, tabInput.origin.z)
        profileInput.length = profileMaxX - profileMinX
        profileInput.width = profileWidth - tabFilletAllowance(tabInput.overhangAngle, tabInput.labelAngle)
        profileInput.topClearance = tabInput.origin.z - top
        return createGridfinityBinBodyTab(profileInput, targetComponent, name=f'{name} {profileName}')

    # the back opening is the profile running back to the cut depth, less the one running back to the wall face,
    # which leaves the part within the wall
    openingBackY = cavity.backY + depth
    def createBackOpening(openingMinX: Dim, openingMaxX: Dim, openingName: str) -> list[adsk.fusion.BRepBody]:
        openingBody = createHollowProfile(openingMinX, openingMaxX, openingBackY, openingName)
        # wider than the opening, so the two don't share their end faces
        frontMargin = Dim.length(margin)
        frontBody = createHollowProfile(openingMinX - frontMargin, openingMaxX + frontMargin, cavity.backY, f'{openingName} front')
        trim = combineUtils.cutBody(
            openingBody,
            commonUtils.objectCollectionFromList([frontBody]),
            targetComponent,
            name=f'{name} {openingName} trim',
        )
        return list(trim.bodies)

    flatMinX = cavity.minX + Dim.length(cavity.cornerRadius)
    flatMaxX = cavity.maxX - Dim.length(cavity.cornerRadius)
    openingMinX = hollowMinX if hollowMinX.value >= flatMinX.value else flatMinX
    openingMaxX = hollowMaxX if hollowMaxX.value <= flatMaxX.value else flatMaxX
    if openings.back and (openingMaxX - openingMinX).value > 0:
        cuts.back = createBackOpening(openingMinX, openingMaxX, 'back opening')
    # a side opened along with the back also takes the back wall at the corner between them, so no pillar is left
    if openings.back and isMinXSideOpened:
        cuts.minXSide += createBackOpening(cavity.minX - depth, flatMinX, 'min x corner opening')
    if openings.back and isMaxXSideOpened:
        cuts.maxXSide += createBackOpening(flatMaxX, cavity.maxX + depth, 'max x corner opening')

    # side openings are the hollow profile running back to the back wall carried on through the side walls,
    # they reach into the cavity by its corner radius, taking the rounded corner, where they match the hollow
    sideLength = depth + Dim.length(cavity.cornerRadius)
    if isMinXSideOpened:
        cuts.minXSide += [createHollowProfile(cavity.minX - depth, cavity.minX - depth + sideLength, cavity.backY, 'min x side opening')]
    if isMaxXSideOpened:
        sideMinX = cavity.maxX - Dim.length(cavity.cornerRadius)
        cuts.maxXSide += [createHollowProfile(sideMinX, sideMinX + sideLength, cavity.backY, 'max x side opening')]
    return cuts
