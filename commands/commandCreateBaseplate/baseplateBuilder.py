import adsk.core, adsk.fusion

from ...lib import tagUtils
from ...lib import placementUtils
from ...lib.gridfinityUtils.baseplateGenerator import createGridfinityBaseplate, createGridfinityBaseplateFill
from ...lib.gridfinityUtils import baseplateLayout
from ...lib.gridfinityUtils.baseGenerator import cellCenters, createCellJointOrigins
from ...lib.gridfinityUtils.baseplateGeneratorInput import BaseplateGeneratorInput
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils import parameterUtils
from ...lib.gridfinityUtils import sharedParameters
from ...lib.gridfinityUtils.dim import Dim
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException
from .inputState import InputState

# Builds baseplates from an InputState, without the dialog, so the same settings always build the same baseplate

LOG_PREFIX = 'Gridfinity baseplate'

# default name of baseplates generated before tagging, keep as is even if the naming changes
BASEPLATE_LEGACY_NAME_PREFIX = 'Gridfinity baseplate '

# User parameter names are stored in user documents, keep these literal
BASEPLATE_PARAMETER_BASE_NAME = 'gfPlate'
BASEPLATE_PADDING_LEFT_PARAMETER = 'paddingLeft'
BASEPLATE_PADDING_TOP_PARAMETER = 'paddingTop'
BASEPLATE_PADDING_RIGHT_PARAMETER = 'paddingRight'
BASEPLATE_PADDING_BOTTOM_PARAMETER = 'paddingBottom'
BASEPLATE_PARAMETERS = [
    sharedParameters.BASE_WIDTH_FALLBACK_PARAMETER,
    sharedParameters.BASE_LENGTH_FALLBACK_PARAMETER,
    BASEPLATE_PADDING_LEFT_PARAMETER,
    BASEPLATE_PADDING_TOP_PARAMETER,
    BASEPLATE_PADDING_RIGHT_PARAMETER,
    BASEPLATE_PADDING_BOTTOM_PARAMETER,
]

SIZING_MODE_GRID_UNITS = 'Grid units'
SIZING_MODE_FILL_AREA = 'Fill area'

# where the grid goes, the padding takes the rest of the space
FILL_ALIGN_X_OPTIONS = {'Left': baseplateLayout.ALIGN_START, 'Center': baseplateLayout.ALIGN_CENTER, 'Right': baseplateLayout.ALIGN_END}
FILL_ALIGN_Y_OPTIONS = {'Front': baseplateLayout.ALIGN_START, 'Center': baseplateLayout.ALIGN_CENTER, 'Back': baseplateLayout.ALIGN_END}

BASEPLATE_TYPE_LIGHT = 'Light'
BASEPLATE_TYPE_FULL = 'Full'
BASEPLATE_TYPE_SKELETONIZED = 'Skeletonized'

FILL_PREVIEW_PIECE_GAP = 0.5

def computeFillLayout(inputsState: InputState) -> baseplateLayout.FillLayout:
    return baseplateLayout.computeFillLayout(
        inputsState.areaWidth,
        inputsState.areaLength,
        inputsState.fitTolerance,
        inputsState.bedWidth,
        inputsState.bedLength,
        inputsState.bedMargin,
        inputsState.baseWidth,
        inputsState.baseLength,
        inputsState.xyClearance,
        FILL_ALIGN_X_OPTIONS.get(inputsState.alignmentX, baseplateLayout.ALIGN_CENTER),
        FILL_ALIGN_Y_OPTIONS.get(inputsState.alignmentY, baseplateLayout.ALIGN_CENTER),
        inputsState.useHalfCells,
    )

def gridPlateExtent(inputsState: InputState) -> tuple[float, float, float, float]:
    """XY extent (minX, minY, maxX, maxY) of a grid units plate, where a plate without padding starts at the origin"""
    hasPadding = inputsState.hasPadding
    return (
        -inputsState.paddingLeft if hasPadding else 0,
        -inputsState.paddingBottom if hasPadding else 0,
        inputsState.plateWidth * inputsState.baseWidth - inputsState.xyClearance * 2 + (inputsState.paddingRight if hasPadding else 0),
        inputsState.plateLength * inputsState.baseLength - inputsState.xyClearance * 2 + (inputsState.paddingTop if hasPadding else 0),
    )

def baseplateDisplayName(plateWidth: int, plateLength: int) -> str:
    return 'Gridfinity baseplate {}x{}'.format(int(plateLength), int(plateWidth))

def baseplateName(inputsState: InputState) -> str:
    """Name of the component and timeline group of the baseplate"""
    if inputsState.sizingMode == SIZING_MODE_FILL_AREA:
        return 'Gridfinity baseplate fill {:g}x{:g} mm'.format(round(inputsState.areaLength * 10, 1), round(inputsState.areaWidth * 10, 1))
    return baseplateDisplayName(inputsState.plateWidth, inputsState.plateLength)

