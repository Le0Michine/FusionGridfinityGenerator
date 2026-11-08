import adsk.core, adsk.fusion, traceback
import json
import os
import pathlib
import time
import math


from ...lib import configUtils
from ...lib import tagUtils
from ...lib import settingsUtils
from ...lib import placementUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils import combineUtils
from ...lib.gridfinityUtils import geometryUtils
from ...lib.gridfinityUtils import faceUtils
from ...lib.gridfinityUtils import shellUtils
from ...lib.gridfinityUtils import commonUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils import parameterUtils
from ...lib.gridfinityUtils import sharedParameters
from ...lib.gridfinityUtils.dim import Dim
from ...lib.gridfinityUtils.baseGenerator import createSingleGridfinityBaseBody, createBaseBodyPattern, cutBaseClearance, cutWallJunctionPockets, cellCenters, createCellJointOrigins, keepBodiesInCells, cutOutsideShape, cutShapeWallJunctionPockets
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.binBodyGenerator import createGridfinityBinBody, createShapeCavity, binBodyTopHeight, createCompartmentCutout, compartmentCutoutFilletRadius, tabTopClearance, createTabLabel, hollowTabWallThickness
from ...lib.gridfinityUtils import labelGenerator
from ...lib.gridfinityUtils import compartmentLayout
from ...lib.gridfinityUtils import binShape
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput, BinBodyCompartmentDefinition
from ...lib.gridfinityUtils.binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from ...lib.gridfinityUtils.binBodyTabGenerator import createGridfinityBinBodyTab, createTabHollowCuts, TabCavity, TabWallOpenings
from ...lib.ui.commandUiState import CommandUiState
from ...lib.ui.defaultsButtons import addDefaultsButtonRow, handleDefaultsButtons, DEFAULTS_SAVE, DEFAULTS_FACTORY_RESET
from ...lib.ui.dialogFont import dialogFontUrl
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException

app = adsk.core.Application.get()
ui = app.userInterface


# *** The command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBin'
CMD_NAME = 'Gridfinity bin'
CMD_Description = 'Create simple gridfinity bin'

commandUIState = CommandUiState(CMD_NAME)
actualDimensionsTableUiState = CommandUiState(CMD_NAME)
# pockets drawn in the compartments drawing, see compartmentLayout
compartmentPockets: list[dict] = []
# cells of a custom shaped bin, see binShape, empty while the bin is a plain rectangle
binShapeCells: list[tuple[int, int]] = []

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
COMPARTMENTS_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'compartments.html').as_uri()
SHAPE_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'shape.html').as_uri()

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Constants
BIN_BASIC_SIZES_GROUP = "bin_basic_sizes_group"
BIN_DIMENSIONS_GROUP = "bin_dimensions_group"
BIN_FEATURES_GROUP = "bin_features_group"
BIN_COMPARTMENTS_GROUP_ID = 'compartments_group'
BIN_SCOOP_GROUP_ID = 'bin_scoop_group'
BIN_TAB_FEATURES_GROUP_ID = 'bin_tab_features_group'
BIN_BASE_FEATURES_GROUP_ID = 'bin_base_features_group'
USER_CHANGES_GROUP_ID = 'user_changes_group'
PREVIEW_GROUP_ID = 'preview_group'
INFO_GROUP = 'info_group'

BIN_BASE_WIDTH_UNIT_INPUT_ID = 'base_width_unit'
BIN_BASE_LENGTH_UNIT_INPUT_ID = 'base_length_unit'
BIN_HEIGHT_UNIT_INPUT_ID = 'height_unit'
BIN_XY_CLEARANCE_INPUT_ID = 'bin_xy_tolerance'
BIN_WIDTH_INPUT_ID = 'bin_width'
BIN_LENGTH_INPUT_ID = 'bin_length'
BIN_HEIGHT_INPUT_ID = 'bin_height'
BIN_REAL_DIMENSIONS_TABLE = "real_dimensions"
BIN_REAL_DIMENSIONS_TABLE_TOTAL_WIDTH = "total_real_width"
BIN_REAL_DIMENSIONS_TABLE_TOTAL_LENGTH = "total_real_length"
BIN_REAL_DIMENSIONS_TABLE_TOTAL_HEIGHT = "total_real_height"
BIN_WALL_THICKNESS_INPUT_ID = 'bin_wall_thickness'
BIN_GENERATE_BASE_INPUT_ID = 'bin_generate_base'
BIN_GENERATE_BODY_INPUT_ID = 'bin_generate_body'
BIN_JOINT_ORIGINS_INPUT_ID = 'bin_joint_origins'
BIN_SCREW_HOLES_INPUT_ID = 'bin_screw_holes'
BIN_MAGNET_CUTOUTS_INPUT_ID = 'bin_magnet_cutouts'
BIN_MAGNET_CUTOUTS_TABS_INPUT_ID = 'bin_magnet_cutouts_tabs'
BIN_SCREW_DIAMETER_INPUT = 'screw_diameter'
BIN_MAGNET_DIAMETER_INPUT = 'magnet_diameter'
BIN_MAGNET_HEIGHT_INPUT = 'magnet_height'
BIN_HAS_SCOOP_INPUT_ID = 'bin_has_scoop'
BIN_SCOOP_MAX_RADIUS_INPUT_ID = 'bin_scoop_max_radius'
BIN_HAS_TAB_INPUT_ID = 'bin_has_tab'
BIN_TAB_LENGTH_INPUT_ID = 'bin_tab_length'
BIN_TAB_WIDTH_INPUT_ID = 'bin_tab_width'
BIN_TAB_POSITION_INPUT_ID = 'bin_tab_position'
BIN_TAB_ANGLE_INPUT_ID = 'bin_tab_angle'
BIN_TAB_HOLLOW_INPUT_ID = 'bin_tab_hollow'
BIN_TAB_HOLLOW_SIDES_INPUT_ID = 'bin_tab_hollow_sides'
BIN_TAB_TOP_ANGLE_INPUT_ID = 'bin_tab_top_angle'
BIN_TAB_LABEL_TEXT_INPUT_ID = 'bin_tab_label_text'
BIN_TAB_LABEL_ICON_INPUT_ID = 'bin_tab_label_icon'
BIN_TAB_LABEL_STYLE_INPUT_ID = 'bin_tab_label_style'
BIN_TAB_LABEL_BOLD_INPUT_ID = 'bin_tab_label_bold'
BIN_WITH_LIP_INPUT_ID = 'with_lip'
BIN_WITH_LIP_NOTCHES_INPUT_ID = 'with_lip_notches'
# replaced by the drawing, still read from defaults saved before it
LEGACY_COMPARTMENTS_GRID_TYPE_ID = 'compartments_grid_type'
LEGACY_COMPARTMENTS_GRID_TYPE_CUSTOM = 'Custom grid'
BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID = 'compartments_grid_w'
BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID = 'compartments_grid_l'
GRID_CELLS_MAX = 100
# the same page twice, a row with the grid size and a drawing to pick compartment shapes, labels and depths,
# the drawing shown on request as it takes space. Fusion doesn't resize a browser input once it's shown
BIN_COMPARTMENTS_SHOW_LAYOUT_ID = 'compartments_show_layout'
BIN_COMPARTMENTS_GRID_BROWSER_ID = 'compartments_grid_browser'
BIN_COMPARTMENTS_BROWSER_ID = 'compartments_browser'
COMPARTMENTS_PAGE_GRID = 'grid'
COMPARTMENTS_PAGE_LAYOUT = 'layout'
BIN_TYPE_DROPDOWN_ID = 'bin_type'
# a drawing of the bin's cells to leave some out, like a tetris piece, shown with the checkbox
BIN_SHAPE_CUSTOM_ID = 'custom_shape'
BIN_SHAPE_BROWSER_ID = 'shape_browser'
SHAPE_NOTE = 'Compartments, scoop and label tab are not built for custom shapes yet'
BIN_TYPE_HOLLOW = 'Hollow'
BIN_TYPE_SHELLED = 'Shelled'

# default name of bins generated before tagging, keep as is even if the naming changes
BIN_LEGACY_NAME_PREFIX = 'Gridfinity bin '

# User parameter names are stored in user documents, keep these literal
BIN_PARAMETER_BASE_NAME = 'gfBin'
BIN_HEIGHT_PARAMETER = 'heightU'
BIN_LABEL_PARAMETER = 'label'
# per bin fallback for the shared height unit
BIN_HEIGHT_UNIT_PARAMETER = 'heightUnit'
BIN_PARAMETERS = [BIN_HEIGHT_PARAMETER, BIN_HEIGHT_UNIT_PARAMETER, sharedParameters.BASE_WIDTH_FALLBACK_PARAMETER, sharedParameters.BASE_LENGTH_FALLBACK_PARAMETER]
BIN_TYPE_SOLID = 'Solid'

INPUT_CHANGES_BUTTONS_BROWSER = 'input_changes_buttons'
PRESERVE_CHAGES_RADIO_GROUP = 'preserve_changes'
PRESERVE_CHAGES_RADIO_GROUP_PRESERVE = 'Preserve inputs'
PRESERVE_CHAGES_RADIO_GROUP_RESET = 'Reset inputs after creation'
RESET_CHAGES_INPUT = 'reset_changes'
SHOW_PREVIEW_INPUT = 'show_preview'
SHOW_PREVIEW_MANUAL_INPUT = 'show_preview_manual'
PREVIEW_TIME_INPUT = 'preview_time'

INFO_TEXT = ("<b>Help:</b> Info for inputs can be found "
             "<a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Bin-generator-options\">"
             "Here on our GitHub</a>.")

def infoText():
    version = tagUtils.getGeneratorVersion()
    return f"{INFO_TEXT}<br><span style=\"color:#808080; font-size:small\">Version {version}</span>" if version else INFO_TEXT

