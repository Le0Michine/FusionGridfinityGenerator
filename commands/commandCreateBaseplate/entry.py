import adsk.core, adsk.fusion, traceback
import json
import math
import os
import pathlib
import time



from ...lib import configUtils
from ...lib import tagUtils
from ...lib import settingsUtils
from ...lib import placementUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils.const import DIMENSION_DEFAULT_WIDTH_UNIT
from ...lib.gridfinityUtils.baseplateGenerator import createGridfinityBaseplate, createGridfinityBaseplateFill
from ...lib.gridfinityUtils import baseplateLayout
from ...lib.gridfinityUtils.baseGenerator import cellCenters, createCellJointOrigins
from ...lib.gridfinityUtils.baseplateGeneratorInput import BaseplateGeneratorInput
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils import commonUtils
from ...lib.gridfinityUtils import parameterUtils
from ...lib.gridfinityUtils import sharedParameters
from ...lib.gridfinityUtils.dim import Dim
from .inputState import InputState
from . import printBeds
from ...lib.ui.commandUiState import CommandUiState
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException

app = adsk.core.Application.get()
ui = app.userInterface


# The command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBaseplate'
CMD_NAME = 'Gridfinity baseplate'
CMD_Description = 'Create gridfinity baseplate'

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

uiState = CommandUiState(CMD_NAME)
# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

CONFIG_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'commandConfig')
UI_INPUT_DEFAULTS_CONFIG_PATH = os.path.join(CONFIG_FOLDER_PATH, "ui_input_defaults.json")

LAYOUT_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'layout.html').as_uri()

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Input groups
INFO_GROUP = 'info_group'
BASIC_SIZES_GROUP = 'basic_sizes'
XY_DIMENSIONS_GROUP = 'xy_dimensions'
PLATE_FEATURES_GROUP = 'plate_features'
MAGNET_SOCKET_GROUP = 'magnet_cutout_group'
SCREW_HOLE_GROUP = 'screw_hole_group'
SIDE_PADDING_GROUP = 'side_padding_group'
ADVANCED_PLATE_SIZE_GROUP = 'advanced_plate_size_group'
INPUT_CHANGES_GROUP = 'input_changes_group'
PREVIEW_GROUP = 'preview_group'
# Input ids
BASEPLATE_BASE_UNIT_WIDTH_INPUT = 'base_width_unit'
BASEPLATE_BASE_UNIT_LENGTH_INPUT = 'base_length_unit'
BIN_XY_CLEARANCE_INPUT_ID = 'bin_xy_clearance'
BASEPLATE_WIDTH_INPUT = 'plate_width'
BASEPLATE_LENGTH_INPUT = 'plate_length'
BASEPLATE_TYPE_DROPDOWN = 'plate_type_dropdown'

SIZING_MODE_DROPDOWN = 'sizing_mode_dropdown'
SIZING_MODE_GRID_UNITS = 'Grid units'
SIZING_MODE_FILL_AREA = 'Fill area'

FILL_AREA_WIDTH_INPUT = 'fill_area_width'
FILL_AREA_LENGTH_INPUT = 'fill_area_length'
FILL_FIT_TOLERANCE_INPUT = 'fill_fit_tolerance'
FILL_HALF_CELLS_INPUT = 'fill_half_cells'
FILL_ALIGN_X_DROPDOWN = 'fill_align_x'
FILL_ALIGN_Y_DROPDOWN = 'fill_align_y'
# where the grid goes, the padding takes the rest of the space
FILL_ALIGN_X_OPTIONS = {'Left': baseplateLayout.ALIGN_START, 'Center': baseplateLayout.ALIGN_CENTER, 'Right': baseplateLayout.ALIGN_END}
FILL_ALIGN_Y_OPTIONS = {'Front': baseplateLayout.ALIGN_START, 'Center': baseplateLayout.ALIGN_CENTER, 'Back': baseplateLayout.ALIGN_END}
PRINT_BED_GROUP = 'print_bed_group'
PRINT_BED_PRESET_DROPDOWN = 'print_bed_preset_dropdown'
PRINT_BED_WIDTH_INPUT = 'print_bed_width'
PRINT_BED_LENGTH_INPUT = 'print_bed_length'
PRINT_BED_MARGIN_INPUT = 'print_bed_margin'
# drawing of the plate or of the fill pieces, shown in both sizing modes
LAYOUT_BROWSER = 'layout_browser'

# inputs only one of the sizing modes uses
GRID_UNITS_MODE_INPUTS = [BASEPLATE_WIDTH_INPUT, BASEPLATE_LENGTH_INPUT, SIDE_PADDING_GROUP]
FILL_AREA_MODE_INPUTS = [FILL_AREA_WIDTH_INPUT, FILL_AREA_LENGTH_INPUT, FILL_FIT_TOLERANCE_INPUT, FILL_ALIGN_X_DROPDOWN, FILL_ALIGN_Y_DROPDOWN, FILL_HALF_CELLS_INPUT, PRINT_BED_GROUP]

BASEPLATE_TYPE_LIGHT = 'Light'
BASEPLATE_TYPE_FULL = 'Full'
BASEPLATE_TYPE_SKELETONIZED = 'Skeletonized'

BASEPLATE_WITH_MAGNETS_INPUT = 'with_magnet_cutouts'
BASEPLATE_MAGNET_DIAMETER_INPUT = 'magnet_diameter'
BASEPLATE_MAGNET_HEIGHT_INPUT = 'magnet_height'

BASEPLATE_WITH_SCREWS_INPUT = 'with_screw_holes'
BASEPLATE_SCREW_DIAMETER_INPUT = 'screw_diameter'
BASEPLATE_SCREW_HEIGHT_INPUT = 'screw_head_diameter'

BASEPLATE_WITH_SIDE_PADDING_INPUT = 'with_side_padding'
BASEPLATE_SIDE_PADDING_LEFT_INPUT = 'side_padding_left'
BASEPLATE_SIDE_PADDING_TOP_INPUT = 'side_padding_top'
BASEPLATE_SIDE_PADDING_RIGHT_INPUT = 'side_padding_right'
BASEPLATE_SIDE_PADDING_BOTTOM_INPUT = 'side_padding_bottom'

BASEPLATE_EXTRA_THICKNESS_INPUT = 'extra_bottom_thickness'
BASEPLATE_BIN_Z_CLEARANCE_INPUT = 'bin_z_clearance'
BASEPLATE_HAS_CONNECTION_HOLE_INPUT = 'has_connection_hole'
BASEPLATE_JOINT_ORIGINS_INPUT = 'has_joint_origins'
BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT = 'connection_hole_diameter'

INPUT_CHANGES_SAVE_DEFAULTS = 'input_changes_buttons_save_new_defaults'
INPUT_CHANGES_RESET_TO_DEFAULTS = 'input_changes_button_reset_to_defaults'
INPUT_CHANGES_RESET_TO_FACTORY = 'input_changes_button_factory_reset'

