import adsk.core, adsk.fusion
import copy

from ...lib import tagUtils
from ...lib import configJson
from ...lib import placementUtils
from ...lib.gridfinityUtils import combineUtils
from ...lib.gridfinityUtils import geometryUtils
from ...lib.gridfinityUtils import faceUtils
from ...lib.gridfinityUtils import shellUtils
from ...lib.gridfinityUtils import commonUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils import parameterUtils
from ...lib.gridfinityUtils import sharedParameters
from ...lib.gridfinityUtils.dim import Dim
from ...lib.gridfinityUtils.baseGenerator import createFootGrid, cutBaseClearance, cutWallJunctionPockets, footCenters, createCellJointOrigins, keepBodiesInCells, cutOutsideShape, cutShapeWallJunctionPockets
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.binBodyGenerator import createGridfinityBinBody, createShapeCavity, binBodyTopHeight, createCompartmentCutout, compartmentCutoutFilletRadius, tabTopClearance, createTabLabel, hollowTabWallThickness
from ...lib.gridfinityUtils import labelGenerator
from ...lib.gridfinityUtils import compartmentLayout
from ...lib.gridfinityUtils import binShape
from ...lib.gridfinityUtils import binGrid
from ...lib.gridfinityUtils import wallCreases
from ...lib.gridfinityUtils.wallCreaseGenerator import createCreaseFolds
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput, BinBodyCompartmentDefinition
from ...lib.gridfinityUtils.binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from ...lib.gridfinityUtils.binBodyTabGenerator import createGridfinityBinBodyTab, createTabHollowCuts, TabCavity, TabWallOpenings
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException
from .inputState import InputState

# Builds bins from an InputState, without the dialog, so the same settings always build the same bin

LOG_PREFIX = 'Gridfinity bin'

BIN_TYPE_HOLLOW = 'Hollow'
BIN_TYPE_SHELLED = 'Shelled'
BIN_TYPE_SOLID = 'Solid'

# default name of bins generated before tagging, keep as is even if the naming changes
BIN_LEGACY_NAME_PREFIX = 'Gridfinity bin '

# User parameter names are stored in user documents, keep these literal
BIN_PARAMETER_BASE_NAME = 'gfBin'
BIN_HEIGHT_PARAMETER = 'heightU'
BIN_LABEL_PARAMETER = 'label'
# per bin fallback for the shared height unit
BIN_HEIGHT_UNIT_PARAMETER = 'heightUnit'
BIN_PARAMETERS = [BIN_HEIGHT_PARAMETER, BIN_HEIGHT_UNIT_PARAMETER, sharedParameters.BASE_WIDTH_FALLBACK_PARAMETER, sharedParameters.BASE_LENGTH_FALLBACK_PARAMETER]

def binDisplayName(state: InputState) -> str:
    return 'Gridfinity bin {}x{}x{}{}'.format(
        binGrid.formatSize(state.binLength),
        binGrid.formatSize(state.binWidth),
        int(state.binHeight),
        ' half grid' if state.isHalfGrid else '',
    )

def gridDivisions(state: InputState) -> int:
    """Grid cells per base unit of the bin outline, see binGrid.outlineDivisions"""
    return binGrid.outlineDivisions(state.binWidth, state.binLength, state.isHalfGrid)

def feetSize(state: InputState) -> tuple[float, float]:
    """The bin size in feet, half ones in a half grid, ending in a half foot for a whole grid bin ending in a half"""
    feetPerUnit = binGrid.feetPerUnit(state.isHalfGrid)
    return (state.binWidth * feetPerUnit, state.binLength * feetPerUnit)

def feetGridSize(state: InputState) -> tuple[int, int]:
    """Columns and rows of feet, the shape is drawn in, a half foot counts as one"""
    (columns, rows) = feetSize(state)
    return (len(binGrid.footSpans(columns)), len(binGrid.footSpans(rows)))

def outlineCellsPerFoot(state: InputState) -> int:
    return binGrid.outlineCellsPerFoot(state.binWidth, state.binLength, state.isHalfGrid)

def shapeCells(state: InputState) -> list[tuple[int, int]]:
    """Feet the bin stands on, as drawn, all of them without a custom shape, see feetGridSize"""
    (columns, rows) = feetGridSize(state)
    if not state.hasCustomShape:
        return binShape.rectangle(columns, rows)
    return binShape.normalizeShape(state.shapeCells, columns, rows)