def applySharedParameterDefaults():
    """Usable shared units of the design replace the remembered inputs, so new bins match the existing ones by default"""
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        return
    (baseWidth, baseLength) = sharedParameters.usableSharedBaseUnits(design)
    for (inputId, value) in [
        (BIN_BASE_WIDTH_UNIT_INPUT_ID, baseWidth),
        (BIN_BASE_LENGTH_UNIT_INPUT_ID, baseLength),
        (BIN_HEIGHT_UNIT_INPUT_ID, sharedParameters.usableSharedHeightUnit(design)),
    ]:
        if value is not None:
            commandUIState.initValue(inputId, value, adsk.core.ValueCommandInput.classType())
            commonUtils.debugLog(f'{CMD_NAME} dialog default {inputId} = {value} from the shared parameter')

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

def refreshUi():
    global commandUIState
    commandUIState.forceUIRefresh()
    update_actual_bin_dimensions()
    # before the inputs that depend on the shape
    normalizeShapeCells()
    onChangeValidate()
    normalizeCompartmentPockets()
    refreshCompartmentsDrawing()
    refreshShapeDrawing()

def initDefaultUiState():
    global commandUIState
    global actualDimensionsTableUiState
    global compartmentPockets
    global binShapeCells
    commandUIState.initValue(INFO_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_BASIC_SIZES_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_DIMENSIONS_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_FEATURES_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_COMPARTMENTS_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_COMPARTMENTS_SHOW_LAYOUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCOOP_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_TAB_FEATURES_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_BASE_FEATURES_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(USER_CHANGES_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(PREVIEW_GROUP_ID, True, adsk.core.GroupCommandInput.classType())

    commandUIState.initValue(BIN_BASE_WIDTH_UNIT_INPUT_ID, const.DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_BASE_LENGTH_UNIT_INPUT_ID, const.DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_HEIGHT_UNIT_INPUT_ID, const.DIMENSION_DEFAULT_HEIGHT_UNIT, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_XY_CLEARANCE_INPUT_ID, const.BIN_XY_CLEARANCE, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_WIDTH_INPUT_ID, 2, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_LENGTH_INPUT_ID, 3, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_SHAPE_CUSTOM_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_HEIGHT_INPUT_ID, 5, adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_GENERATE_BODY_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TYPE_DROPDOWN_ID, BIN_TYPE_HOLLOW, adsk.core.DropDownCommandInput.classType())
    commandUIState.initValue(BIN_WALL_THICKNESS_INPUT_ID, const.BIN_WALL_THICKNESS, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_WITH_LIP_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_WITH_LIP_NOTCHES_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())

    commandUIState.initValue(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, 1, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, 1, adsk.core.IntegerSpinnerCommandInput.classType())

    commandUIState.initValue(BIN_HAS_SCOOP_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCOOP_MAX_RADIUS_INPUT_ID, const.BIN_SCOOP_MAX_RADIUS, adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_HAS_TAB_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_LENGTH_INPUT_ID, 1, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_WIDTH_INPUT_ID, const.BIN_TAB_WIDTH, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_POSITION_INPUT_ID, 0, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_ANGLE_INPUT_ID, '45 deg', adsk.core.ValueCommandInput.classType())
    # follows the bin type when it changes, shelled bins get hollow tabs
    commandUIState.initValue(BIN_TAB_HOLLOW_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_HOLLOW_SIDES_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_TOP_ANGLE_INPUT_ID, '0 deg', adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_LABEL_TEXT_INPUT_ID, '', adsk.core.StringValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_LABEL_ICON_INPUT_ID, labelGenerator.LABEL_ICON_NONE, adsk.core.DropDownCommandInput.classType())
    commandUIState.initValue(BIN_TAB_LABEL_STYLE_INPUT_ID, labelGenerator.LABEL_STYLE_OUTLINE, adsk.core.DropDownCommandInput.classType())
    commandUIState.initValue(BIN_TAB_LABEL_BOLD_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())

    commandUIState.initValue(BIN_GENERATE_BASE_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_JOINT_ORIGINS_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCREW_HOLES_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCREW_DIAMETER_INPUT, const.DIMENSION_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_SCREW_DIAMETER_INPUT, const.DIMENSION_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_CUTOUTS_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_DIAMETER_INPUT, const.DIMENSION_MAGNET_CUTOUT_DIAMETER, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_HEIGHT_INPUT, const.DIMENSION_MAGNET_CUTOUT_DEPTH, adsk.core.ValueCommandInput.classType())

    compartmentPockets = []
    binShapeCells = []
    recordedDefaults = configUtils.readJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH)
    if recordedDefaults is not None and recordedDefaults.get('static_ui') is not None:
        staticUiState = recordedDefaults['static_ui']
        futil.log(f'{CMD_NAME} Found previously saved default values, restoring {staticUiState}')
        try:
            commandUIState.initValues(staticUiState)
            futil.log(f'{CMD_NAME} Successfully restored default values')
        except Exception as err:
            futil.log(f'{CMD_NAME} Failed to restore default values, err: {err}')
        try:
            if isinstance(recordedDefaults.get('compartments'), list):
                # pockets only count with the layout shown, the grid is uniform otherwise
                if commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID):
                    compartmentPockets = recordedDefaults['compartments']
            elif staticUiState.get(LEGACY_COMPARTMENTS_GRID_TYPE_ID, {}).get('value') == LEGACY_COMPARTMENTS_GRID_TYPE_CUSTOM:
                # the custom grid table saved before the drawing, its rows become pockets
                compartmentPockets = compartmentLayout.fromTableRows(recordedDefaults.get('compartments_table'), fullCompartmentDepth() / 10)
                commandUIState.initValue(BIN_COMPARTMENTS_SHOW_LAYOUT_ID, True, adsk.core.BoolValueCommandInput.classType())
                futil.log(f'{CMD_NAME} Restored compartments from the saved custom grid table')
        except Exception as err:
            futil.log(f'{CMD_NAME} Failed to restore compartments, err: {err}')
        commandUIState.removeValue(LEGACY_COMPARTMENTS_GRID_TYPE_ID)
        if commandUIState.getState(BIN_SHAPE_CUSTOM_ID) and isinstance(recordedDefaults.get('shape'), list):
            binShapeCells = recordedDefaults['shape']
    futil.log(f'{CMD_NAME} UI state initialized')

def getErrorMessage(text = "An unknown error occurred, please validate your inputs and try again"):
    stackTrace = traceback.format_exc()
    return f"{text}:<br>{stackTrace}"

def showErrorInMessageBox(text = "An unknown error occurred, please validate your inputs and try again"):
    if ui:
        ui.messageBox(getErrorMessage(text), f"{CMD_NAME} Error")

# Executed when add-in is run.
def start():
    try:
        futil.log(f'{CMD_NAME} Command Start Event')
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
        initDefaultUiState()
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

def render_actual_bin_dimensions_table(inputs: adsk.core.CommandInputs):
    global actualDimensionsTableUiState
    actualDimensionsTable = inputs.addTableCommandInput(BIN_REAL_DIMENSIONS_TABLE, "Actual dimensions (mm)", 3, "1:1:1")
    totalWidth = actualDimensionsTable.commandInputs.addStringValueInput(BIN_REAL_DIMENSIONS_TABLE_TOTAL_WIDTH, "", "Width")
    totalWidth.isReadOnly = True
    actualDimensionsTableUiState.registerCommandInput(totalWidth)
    actualDimensionsTableUiState.initValue(totalWidth.id, "", totalWidth.objectType)
    totalLength = actualDimensionsTable.commandInputs.addStringValueInput(BIN_REAL_DIMENSIONS_TABLE_TOTAL_LENGTH, "", "Length")
    totalLength.isReadOnly = True
    actualDimensionsTableUiState.registerCommandInput(totalLength)
    actualDimensionsTableUiState.initValue(totalLength.id, "", totalLength.objectType)
    totalHeight = actualDimensionsTable.commandInputs.addStringValueInput(BIN_REAL_DIMENSIONS_TABLE_TOTAL_HEIGHT, "", "Height")
    totalHeight.isReadOnly = True
    actualDimensionsTableUiState.registerCommandInput(totalHeight)
    actualDimensionsTableUiState.initValue(totalHeight.id, "", totalHeight.objectType)
    actualDimensionsTable.addCommandInput(totalWidth, 0, 0)
    actualDimensionsTable.addCommandInput(totalLength, 0, 1)
    actualDimensionsTable.addCommandInput(totalHeight, 0, 2)
    actualDimensionsTable.tooltip = 'Actual bin dimensions'
    actualDimensionsTable.tablePresentationStyle = adsk.core.TablePresentationStyles.transparentBackgroundTablePresentationStyle
    actualDimensionsTable.hasGrid = False
    actualDimensionsTable.minimumVisibleRows = 1
    actualDimensionsTable.maximumVisibleRows = 1
    return actualDimensionsTable

def compartmentCellSize() -> tuple[float, float, float]:
    """Width and length of a compartment grid cell in mm, and the smallest one that still fits the corner fillets"""
    wallThickness: float = commandUIState.getState(BIN_WALL_THICKNESS_INPUT_ID)
    xyClearance: float = commandUIState.getState(BIN_XY_CLEARANCE_INPUT_ID)
    def cell(baseUnit: float, binSize: int, cells: int) -> float:
        return round((baseUnit * binSize - wallThickness * 2 - xyClearance * 2 - wallThickness * (cells - 1)) / cells * 10, 2)
    return (
        cell(commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID), commandUIState.getState(BIN_WIDTH_INPUT_ID), commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)),
        cell(commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID), commandUIState.getState(BIN_LENGTH_INPUT_ID), commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)),
        round((const.BIN_CORNER_FILLET_RADIUS - wallThickness) * 2 * 10, 2),
    )