def buildBaseplate(
    des: adsk.fusion.Design,
    inputsState: InputState,
    settings: list[dict],
    isPreview: bool = False,
) -> list[adsk.fusion.BRepBody]:
    """
    Builds the baseplate into the design, tagged with the settings to show later, see settingsUtils.snapshotInputs.
    A preview spreads fill pieces apart and goes without joint origins
    """
    if des.designType == 0:
        raise UnsupportedDesignTypeException('Timeline must be enabled for the generator to work, projects with disabled design history currently are not supported')
    root = adsk.fusion.Component.cast(des.rootComponent)

    # a fill is laid out as one plate of the whole grid with the centering padding, then split into pieces
    isFillArea = inputsState.sizingMode == SIZING_MODE_FILL_AREA
    plateName = baseplateName(inputsState)
    if isFillArea:
        fillLayout = computeFillLayout(inputsState)
        (plateWidth, plateLength) = (fillLayout.x.cells, fillLayout.y.cells)
        hasPadding = True
        (paddingLeft, paddingTop, paddingRight, paddingBottom) = (fillLayout.x.paddingStart, fillLayout.y.paddingEnd, fillLayout.x.paddingEnd, fillLayout.y.paddingStart)
        plateExtent = baseplateLayout.layoutOutline(fillLayout, inputsState.baseWidth, inputsState.baseLength, inputsState.xyClearance)
    else:
        (plateWidth, plateLength) = (inputsState.plateWidth, inputsState.plateLength)
        hasPadding = inputsState.hasPadding
        (paddingLeft, paddingTop, paddingRight, paddingBottom) = (inputsState.paddingLeft, inputsState.paddingTop, inputsState.paddingRight, inputsState.paddingBottom)
        plateExtent = gridPlateExtent(inputsState)

    originalTimelineCount = des.timeline.count
    if des.designIntent == adsk.fusion.DesignIntentTypes.HybridDesignIntentType:
        # create new component, only allowed in hybrid intent type
        newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())

        newCmpOcc.component.name = plateName
        newCmpOcc.activate()
        gridfinityBaseplateComponent: adsk.fusion.Component = newCmpOcc.component
    else:
        gridfinityBaseplateComponent: adsk.fusion.Component = des.rootComponent
    baseplateGeneratorInput = BaseplateGeneratorInput()

    baseplateGeneratorInput.xyClearance = inputsState.xyClearance
    baseplateGeneratorInput.baseplateWidth = plateWidth
    baseplateGeneratorInput.baseplateLength = plateLength
    baseplateGeneratorInput.hasExtendedBottom = not inputsState.plateType == BASEPLATE_TYPE_LIGHT
    baseplateGeneratorInput.hasSkeletonizedBottom = inputsState.plateType == BASEPLATE_TYPE_SKELETONIZED
    baseplateGeneratorInput.hasMagnetCutouts = inputsState.hasMagnetSockets
    baseplateGeneratorInput.magnetCutoutsDiameter = inputsState.magnetSocketSize
    baseplateGeneratorInput.magnetCutoutsDepth = inputsState.magnetSocketDepth
    baseplateGeneratorInput.hasScrewHoles = inputsState.hasScrewHoles
    baseplateGeneratorInput.screwHolesDiameter = inputsState.screwHoleSize
    baseplateGeneratorInput.screwHeadCutoutDiameter = inputsState.screwHeadSize
    baseplateGeneratorInput.hasPadding = hasPadding
    baseplateGeneratorInput.bottomExtensionHeight = inputsState.extraBottomThickness
    baseplateGeneratorInput.binZClearance = inputsState.verticalClearance
    baseplateGeneratorInput.hasConnectionHoles = inputsState.hasConnectionHoles
    baseplateGeneratorInput.connectionScrewHolesDiameter = inputsState.connectionHoleSize
    baseplateGeneratorInput.cornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS
    if isFillArea:
        baseplateGeneratorInput.hasHalfCellsLeft = fillLayout.x.hasHalfCellsStart
        baseplateGeneratorInput.hasHalfCellsRight = fillLayout.x.hasHalfCellsEnd
        baseplateGeneratorInput.hasHalfCellsBottom = fillLayout.y.hasHalfCellsStart
        baseplateGeneratorInput.hasHalfCellsTop = fillLayout.y.hasHalfCellsEnd

    # pick the spot before generating, so none of this baseplate's geometry can count as an obstacle
    baseplatePlacement = placementUtils.findPlacement(
        des,
        tagUtils.TAG_BASEPLATE,
        BASEPLATE_LEGACY_NAME_PREFIX,
        plateExtent,
        inputsState.baseWidth,
        inputsState.baseLength,
    )

    plateParameterPrefix = parameterUtils.nextFreePrefix(des, BASEPLATE_PARAMETER_BASE_NAME, BASEPLATE_PARAMETERS)
    (baseWidthParameter, baseLengthParameter) = sharedParameters.findOrCreateBaseUnitParameters(
        des,
        inputsState.baseWidth,
        inputsState.baseLength,
        plateParameterPrefix,
        'baseplate',
        LOG_PREFIX,
    )
    baseplateGeneratorInput.baseWidth = Dim.parameter(baseWidthParameter)
    baseplateGeneratorInput.baseLength = Dim.parameter(baseLengthParameter)
    # user parameters driving the baseplate, kept in its tag to show with its settings
    baseplateParameters = [['Base width unit', baseWidthParameter.name], ['Base length unit', baseLengthParameter.name]]

    def paddingDim(name: str, label: str, value: float) -> Dim:
        """Unused sides stay plain values, so no parameter is left around that drives nothing"""
        if not hasPadding or value <= 0:
            return Dim.length(value)
        return Dim.parameter(parameterUtils.addLengthParameter(
            des,
            parameterUtils.parameterName(plateParameterPrefix, name),
            value,
            f'Gridfinity baseplate {label} padding',
        ))
    baseplateGeneratorInput.paddingLeft = paddingDim(BASEPLATE_PADDING_LEFT_PARAMETER, 'left', paddingLeft)
    baseplateGeneratorInput.paddingTop = paddingDim(BASEPLATE_PADDING_TOP_PARAMETER, 'top', paddingTop)
    baseplateGeneratorInput.paddingRight = paddingDim(BASEPLATE_PADDING_RIGHT_PARAMETER, 'right', paddingRight)
    baseplateGeneratorInput.paddingBottom = paddingDim(BASEPLATE_PADDING_BOTTOM_PARAMETER, 'bottom', paddingBottom)
    for (label, padding) in [
        ('Padding left', baseplateGeneratorInput.paddingLeft),
        ('Padding top', baseplateGeneratorInput.paddingTop),
        ('Padding right', baseplateGeneratorInput.paddingRight),
        ('Padding bottom', baseplateGeneratorInput.paddingBottom),
    ]:
        if padding.isExpression:
            baseplateParameters.append([label, padding.expression])

    # whole cells as (first column, first row, columns, rows), half cells take no bin foot of their own
    cellBlocks = []
    if isFillArea:
        baseplateBodies = []
        for (piece, pieceBody) in createGridfinityBaseplateFill(
            baseplateGeneratorInput,
            fillLayout,
            gridfinityBaseplateComponent,
            pieceGap=FILL_PREVIEW_PIECE_GAP if isPreview else 0,
        ):
            pieceBody.name = f'{baseplateDisplayName(piece.cellsX, piece.cellsY)} ({piece.column + 1}-{piece.row + 1})'
            baseplateBodies.append(pieceBody)
            cellBlocks.append((piece.cellOffsetX, piece.cellOffsetY, piece.cellsX, piece.cellsY))
    else:
        baseplateBody = createGridfinityBaseplate(baseplateGeneratorInput, gridfinityBaseplateComponent)
        baseplateBody.name = plateName
        baseplateBodies = [baseplateBody]
        cellBlocks.append((0, 0, int(baseplateGeneratorInput.baseplateWidth), int(baseplateGeneratorInput.baseplateLength)))
    if baseplatePlacement != (0, 0):
        placementUtils.moveBodies(baseplateBodies, *baseplatePlacement, gridfinityBaseplateComponent, name='Baseplate placement')
    # last, after the placement, joint origins sit on sketches which don't follow body moves.
    # The preview spreads fill pieces apart and only shows the shape, it goes without them
    if not isPreview and inputsState.hasJointOrigins:
        createCellJointOrigins(
            [
                center
                for (firstColumn, firstRow, columns, rows) in cellBlocks
                for center in cellCenters(
                    baseplateGeneratorInput.baseWidth,
                    baseplateGeneratorInput.baseLength,
                    baseplateGeneratorInput.xyClearance,
                    range(firstColumn, firstColumn + columns),
                    range(firstRow, firstRow + rows),
                    Dim.length(baseplatePlacement[0]) if baseplatePlacement[0] != 0 else None,
                    Dim.length(baseplatePlacement[1]) if baseplatePlacement[1] != 0 else None,
                )
            ],
            gridfinityBaseplateComponent,
            name='Socket joint origin',
        )
    # mark generated geometry so it can be told apart from the rest of the design
    for baseplateBody in baseplateBodies:
        tagUtils.tagBody(baseplateBody, tagUtils.TAG_BASEPLATE, settings, baseplateParameters)

    if des.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        # group features in timeline
        plateGroup = des.timeline.timelineGroups.add(originalTimelineCount, des.timeline.count - 1)
        plateGroup.name = plateName
    return baseplateBodies