SHOW_PREVIEW_INPUT = 'show_preview'

INFO_TEXT = ("<b>Help:</b> Info for inputs can be found "
             "<a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Baseplate-generator-options\">"
             "Here on our GitHub</a>.")

def infoText():
    version = tagUtils.getGeneratorVersion()
    return f"{INFO_TEXT}<br><span style=\"color:#808080; font-size:small\">Version {version}</span>" if version else INFO_TEXT

INPUTS_VALID = True
# fill pieces are spread apart in the preview to show where the plate is split
FILL_PREVIEW_PIECE_GAP = 0.5
isApplyingBedPreset = False

def getErrorMessage(text = "An unknown error occurred, please validate your inputs and try again"):
    stackTrace = traceback.format_exc()
    return f"{text}:<br>{stackTrace}"

def showErrorInMessageBox(text = "An unknown error occurred, please validate your inputs and try again"):
    if ui:
        ui.messageBox(getErrorMessage(text), f"{CMD_NAME} Error")

# Executed when add-in is run.
def start():
    futil.log(f'{CMD_NAME} Command Start Event')
    try:
        addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)

        # Create a command Definition.
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

            # Define an event handler for the command created event. It will be called when the button is clicked.
            futil.add_handler(cmd_def.commandCreated, command_created)

            # ******** Add a button into the UI so the user can run the command. ********
            # Get the target workspace the button will be created in.
            workspace = ui.workspaces.itemById(WORKSPACE_ID)

            # Get the panel the button will be created in.
            panel = workspace.toolbarPanels.itemById(PANEL_ID)

            # Create the button command control in the UI after the specified existing command.
            control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

            # Specify if the command is promoted to the main toolbar. 
            control.isPromoted = addinConfig['UI'].getboolean('is_promoted')

        initUiState()
        ui.statusMessage = ""
    except Exception as err:
        futil.log(f'{CMD_NAME} Error occurred at the start, {err}, {getErrorMessage()}')
        ui.statusMessage = f"{CMD_NAME} failed to initialize"
        showErrorInMessageBox(f"{CMD_NAME} Critical error occurred at the start, the command will be unavailable, if the issue persists use <a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/issues/new\">this link</a> to report it")


# Executed when add-in is stopped.
def stop():
    futil.log(f'{CMD_NAME} Command Stop Event')
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control: adsk.core.CommandControl = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)
    addinConfig['UI']['is_promoted'] = 'yes' if command_control.isPromoted else 'no'
    configUtils.writeConfig(addinConfig, CONFIG_FOLDER_PATH)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def applySharedParameterDefaults():
    """Usable shared units of the design replace the remembered inputs, so new baseplates match the existing bins by default"""
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        return
    (baseWidth, baseLength) = sharedParameters.usableSharedBaseUnits(design)
    for (inputId, value) in [
        (BASEPLATE_BASE_UNIT_WIDTH_INPUT, baseWidth),
        (BASEPLATE_BASE_UNIT_LENGTH_INPUT, baseLength),
    ]:
        if value is not None:
            uiState.initValue(inputId, value, adsk.core.ValueCommandInput.classType())
            commonUtils.debugLog(f'{CMD_NAME} dialog default {inputId} = {value} from the shared parameter')