def update_actual_bin_dimensions():
    global actualDimensionsTableUiState
    try:
        actualWidth = commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID) * commandUIState.getState(BIN_WIDTH_INPUT_ID) - const.BIN_XY_CLEARANCE * 2
        actualLength = commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID) * commandUIState.getState(BIN_LENGTH_INPUT_ID) - const.BIN_XY_CLEARANCE * 2
        actualHeight = commandUIState.getState(BIN_HEIGHT_UNIT_INPUT_ID) * commandUIState.getState(BIN_HEIGHT_INPUT_ID) + ((const.BIN_LIP_EXTRA_HEIGHT - const.BIN_LIP_TOP_RECESS_HEIGHT) if commandUIState.getState(BIN_WITH_LIP_INPUT_ID) else 0)
        totalWidthValue = round(actualWidth * 10, 2)
        totalLengthValue = round(actualLength * 10, 2)
        totalHeightValue = round(actualHeight * 10, 2)
        actualDimensionsTableUiState.updateValue(BIN_REAL_DIMENSIONS_TABLE_TOTAL_WIDTH, f'Width: {totalWidthValue}mm')
        actualDimensionsTableUiState.getInput(BIN_REAL_DIMENSIONS_TABLE_TOTAL_WIDTH).tooltip = f'Total bin height: {totalWidthValue}mm'
        actualDimensionsTableUiState.updateValue(BIN_REAL_DIMENSIONS_TABLE_TOTAL_LENGTH, f'Length: {totalLengthValue}mm')
        actualDimensionsTableUiState.getInput(BIN_REAL_DIMENSIONS_TABLE_TOTAL_LENGTH).tooltip = f'Total bin length: {totalLengthValue}mm'
        actualDimensionsTableUiState.updateValue(BIN_REAL_DIMENSIONS_TABLE_TOTAL_HEIGHT, f'Height: {totalHeightValue}mm')
        actualDimensionsTableUiState.getInput(BIN_REAL_DIMENSIONS_TABLE_TOTAL_HEIGHT).tooltip = f'Total bin height: {totalHeightValue}mm'
    except:
        showErrorInMessageBox()

def addIconItems(dropdown: adsk.core.DropDownCommandInput, firstItems: list[str], selected: str):
    """Icons show their preview, separated by type"""
    for name in firstItems:
        dropdown.listItems.add(name, name == selected)
    for group in labelGenerator.listIconGroups():
        dropdown.listItems.addSeparator(-1)
        for icon in group:
            dropdown.listItems.add(icon.name, icon.name == selected, icon.previewFolder)
    if dropdown.selectedItem is None:
        dropdown.listItems.item(0).isSelected = True

def fullCompartmentDepth() -> float:
    """Depth of a full depth compartment from the bin top in mm, as the generator builds it"""
    heightUnit: float = commandUIState.getState(BIN_HEIGHT_UNIT_INPUT_ID)
    binHeight: float = commandUIState.getState(BIN_HEIGHT_INPUT_ID)
    # see binBodyTopHeight
    bodyHeight = binHeight * heightUnit - const.BIN_BASE_HEIGHT if heightUnit >= const.BIN_BASE_HEIGHT else (binHeight - 1) * heightUnit
    return round((bodyHeight - const.BIN_COMPARTMENT_BOTTOM_THICKNESS) * 10, 2)

def normalizeCompartmentPockets():
    """Pockets fitted to the compartment grid, after it changes size"""
    global compartmentPockets
    compartmentPockets = compartmentLayout.normalizePockets(
        compartmentPockets,
        commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID),
        commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID),
    )

def hasSingleCompartment() -> bool:
    """Merged cells of a custom grid make one compartment"""
    return len(compartmentLayout.normalizePockets(
        compartmentPockets,
        commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID),
        commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID),
    )) == 1

def updateTabHollowSidesInput(isTabEnabled: bool):
    """Side walls are only opened for a hollow tab of a single compartment, the option is cleared when it can't apply"""
    isEnabled = isTabEnabled and commandUIState.getState(BIN_TAB_HOLLOW_INPUT_ID) and hasSingleCompartment()
    commandUIState.getInput(BIN_TAB_HOLLOW_SIDES_INPUT_ID).isEnabled = isEnabled
    if not isEnabled:
        commandUIState.updateValue(BIN_TAB_HOLLOW_SIDES_INPUT_ID, False)

def compartmentIconOptions() -> list[dict]:
    """Label icons for the drawing, with the preview images the icon dropdowns show"""
    def option(name: str, group: str = '', previewFolder: str = '') -> dict:
        def image(fileName: str) -> str:
            path = os.path.join(previewFolder, fileName)
            return pathlib.Path(path).as_uri() if previewFolder and os.path.isfile(path) else ''
        return {'name': name, 'group': group, 'image': image('32x32.png'), 'imageDark': image('32x32-dark.png')}
    options = [option(compartmentLayout.DEFAULT_ICON), option(labelGenerator.LABEL_ICON_NONE)]
    for group in labelGenerator.listIconGroups():
        for icon in group:
            folder = os.path.dirname(icon.path)
            groupName = 'Other' if os.path.samefile(folder, labelGenerator.LABEL_ICONS_FOLDER) else os.path.basename(folder).capitalize()
            options.append(option(icon.name, groupName, icon.previewFolder))
    return options

def compartmentsDrawingData(browserId: str) -> dict:
    """Everything the compartments drawing shows, sizes in mm"""
    xyClearance: float = commandUIState.getState(BIN_XY_CLEARANCE_INPUT_ID)
    (cellWidth, cellLength, minCellSize) = compartmentCellSize()
    hasTab = commandUIState.getState(BIN_HAS_TAB_INPUT_ID) and commandUIState.getState(BIN_GENERATE_BODY_INPUT_ID) and commandUIState.getState(BIN_TYPE_DROPDOWN_ID) == BIN_TYPE_HOLLOW
    return {
        'page': COMPARTMENTS_PAGE_GRID if browserId == BIN_COMPARTMENTS_GRID_BROWSER_ID else COMPARTMENTS_PAGE_LAYOUT,
        'columns': commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID),
        'rows': commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID),
        'binWidth': round((commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID) * commandUIState.getState(BIN_WIDTH_INPUT_ID) - xyClearance * 2) * 10, 2),
        'binLength': round((commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID) * commandUIState.getState(BIN_LENGTH_INPUT_ID) - xyClearance * 2) * 10, 2),
        'cellWidth': cellWidth,
        'cellLength': cellLength,
        'minCellSize': minCellSize,
        'maxCells': GRID_CELLS_MAX,
        'fullDepth': fullCompartmentDepth(),
        'pockets': compartmentPockets,
        'hasTab': hasTab,
        'defaultLabel': commandUIState.getState(BIN_TAB_LABEL_TEXT_INPUT_ID),
        'defaultIcon': commandUIState.getState(BIN_TAB_LABEL_ICON_INPUT_ID),
        'icons': compartmentIconOptions(),
        'fontUrl': dialogFontUrl(),
    }

def refreshCompartmentsDrawing(skipBrowserId: str = None):
    """Both compartment pages, but the one that is getting its answer already"""
    for browserId in [BIN_COMPARTMENTS_GRID_BROWSER_ID, BIN_COMPARTMENTS_BROWSER_ID]:
        browserInput: adsk.core.BrowserCommandInput = commandUIState.commandInputs.get(browserId)
        if browserInput is None or browserId == skipBrowserId:
            continue
        try:
            browserInput.sendInfoToHTML('update', json.dumps(compartmentsDrawingData(browserId)))
        except Exception as err:
            # the page asks for the data itself once it has loaded
            futil.log(f'{CMD_NAME} Compartments page {browserId} not ready yet, {err}')

def normalizeShapeCells():
    """Shape cells within the bin, every cell when the shape is first shown"""
    global binShapeCells
    columns = commandUIState.getState(BIN_WIDTH_INPUT_ID)
    rows = commandUIState.getState(BIN_LENGTH_INPUT_ID)
    if not commandUIState.getState(BIN_SHAPE_CUSTOM_ID):
        binShapeCells = []
        return
    binShapeCells = binShape.normalizeShape(binShapeCells, columns, rows)
    if len(binShapeCells) == 0:
        binShapeCells = binShape.rectangle(columns, rows)

def shapeCells() -> list[tuple[int, int]]:
    """Cells the bin covers, all of them without a custom shape"""
    columns = commandUIState.getState(BIN_WIDTH_INPUT_ID)
    rows = commandUIState.getState(BIN_LENGTH_INPUT_ID)
    if not commandUIState.getState(BIN_SHAPE_CUSTOM_ID):
        return binShape.rectangle(columns, rows)
    return binShape.normalizeShape(binShapeCells, columns, rows)

def isShaped() -> bool:
    """A custom shape leaving cells out, a full one builds a plain bin"""
    return commandUIState.getState(BIN_SHAPE_CUSTOM_ID) and not binShape.isRectangle(
        shapeCells(),
        commandUIState.getState(BIN_WIDTH_INPUT_ID),
        commandUIState.getState(BIN_LENGTH_INPUT_ID),
    )

def shapeError() -> str | None:
    """Why the shaped bin can't be built, none when it can or the bin is a plain rectangle"""
    if not isShaped():
        return None
    return binShape.shapeError(shapeCells())

def shapeDrawingData() -> dict:
    return {
        'columns': commandUIState.getState(BIN_WIDTH_INPUT_ID),
        'rows': commandUIState.getState(BIN_LENGTH_INPUT_ID),
        'cells': shapeCells(),
        'error': shapeError(),
        'note': SHAPE_NOTE if isShaped() else '',
        'fontUrl': dialogFontUrl(),
    }