def outlineCells(state: InputState) -> list[tuple[int, int]]:
    """Cells of the outline grid the bin covers, half cells in a half grid or for sizes ending in a half, see gridDivisions"""
    return binShape.footShapeToOutline(shapeCells(state), *feetSize(state), outlineCellsPerFoot(state))

def isShaped(state: InputState) -> bool:
    """A custom shape leaving cells out, a full one builds a plain bin"""
    return state.hasCustomShape and not binShape.isRectangle(shapeCells(state), *feetGridSize(state))

def shapeError(state: InputState) -> str | None:
    """Why the shaped bin can't be built, none when it can or the bin is a plain rectangle"""
    if not isShaped(state):
        return None
    return binShape.shapeError(shapeCells(state))

def creaseLayout(state: InputState) -> list[tuple[wallCreases.WallSide, int]]:
    """
    Creased walls of the bin with their panel count, none when it gets no creases. A creased bin has a single compartment and a solid label tab,
    the folds would run into dividers and tab hollows
    """
    if not state.generateBody or not state.hasCreases:
        return []
    if state.binType not in [BIN_TYPE_HOLLOW, BIN_TYPE_SHELLED]:
        return []
    if state.binHeight < state.creaseMinHeight:
        return []
    # the scoop braces the front wall already
    hasScoop = state.hasScoop and state.binType == BIN_TYPE_HOLLOW and not isShaped(state)
    # in outline grid cells, the lengths in base units scale along
    divisions = gridDivisions(state)
    return wallCreases.creaseLayout(
        outlineCells(state),
        state.baseWidth / divisions,
        state.baseLength / divisions,
        state.creaseMinLength * divisions,
        state.creaseMaxPanelLength * divisions,
        hasScoop,
    )

def createLabelDefinition(
    design: adsk.fusion.Design,
    binParameterPrefix: str,
    parameterName: str,
    text: str,
    icon: str,
) -> labelGenerator.BinLabelDefinition | None:
    """The text goes into a text parameter so the label can be edited later, nothing for a blank label"""
    textParameter = None
    if len(text.strip()) > 0:
        textParameter = parameterUtils.addTextParameter(
            design,
            parameterUtils.parameterName(binParameterPrefix, parameterName),
            text,
            'Gridfinity bin label text',
        )
    definition = labelGenerator.BinLabelDefinition(textParameter, labelGenerator.iconPath(icon))
    return None if definition.isEmpty else definition