def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')
    global uiState

    args.command.setDialogInitialSize(400, 500)
    applySharedParameterDefaults()

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs
    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

    infoGroup = inputs.addGroupCommandInput(INFO_GROUP, 'Info')
    infoGroup.isExpanded = uiState.getState(INFO_GROUP)
    uiState.registerCommandInput(infoGroup)
    # as many rows as the text has lines, so the box takes no more room than it needs, and a row for the help line
    # to wrap into, as the box keeps its height when the dialog is made narrower
    info = infoText()
    infoGroup.children.addTextBoxCommandInput("info_text", "Info", info, info.count('<br>') + 2, True)

    basicSizesGroup = inputs.addGroupCommandInput(BASIC_SIZES_GROUP, 'Basic size')
    basicSizesGroup.isExpanded = uiState.getState(BASIC_SIZES_GROUP)
    uiState.registerCommandInput(basicSizesGroup)
    baseWidthUnitInput = basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_WIDTH_INPUT, 'Base width unit, X (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BASE_UNIT_WIDTH_INPUT)))
    baseWidthUnitInput.minimumValue = sharedParameters.BASE_UNIT_MIN
    baseWidthUnitInput.isMinimumInclusive = True
    uiState.registerCommandInput(baseWidthUnitInput)
    baseLengthUnitInput = basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_LENGTH_INPUT, 'Base length unit, Y (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BASE_UNIT_LENGTH_INPUT)))
    baseLengthUnitInput.minimumValue = sharedParameters.BASE_UNIT_MIN
    baseLengthUnitInput.isMinimumInclusive = True
    uiState.registerCommandInput(baseLengthUnitInput)

    xyClearanceInput = basicSizesGroup.children.addValueInput(BIN_XY_CLEARANCE_INPUT_ID, 'Bin xy clearance (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BIN_XY_CLEARANCE_INPUT_ID)))
    xyClearanceInput.minimumValue = 0.01
    xyClearanceInput.isMinimumInclusive = True
    xyClearanceInput.maximumValue = 0.05
    xyClearanceInput.isMaximumInclusive = True
    xyClearanceInput.tooltip = "Must be within range [0.1, 0.5]mm"
    uiState.registerCommandInput(xyClearanceInput)

    mainDimensionsGroup = inputs.addGroupCommandInput(XY_DIMENSIONS_GROUP, 'Main dimensions')
    mainDimensionsGroup.isExpanded = uiState.getState(XY_DIMENSIONS_GROUP)
    uiState.registerCommandInput(mainDimensionsGroup)
    sizingModeDropdown = mainDimensionsGroup.children.addDropDownCommandInput(SIZING_MODE_DROPDOWN, 'Sizing mode', adsk.core.DropDownStyles.TextListDropDownStyle)
    sizingModeDropdown.tooltip = "Fill area generates the grid for a whole area, e.g. a drawer, split into pieces fitting the print bed"
    for sizingMode in [SIZING_MODE_GRID_UNITS, SIZING_MODE_FILL_AREA]:
        sizingModeDropdown.listItems.add(sizingMode, uiState.getState(SIZING_MODE_DROPDOWN) == sizingMode)
    uiState.registerCommandInput(sizingModeDropdown)

    baseplateWidthInput = mainDimensionsGroup.children.addIntegerSpinnerCommandInput(BASEPLATE_WIDTH_INPUT, 'Plate width, X (u)', 1, 100, 1, uiState.getState(BASEPLATE_WIDTH_INPUT))
    uiState.registerCommandInput(baseplateWidthInput)
    baseplateLengthInput = mainDimensionsGroup.children.addIntegerSpinnerCommandInput(BASEPLATE_LENGTH_INPUT, 'Plate length, Y (u)', 1, 100, 1, uiState.getState(BASEPLATE_LENGTH_INPUT))
    uiState.registerCommandInput(baseplateLengthInput)

    fillAreaWidthInput = mainDimensionsGroup.children.addValueInput(FILL_AREA_WIDTH_INPUT, 'Area width, X', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(FILL_AREA_WIDTH_INPUT)))
    fillAreaWidthInput.minimumValue = 0
    fillAreaWidthInput.isMinimumInclusive = False
    uiState.registerCommandInput(fillAreaWidthInput)
    fillAreaLengthInput = mainDimensionsGroup.children.addValueInput(FILL_AREA_LENGTH_INPUT, 'Area length, Y', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(FILL_AREA_LENGTH_INPUT)))
    fillAreaLengthInput.minimumValue = 0
    fillAreaLengthInput.isMinimumInclusive = False
    uiState.registerCommandInput(fillAreaLengthInput)
    fillFitToleranceInput = mainDimensionsGroup.children.addValueInput(FILL_FIT_TOLERANCE_INPUT, 'Fit tolerance', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(FILL_FIT_TOLERANCE_INPUT)))
    fillFitToleranceInput.minimumValue = 0
    fillFitToleranceInput.isMinimumInclusive = True
    fillFitToleranceInput.tooltip = "Total gap left between the plate and the area walls on each axis"
    uiState.registerCommandInput(fillFitToleranceInput)
    for (inputId, label, options) in [
        (FILL_ALIGN_X_DROPDOWN, 'Grid position, X', FILL_ALIGN_X_OPTIONS),
        (FILL_ALIGN_Y_DROPDOWN, 'Grid position, Y', FILL_ALIGN_Y_OPTIONS),
    ]:
        alignDropdown = mainDimensionsGroup.children.addDropDownCommandInput(inputId, label, adsk.core.DropDownStyles.TextListDropDownStyle)
        alignDropdown.tooltip = "Side the grid is pushed to, the padding fills the rest of the space"
        for option in options.keys():
            alignDropdown.listItems.add(option, uiState.getState(inputId) == option)
        uiState.registerCommandInput(alignDropdown)
    fillHalfCellsInput = mainDimensionsGroup.children.addBoolValueInput(FILL_HALF_CELLS_INPUT, 'Fill gaps with half cells', True, '', uiState.getState(FILL_HALF_CELLS_INPUT))
    fillHalfCellsInput.tooltip = "Where the space left past the grid fits a row of half size sockets, adds one instead of solid padding"
    uiState.registerCommandInput(fillHalfCellsInput)

    printBedGroup = mainDimensionsGroup.children.addGroupCommandInput(PRINT_BED_GROUP, 'Print bed')
    printBedGroup.isExpanded = uiState.getState(PRINT_BED_GROUP)
    uiState.registerCommandInput(printBedGroup)
    printBedPresetDropdown = printBedGroup.children.addDropDownCommandInput(PRINT_BED_PRESET_DROPDOWN, 'Printer', adsk.core.DropDownStyles.TextListDropDownStyle)
    presetNames = [printBeds.PRINT_BED_CUSTOM] + list(printBeds.PRINT_BED_PRESETS.keys())
    # a preset saved with the defaults can be gone from the list since, the bed size it set stays as custom
    if uiState.getState(PRINT_BED_PRESET_DROPDOWN) not in presetNames:
        uiState.updateValue(PRINT_BED_PRESET_DROPDOWN, printBeds.PRINT_BED_CUSTOM)
    for presetName in presetNames:
        printBedPresetDropdown.listItems.add(presetName, uiState.getState(PRINT_BED_PRESET_DROPDOWN) == presetName)
    if printBedPresetDropdown.selectedItem is None:
        printBedPresetDropdown.listItems.item(0).isSelected = True
        uiState.updateValue(PRINT_BED_PRESET_DROPDOWN, printBeds.PRINT_BED_CUSTOM)
    uiState.registerCommandInput(printBedPresetDropdown)
    printBedWidthInput = printBedGroup.children.addValueInput(PRINT_BED_WIDTH_INPUT, 'Bed width, X', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(PRINT_BED_WIDTH_INPUT)))
    printBedWidthInput.minimumValue = 0
    printBedWidthInput.isMinimumInclusive = False
    uiState.registerCommandInput(printBedWidthInput)
    printBedLengthInput = printBedGroup.children.addValueInput(PRINT_BED_LENGTH_INPUT, 'Bed length, Y', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(PRINT_BED_LENGTH_INPUT)))
    printBedLengthInput.minimumValue = 0
    printBedLengthInput.isMinimumInclusive = False
    uiState.registerCommandInput(printBedLengthInput)
    printBedMarginInput = printBedGroup.children.addValueInput(PRINT_BED_MARGIN_INPUT, 'Bed margin', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(PRINT_BED_MARGIN_INPUT)))
    printBedMarginInput.minimumValue = 0
    printBedMarginInput.isMinimumInclusive = True
    printBedMarginInput.tooltip = "Space kept clear on every side of the bed"
    uiState.registerCommandInput(printBedMarginInput)

    # not registered, as it holds no value to save with the defaults
    mainDimensionsGroup.children.addBrowserCommandInput(LAYOUT_BROWSER, 'Result', LAYOUT_HTML_URL, 220, 220)

    plateFeaturesGroup = inputs.addGroupCommandInput(PLATE_FEATURES_GROUP, 'Features')
    plateFeaturesGroup.isExpanded = uiState.getState(PLATE_FEATURES_GROUP)
    uiState.registerCommandInput(plateFeaturesGroup)
    plateTypeDropdown = plateFeaturesGroup.children.addDropDownCommandInput(BASEPLATE_TYPE_DROPDOWN, 'Baseplate type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    plateTypeDropdownInitialState = uiState.getState(BASEPLATE_TYPE_DROPDOWN)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_LIGHT, plateTypeDropdownInitialState == BASEPLATE_TYPE_LIGHT)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_SKELETONIZED, plateTypeDropdownInitialState == BASEPLATE_TYPE_SKELETONIZED)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_FULL, plateTypeDropdownInitialState == BASEPLATE_TYPE_FULL)
    uiState.registerCommandInput(plateTypeDropdown)
    jointOriginsInput = plateFeaturesGroup.children.addBoolValueInput(BASEPLATE_JOINT_ORIGINS_INPUT, 'Add joint origins', True, '', uiState.getState(BASEPLATE_JOINT_ORIGINS_INPUT))
    jointOriginsInput.tooltip = 'A joint origin at the bottom center of every socket, to joint bins into it'
    uiState.registerCommandInput(jointOriginsInput)

    magnetCutoutGroup = plateFeaturesGroup.children.addGroupCommandInput(MAGNET_SOCKET_GROUP, 'Magnet cutouts')
    magnetCutoutGroup.isExpanded = uiState.getState(MAGNET_SOCKET_GROUP)
    uiState.registerCommandInput(magnetCutoutGroup)
    generateMagnetSocketInput = magnetCutoutGroup.children.addBoolValueInput(BASEPLATE_WITH_MAGNETS_INPUT, 'Add magnet cutouts', True, '', uiState.getState(BASEPLATE_WITH_MAGNETS_INPUT))
    uiState.registerCommandInput(generateMagnetSocketInput)
    magnetSocketDiameterInput = magnetCutoutGroup.children.addValueInput(BASEPLATE_MAGNET_DIAMETER_INPUT, 'Magnet cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_MAGNET_DIAMETER_INPUT)))
    uiState.registerCommandInput(magnetSocketDiameterInput)
    magnetSocketDepthInput = magnetCutoutGroup.children.addValueInput(BASEPLATE_MAGNET_HEIGHT_INPUT, 'Magnet cutout depth', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_MAGNET_HEIGHT_INPUT)))
    uiState.registerCommandInput(magnetSocketDepthInput)

    screwHoleGroup = plateFeaturesGroup.children.addGroupCommandInput(SCREW_HOLE_GROUP, 'Screw holes')
    screwHoleGroup.isExpanded = uiState.getState(SCREW_HOLE_GROUP)
    uiState.registerCommandInput(screwHoleGroup)
    generateScrewHolesInput = screwHoleGroup.children.addBoolValueInput(BASEPLATE_WITH_SCREWS_INPUT, 'Add screw holes', True, '', uiState.getState(BASEPLATE_WITH_SCREWS_INPUT))
    uiState.registerCommandInput(generateScrewHolesInput)
    screwSizeInput = screwHoleGroup.children.addValueInput(BASEPLATE_SCREW_DIAMETER_INPUT, 'Screw hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SCREW_DIAMETER_INPUT)))
    screwSizeInput.minimumValue = 0.1
    screwSizeInput.isMinimumInclusive = True
    screwSizeInput.maximumValue = 1
    screwSizeInput.isMaximumInclusive = True
    uiState.registerCommandInput(screwSizeInput)

    screwHeadSizeInput = screwHoleGroup.children.addValueInput(BASEPLATE_SCREW_HEIGHT_INPUT, 'Screw head cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SCREW_HEIGHT_INPUT)))
    screwHeadSizeInput.minimumValue = 0.2
    screwHeadSizeInput.isMinimumInclusive = True
    screwHeadSizeInput.maximumValue = 1.5
    screwHeadSizeInput.isMaximumInclusive = True
    screwHeadSizeInput.tooltip = "Must be greater than screw diameter"
    uiState.registerCommandInput(screwHeadSizeInput)

    sidePaddingGroup = plateFeaturesGroup.children.addGroupCommandInput(SIDE_PADDING_GROUP, 'Side padding')
    sidePaddingGroup.isExpanded = uiState.getState(SIDE_PADDING_GROUP)
    uiState.registerCommandInput(sidePaddingGroup)
    generateSidePaddingInput = sidePaddingGroup.children.addBoolValueInput(BASEPLATE_WITH_SIDE_PADDING_INPUT, 'Add side padding', True, '', uiState.getState(BASEPLATE_WITH_SIDE_PADDING_INPUT))
    uiState.registerCommandInput(generateSidePaddingInput)

    sidePaddingLeftInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_LEFT_INPUT, 'Padding left', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_LEFT_INPUT)))
    sidePaddingLeftInput.minimumValue = 0
    sidePaddingLeftInput.isMinimumInclusive = True
    sidePaddingLeftInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingLeftInput)

    sidePaddingTopInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_TOP_INPUT, 'Padding top', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_TOP_INPUT)))
    sidePaddingTopInput.minimumValue = 0
    sidePaddingTopInput.isMinimumInclusive = True
    sidePaddingTopInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingTopInput)

    sidePaddingRightInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_RIGHT_INPUT, 'Padding right', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_RIGHT_INPUT)))
    sidePaddingRightInput.minimumValue = 0
    sidePaddingRightInput.isMinimumInclusive = True
    sidePaddingRightInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingRightInput)

    sidePaddingBottomInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT, 'Padding bottom', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT)))
    sidePaddingBottomInput.minimumValue = 0
    sidePaddingBottomInput.isMinimumInclusive = True
    sidePaddingBottomInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingBottomInput)

    advancedPlateSizeGroup = plateFeaturesGroup.children.addGroupCommandInput(ADVANCED_PLATE_SIZE_GROUP, 'Advanced plate size options')
    advancedPlateSizeGroup.isExpanded = uiState.getState(ADVANCED_PLATE_SIZE_GROUP)
    uiState.registerCommandInput(advancedPlateSizeGroup)
    extraBottomThicknessInput = advancedPlateSizeGroup.children.addValueInput(BASEPLATE_EXTRA_THICKNESS_INPUT, 'Extra bottom thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_EXTRA_THICKNESS_INPUT)))
    extraBottomThicknessInput.minimumValue = 0
    extraBottomThicknessInput.isMinimumInclusive = False
    uiState.registerCommandInput(extraBottomThicknessInput)

    verticalClearanceInput = advancedPlateSizeGroup.children.addValueInput(BASEPLATE_BIN_Z_CLEARANCE_INPUT, 'Clearance between baseplate and bin', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BIN_Z_CLEARANCE_INPUT)))
    verticalClearanceInput.minimumValue = 0
    verticalClearanceInput.isMinimumInclusive = True
    verticalClearanceInput.maximumValue = 0.3
    verticalClearanceInput.isMaximumInclusive = True
    uiState.registerCommandInput(verticalClearanceInput)
    
    generateBaseplateConnectionPinHoleInput = advancedPlateSizeGroup.children.addBoolValueInput(BASEPLATE_HAS_CONNECTION_HOLE_INPUT, 'Add connection holes',  True, '', uiState.getState(BASEPLATE_HAS_CONNECTION_HOLE_INPUT))
    uiState.registerCommandInput(generateBaseplateConnectionPinHoleInput)
    connectionHoleSizeInput = advancedPlateSizeGroup.children.addValueInput(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT, 'Connection hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT)))
    connectionHoleSizeInput.minimumValue = 0.1
    connectionHoleSizeInput.isMinimumInclusive = True
    connectionHoleSizeInput.maximumValue = 0.5
    connectionHoleSizeInput.isMaximumInclusive = True
    uiState.registerCommandInput(connectionHoleSizeInput)
    
    inputChangesGroup = inputs.addGroupCommandInput(INPUT_CHANGES_GROUP, 'Inputs')
    inputChangesGroup.isExpanded = uiState.getState(INPUT_CHANGES_GROUP)
    uiState.registerCommandInput(inputChangesGroup)
    saveAsDefaultsButtonInput = inputChangesGroup.children.addBoolValueInput(INPUT_CHANGES_SAVE_DEFAULTS, 'Save as new defaults', False, '', False)
    saveAsDefaultsButtonInput.text = 'Save'
    resetToDefaultsButtonInput = inputChangesGroup.children.addBoolValueInput(INPUT_CHANGES_RESET_TO_DEFAULTS, 'Reset to defaults', False, '', False)
    resetToDefaultsButtonInput.text = 'Reset'
    factoryResetButtonInput = inputChangesGroup.children.addBoolValueInput(INPUT_CHANGES_RESET_TO_FACTORY, 'Wipe saved settings', False, '', False)
    factoryResetButtonInput.text = 'Factory reset'

    previewGroup = inputs.addGroupCommandInput(PREVIEW_GROUP, 'Preview')
    uiState.registerCommandInput(previewGroup)
    previewGroup.isExpanded = uiState.getState(PREVIEW_GROUP)
    showLivePreview = previewGroup.children.addBoolValueInput(SHOW_PREVIEW_INPUT, 'Show preview (slow)', True, '', uiState.getState(SHOW_PREVIEW_INPUT))
    uiState.registerCommandInput(showLivePreview)

    updateSizingModeInputs(inputs)

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.incomingFromHTML, command_incoming_from_html, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')
    generateBaseplate(args)


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    # Get a reference to command's inputs.
    inputs = args.command.commandInputs
    showPreview: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_INPUT)
    if showPreview.value:
        if INPUTS_VALID:
            generateBaseplate(args, isPreview=True)
        else:
            args.executeFailed = True
            args.executeFailedMessage = "Some inputs are invalid, unable to generate preview"


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    global uiState
    if changed_input.id == INPUT_CHANGES_SAVE_DEFAULTS:
        saveUIInputsAsDefaults()
    elif changed_input.id == INPUT_CHANGES_RESET_TO_DEFAULTS:
        initUiState()
        uiState.forceUIRefresh()
    elif changed_input.id == INPUT_CHANGES_RESET_TO_FACTORY:
        configUtils.deleteConfigFile(UI_INPUT_DEFAULTS_CONFIG_PATH)
        initUiState()
        uiState.forceUIRefresh()
    else:
        uiState.onInputUpdate(changed_input)

    global isApplyingBedPreset
    if changed_input.id == PRINT_BED_PRESET_DROPDOWN:
        presetBedSize = printBeds.presetBedSize(uiState.getState(PRINT_BED_PRESET_DROPDOWN))
        if presetBedSize is not None:
            # the width alone doesn't match the preset yet, so its change mustn't switch to custom
            isApplyingBedPreset = True
            try:
                uiState.updateValue(PRINT_BED_WIDTH_INPUT, presetBedSize[0])
                uiState.updateValue(PRINT_BED_LENGTH_INPUT, presetBedSize[1])
            finally:
                isApplyingBedPreset = False
    elif changed_input.id in [PRINT_BED_WIDTH_INPUT, PRINT_BED_LENGTH_INPUT] and not isApplyingBedPreset:
        # a bed size edited by hand no longer is the preset's
        presetBedSize = printBeds.presetBedSize(uiState.getState(PRINT_BED_PRESET_DROPDOWN))
        bedSize = (uiState.getState(PRINT_BED_WIDTH_INPUT), uiState.getState(PRINT_BED_LENGTH_INPUT))
        if presetBedSize is not None and not all(math.isclose(a, b, abs_tol=const.DEFAULT_FILTER_TOLERANCE) for (a, b) in zip(presetBedSize, bedSize)):
            uiState.updateValue(PRINT_BED_PRESET_DROPDOWN, printBeds.PRINT_BED_CUSTOM)

    if isinstance(changed_input, adsk.core.GroupCommandInput) and changed_input.isExpanded == True:
        for input in changed_input.children:
            uiState.registerCommandInput(input)
        uiState.forceUIRefresh()

    # args.inputs only holds the siblings of the changed input, the dialog inputs are on the command
    updateSizingModeInputs(changed_input.parentCommand.commandInputs)

    inputs = args.inputs

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputsState = getInputsState()
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    INPUTS_VALID = inputsState.baseWidth >= sharedParameters.BASE_UNIT_MIN \
        and inputsState.baseLength >= sharedParameters.BASE_UNIT_MIN \
        and inputsState.xyClearance >= 0.01 \
        and inputsState.xyClearance <= 0.05 \
        and inputsState.plateWidth > 0 \
        and inputsState.plateLength > 0 \
        and (not inputsState.hasMagnetSockets or (inputsState.magnetSocketSize <= 1 and inputsState.magnetSocketSize > 0 and inputsState.magnetSocketDepth > 0)) \
        and (not inputsState.hasScrewHoles or (inputsState.screwHoleSize > 0 and inputsState.screwHoleSize <= 1 and inputsState.screwHeadSize > inputsState.screwHoleSize and inputsState.screwHeadSize <= 1.5)) \
        and (not inputsState.hasConnectionHoles or (inputsState.connectionHoleSize > 0 and inputsState.connectionHoleSize <= 0.5)) \
        and (inputsState.extraBottomThickness > 0) \
        and (inputsState.sizingMode != SIZING_MODE_FILL_AREA or fillLayoutError(inputsState) is None)


    args.areInputsValid = INPUTS_VALID
        