def refreshShapeDrawing():
    browserInput: adsk.core.BrowserCommandInput = commandUIState.commandInputs.get(BIN_SHAPE_BROWSER_ID)
    if browserInput is None:
        return
    try:
        browserInput.sendInfoToHTML('update', json.dumps(shapeDrawingData()))
    except Exception as err:
        # the page asks for the data itself once it has loaded
        futil.log(f'{CMD_NAME} Shape page not ready yet, {err}')

def is_all_input_valid(inputs: adsk.core.CommandInputs):
    result = True
    base_width_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_WIDTH_UNIT_INPUT_ID)
    base_length_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_LENGTH_UNIT_INPUT_ID)

    height_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_UNIT_INPUT_ID)
    xy_tolerance: adsk.core.ValueCommandInput = inputs.itemById(BIN_XY_CLEARANCE_INPUT_ID)
    bin_width: adsk.core.ValueCommandInput = inputs.itemById(BIN_WIDTH_INPUT_ID)
    bin_length: adsk.core.ValueCommandInput = inputs.itemById(BIN_LENGTH_INPUT_ID)
    bin_height: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_INPUT_ID)
    bin_wall_thickness: adsk.core.ValueCommandInput = inputs.itemById(BIN_WALL_THICKNESS_INPUT_ID)
    bin_screw_holes: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_SCREW_HOLES_INPUT_ID)
    bin_magnet_cutouts: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_MAGNET_CUTOUTS_INPUT_ID)
    bin_generate_base: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BASE_INPUT_ID)
    bin_generate_body: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BODY_INPUT_ID)
    bin_screw_hole_diameter: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCREW_DIAMETER_INPUT)
    bin_magnet_cutout_diameter: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_DIAMETER_INPUT)
    bin_magnet_cutout_depth: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_HEIGHT_INPUT)
    with_lip: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_INPUT_ID)
    with_lip_notches: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_NOTCHES_INPUT_ID)
    has_scoop: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_SCOOP_INPUT_ID)
    binScoopMaxRadius: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCOOP_MAX_RADIUS_INPUT_ID)
    hasTabInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_TAB_INPUT_ID)
    binTabLength: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_LENGTH_INPUT_ID)
    binTabWidth: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_WIDTH_INPUT_ID)
    binTabPosition: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_POSITION_INPUT_ID)
    binTabAngle: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_ANGLE_INPUT_ID)
    binTypeDropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TYPE_DROPDOWN_ID)

    result = result and base_width_unit.value > 1
    result = result and base_length_unit.value > 1
    result = result and height_unit.value > 0.5
    result = result and xy_tolerance.value >= 0.01 and xy_tolerance.value <= 0.05
    result = result and bin_width.value > 0
    result = result and bin_length.value > 0
    result = result and bin_height.value >= 1
    result = result and bin_wall_thickness.value >= 0.04 and bin_wall_thickness.value <= 0.2
    if bin_generate_base.value:
        result = result and (not bin_screw_holes.value or bin_screw_hole_diameter.value > 0.1) and (not bin_magnet_cutouts.value or bin_screw_hole_diameter.value < bin_magnet_cutout_diameter.value)
        result = result and bin_magnet_cutout_depth.value > 0

    result = result and shapeError() is None

    if bin_generate_body.value and binTypeDropdownInput.selectedItem.name == BIN_TYPE_HOLLOW:
        if has_scoop.value:
            result = result and binScoopMaxRadius.value > 0
        if hasTabInput.value:
            result = result and binTabLength.value > 0
            result = result and binTabWidth.value > 0
            result = result and binTabPosition.value >= 0
            result = result and binTabAngle.value >= math.radians(30) and binTabAngle.value <= math.radians(65)
            binTabTopAngle: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_TOP_ANGLE_INPUT_ID)
            result = result and binTabTopAngle.value >= 0 and binTabTopAngle.value <= math.radians(45)

    return result

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')
    global commandUIState
    global actualDimensionsTableUiState

    args.command.setDialogInitialSize(400, 500)
    applySharedParameterDefaults()

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs
    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

    infoGroup = inputs.addGroupCommandInput(INFO_GROUP, 'Info')
    # as many rows as the text has lines, so the box takes no more room than it needs, and a row for the help line
    # to wrap into, as the box keeps its height when the dialog is made narrower
    info = infoText()
    infoGroup.children.addTextBoxCommandInput("info_text", "Info", info, info.count('<br>') + 2, True)
    infoGroup.isExpanded = commandUIState.getState(INFO_GROUP)
    commandUIState.registerCommandInput(infoGroup)

    basicSizesGroup = inputs.addGroupCommandInput(BIN_BASIC_SIZES_GROUP, 'Basic sizes')
    basicSizesGroup.isExpanded = commandUIState.getState(BIN_BASIC_SIZES_GROUP)
    commandUIState.registerCommandInput(basicSizesGroup)
    baseWidthUnitInput = basicSizesGroup.children.addValueInput(BIN_BASE_WIDTH_UNIT_INPUT_ID, 'Base width unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID)))
    baseWidthUnitInput.minimumValue = sharedParameters.BASE_UNIT_MIN
    baseWidthUnitInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(baseWidthUnitInput)
    baseLengthUnitInput = basicSizesGroup.children.addValueInput(BIN_BASE_LENGTH_UNIT_INPUT_ID, 'Base length unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID)))
    baseLengthUnitInput.minimumValue = sharedParameters.BASE_UNIT_MIN
    baseLengthUnitInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(baseLengthUnitInput)
    binHeightUnitInput = basicSizesGroup.children.addValueInput(BIN_HEIGHT_UNIT_INPUT_ID, 'Bin height unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_HEIGHT_UNIT_INPUT_ID)))
    binHeightUnitInput.minimumValue = sharedParameters.HEIGHT_UNIT_MIN
    binHeightUnitInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(binHeightUnitInput)
    xyClearanceInput = basicSizesGroup.children.addValueInput(BIN_XY_CLEARANCE_INPUT_ID, 'Bin xy clearance (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_XY_CLEARANCE_INPUT_ID)))
    xyClearanceInput.minimumValue = 0.01
    xyClearanceInput.isMinimumInclusive = True
    xyClearanceInput.maximumValue = 0.05
    xyClearanceInput.isMaximumInclusive = True
    commandUIState.registerCommandInput(xyClearanceInput)

    binDimensionsGroup = inputs.addGroupCommandInput(BIN_DIMENSIONS_GROUP, 'Main dimensions')
    binDimensionsGroup.tooltipDescription = 'Set in base units'
    binDimensionsGroup.isExpanded = commandUIState.getState(BIN_DIMENSIONS_GROUP)
    commandUIState.registerCommandInput(binDimensionsGroup)
    binWidthInput = binDimensionsGroup.children.addIntegerSpinnerCommandInput(BIN_WIDTH_INPUT_ID, 'Bin width, X (u)', 1, 100, 1, commandUIState.getState(BIN_WIDTH_INPUT_ID))
    commandUIState.registerCommandInput(binWidthInput)
    binLengthInput = binDimensionsGroup.children.addIntegerSpinnerCommandInput(BIN_LENGTH_INPUT_ID, 'Bin length, Y (u)', 1, 100, 1, commandUIState.getState(BIN_LENGTH_INPUT_ID))
    commandUIState.registerCommandInput(binLengthInput)
    binHeightInput = binDimensionsGroup.children.addValueInput(BIN_HEIGHT_INPUT_ID, 'Bin height, Z (u)', '', adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_HEIGHT_INPUT_ID)))
    binHeightInput.minimumValue = 1
    binHeightInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(binHeightInput)
    customShapeInput = binDimensionsGroup.children.addBoolValueInput(BIN_SHAPE_CUSTOM_ID, 'Custom shape', True, '', commandUIState.getState(BIN_SHAPE_CUSTOM_ID))
    customShapeInput.tooltip = 'Shows a drawing of the bin cells to leave some of them out, so the bin fills an L or another tetris like spot. Unticking it fills every cell again'
    commandUIState.registerCommandInput(customShapeInput)
    shapeBrowser = binDimensionsGroup.children.addBrowserCommandInput(BIN_SHAPE_BROWSER_ID, '', SHAPE_HTML_URL, 200, 200)
    shapeBrowser.isFullWidth = True
    shapeBrowser.isVisible = commandUIState.getState(BIN_SHAPE_CUSTOM_ID)
    commandUIState.registerCommandInput(shapeBrowser)

    render_actual_bin_dimensions_table(binDimensionsGroup.children)

    binFeaturesGroup = inputs.addGroupCommandInput(BIN_FEATURES_GROUP, 'Bin features')
    binFeaturesGroup.isExpanded = commandUIState.getState(BIN_FEATURES_GROUP)
    commandUIState.registerCommandInput(binFeaturesGroup)
    generateBodyCheckboxInput = binFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BODY_INPUT_ID, 'Generate body', True, '', commandUIState.getState(BIN_GENERATE_BODY_INPUT_ID))
    commandUIState.registerCommandInput(generateBodyCheckboxInput)
    binTypeDropdown = binFeaturesGroup.children.addDropDownCommandInput(BIN_TYPE_DROPDOWN_ID, 'Bin type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    binTypeDropdownDefaultValue = commandUIState.getState(BIN_TYPE_DROPDOWN_ID)
    binTypeDropdown.listItems.add(BIN_TYPE_HOLLOW, binTypeDropdownDefaultValue == BIN_TYPE_HOLLOW)
    binTypeDropdown.listItems.add(BIN_TYPE_SHELLED, binTypeDropdownDefaultValue == BIN_TYPE_SHELLED)
    binTypeDropdown.listItems.add(BIN_TYPE_SOLID, binTypeDropdownDefaultValue == BIN_TYPE_SOLID)
    commandUIState.registerCommandInput(binTypeDropdown)

    binWallThicknessInput = binFeaturesGroup.children.addValueInput(BIN_WALL_THICKNESS_INPUT_ID, 'Bin wall thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_WALL_THICKNESS_INPUT_ID)))
    binWallThicknessInput.minimumValue = 0.04
    binWallThicknessInput.isMinimumInclusive = True
    binWallThicknessInput.maximumValue = 0.2
    binWallThicknessInput.isMaximumInclusive = True
    commandUIState.registerCommandInput(binWallThicknessInput)
    generateLipCheckboxInput = binFeaturesGroup.children.addBoolValueInput(BIN_WITH_LIP_INPUT_ID, 'Generate lip for stackability', True, '', commandUIState.getState(BIN_WITH_LIP_INPUT_ID))
    commandUIState.registerCommandInput(generateLipCheckboxInput)
    hasLipNotches = binFeaturesGroup.children.addBoolValueInput(BIN_WITH_LIP_NOTCHES_INPUT_ID, 'Generate lip notches', True, '', commandUIState.getState(BIN_WITH_LIP_NOTCHES_INPUT_ID))
    hasLipNotches.isEnabled = commandUIState.getState(BIN_WITH_LIP_INPUT_ID)
    commandUIState.registerCommandInput(hasLipNotches)

    compartmentsGroup: adsk.core.GroupCommandInput = inputs.addGroupCommandInput(BIN_COMPARTMENTS_GROUP_ID, 'Bin compartments')
    compartmentsGroup.isExpanded = commandUIState.getState(BIN_COMPARTMENTS_GROUP_ID)
    commandUIState.registerCommandInput(compartmentsGroup)
    compartmentsGridBrowser = compartmentsGroup.children.addBrowserCommandInput(BIN_COMPARTMENTS_GRID_BROWSER_ID, '', COMPARTMENTS_HTML_URL, 30, 30)
    compartmentsGridBrowser.isFullWidth = True
    commandUIState.registerCommandInput(compartmentsGridBrowser)
    showLayoutInput = compartmentsGroup.children.addBoolValueInput(BIN_COMPARTMENTS_SHOW_LAYOUT_ID, 'Edit compartment layout', True, '', commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID))
    showLayoutInput.tooltip = 'Shows a drawing of the compartment grid to merge cells into larger compartments and give each its own label and depth. Unticking it resets the compartments to the uniform grid'
    commandUIState.registerCommandInput(showLayoutInput)
    compartmentsBrowser = compartmentsGroup.children.addBrowserCommandInput(BIN_COMPARTMENTS_BROWSER_ID, '', COMPARTMENTS_HTML_URL, 270, 270)
    compartmentsBrowser.isFullWidth = True
    compartmentsBrowser.isVisible = commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID)
    commandUIState.registerCommandInput(compartmentsBrowser)

    binScoopGroup = compartmentsGroup.children.addGroupCommandInput(BIN_SCOOP_GROUP_ID, 'Scoop')
    binScoopGroup.isExpanded = commandUIState.getState(BIN_SCOOP_GROUP_ID)
    commandUIState.registerCommandInput(binScoopGroup)
    generateScoopCheckboxInput = binScoopGroup.children.addBoolValueInput(BIN_HAS_SCOOP_INPUT_ID, 'Add scoop (along bin width)', True, '', commandUIState.getState(BIN_HAS_SCOOP_INPUT_ID))
    commandUIState.registerCommandInput(generateScoopCheckboxInput)
    binScoopMaxRadiusInput = binScoopGroup.children.addValueInput(BIN_SCOOP_MAX_RADIUS_INPUT_ID, 'Scoop max radius (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_SCOOP_MAX_RADIUS_INPUT_ID)))
    commandUIState.registerCommandInput(binScoopMaxRadiusInput)
    for input in binScoopGroup.children:
        if not input.id == BIN_HAS_SCOOP_INPUT_ID:
            input.isEnabled = commandUIState.getState(BIN_HAS_SCOOP_INPUT_ID)

    binTabFeaturesGroup = compartmentsGroup.children.addGroupCommandInput(BIN_TAB_FEATURES_GROUP_ID, 'Label tab')
    binTabFeaturesGroup.isExpanded = commandUIState.getState(BIN_TAB_FEATURES_GROUP_ID)
    commandUIState.registerCommandInput(binTabFeaturesGroup)
    generateTabCheckboxinput = binTabFeaturesGroup.children.addBoolValueInput(BIN_HAS_TAB_INPUT_ID, 'Add label tab (along bin width)', True, '', commandUIState.getState(BIN_HAS_TAB_INPUT_ID))
    commandUIState.registerCommandInput(generateTabCheckboxinput)
    binTabLengthInput = binTabFeaturesGroup.children.addValueInput(BIN_TAB_LENGTH_INPUT_ID, 'Tab length (u)', '', adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_TAB_LENGTH_INPUT_ID)))
    commandUIState.registerCommandInput(binTabLengthInput)
    binTabWidthInput = binTabFeaturesGroup.children.addValueInput(BIN_TAB_WIDTH_INPUT_ID, 'Tab width (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_TAB_WIDTH_INPUT_ID)))
    commandUIState.registerCommandInput(binTabWidthInput)
    binTabPostionInput = binTabFeaturesGroup.children.addValueInput(BIN_TAB_POSITION_INPUT_ID, 'Tab offset (u)', '', adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_TAB_POSITION_INPUT_ID)))
    commandUIState.registerCommandInput(binTabPostionInput)
    tabObverhangAngleInput = binTabFeaturesGroup.children.addValueInput(BIN_TAB_ANGLE_INPUT_ID, 'Tab overhang angle', 'deg', adsk.core.ValueInput.createByString(str(commandUIState.getState(BIN_TAB_ANGLE_INPUT_ID))))
    tabObverhangAngleInput.minimumValue = math.radians(30)
    tabObverhangAngleInput.isMinimumInclusive = True
    tabObverhangAngleInput.maximumValue = math.radians(65)
    tabObverhangAngleInput.isMaximumInclusive = True
    commandUIState.registerCommandInput(tabObverhangAngleInput)
    tabTopAngleInput = binTabFeaturesGroup.children.addValueInput(BIN_TAB_TOP_ANGLE_INPUT_ID, 'Tab top angle', 'deg', adsk.core.ValueInput.createByString(str(commandUIState.getState(BIN_TAB_TOP_ANGLE_INPUT_ID))))
    tabTopAngleInput.tooltip = 'Tilts the tab top down towards the front, so the label faces the front of the bin'
    tabTopAngleInput.minimumValue = 0
    tabTopAngleInput.isMinimumInclusive = True
    tabTopAngleInput.maximumValue = math.radians(45)
    tabTopAngleInput.isMaximumInclusive = True
    commandUIState.registerCommandInput(tabTopAngleInput)
    tabHollowInput = binTabFeaturesGroup.children.addBoolValueInput(BIN_TAB_HOLLOW_INPUT_ID, 'Hollow tab', True, '', commandUIState.getState(BIN_TAB_HOLLOW_INPUT_ID))
    tabHollowInput.tooltip = 'Shells the tab with the wall thickness. With a single compartment it is opened through the back wall of the bin, with more compartments it is left closed. On by default for shelled bins'
    commandUIState.registerCommandInput(tabHollowInput)
    tabHollowSidesInput = binTabFeaturesGroup.children.addBoolValueInput(BIN_TAB_HOLLOW_SIDES_INPUT_ID, 'Open through side walls', True, '', commandUIState.getState(BIN_TAB_HOLLOW_SIDES_INPUT_ID))
    tabHollowSidesInput.tooltip = 'Also opens a hollow tab through the side walls of the bin where it runs into them, not only through the back wall. Only for a single compartment'
    commandUIState.registerCommandInput(tabHollowSidesInput)
    labelTextInput = binTabFeaturesGroup.children.addStringValueInput(BIN_TAB_LABEL_TEXT_INPUT_ID, 'Label text', commandUIState.getState(BIN_TAB_LABEL_TEXT_INPUT_ID))
    labelTextInput.tooltip = 'Text on every compartment label, compartments in the drawing above can have their own. Each label gets a text parameter to edit it later'
    commandUIState.registerCommandInput(labelTextInput)
    labelIconInput = binTabFeaturesGroup.children.addDropDownCommandInput(BIN_TAB_LABEL_ICON_INPUT_ID, 'Label icon', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    addIconItems(labelIconInput, [labelGenerator.LABEL_ICON_NONE], commandUIState.getState(BIN_TAB_LABEL_ICON_INPUT_ID))
    commandUIState.registerCommandInput(labelIconInput)
    labelStyleInput = binTabFeaturesGroup.children.addDropDownCommandInput(BIN_TAB_LABEL_STYLE_INPUT_ID, 'Label style', adsk.core.DropDownStyles.TextListDropDownStyle)
    labelStyleInput.tooltip = 'Outline splits the tab face along the label so a slicer can color it, engraved cuts it in, embossed raises it from a lowered tab'
    for style in labelGenerator.LABEL_STYLES:
        labelStyleInput.listItems.add(style, style == commandUIState.getState(BIN_TAB_LABEL_STYLE_INPUT_ID))
    commandUIState.registerCommandInput(labelStyleInput)
    labelBoldInput = binTabFeaturesGroup.children.addBoolValueInput(BIN_TAB_LABEL_BOLD_INPUT_ID, 'Bold label text', True, '', commandUIState.getState(BIN_TAB_LABEL_BOLD_INPUT_ID))
    commandUIState.registerCommandInput(labelBoldInput)
    for input in binTabFeaturesGroup.children:
        if not input.id == BIN_HAS_TAB_INPUT_ID:
            input.isEnabled = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)
    updateTabHollowSidesInput(commandUIState.getState(BIN_HAS_TAB_INPUT_ID))

    baseFeaturesGroup = inputs.addGroupCommandInput(BIN_BASE_FEATURES_GROUP_ID, 'Base interface features')
    baseFeaturesGroup.isExpanded = commandUIState.getState(BIN_BASE_FEATURES_GROUP_ID)
    commandUIState.registerCommandInput(baseFeaturesGroup)
    generateBaseCheckboxInput = baseFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BASE_INPUT_ID, 'Generate base', True, '', commandUIState.getState(BIN_GENERATE_BASE_INPUT_ID))
    commandUIState.registerCommandInput(generateBaseCheckboxInput)
    jointOriginsCheckboxInput = baseFeaturesGroup.children.addBoolValueInput(BIN_JOINT_ORIGINS_INPUT_ID, 'Add joint origins', True, '', commandUIState.getState(BIN_JOINT_ORIGINS_INPUT_ID))
    jointOriginsCheckboxInput.tooltip = 'A joint origin at the bottom center of every foot, to joint the bin into baseplate sockets'
    commandUIState.registerCommandInput(jointOriginsCheckboxInput)
    generateScrewHolesCheckboxInput = baseFeaturesGroup.children.addBoolValueInput(BIN_SCREW_HOLES_INPUT_ID, 'Add screw holes', True, '', commandUIState.getState(BIN_SCREW_HOLES_INPUT_ID))
    commandUIState.registerCommandInput(generateScrewHolesCheckboxInput)
    screwSizeInput = baseFeaturesGroup.children.addValueInput(BIN_SCREW_DIAMETER_INPUT, 'Screw hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_SCREW_DIAMETER_INPUT)))
    screwSizeInput.minimumValue = 0.1
    screwSizeInput.isMinimumInclusive = True
    screwSizeInput.maximumValue = 1
    screwSizeInput.isMaximumInclusive = True
    commandUIState.registerCommandInput(screwSizeInput)
    generateMagnetSocketCheckboxInput = baseFeaturesGroup.children.addBoolValueInput(BIN_MAGNET_CUTOUTS_INPUT_ID, 'Add magnet sockets', True, '', commandUIState.getState(BIN_MAGNET_CUTOUTS_INPUT_ID))
    commandUIState.registerCommandInput(generateMagnetSocketCheckboxInput)
    generateMagnetsTabCheckboxInput = baseFeaturesGroup.children.addBoolValueInput(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID, 'Add tabs to magnet sockets', True, '', commandUIState.getState(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID))
    commandUIState.registerCommandInput(generateMagnetsTabCheckboxInput)
    magnetSizeInput = baseFeaturesGroup.children.addValueInput(BIN_MAGNET_DIAMETER_INPUT, 'Magnet cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_MAGNET_DIAMETER_INPUT)))
    magnetSizeInput.minimumValue = 0.1
    magnetSizeInput.isMinimumInclusive = True
    magnetSizeInput.maximumValue = 1
    magnetSizeInput.isMaximumInclusive = True
    commandUIState.registerCommandInput(magnetSizeInput)
    magnetHeightInput = baseFeaturesGroup.children.addValueInput(BIN_MAGNET_HEIGHT_INPUT, 'Magnet cutout depth', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_MAGNET_HEIGHT_INPUT)))
    magnetHeightInput.minimumValue = 0.1
    magnetHeightInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(magnetHeightInput)

    userChangesGroup = inputs.addGroupCommandInput(USER_CHANGES_GROUP_ID, 'Changes')
    userChangesGroup.isExpanded = commandUIState.getState(USER_CHANGES_GROUP_ID)
    commandUIState.registerCommandInput(userChangesGroup)
    addDefaultsButtonRow(userChangesGroup.children, INPUT_CHANGES_BUTTONS_BROWSER)

    previewGroup = inputs.addGroupCommandInput(PREVIEW_GROUP_ID, 'Preview')
    previewGroup.isExpanded = commandUIState.getState(PREVIEW_GROUP_ID)
    commandUIState.registerCommandInput(userChangesGroup)
    showPreviewCheckboxInput =  previewGroup.children.addBoolValueInput(SHOW_PREVIEW_INPUT, 'Show auto update preview (slow)', True, '', False)
    commandUIState.registerCommandInput(showPreviewCheckboxInput)
    showPreviewManual = previewGroup.children.addBoolValueInput(SHOW_PREVIEW_MANUAL_INPUT, 'Update preview once', False, '', False)
    showPreviewManual.isFullWidth = True
    commandUIState.registerCommandInput(showPreviewManual)
    # not registered with the dialog state, it's neither remembered nor part of the generated settings
    previewGroup.children.addTextBoxCommandInput(PREVIEW_TIME_INPUT, 'Last preview', 'None yet', 1, True)

    refreshUi()

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.incomingFromHTML, command_incoming_from_html, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')
    generateBin(args)

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs
    if is_all_input_valid(inputs):
        showPreview: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_INPUT)
        showPreviewManual: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_MANUAL_INPUT)
        if showPreview.value or showPreviewManual.value:
            startTime = time.perf_counter()
            args.isValidResult = generateBin(args)
            showPreviewTime(inputs, time.perf_counter() - startTime, args.isValidResult)
            showPreviewManual.value = False
            commandUIState.onInputUpdate(showPreviewManual)
    else:
        args.executeFailed = True
        args.executeFailedMessage = "Some inputs are invalid, unable to generate preview"