def buildBin(
    des: adsk.fusion.Design,
    state: InputState,
    settings: list[dict],
) -> list[adsk.fusion.BRepBody]:
    """Builds the bin into the design, tagged with the settings to show later, see settingsUtils.snapshotInputs"""
    # creased bins have a single compartment and a solid tab, see creaseLayout
    creases = creaseLayout(state)
    compartmentsX: int = 1 if len(creases) > 0 else state.compartmentsX
    compartmentsY: int = 1 if len(creases) > 0 else state.compartmentsY

    isHollow = state.binType == BIN_TYPE_HOLLOW
    isSolid = state.binType == BIN_TYPE_SOLID
    isShelled = state.binType == BIN_TYPE_SHELLED
    # a custom shape leaving cells out, without lip, scoop and tab for now. It's drawn in feet, its outline may be in half cells
    cells = shapeCells(state)
    shaped = isShaped(state)
    outline = outlineCells(state)
    cellsPerFoot = outlineCellsPerFoot(state)
    # the bin size in feet, half ones in a half grid, the feet grid cells are as much smaller
    halfGrid = state.isHalfGrid
    feetPerUnit = binGrid.feetPerUnit(halfGrid)
    columns = state.binWidth * feetPerUnit
    rows = state.binLength * feetPerUnit

    if shapeError(state) is not None:
        raise ValueError(shapeError(state))
    if des.designType == adsk.fusion.DesignTypes.DirectDesignType:
        raise UnsupportedDesignTypeException('Timeline must be enabled for the generator to work, projects with disabled design history currently are not supported')
    root = adsk.fusion.Component.cast(des.rootComponent)

    xyClearance = state.xyClearance
    binName = binDisplayName(state)

    originalTimelineCount = des.timeline.count
    if des.designIntent == adsk.fusion.DesignIntentTypes.HybridDesignIntentType:
        # create new component, only allowed in hybrid intent type
        newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())
        newCmpOcc.component.name = binName
        newCmpOcc.activate()
        gridfinityBinComponent: adsk.fusion.Component = newCmpOcc.component
    else:
        gridfinityBinComponent: adsk.fusion.Component = des.rootComponent
    features: adsk.fusion.Features = gridfinityBinComponent.features

    # pick the spot before generating, so none of this bin's geometry can count as an obstacle
    binPlacement = placementUtils.findPlacement(
        des,
        tagUtils.TAG_BIN,
        BIN_LEGACY_NAME_PREFIX,
        (
            0,
            0,
            state.binWidth * state.baseWidth - xyClearance * 2,
            state.binLength * state.baseLength - xyClearance * 2,
        ),
        state.baseWidth,
        state.baseLength,
    )

    binParameterPrefix = parameterUtils.nextFreePrefix(des, BIN_PARAMETER_BASE_NAME, BIN_PARAMETERS)
    (baseWidthParameter, baseLengthParameter) = sharedParameters.findOrCreateBaseUnitParameters(
        des,
        state.baseWidth,
        state.baseLength,
        binParameterPrefix,
        'bin',
        LOG_PREFIX,
    )
    baseWidth = Dim.parameter(baseWidthParameter)
    baseLength = Dim.parameter(baseLengthParameter)
    gridWidth = baseWidth / feetPerUnit if halfGrid else baseWidth
    gridLength = baseLength / feetPerUnit if halfGrid else baseLength
    # user parameters driving the bin, kept in its tag to show with its settings
    binParameters = [['Base width unit', baseWidthParameter.name], ['Base length unit', baseLengthParameter.name]]

    # create base interface
    baseGeneratorInput = BaseGeneratorInput()
    baseGeneratorInput.originPoint = geometryUtils.createOffsetPoint(
        gridfinityBinComponent.originConstructionPoint.geometry,
        byX=-xyClearance,
        byY=-xyClearance,
    )
    baseGeneratorInput.baseWidth = gridWidth
    baseGeneratorInput.baseLength = gridLength
    baseGeneratorInput.xyClearance = xyClearance
    # half feet have no room for holes
    baseGeneratorInput.hasScrewHoles = state.hasScrewHoles and not isShelled and not halfGrid
    baseGeneratorInput.hasMagnetCutouts = state.hasMagnetCutouts and not isShelled and not halfGrid
    baseGeneratorInput.hasMagnetCutoutsTabs = state.hasMagnetCutoutsTabs and not isShelled and not halfGrid
    baseGeneratorInput.screwHolesDiameter = state.screwHoleDiameter
    baseGeneratorInput.magnetCutoutsDiameter = state.magnetCutoutDiameter
    baseGeneratorInput.magnetCutoutsDepth = state.magnetCutoutDepth

    # the grid of the outline, for the shape and creases, in half cells for a whole grid bin ending in a half, see gridDivisions
    if gridDivisions(state) == feetPerUnit:
        outlineGrid = baseGeneratorInput
    else:
        outlineGrid = copy.copy(baseGeneratorInput)
        outlineGrid.baseWidth = baseWidth / gridDivisions(state)
        outlineGrid.baseLength = baseLength / gridDivisions(state)

    baseBodies: list[adsk.fusion.BRepBody]
    if state.generateBase:
        baseBodies = createFootGrid(
            baseGeneratorInput,
            columns,
            rows,
            gridfinityBinComponent,
        )
        if shaped:
            baseBodies = keepBodiesInCells(baseBodies, cells, baseGeneratorInput, gridfinityBinComponent, name='Foot outside shape remove')

    # create bin body
    binBodyInput = BinBodyGeneratorInput()
    binBodyInput.hasLip = state.hasLip
    binBodyInput.shapeCells = outline if shaped else None
    binBodyInput.shapeCellsPerFoot = cellsPerFoot
    binBodyInput.hasLipNotches = state.hasLipNotches
    binBodyInput.binWidth = columns
    binBodyInput.binLength = rows
    binBodyInput.binHeight = Dim.number(state.binHeight)
    binBodyInput.baseWidth = gridWidth
    binBodyInput.baseLength = gridLength
    binBodyInput.heightUnit = Dim.length(state.heightUnit)
    binBodyInput.xyClearance = xyClearance
    binBodyInput.binCornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS - xyClearance
    # a shaped hollow bin gets its cavity once trimmed to the shape
    binBodyInput.isSolid = isSolid or isShelled or shaped
    binBodyInput.wallThickness = state.wallThickness
    binBodyInput.hasScoop = state.hasScoop and isHollow and not shaped
    binBodyInput.scoopMaxRadius = state.scoopMaxRadius
    binBodyInput.hasTab = state.hasTab and isHollow and not shaped
    # in base units like the size, the body counts in feet
    binBodyInput.tabLength = state.tabLength * feetPerUnit
    binBodyInput.tabWidth = state.tabWidth
    binBodyInput.tabPosition = state.tabPosition * feetPerUnit
    binBodyInput.tabOverhangAngle = state.tabOverhangAngle
    binBodyInput.isTabHollow = state.isTabHollow and len(creases) == 0
    binBodyInput.isTabOpenThroughSides = state.isTabOpenThroughSides
    binBodyInput.tabTopAngle = state.tabTopAngle
    binBodyInput.labelStyle = state.labelStyle
    binBodyInput.isLabelBold = state.isLabelBold
    binBodyInput.compartmentsByX = compartmentsX
    binBodyInput.compartmentsByY = compartmentsY

    # label text and icon per compartment, the label tab section fills in the ones left blank
    # without the layout the grid is uniform, also for pockets saved with the layout hidden
    pockets = compartmentLayout.normalizePockets(state.compartmentPockets if state.showCompartmentsLayout and len(creases) == 0 else [], compartmentsX, compartmentsY)
    compartmentLabels: list[tuple[str, str]] = [(item['label'], item['icon']) for item in pockets]
    # pockets come in pattern order, single full depth cells are built once and patterned
    binBodyInput.isUniformCompartments = compartmentLayout.isUniform(pockets)
    binBodyInput.compartments = []
    for item in pockets:
        compartment = BinBodyCompartmentDefinition(item['x'], item['y'], item['width'], item['length'])
        if item['depth'] is not None:
            compartment.depth = item['depth'] / 10
        binBodyInput.compartments.append(compartment)

    binBody: adsk.fusion.BRepBody

    if state.generateBody:
        binBodyInput.binHeight = Dim.parameter(parameterUtils.addUnitlessParameter(
            des,
            parameterUtils.parameterName(binParameterPrefix, BIN_HEIGHT_PARAMETER),
            state.binHeight,
            'Gridfinity bin height, in height units',
        ))
        binParameters.append(['Bin height (u)', binBodyInput.binHeight.expression])
        if binBodyInput.hasTab:
            for compartmentIndex, compartment in enumerate(binBodyInput.compartments):
                (compartmentText, compartmentIcon) = compartmentLabels[compartmentIndex] if compartmentIndex < len(compartmentLabels) else ('', compartmentLayout.DEFAULT_ICON)
                compartment.label = createLabelDefinition(
                    des,
                    binParameterPrefix,
                    BIN_LABEL_PARAMETER if len(binBodyInput.compartments) == 1 else f'{BIN_LABEL_PARAMETER}{compartmentIndex + 1}',
                    compartmentText or state.labelText,
                    state.labelIcon if compartmentIcon == compartmentLayout.DEFAULT_ICON else compartmentIcon,
                )
                if compartment.label is not None and compartment.label.textParameter is not None:
                    binParameters.append([
                        'Label' if len(binBodyInput.compartments) == 1 else f'Compartment {compartmentIndex + 1} label',
                        compartment.label.textParameter.name,
                    ])
        binBodyInput.heightUnit = Dim.parameter(sharedParameters.findOrCreateSharedLengthParameter(
            des,
            tagUtils.TAG_HEIGHT_UNIT_PARAMETER,
            sharedParameters.HEIGHT_UNIT_PARAMETER,
            'height unit',
            sharedParameters.HEIGHT_UNIT_MIN,
            state.heightUnit,
            parameterUtils.parameterName(binParameterPrefix, BIN_HEIGHT_UNIT_PARAMETER),
            'bin',
            LOG_PREFIX,
        ))
        binParameters.append(['Height unit', binBodyInput.heightUnit.expression])
        binBody = createGridfinityBinBody(
            binBodyInput,
            gridfinityBinComponent,
        )
    combineFeatures = gridfinityBinComponent.features.combineFeatures

    # merge everything before the clearance cut, so the cut only has to reference the bin body
    if state.generateBody and state.generateBase:
        toolBodies = commonUtils.objectCollectionFromList(baseBodies)
        combineFeatureInput = combineFeatures.createInput(binBody, toolBodies)
        combineFeatures.add(combineFeatureInput).name = 'Bin body and feet join'
        binBody.name = binName

    # feet only touch each other along edges, so without a body they stay separate
    clearanceBodies = [binBody] if state.generateBody else baseBodies
    if shaped and (state.generateBody or state.generateBase):
        # the body is built over the whole grid, the outline trims it down to the shape
        cutOutsideShape(outline, outlineGrid, clearanceBodies, gridfinityBinComponent, name='Outer clearance trim')
    elif state.generateBase:
        # the body is built inside the clearance already, alone it has nothing to trim
        cutBaseClearance(
            baseGeneratorInput,
            columns,
            rows,
            clearanceBodies,
            gridfinityBinComponent,
        )

    if state.generateBody and state.generateBase and (shaped or not isShelled):
        # curve up the gaps between feet along the walls instead of leaving flat overhangs,
        # shaped bins need them at the inner corners whatever the type, the shell follows the pockets cut before it
        if shaped:
            cutShapeWallJunctionPockets(
                outlineGrid,
                outline,
                binBody,
                gridfinityBinComponent,
                (binGrid.footLines(columns, cellsPerFoot), binGrid.footLines(rows, cellsPerFoot)),
            )
        elif columns > 1 or rows > 1:
            cutWallJunctionPockets(baseGeneratorInput, columns, rows, binBody, gridfinityBinComponent)

    if shaped and isHollow and state.generateBody:
        cavity = createShapeCavity(
            outline,
            outlineGrid,
            binBodyInput.wallThickness,
            binBodyTopHeight(binBodyInput),
            gridfinityBinComponent,
            name='Cavity',
        )
        combineUtils.cutBody(binBody, commonUtils.objectCollectionFromList([cavity]), gridfinityBinComponent, name='Cavity cut')

    if state.generateBody and len(creases) > 0:
        # panels from where the floor fillet ends up the inside of the wall to the body top
        wallOffset = xyClearance + binBodyInput.wallThickness
        creaseBottomZ = const.BIN_COMPARTMENT_BOTTOM_THICKNESS + compartmentCutoutFilletRadius(
            binShape.cornerRadius(True, baseGeneratorInput.cornerFilletRadius, wallOffset)
        )
        creaseTopZ = binBodyTopHeight(binBodyInput)
        creaseDepth = state.creaseDepth
        if isHollow:
            # the inside follows the dent, so the wall keeps its thickness, a shell does it by itself.
            # Joined before the dent is cut, the dent goes deeper than the wall and would get filled back in
            innerFolds = createCreaseFolds(creases, outlineGrid, wallOffset, creaseDepth, creaseBottomZ, creaseTopZ, gridfinityBinComponent, name='Wall crease inside')
            combineUtils.joinBodies(binBody, commonUtils.objectCollectionFromList(innerFolds), gridfinityBinComponent, name='Wall creases inside join')
        outerFolds = createCreaseFolds(creases, outlineGrid, xyClearance, creaseDepth, creaseBottomZ, creaseTopZ, gridfinityBinComponent, name='Wall crease')
        combineUtils.cutBody(binBody, commonUtils.objectCollectionFromList(outerFolds), gridfinityBinComponent, name='Wall creases cut')

    if isShelled and state.generateBody:
        # the body already stands the xy clearance in from the cell border, so the walls take the full thickness
        # face.boundingBox.maxPoint.z ~ face.boundingBox.minPoint.z => face horizontal
        # largest horizontal face
        horizontalFaces = [face for face in binBody.faces if geometryUtils.isHorizontal(face)]
        topFace = faceUtils.maxByArea(horizontalFaces)
        topFaceMinPoint = topFace.boundingBox.minPoint
        if binBodyInput.hasLip:
            splitBodyFeatures = features.splitBodyFeatures
            splitBodyInput = splitBodyFeatures.createInput(
                binBody,
                topFace,
                True
            )
            splitBodies = splitBodyFeatures.add(splitBodyInput)
            splitBodies.name = 'Shell split at lip'
            bottomBody = min(splitBodies.bodies, key=lambda x: x.boundingBox.minPoint.z)
            topBody = max(splitBodies.bodies, key=lambda x: x.boundingBox.minPoint.z)
            horizontalFaces = [face for face in bottomBody.faces if geometryUtils.isHorizontal(face)]
            topFace = faceUtils.maxByArea(horizontalFaces)
            shellUtils.simpleShell([topFace], binBodyInput.wallThickness, gridfinityBinComponent, name='Shell', isRounded=state.isShellRounded)
            toolBodies = adsk.core.ObjectCollection.create()
            toolBodies.add(topBody)
            combineAfterShellFeatureInput = combineFeatures.createInput(bottomBody, toolBodies)
            combineAfterShellFeature = combineFeatures.add(combineAfterShellFeatureInput)
            combineAfterShellFeature.name = 'Shell and lip join'
            binBody = combineAfterShellFeature.bodies.item(0)
        else:
            shellUtils.simpleShell([topFace], binBodyInput.wallThickness, gridfinityBinComponent, name='Shell', isRounded=state.isShellRounded)

        if state.hasTab and not shaped:
            compartmentTabInput = BinBodyTabGeneratorInput()
            tabOriginX = Dim.length(binBodyInput.wallThickness) + binBodyInput.baseWidth * max(0, min(binBodyInput.tabPosition, binBodyInput.binWidth - binBodyInput.tabLength))
            if binBodyInput.hasLip and binBodyInput.hasScoop:
                tabOriginY = Dim.length(const.BIN_LIP_WALL_THICKNESS)
            else:
                # back wall, the shell keeps the outer size
                tabOriginY = binBodyInput.baseLength * binBodyInput.binLength - Dim.length(binBodyInput.xyClearance * 2)
            tabOriginZ = binBodyTopHeight(binBodyInput)
            compartmentTabInput.origin = adsk.core.Point3D.create(tabOriginX.value, tabOriginY.value, tabOriginZ.value)
            compartmentTabInput.originX = tabOriginX
            compartmentTabInput.originY = tabOriginY
            compartmentTabInput.originZ = tabOriginZ
            compartmentTabInput.length = binBodyInput.baseWidth * max(0, min(binBodyInput.tabLength, binBodyInput.binWidth)) - Dim.length(binBodyInput.wallThickness * 2 + binBodyInput.xyClearance * 2)
            compartmentTabInput.width = binBodyInput.tabWidth
            compartmentTabInput.overhangAngle = binBodyInput.tabOverhangAngle
            compartmentTabInput.labelAngle = binBodyInput.tabTopAngle
            compartmentTabInput.topClearance = tabTopClearance(binBodyInput.labelStyle)
            tabBody = createGridfinityBinBodyTab(compartmentTabInput, gridfinityBinComponent, name='Label tab')

            # trim the tab to the shell interior, its ends would otherwise poke out past the rounded outer corners,
            # intersecting leaves a single body, so nothing has to be picked out of the pieces
            shellThickness = Dim.length(binBodyInput.wallThickness)
            shellInteriorCornerFilletRadius = binBodyInput.binCornerFilletRadius - binBodyInput.wallThickness
            bodyWidth = binBodyInput.baseWidth * binBodyInput.binWidth - Dim.length(xyClearance * 2)
            bodyLength = binBodyInput.baseLength * binBodyInput.binLength - Dim.length(xyClearance * 2)
            shellInterior = createCompartmentCutout(
                binBodyInput.wallThickness,
                shellThickness,
                shellThickness,
                tabOriginZ,
                bodyWidth - shellThickness * 2,
                bodyLength - shellThickness * 2,
                tabOriginZ,
                shellInteriorCornerFilletRadius,
                False,
                0,
                False,
                gridfinityBinComponent,
                name='Shell interior',
            )
            intersectTabInput = combineFeatures.createInput(tabBody, commonUtils.objectCollectionFromList([shellInterior]))
            intersectTabInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
            intersectTabInput.isKeepToolBodies = True
            intersectTabFeature = combineFeatures.add(intersectTabInput)
            intersectTabFeature.name = 'Label tab trim'
            trimmedTabBodies = [body for body in list(intersectTabFeature.bodies) if not body.revisionId == shellInterior.revisionId]
            tabHollowCuts: list[adsk.fusion.BRepBody] = []
            if binBodyInput.isTabHollow:
                # the tab sits on the back wall, opened through it so the hollow isn't sealed
                shellInteriorMaxX = bodyWidth - shellThickness
                tabMaxX = tabOriginX + compartmentTabInput.length
                tabHollowCuts = createTabHollowCuts(
                    compartmentTabInput,
                    tabOriginX if tabOriginX.value >= shellThickness.value else shellThickness,
                    tabMaxX if tabMaxX.value <= shellInteriorMaxX.value else shellInteriorMaxX,
                    hollowTabWallThickness(shellThickness.value, binBodyInput.labelStyle),
                    shellInterior,
                    TabCavity(shellThickness, shellInteriorMaxX, bodyLength - shellThickness, compartmentCutoutFilletRadius(shellInteriorCornerFilletRadius)),
                    TabWallOpenings(
                        shellThickness.value * 2,
                        back=True,
                        minXSide=binBodyInput.isTabOpenThroughSides,
                        maxXSide=binBodyInput.isTabOpenThroughSides,
                    ),
                    gridfinityBinComponent,
                    name='Label tab',
                ).all()
            gridfinityBinComponent.features.removeFeatures.add(shellInterior).name = 'Shell interior remove'
            combineUtils.joinBodies(binBody, commonUtils.objectCollectionFromList(trimmedTabBodies), gridfinityBinComponent, name='Label tab join')
            if len(tabHollowCuts) > 0:
                combineUtils.cutBody(binBody, commonUtils.objectCollectionFromList(tabHollowCuts), gridfinityBinComponent, name='Label tab hollow cut')

            shelledLabel = createLabelDefinition(des, binParameterPrefix, BIN_LABEL_PARAMETER, state.labelText, state.labelIcon)
            if shelledLabel is not None and shelledLabel.textParameter is not None:
                binParameters.append(['Label', shelledLabel.textParameter.name])
            if shelledLabel is not None:
                createTabLabel(
                    shelledLabel,
                    binBodyInput.labelStyle,
                    binBodyInput.isLabelBold,
                    tabOriginX,
                    tabOriginX + compartmentTabInput.length,
                    tabOriginY,
                    binBodyInput.tabWidth,
                    tabOriginZ,
                    binBody,
                    gridfinityBinComponent,
                    binBodyInput.tabTopAngle,
                    name='Label',
                )

    generatedBodies: list[adsk.fusion.BRepBody] = []
    if state.generateBody or state.generateBase:
        generatedBodies = [binBody] if state.generateBody else baseBodies
        if binPlacement != (0, 0):
            placementUtils.moveBodies(generatedBodies, *binPlacement, gridfinityBinComponent, name='Bin placement')
        # mark generated geometry so later bins can tell it apart from the rest of the design,
        # with the settings it was generated with to show later
        for body in generatedBodies:
            tagUtils.tagBody(body, tagUtils.TAG_BIN, settings, binParameters, configJson.stateToJson(configJson.GENERATOR_BIN, state))

    if state.generateBase and state.hasJointOrigins:
        # last, after the placement, joint origins sit on sketches which don't follow body moves
        centers = footCenters(
            gridWidth,
            gridLength,
            xyClearance,
            columns,
            rows,
            Dim.length(binPlacement[0]) if binPlacement[0] != 0 else None,
            Dim.length(binPlacement[1]) if binPlacement[1] != 0 else None,
        )
        createCellJointOrigins(
            [center for center in centers if not shaped or (center[0], center[1]) in set(cells)],
            gridfinityBinComponent,
            name='Foot joint origin',
        )

    # group features in timeline
    binGroup = des.timeline.timelineGroups.add(originalTimelineCount, des.timeline.count - 1)
    binGroup.name = binName
    return generatedBodies