# This event handler is called when the layout drawing asks for its data once loaded.
def command_incoming_from_html(args: adsk.core.HTMLEventArgs):
    if args.action == 'ready':
        args.returnData = json.dumps(layoutData(getInputsState()))


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []
    global uiState


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

def fillLayoutError(inputsState: InputState) -> str | None:
    if inputsState.baseWidth <= 0 or inputsState.baseLength <= 0:
        return 'Base units must be greater than 0'
    try:
        computeFillLayout(inputsState)
        return None
    except baseplateLayout.FillLayoutError as err:
        return str(err)

def socketDrawingData(inputsState: InputState) -> dict:
    """How the drawing shows a socket from above, in mm from its cell corner, after the plate type"""
    xyClearance = inputsState.xyClearance
    isLight = inputsState.plateType == BASEPLATE_TYPE_LIGHT
    isSkeletonized = inputsState.plateType == BASEPLATE_TYPE_SKELETONIZED
    # the socket reaches a clearance past its cell and narrows by both chamfers towards its bottom
    socketNarrowing = const.BIN_BASE_TOP_SECTION_HEIGH + const.BIN_BASE_BOTTOM_SECTION_HEIGH
    hasMagnets = not isLight and inputsState.hasMagnetSockets
    hasScrews = not isLight and inputsState.hasScrewHoles
    return {
        'type': inputsState.plateType.lower(),
        'inset': (socketNarrowing - xyClearance) * 10,
        'radius': max(const.BIN_CORNER_FILLET_RADIUS + xyClearance - socketNarrowing, 0.01) * 10,
        'holeOffset': const.DIMENSION_SCREW_HOLES_OFFSET * 10,
        'magnetRadius': inputsState.magnetSocketSize / 2 * 10 if hasMagnets else None,
        'screwRadius': inputsState.screwHoleSize / 2 * 10 if hasScrews else None,
        'screwHeadRadius': inputsState.screwHeadSize / 2 * 10 if hasScrews else None,
        # the skeleton cutout keeps a pad around the holes in every corner, the same as the generator
        'padRadius': (max(inputsState.magnetSocketSize, inputsState.screwHeadSize) / 2 + 0.1) * 10 if isSkeletonized else None,
    }