def showPreviewTime(inputs: adsk.core.CommandInputs, seconds: float, isValid: bool):
    inputs.itemById(PREVIEW_TIME_INPUT).text = f'{seconds:.2f} s' if isValid else f'failed after {seconds:.2f} s'

def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    global commandUIState
    global compartmentPockets
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')
    # the preview time is only shown, nothing follows from it
    if changed_input.id == PREVIEW_TIME_INPUT:
        return
    commandUIState.onInputUpdate(changed_input)
    if changed_input.id == BIN_TYPE_DROPDOWN_ID:
        commandUIState.updateValue(BIN_TAB_HOLLOW_INPUT_ID, commandUIState.getState(BIN_TYPE_DROPDOWN_ID) == BIN_TYPE_SHELLED)
    elif changed_input.id == BIN_COMPARTMENTS_SHOW_LAYOUT_ID and not commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID):
        # back to the uniform grid, refreshUi fills it with single cells
        compartmentPockets = []
    refreshUi()

    if isinstance(changed_input, adsk.core.GroupCommandInput) and changed_input.isExpanded == True:
        for input in changed_input.children:
            commandUIState.registerCommandInput(input)
        refreshUi()


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs

    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    args.areInputsValid = is_all_input_valid(inputs)
    futil.log(f'{CMD_NAME} Inputs are {"valid" if args.areInputsValid else "invalid"}')


# This event handler is called when the compartments drawing asks for its data once loaded or changes the pockets.
def command_incoming_from_html(args: adsk.core.HTMLEventArgs):
    global compartmentPockets
    global binShapeCells
    browserId = args.browserCommandInput.id
    if browserId == INPUT_CHANGES_BUTTONS_BROWSER:
        action = handleDefaultsButtons(args)
        if action == DEFAULTS_SAVE:
            saveUIInputsAsDefaults()
        elif action is not None:
            if action == DEFAULTS_FACTORY_RESET:
                configUtils.deleteConfigFile(UI_INPUT_DEFAULTS_CONFIG_PATH)
            initDefaultUiState()
            refreshUi()
            if commandUIState.getInput(SHOW_PREVIEW_INPUT).value:
                args.browserCommandInput.parentCommand.doExecutePreview()
        return
    if browserId == BIN_SHAPE_BROWSER_ID:
        if args.action == 'shape':
            try:
                binShapeCells = json.loads(args.data)
            except ValueError as err:
                futil.log(f'{CMD_NAME} Ignoring shape from the drawing, {err}')
            normalizeShapeCells()
            # scoop, tab and compartments inputs depend on the shape
            onChangeValidate()
            if commandUIState.getInput(SHOW_PREVIEW_INPUT).value:
                args.browserCommandInput.parentCommand.doExecutePreview()
        # the page redraws from the answer, with the error of the shape it sent
        args.returnData = json.dumps(shapeDrawingData())
        return
    if args.action == 'ready':
        args.returnData = json.dumps(compartmentsDrawingData(browserId))
    elif args.action == 'pockets':
        try:
            compartmentPockets = json.loads(args.data)
        except ValueError as err:
            futil.log(f'{CMD_NAME} Ignoring pockets from the drawing, {err}')
        normalizeCompartmentPockets()
        # merging cells changes how many compartments there are, which some inputs depend on
        onChangeValidate()
        args.returnData = 'OK'
        if commandUIState.getInput(SHOW_PREVIEW_INPUT).value:
            args.browserCommandInput.parentCommand.doExecutePreview()
    elif args.action == 'grid':
        try:
            grid = json.loads(args.data)
            for (inputId, key) in [(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, 'columns'), (BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, 'rows')]:
                commandUIState.updateValue(inputId, max(1, min(GRID_CELLS_MAX, int(grid[key]))))
        except (ValueError, TypeError, KeyError) as err:
            futil.log(f'{CMD_NAME} Ignoring grid size from the drawing, {err}')
        normalizeCompartmentPockets()
        onChangeValidate()
        # the page that changed it redraws from the answer
        args.returnData = json.dumps(compartmentsDrawingData(browserId))
        refreshCompartmentsDrawing(browserId)
        if commandUIState.getInput(SHOW_PREVIEW_INPUT).value:
            args.browserCommandInput.parentCommand.doExecutePreview()

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event "{args.terminationReason}"')
    global local_handlers
    local_handlers = []