def cellRects(
    inputsState: InputState,
    columnStart: int,
    columns: int,
    rowStart: int,
    rows: int,
    halfCells: tuple[bool, bool, bool, bool] = (False, False, False, False),
) -> list[tuple[float, float, float, float, bool]]:
    """Extents (minX, minY, maxX, maxY, isWhole) of the cells of a block of whole cells, in the generator
    coordinates, with half cells past the sides asked for (left, right, bottom, top). Cells start a clearance before
    the origin, only whole cells have holes"""
    (baseWidth, baseLength, xyClearance) = (inputsState.baseWidth, inputsState.baseLength, inputsState.xyClearance)
    def spans(start: int, count: int, baseUnit: float, halfStart: bool, halfEnd: bool) -> list[tuple[float, float, bool]]:
        result = [((start + i) * baseUnit - xyClearance, (start + i + 1) * baseUnit - xyClearance, True) for i in range(count)]
        if halfStart:
            result.insert(0, (start * baseUnit - xyClearance - baseUnit / 2, start * baseUnit - xyClearance, False))
        if halfEnd:
            result.append(((start + count) * baseUnit - xyClearance, (start + count + 0.5) * baseUnit - xyClearance, False))
        return result
    (halfLeft, halfRight, halfBottom, halfTop) = halfCells
    return [
        (minX, minY, maxX, maxY, isWholeX and isWholeY)
        for (minX, maxX, isWholeX) in spans(columnStart, columns, baseWidth, halfLeft, halfRight)
        for (minY, maxY, isWholeY) in spans(rowStart, rows, baseLength, halfBottom, halfTop)
    ]