def onChangeValidate():
    global commandUIState

    generateBase: bool = commandUIState.getState(BIN_GENERATE_BASE_INPUT_ID)
    commandUIState.getInput(BIN_SCREW_HOLES_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_JOINT_ORIGINS_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_CUTOUTS_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_DIAMETER_INPUT).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_HEIGHT_INPUT).isEnabled = generateBase
    commandUIState.getInput(BIN_SCREW_DIAMETER_INPUT).isEnabled = generateBase

    generateBody: bool = commandUIState.getState(BIN_GENERATE_BODY_INPUT_ID)
    binType: str = commandUIState.getState(BIN_TYPE_DROPDOWN_ID)
    # scoop and tab only follow a rectangle so far
    shaped = isShaped()
    commandUIState.getInput(BIN_WALL_THICKNESS_INPUT_ID).isEnabled = generateBody and not binType == BIN_TYPE_SOLID
    commandUIState.getInput(BIN_WITH_LIP_INPUT_ID).isEnabled = generateBody
    commandUIState.getInput(BIN_WITH_LIP_NOTCHES_INPUT_ID).isEnabled = generateBody
    commandUIState.getInput(BIN_HAS_SCOOP_INPUT_ID).isEnabled = not shaped
    commandUIState.getInput(BIN_HAS_TAB_INPUT_ID).isEnabled = generateBody and not shaped
    generateTab: bool = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)
    for input in commandUIState.getInput(BIN_TAB_FEATURES_GROUP_ID).children:
        if not input.id == BIN_HAS_TAB_INPUT_ID:
            input.isEnabled = generateBody and generateTab and not shaped
    updateTabHollowSidesInput(generateBody and generateTab and not shaped)

    generateLip: bool = commandUIState.getState(BIN_WITH_LIP_INPUT_ID)
    commandUIState.getInput(BIN_WITH_LIP_NOTCHES_INPUT_ID).isEnabled = generateLip

    generateScoop: bool = commandUIState.getState(BIN_HAS_SCOOP_INPUT_ID)
    commandUIState.getInput(BIN_SCOOP_MAX_RADIUS_INPUT_ID).isEnabled = generateScoop and not shaped

    generateTab: bool = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)
    commandUIState.getInput(BIN_TAB_LENGTH_INPUT_ID).isEnabled = generateTab and not shaped
    commandUIState.getInput(BIN_TAB_WIDTH_INPUT_ID).isEnabled = generateTab and not shaped
    commandUIState.getInput(BIN_TAB_ANGLE_INPUT_ID).isEnabled = generateTab and not shaped
    commandUIState.getInput(BIN_TAB_POSITION_INPUT_ID).isEnabled = generateTab and not shaped

    # shaped bins have a single cavity, the compartments drawing is hidden but keeps its layout for when the shape is filled again
    commandUIState.getInput(BIN_COMPARTMENTS_SHOW_LAYOUT_ID).isEnabled = not shaped
    commandUIState.getInput(BIN_COMPARTMENTS_GRID_BROWSER_ID).isVisible = not shaped
    commandUIState.getInput(BIN_COMPARTMENTS_BROWSER_ID).isVisible = commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID) and not shaped
    commandUIState.getInput(BIN_SHAPE_BROWSER_ID).isVisible = commandUIState.getState(BIN_SHAPE_CUSTOM_ID)

    showPreview: bool = commandUIState.getInput(SHOW_PREVIEW_INPUT).value
    commandUIState.getInput(SHOW_PREVIEW_MANUAL_INPUT).isVisible = not showPreview

def saveUIInputsAsDefaults():
    futil.log(f'{CMD_NAME} Saving UI state to file')
    result = configUtils.dumpJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH, {
        'static_ui': commandUIState.toDict(ignoreKeys=[SHOW_PREVIEW_MANUAL_INPUT, SHOW_PREVIEW_INPUT]),
        'compartments': compartmentPockets,
        'shape': binShapeCells,
        })
    if result:
        futil.log(f'{CMD_NAME} Saved successfully')
    else:
        futil.log(f'{CMD_NAME} UI state failed to save')

def snapshotSettings(inputs: adsk.core.CommandInputs) -> list[dict]:
    settings = settingsUtils.snapshotInputs(
        inputs,
        [INFO_GROUP, USER_CHANGES_GROUP_ID, PREVIEW_GROUP_ID, BIN_REAL_DIMENSIONS_TABLE],
        CMD_NAME,
    )
    # the drawing isn't an input with a value, it holds the grid size too
    items = [['Grid', f'{commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)} x {commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)}']]
    if commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID) and compartmentLayout.isCustomized(compartmentPockets):
        items.extend([f'Compartment {index}', compartmentLayout.describe(item)] for (index, item) in enumerate(compartmentPockets, 1))
    settings.append({'title': 'Compartments', 'items': items})
    if isShaped():
        # the drawing as text, front row last like it's shown
        cells = set(shapeCells())
        rows = [
            ''.join('#' if (x, y) in cells else '.' for x in range(commandUIState.getState(BIN_WIDTH_INPUT_ID)))
            for y in reversed(range(commandUIState.getState(BIN_LENGTH_INPUT_ID)))
        ]
        settings.append({'title': 'Shape', 'items': [[f'Row {index}', row] for (index, row) in zip(reversed(range(1, len(rows) + 1)), rows)]})
    return settings

def generateBin(args: adsk.core.CommandEventArgs):
    startTime = time.perf_counter()
    inputs = args.command.commandInputs
    # the settings come first, so a failing build can be reproduced from the log
    commonUtils.fileLog(f'{CMD_NAME} generating with settings:\n{settingsUtils.settingsText(snapshotSettings(inputs))}')
    base_width_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_WIDTH_UNIT_INPUT_ID)
    base_length_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_LENGTH_UNIT_INPUT_ID)
    height_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_UNIT_INPUT_ID)
    xy_clearance: adsk.core.ValueCommandInput = inputs.itemById(BIN_XY_CLEARANCE_INPUT_ID)
    bin_width: adsk.core.ValueCommandInput = inputs.itemById(BIN_WIDTH_INPUT_ID)
    bin_length: adsk.core.ValueCommandInput = inputs.itemById(BIN_LENGTH_INPUT_ID)
    bin_height: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_INPUT_ID)
    bin_wall_thickness: adsk.core.ValueCommandInput = inputs.itemById(BIN_WALL_THICKNESS_INPUT_ID)
    bin_screw_holes: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_SCREW_HOLES_INPUT_ID)
    bin_generate_base: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BASE_INPUT_ID)
    bin_generate_body: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BODY_INPUT_ID)
    bin_magnet_cutouts: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_MAGNET_CUTOUTS_INPUT_ID)
    bin_screw_hole_diameter: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCREW_DIAMETER_INPUT)
    bin_magnet_cutouts_tabs: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID)
    bin_magnet_cutout_diameter: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_DIAMETER_INPUT)
    bin_magnet_cutout_depth: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_HEIGHT_INPUT)
    with_lip: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_INPUT_ID)
    with_lip_notches: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_NOTCHES_INPUT_ID)
    has_scoop: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_SCOOP_INPUT_ID)
    binScoopMaxRadius: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCOOP_MAX_RADIUS_INPUT_ID)
    hasTabInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_TAB_INPUT_ID)
    binTabLength: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_LENGTH_INPUT_ID)
    binTabWidth: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_WIDTH_INPUT_ID)
    binTabPosition: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_POSITION_INPUT_ID)
    binTabAngle: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_ANGLE_INPUT_ID)
    binTabHollow: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_TAB_HOLLOW_INPUT_ID)
    labelTextInput: adsk.core.StringValueCommandInput = inputs.itemById(BIN_TAB_LABEL_TEXT_INPUT_ID)
    labelIconInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TAB_LABEL_ICON_INPUT_ID)
    labelStyleInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TAB_LABEL_STYLE_INPUT_ID)
    labelBoldInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_TAB_LABEL_BOLD_INPUT_ID)
    binTypeDropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TYPE_DROPDOWN_ID)
    compartmentsX: int = commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)
    compartmentsY: int = commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)

    isHollow = binTypeDropdownInput.selectedItem.name == BIN_TYPE_HOLLOW
    isSolid = binTypeDropdownInput.selectedItem.name == BIN_TYPE_SOLID
    isShelled = binTypeDropdownInput.selectedItem.name == BIN_TYPE_SHELLED
    # a custom shape leaving cells out, without lip, scoop and tab for now
    cells = shapeCells()
    shaped = isShaped()

    try:
        if shapeError() is not None:
            raise ValueError(shapeError())
        des = adsk.fusion.Design.cast(app.activeProduct)
        if des.designType == adsk.fusion.DesignTypes.DirectDesignType:
            raise UnsupportedDesignTypeException('Timeline must be enabled for the generator to work, projects with disabled design history currently are not supported')
        root = adsk.fusion.Component.cast(des.rootComponent)

        xyClearance = xy_clearance.value
        binName = 'Gridfinity bin {}x{}x{}'.format(int(bin_length.value), int(bin_width.value), int(bin_height.value))

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
                bin_width.value * base_width_unit.value - xyClearance * 2,
                bin_length.value * base_length_unit.value - xyClearance * 2,
            ),
            base_width_unit.value,
            base_length_unit.value,
        )

        binParameterPrefix = parameterUtils.nextFreePrefix(des, BIN_PARAMETER_BASE_NAME, BIN_PARAMETERS)
        (baseWidthParameter, baseLengthParameter) = sharedParameters.findOrCreateBaseUnitParameters(
            des,
            base_width_unit.value,
            base_length_unit.value,
            binParameterPrefix,
            'bin',
            CMD_NAME,
        )
        baseWidth = Dim.parameter(baseWidthParameter)
        baseLength = Dim.parameter(baseLengthParameter)
        # user parameters driving the bin, kept in its tag to show with its settings
        binParameters = [['Base width unit', baseWidthParameter.name], ['Base length unit', baseLengthParameter.name]]

        # create base interface
        baseGeneratorInput = BaseGeneratorInput()
        baseGeneratorInput.originPoint = geometryUtils.createOffsetPoint(
            gridfinityBinComponent.originConstructionPoint.geometry,
            byX=-xyClearance,
            byY=-xyClearance,
        )
        baseGeneratorInput.baseWidth = baseWidth
        baseGeneratorInput.baseLength = baseLength
        baseGeneratorInput.xyClearance = xyClearance
        baseGeneratorInput.hasScrewHoles = bin_screw_holes.value and not isShelled
        baseGeneratorInput.hasMagnetCutouts = bin_magnet_cutouts.value and not isShelled
        baseGeneratorInput.hasMagnetCutoutsTabs = bin_magnet_cutouts_tabs.value and not isShelled
        baseGeneratorInput.screwHolesDiameter = bin_screw_hole_diameter.value
        baseGeneratorInput.magnetCutoutsDiameter = bin_magnet_cutout_diameter.value
        baseGeneratorInput.magnetCutoutsDepth = bin_magnet_cutout_depth.value

        baseBodies: list[adsk.fusion.BRepBody]
        if bin_generate_base.value:
            baseBodies = createBaseBodyPattern(
                baseGeneratorInput,
                bin_width.value,
                bin_length.value,
                gridfinityBinComponent,
            )
            if shaped:
                baseBodies = keepBodiesInCells(baseBodies, cells, baseGeneratorInput, gridfinityBinComponent, name='Foot outside shape remove')

        # create bin body
        binBodyInput = BinBodyGeneratorInput()
        binBodyInput.hasLip = with_lip.value
        binBodyInput.shapeCells = cells if shaped else None
        binBodyInput.hasLipNotches = with_lip_notches.value
        binBodyInput.binWidth = bin_width.value
        binBodyInput.binLength = bin_length.value
        binBodyInput.binHeight = Dim.number(bin_height.value)
        binBodyInput.baseWidth = baseWidth
        binBodyInput.baseLength = baseLength
        binBodyInput.heightUnit = Dim.length(height_unit.value)
        binBodyInput.xyClearance = xyClearance
        binBodyInput.binCornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS - xyClearance
        # a shaped hollow bin gets its cavity once trimmed to the shape
        binBodyInput.isSolid = isSolid or isShelled or shaped
        binBodyInput.wallThickness = bin_wall_thickness.value
        binBodyInput.hasScoop = has_scoop.value and isHollow and not shaped
        binBodyInput.scoopMaxRadius = binScoopMaxRadius.value
        binBodyInput.hasTab = hasTabInput.value and isHollow and not shaped
        binBodyInput.tabLength = binTabLength.value
        binBodyInput.tabWidth = binTabWidth.value
        binBodyInput.tabPosition = binTabPosition.value
        binBodyInput.tabOverhangAngle = binTabAngle.value
        binBodyInput.isTabHollow = binTabHollow.value
        binBodyInput.isTabOpenThroughSides = inputs.itemById(BIN_TAB_HOLLOW_SIDES_INPUT_ID).value
        binBodyInput.tabTopAngle = inputs.itemById(BIN_TAB_TOP_ANGLE_INPUT_ID).value
        binBodyInput.labelStyle = labelStyleInput.selectedItem.name
        binBodyInput.isLabelBold = labelBoldInput.value
        binBodyInput.compartmentsByX = compartmentsX
        binBodyInput.compartmentsByY = compartmentsY

        # label text and icon per compartment, the label tab section fills in the ones left blank
        # without the layout the grid is uniform, also for pockets saved with the layout hidden
        pockets = compartmentLayout.normalizePockets(compartmentPockets if commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID) else [], compartmentsX, compartmentsY)
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

        if bin_generate_body.value:
            binBodyInput.binHeight = Dim.parameter(parameterUtils.addUnitlessParameter(
                des,
                parameterUtils.parameterName(binParameterPrefix, BIN_HEIGHT_PARAMETER),
                bin_height.value,
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
                        compartmentText or labelTextInput.value,
                        labelIconInput.selectedItem.name if compartmentIcon == compartmentLayout.DEFAULT_ICON else compartmentIcon,
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
                height_unit.value,
                parameterUtils.parameterName(binParameterPrefix, BIN_HEIGHT_UNIT_PARAMETER),
                'bin',
                CMD_NAME,
            ))
            binParameters.append(['Height unit', binBodyInput.heightUnit.expression])
            binBody = createGridfinityBinBody(
                binBodyInput,
                gridfinityBinComponent,
            )
        combineFeatures = gridfinityBinComponent.features.combineFeatures

        # merge everything before the clearance cut, so the cut only has to reference the bin body
        if bin_generate_body.value and bin_generate_base.value:
            toolBodies = commonUtils.objectCollectionFromList(baseBodies)
            combineFeatureInput = combineFeatures.createInput(binBody, toolBodies)
            combineFeatures.add(combineFeatureInput).name = 'Bin body and feet join'
            binBody.name = binName

        # feet only touch each other along edges, so without a body they stay separate
        clearanceBodies = [binBody] if bin_generate_body.value else baseBodies
        if shaped and (bin_generate_body.value or bin_generate_base.value):
            # the body is built over the whole grid, the outline trims it down to the shape
            cutOutsideShape(cells, baseGeneratorInput, clearanceBodies, gridfinityBinComponent, name='Outer clearance trim')
        elif bin_generate_body.value or bin_generate_base.value:
            cutBaseClearance(
                baseGeneratorInput,
                bin_width.value,
                bin_length.value,
                clearanceBodies,
                gridfinityBinComponent,
            )

        binBasesXCount = int(round(bin_width.value))
        binBasesYCount = int(round(bin_length.value))
        if bin_generate_body.value and bin_generate_base.value and (shaped or not isShelled):
            # curve up the gaps between feet along the walls instead of leaving flat overhangs,
            # shaped bins need them at the inner corners whatever the type, the shell follows the pockets cut before it
            if shaped:
                cutShapeWallJunctionPockets(baseGeneratorInput, cells, binBody, gridfinityBinComponent)
            elif binBasesXCount > 1 or binBasesYCount > 1:
                cutWallJunctionPockets(baseGeneratorInput, binBasesXCount, binBasesYCount, binBody, gridfinityBinComponent)

        if shaped and isHollow and bin_generate_body.value:
            cavity = createShapeCavity(
                cells,
                baseGeneratorInput,
                binBodyInput.wallThickness,
                binBodyTopHeight(binBodyInput),
                gridfinityBinComponent,
                name='Cavity',
            )
            combineUtils.cutBody(binBody, commonUtils.objectCollectionFromList([cavity]), gridfinityBinComponent, name='Cavity cut')

        if isShelled and bin_generate_body.value:
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
                shellUtils.simpleShell([topFace], binBodyInput.wallThickness, gridfinityBinComponent, name='Shell')
                toolBodies = adsk.core.ObjectCollection.create()
                toolBodies.add(topBody)
                combineAfterShellFeatureInput = combineFeatures.createInput(bottomBody, toolBodies)
                combineAfterShellFeature = combineFeatures.add(combineAfterShellFeatureInput)
                combineAfterShellFeature.name = 'Shell and lip join'
                binBody = combineAfterShellFeature.bodies.item(0)
            else:
                shellUtils.simpleShell([topFace], binBodyInput.wallThickness, gridfinityBinComponent, name='Shell')

            if hasTabInput.value and not shaped:
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

                shelledLabel = createLabelDefinition(des, binParameterPrefix, BIN_LABEL_PARAMETER, labelTextInput.value, labelIconInput.selectedItem.name)
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

        if bin_generate_body.value or bin_generate_base.value:
            generatedBodies = [binBody] if bin_generate_body.value else baseBodies
            if binPlacement != (0, 0):
                placementUtils.moveBodies(generatedBodies, *binPlacement, gridfinityBinComponent, name='Bin placement')
            # mark generated geometry so later bins can tell it apart from the rest of the design,
            # with the settings it was generated with to show later
            binSettings = snapshotSettings(inputs)
            for body in generatedBodies:
                tagUtils.tagBody(body, tagUtils.TAG_BIN, binSettings, binParameters)

        if bin_generate_base.value and inputs.itemById(BIN_JOINT_ORIGINS_INPUT_ID).value:
            # last, after the placement, joint origins sit on sketches which don't follow body moves
            centers = cellCenters(
                baseWidth,
                baseLength,
                xyClearance,
                range(bin_width.value),
                range(bin_length.value),
                Dim.length(binPlacement[0]) if binPlacement[0] != 0 else None,
                Dim.length(binPlacement[1]) if binPlacement[1] != 0 else None,
            )
            createCellJointOrigins(
                [center for center in centers if (center[0], center[1]) in set(cells)],
                gridfinityBinComponent,
                name='Foot joint origin',
            )

        # group features in timeline
        binGroup = des.timeline.timelineGroups.add(originalTimelineCount, des.timeline.count - 1)
        binGroup.name = binName
        futil.log(f'{CMD_NAME} {binName} generated in {time.perf_counter() - startTime:.3f}s')
    except UnsupportedDesignTypeException as err:
        args.executeFailed = True
        args.executeFailedMessage = 'Design type is unsupported. Projects with disabled design history are unsupported, please enable timeline feature to proceed.'
        return False
    except Exception as err:
        args.executeFailed = True
        args.executeFailedMessage = getErrorMessage()
        futil.log(f'{CMD_NAME} Error occurred, {err}, {getErrorMessage()}')
        return False
    return True