def fillLayoutData(inputsState: InputState) -> dict:
    """What the fill layout drawing shows, sizes in mm with the area corner at the origin"""
    error = fillLayoutError(inputsState)
    if error is not None:
        return {'error': error}
    layout = computeFillLayout(inputsState)
    (baseWidth, baseLength, xyClearance) = (inputsState.baseWidth, inputsState.baseLength, inputsState.xyClearance)
    # the plate reaches past the origin, the fit tolerance is left around it
    originX = layout.x.startExtent(baseWidth) + inputsState.fitTolerance / 2
    originY = layout.y.startExtent(baseLength) + inputsState.fitTolerance / 2
    def rect(minX: float, minY: float, maxX: float, maxY: float) -> dict:
        return {'x': (minX + originX) * 10, 'y': (minY + originY) * 10, 'width': (maxX - minX) * 10, 'length': (maxY - minY) * 10}
    shapes: list[tuple] = []
    pieces = []
    for piece in layout.pieces:
        shape = baseplateLayout.pieceShapeKey(piece)
        if shape not in shapes:
            shapes.append(shape)
        (minX, minY, maxX, maxY) = baseplateLayout.pieceOutline(layout, piece, baseWidth, baseLength, xyClearance)
        cells = cellRects(inputsState, piece.cellOffsetX, piece.cellsX, piece.cellOffsetY, piece.cellsY, (
            piece.isLeftEdge and layout.x.hasHalfCellsStart,
            piece.isRightEdge and layout.x.hasHalfCellsEnd,
            piece.isBottomEdge and layout.y.hasHalfCellsStart,
            piece.isTopEdge and layout.y.hasHalfCellsEnd,
        ))
        pieces.append({
            **rect(minX, minY, maxX, maxY),
            'label': f'{piece.cellsX}x{piece.cellsY}',
            'cells': [{**rect(*cell[:4]), 'holes': cell[4]} for cell in cells],
        })
    pieceCount = f'{len(layout.pieces)} piece' + ('s' if len(layout.pieces) > 1 else '')
    uniqueCount = f', {len(shapes)} unique' if len(shapes) < len(layout.pieces) else ''
    halfCellSides = [side for (hasHalfCells, side) in [
        (layout.x.hasHalfCellsStart, 'left'),
        (layout.x.hasHalfCellsEnd, 'right'),
        (layout.y.hasHalfCellsStart, 'front'),
        (layout.y.hasHalfCellsEnd, 'back'),
    ] if hasHalfCells]
    halfCellsNote = f' + half cells {", ".join(halfCellSides)}' if len(halfCellSides) > 0 else ''
    def padding(axis: baseplateLayout.AxisLayout) -> str:
        return f'{axis.paddingStart * 10:.1f} + {axis.paddingEnd * 10:.1f}'
    return {
        'area': [inputsState.areaWidth * 10, inputsState.areaLength * 10],
        'socket': socketDrawingData(inputsState),
        'pieces': pieces,
        'caption': [
            f'{inputsState.plateType} {layout.x.cells} x {layout.y.cells} u{halfCellsNote}, {pieceCount}{uniqueCount}',
            f'padding X {padding(layout.x)} mm, Y {padding(layout.y)} mm'
            + (', turned 90° on the bed' if layout.isBedRotated else ''),
        ],
    }

def gridPlateExtent(inputsState: InputState) -> tuple[float, float, float, float]:
    """XY extent (minX, minY, maxX, maxY) of a grid units plate, where a plate without padding starts at the origin"""
    hasPadding = inputsState.hasPadding
    return (
        -inputsState.paddingLeft if hasPadding else 0,
        -inputsState.paddingBottom if hasPadding else 0,
        inputsState.plateWidth * inputsState.baseWidth - inputsState.xyClearance * 2 + (inputsState.paddingRight if hasPadding else 0),
        inputsState.plateLength * inputsState.baseLength - inputsState.xyClearance * 2 + (inputsState.paddingTop if hasPadding else 0),
    )

def gridLayoutData(inputsState: InputState) -> dict:
    """What the plate drawing shows in grid units mode, the same shape as the fill layout data with the plate as the only piece"""
    if inputsState.baseWidth <= 0 or inputsState.baseLength <= 0:
        return {'error': 'Base units must be greater than 0'}
    if inputsState.plateWidth <= 0 or inputsState.plateLength <= 0:
        return {'error': 'Plate size must be at least 1 x 1 u'}
    (columns, rows) = (int(inputsState.plateWidth), int(inputsState.plateLength))
    (minX, minY, maxX, maxY) = gridPlateExtent(inputsState)
    def rect(rectMinX: float, rectMinY: float, rectMaxX: float, rectMaxY: float) -> dict:
        return {'x': (rectMinX - minX) * 10, 'y': (rectMinY - minY) * 10, 'width': (rectMaxX - rectMinX) * 10, 'length': (rectMaxY - rectMinY) * 10}
    paddingSides = [
        f'{side} {value * 10:.1f}'
        for (side, value) in [
            ('left', inputsState.paddingLeft),
            ('top', inputsState.paddingTop),
            ('right', inputsState.paddingRight),
            ('bottom', inputsState.paddingBottom),
        ]
        if inputsState.hasPadding and value > 0
    ]
    return {
        'area': [(maxX - minX) * 10, (maxY - minY) * 10],
        'showArea': False,
        'socket': socketDrawingData(inputsState),
        'pieces': [{
            **rect(minX, minY, maxX, maxY),
            'label': f'{columns}x{rows}',
            'cells': [{**rect(*cell[:4]), 'holes': cell[4]} for cell in cellRects(inputsState, 0, columns, 0, rows)],
        }],
        'caption': [
            f'{inputsState.plateType} {columns} x {rows} u',
            f'{(maxX - minX) * 10:.1f} x {(maxY - minY) * 10:.1f} mm',
            f'padding {", ".join(paddingSides)} mm' if len(paddingSides) > 0 else 'no padding',
        ],
    }

def layoutData(inputsState: InputState) -> dict:
    if inputsState.sizingMode == SIZING_MODE_FILL_AREA:
        return fillLayoutData(inputsState)
    return gridLayoutData(inputsState)

def updateSizingModeInputs(inputs: adsk.core.CommandInputs):
    """Shows the inputs of the selected sizing mode and refreshes the layout drawing"""
    isFillArea = uiState.getState(SIZING_MODE_DROPDOWN) == SIZING_MODE_FILL_AREA
    for inputId in GRID_UNITS_MODE_INPUTS:
        inputs.itemById(inputId).isVisible = not isFillArea
    for inputId in FILL_AREA_MODE_INPUTS:
        inputs.itemById(inputId).isVisible = isFillArea
    browserInput: adsk.core.BrowserCommandInput = inputs.itemById(LAYOUT_BROWSER)
    try:
        browserInput.sendInfoToHTML('update', json.dumps(layoutData(getInputsState())))
    except Exception as err:
        # the page asks for the data itself once it has loaded
        futil.log(f'{CMD_NAME} Layout drawing not ready yet, {err}')

def baseplateDisplayName(plateWidth: int, plateLength: int) -> str:
    return 'Gridfinity baseplate {}x{}'.format(int(plateLength), int(plateWidth))

def snapshotSettings(inputs: adsk.core.CommandInputs) -> list[dict]:
    return settingsUtils.snapshotInputs(inputs, [INFO_GROUP, INPUT_CHANGES_GROUP, PREVIEW_GROUP], CMD_NAME)

def generateBaseplate(args: adsk.core.CommandEventArgs, isPreview: bool = False):
    startTime = time.perf_counter()
    # the settings come first, so a failing build can be reproduced from the log
    commonUtils.fileLog(f'{CMD_NAME} Generating baseplate{" preview" if isPreview else ""} with settings:\n{settingsUtils.settingsText(snapshotSettings(args.command.commandInputs))}')
    inputsState = getInputsState()

    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        if des.designType == 0:
            raise UnsupportedDesignTypeException('Timeline must be enabled for the generator to work, projects with disabled design history currently are not supported')
        root = adsk.fusion.Component.cast(des.rootComponent)

        # a fill is laid out as one plate of the whole grid with the centering padding, then split into pieces
        isFillArea = inputsState.sizingMode == SIZING_MODE_FILL_AREA
        if isFillArea:
            fillLayout = computeFillLayout(inputsState)
            (plateWidth, plateLength) = (fillLayout.x.cells, fillLayout.y.cells)
            hasPadding = True
            (paddingLeft, paddingTop, paddingRight, paddingBottom) = (fillLayout.x.paddingStart, fillLayout.y.paddingEnd, fillLayout.x.paddingEnd, fillLayout.y.paddingStart)
            plateExtent = baseplateLayout.layoutOutline(fillLayout, inputsState.baseWidth, inputsState.baseLength, inputsState.xyClearance)
            baseplateName = 'Gridfinity baseplate fill {:g}x{:g} mm'.format(round(inputsState.areaLength * 10, 1), round(inputsState.areaWidth * 10, 1))
        else:
            (plateWidth, plateLength) = (inputsState.plateWidth, inputsState.plateLength)
            hasPadding = inputsState.hasPadding
            (paddingLeft, paddingTop, paddingRight, paddingBottom) = (inputsState.paddingLeft, inputsState.paddingTop, inputsState.paddingRight, inputsState.paddingBottom)
            baseplateName = baseplateDisplayName(plateWidth, plateLength)
            plateExtent = gridPlateExtent(inputsState)

        originalTimelineCount = des.timeline.count
        if des.designIntent == adsk.fusion.DesignIntentTypes.HybridDesignIntentType:
            # create new component, only allowed in hybrid intent type
            newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())

            newCmpOcc.component.name = baseplateName
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
            CMD_NAME,
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
            baseplateBody.name = baseplateName
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
            tagUtils.tagBody(baseplateBody, tagUtils.TAG_BASEPLATE, snapshotSettings(args.command.commandInputs), baseplateParameters)

        if des.designType == adsk.fusion.DesignTypes.ParametricDesignType:
            # group features in timeline
            plateGroup = des.timeline.timelineGroups.add(originalTimelineCount, des.timeline.count - 1)
            plateGroup.name = baseplateName
        futil.log(f'{CMD_NAME} {baseplateName} generated in {time.perf_counter() - startTime:.3f}s')
    except UnsupportedDesignTypeException as err:
        args.executeFailed = True
        args.executeFailedMessage = 'Design type is unsupported. Projects with disabled design history are unsupported, please enable timeline feature to proceed.'
        return False
    except Exception as err:
        args.executeFailed = True
        args.executeFailedMessage = getErrorMessage()
        futil.log(f'{CMD_NAME} Error occurred, {err}, {getErrorMessage()}')
        return False

def initUiState():
    global uiState
    uiState.initValue(INFO_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(BASIC_SIZES_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(XY_DIMENSIONS_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(PLATE_FEATURES_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(MAGNET_SOCKET_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(SCREW_HOLE_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(ADVANCED_PLATE_SIZE_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(INPUT_CHANGES_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(SIDE_PADDING_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(PREVIEW_GROUP, True, adsk.core.GroupCommandInput.classType())

    uiState.initValue(BASEPLATE_BASE_UNIT_WIDTH_INPUT, DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_BASE_UNIT_LENGTH_INPUT, DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BIN_XY_CLEARANCE_INPUT_ID, const.BIN_XY_CLEARANCE, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_WIDTH_INPUT, 2, adsk.core.IntegerSpinnerCommandInput.classType())
    uiState.initValue(BASEPLATE_LENGTH_INPUT, 3, adsk.core.IntegerSpinnerCommandInput.classType())
    uiState.initValue(BASEPLATE_TYPE_DROPDOWN, BASEPLATE_TYPE_LIGHT, adsk.core.DropDownCommandInput.classType())

    uiState.initValue(SIZING_MODE_DROPDOWN, SIZING_MODE_FILL_AREA, adsk.core.DropDownCommandInput.classType())
    uiState.initValue(FILL_AREA_WIDTH_INPUT, 40, adsk.core.ValueCommandInput.classType())
    uiState.initValue(FILL_AREA_LENGTH_INPUT, 30, adsk.core.ValueCommandInput.classType())
    uiState.initValue(FILL_FIT_TOLERANCE_INPUT, 0.1, adsk.core.ValueCommandInput.classType())
    uiState.initValue(FILL_ALIGN_X_DROPDOWN, 'Center', adsk.core.DropDownCommandInput.classType())
    uiState.initValue(FILL_ALIGN_Y_DROPDOWN, 'Center', adsk.core.DropDownCommandInput.classType())
    uiState.initValue(FILL_HALF_CELLS_INPUT, True, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(PRINT_BED_GROUP, True, adsk.core.GroupCommandInput.classType())
    # a common bed size, the dropdown starts on custom, its first option
    (defaultBedWidth, defaultBedLength) = printBeds.presetBedSize(printBeds.presetLabel('Bambu Lab A1, P1, X1'))
    uiState.initValue(PRINT_BED_PRESET_DROPDOWN, printBeds.PRINT_BED_CUSTOM, adsk.core.DropDownCommandInput.classType())
    uiState.initValue(PRINT_BED_WIDTH_INPUT, defaultBedWidth, adsk.core.ValueCommandInput.classType())
    uiState.initValue(PRINT_BED_LENGTH_INPUT, defaultBedLength, adsk.core.ValueCommandInput.classType())
    uiState.initValue(PRINT_BED_MARGIN_INPUT, 0.5, adsk.core.ValueCommandInput.classType())

    uiState.initValue(BASEPLATE_WITH_MAGNETS_INPUT, True, adsk.core.BoolValueCommandInput.classType())

    uiState.initValue(BASEPLATE_MAGNET_DIAMETER_INPUT, const.DIMENSION_MAGNET_CUTOUT_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_MAGNET_HEIGHT_INPUT, const.DIMENSION_MAGNET_CUTOUT_DEPTH, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_WITH_SCREWS_INPUT, True, adsk.core.BoolValueCommandInput.classType())

    uiState.initValue(BASEPLATE_WITH_SIDE_PADDING_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_LEFT_INPUT, 0, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_TOP_INPUT, 0, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_RIGHT_INPUT, 0, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT, 0, adsk.core.BoolValueCommandInput.classType())

    uiState.initValue(BASEPLATE_SCREW_DIAMETER_INPUT, const.DIMENSION_PLATE_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SCREW_HEIGHT_INPUT, const.DIMENSION_SCREW_HEAD_CUTOUT_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_EXTRA_THICKNESS_INPUT, const.BASEPLATE_EXTRA_HEIGHT, adsk.core.ValueCommandInput.classType())

    uiState.initValue(BASEPLATE_BIN_Z_CLEARANCE_INPUT, const.BASEPLATE_BIN_Z_CLEARANCE, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_HAS_CONNECTION_HOLE_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_JOINT_ORIGINS_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT, const.DIMENSION_PLATE_CONNECTION_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(SHOW_PREVIEW_INPUT, False, adsk.core.BoolValueCommandInput.classType())

    recordedDefaults = configUtils.readJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH)
    if recordedDefaults:
        futil.log(f'{CMD_NAME} Found previously saving default values, restoring {recordedDefaults}')

        try:
            uiState.initValues(recordedDefaults)
            futil.log(f'{CMD_NAME} Successfully restored default values')
        except Exception as err:
            futil.log(f'{CMD_NAME} Failed to restore default values, err: {err}')


    else:
        futil.log(f'{CMD_NAME} No previously saved default values')

def saveUIInputsAsDefaults():
    futil.log(f'{CMD_NAME} Saving UI state to file')
    result = configUtils.dumpJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH, uiState.toDict())
    if result:
        futil.log(f'{CMD_NAME} Saved successfully')
    else:
        futil.log(f'{CMD_NAME} UI state failed to save')

def getInputsState():
    global uiState
    return InputState(
        uiState.getState(BASEPLATE_BASE_UNIT_WIDTH_INPUT),
        uiState.getState(BASEPLATE_BASE_UNIT_LENGTH_INPUT),
        uiState.getState(BIN_XY_CLEARANCE_INPUT_ID),
        uiState.getState(BASEPLATE_WIDTH_INPUT),
        uiState.getState(BASEPLATE_LENGTH_INPUT),
        uiState.getState(BASEPLATE_TYPE_DROPDOWN),
        uiState.getState(BASEPLATE_WITH_MAGNETS_INPUT),
        uiState.getState(BASEPLATE_MAGNET_DIAMETER_INPUT),
        uiState.getState(BASEPLATE_MAGNET_HEIGHT_INPUT),
        uiState.getState(BASEPLATE_WITH_SCREWS_INPUT),
        uiState.getState(BASEPLATE_SCREW_DIAMETER_INPUT),
        uiState.getState(BASEPLATE_SCREW_HEIGHT_INPUT),
        uiState.getState(BASEPLATE_WITH_SIDE_PADDING_INPUT),
        uiState.getState(BASEPLATE_SIDE_PADDING_LEFT_INPUT),
        uiState.getState(BASEPLATE_SIDE_PADDING_TOP_INPUT),
        uiState.getState(BASEPLATE_SIDE_PADDING_RIGHT_INPUT),
        uiState.getState(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT),
        uiState.getState(BASEPLATE_EXTRA_THICKNESS_INPUT),
        uiState.getState(BASEPLATE_BIN_Z_CLEARANCE_INPUT),
        uiState.getState(BASEPLATE_HAS_CONNECTION_HOLE_INPUT),
        uiState.getState(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT),
        uiState.getState(SIZING_MODE_DROPDOWN),
        uiState.getState(FILL_AREA_WIDTH_INPUT),
        uiState.getState(FILL_AREA_LENGTH_INPUT),
        uiState.getState(FILL_FIT_TOLERANCE_INPUT),
        uiState.getState(PRINT_BED_WIDTH_INPUT),
        uiState.getState(PRINT_BED_LENGTH_INPUT),
        uiState.getState(PRINT_BED_MARGIN_INPUT),
        uiState.getState(FILL_ALIGN_X_DROPDOWN),
        uiState.getState(FILL_ALIGN_Y_DROPDOWN),
        uiState.getState(FILL_HALF_CELLS_INPUT),
        uiState.getState(BASEPLATE_JOINT_ORIGINS_INPUT),
    )