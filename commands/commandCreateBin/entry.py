import adsk.core, adsk.fusion, traceback
import html
import os
import pathlib
import time
import math


from ...lib import configUtils
from ...lib import tagUtils
from ...lib import settingsUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils import commonUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils import sharedParameters
from ...lib.gridfinityUtils import labelGenerator
from ...lib.gridfinityUtils import compartmentLayout
from ...lib.gridfinityUtils import binShape
from ...lib.gridfinityUtils import binGrid
from ...lib.gridfinityUtils import wallCreases
from .inputState import InputState
from . import binBuilder
from .binBuilder import BIN_TYPE_HOLLOW, BIN_TYPE_SHELLED, BIN_TYPE_SOLID
from ...lib.ui.commandUiState import CommandUiState
from ...lib.ui.defaultsButtons import addDefaultsButtonRow, defaultsButtonsHandlers, DEFAULTS_SAVE, DEFAULTS_FACTORY_RESET
from ...lib.ui.buttonRow import addButtonRow
from ...lib.ui import configButtons
from ...lib.ui import selection
from ...lib.ui import browserPages
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException
from ...lib.ui import errorPalette
from ...lib import errorReport
from ...lib import configJson

app = adsk.core.Application.get()
ui = app.userInterface


# *** The command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBin'
CMD_NAME = 'Gridfinity bin'
# shown on hover over the button, the first paragraph says what it makes, the second how
CMD_Description = ('Creates a gridfinity bin that drops into a baseplate.\n\n'
    'Set its size in base and height units, then pick a hollow, shelled or solid body with a stacking lip, '
    'compartments, a scoop, a label tab and magnet or screw holes in its feet. '
    'A custom shape fills odd spots like a tetris piece.')

commandUIState = CommandUiState(CMD_NAME)
actualDimensionsTableUiState = CommandUiState(CMD_NAME)
# pockets drawn in the compartments drawing, see compartmentLayout
compartmentPockets: list[dict] = []
# cells of a custom shaped bin, see binShape, empty while the bin is a plain rectangle
binShapeCells: list[tuple[int, int]] = []
# config the dialog opens with next, see startWithConfig
pendingConfig: dict | None = None
# bodies of the last build, selected and centered in the view when the dialog closes on OK, see command_destroy
builtBodies: list[adsk.fusion.BRepBody] = []

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
# picture under the description on hover, like Fusion's own commands
TOOL_CLIP_PATH = os.path.join(ICON_FOLDER, 'toolclip.png')

CONFIG_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'commandConfig')
UI_INPUT_DEFAULTS_CONFIG_PATH = os.path.join(CONFIG_FOLDER_PATH, "ui_input_defaults.json")
COMPARTMENTS_HTML_URL = browserPages.pageUrl(__file__, 'compartments.html')
SHAPE_HTML_URL = browserPages.pageUrl(__file__, 'shape.html')

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
# half size feet all over, otherwise sizes ending in a half get a row of half feet, see binGrid
BIN_HALF_GRID_INPUT_ID = 'half_grid'
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
# long walls folded in to stiffen them, see wallCreases
BIN_CREASES_INPUT_ID = 'wall_creases'
BIN_CREASE_DEPTH_INPUT_ID = 'wall_crease_depth'
BIN_CREASE_MIN_LENGTH_INPUT_ID = 'wall_crease_min_length'
BIN_CREASE_MAX_PANEL_LENGTH_INPUT_ID = 'wall_crease_max_panel_length'
BIN_CREASE_MIN_HEIGHT_INPUT_ID = 'wall_crease_min_height'
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

# InputState fields kept as they are in the dialog state, see getInputsState
STATE_INPUT_IDS = {
    'baseWidth': BIN_BASE_WIDTH_UNIT_INPUT_ID,
    'baseLength': BIN_BASE_LENGTH_UNIT_INPUT_ID,
    'heightUnit': BIN_HEIGHT_UNIT_INPUT_ID,
    'xyClearance': BIN_XY_CLEARANCE_INPUT_ID,
    'binWidth': BIN_WIDTH_INPUT_ID,
    'binLength': BIN_LENGTH_INPUT_ID,
    'binHeight': BIN_HEIGHT_INPUT_ID,
    'isHalfGrid': BIN_HALF_GRID_INPUT_ID,
    'wallThickness': BIN_WALL_THICKNESS_INPUT_ID,
    'binType': BIN_TYPE_DROPDOWN_ID,
    'generateBase': BIN_GENERATE_BASE_INPUT_ID,
    'generateBody': BIN_GENERATE_BODY_INPUT_ID,
    'hasJointOrigins': BIN_JOINT_ORIGINS_INPUT_ID,
    'hasScrewHoles': BIN_SCREW_HOLES_INPUT_ID,
    'screwHoleDiameter': BIN_SCREW_DIAMETER_INPUT,
    'hasMagnetCutouts': BIN_MAGNET_CUTOUTS_INPUT_ID,
    'hasMagnetCutoutsTabs': BIN_MAGNET_CUTOUTS_TABS_INPUT_ID,
    'magnetCutoutDiameter': BIN_MAGNET_DIAMETER_INPUT,
    'magnetCutoutDepth': BIN_MAGNET_HEIGHT_INPUT,
    'hasLip': BIN_WITH_LIP_INPUT_ID,
    'hasLipNotches': BIN_WITH_LIP_NOTCHES_INPUT_ID,
    'hasScoop': BIN_HAS_SCOOP_INPUT_ID,
    'scoopMaxRadius': BIN_SCOOP_MAX_RADIUS_INPUT_ID,
    'hasTab': BIN_HAS_TAB_INPUT_ID,
    'tabLength': BIN_TAB_LENGTH_INPUT_ID,
    'tabWidth': BIN_TAB_WIDTH_INPUT_ID,
    'tabPosition': BIN_TAB_POSITION_INPUT_ID,
    'isTabHollow': BIN_TAB_HOLLOW_INPUT_ID,
    'isTabOpenThroughSides': BIN_TAB_HOLLOW_SIDES_INPUT_ID,
    'labelText': BIN_TAB_LABEL_TEXT_INPUT_ID,
    'labelIcon': BIN_TAB_LABEL_ICON_INPUT_ID,
    'labelStyle': BIN_TAB_LABEL_STYLE_INPUT_ID,
    'isLabelBold': BIN_TAB_LABEL_BOLD_INPUT_ID,
    'hasCreases': BIN_CREASES_INPUT_ID,
    'creaseDepth': BIN_CREASE_DEPTH_INPUT_ID,
    'creaseMinLength': BIN_CREASE_MIN_LENGTH_INPUT_ID,
    'creaseMaxPanelLength': BIN_CREASE_MAX_PANEL_LENGTH_INPUT_ID,
    'creaseMinHeight': BIN_CREASE_MIN_HEIGHT_INPUT_ID,
}
# angles are kept as the expression typed in, see CommandUiState.onInputUpdate
STATE_ANGLE_INPUT_IDS = {
    'tabOverhangAngle': BIN_TAB_ANGLE_INPUT_ID,
    'tabTopAngle': BIN_TAB_TOP_ANGLE_INPUT_ID,
}

INPUT_CHANGES_BUTTONS_BROWSER = 'input_changes_buttons'
CONFIG_BUTTONS_BROWSER = 'config_buttons'
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
    commandUIState.initValue(BIN_WIDTH_INPUT_ID, 2, adsk.core.FloatSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_LENGTH_INPUT_ID, 3, adsk.core.FloatSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_HALF_GRID_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SHAPE_CUSTOM_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_HEIGHT_INPUT_ID, 5, adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_GENERATE_BODY_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TYPE_DROPDOWN_ID, BIN_TYPE_HOLLOW, adsk.core.DropDownCommandInput.classType())
    commandUIState.initValue(BIN_WALL_THICKNESS_INPUT_ID, const.BIN_WALL_THICKNESS, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_WITH_LIP_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_WITH_LIP_NOTCHES_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_CREASES_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_CREASE_DEPTH_INPUT_ID, const.BIN_CREASE_DEPTH, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_CREASE_MIN_LENGTH_INPUT_ID, const.BIN_CREASE_MIN_LENGTH, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_CREASE_MAX_PANEL_LENGTH_INPUT_ID, const.BIN_CREASE_MAX_PANEL_LENGTH, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_CREASE_MIN_HEIGHT_INPUT_ID, const.BIN_CREASE_MIN_HEIGHT, adsk.core.ValueCommandInput.classType())

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
            if os.path.isfile(TOOL_CLIP_PATH):
                cmd_def.toolClipFilename = TOOL_CLIP_PATH

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
    }

def refreshCompartmentsDrawing(skipBrowserId: str = None):
    """Both compartment pages, but the one that is getting its answer already"""
    for browserId in [BIN_COMPARTMENTS_GRID_BROWSER_ID, BIN_COMPARTMENTS_BROWSER_ID]:
        if browserId != skipBrowserId:
            browserPages.sendUpdate(commandUIState.commandInputs.get(browserId), compartmentsDrawingData(browserId))

def isHalfGrid() -> bool:
    return commandUIState.getState(BIN_HALF_GRID_INPUT_ID)

def gridDivisions() -> int:
    return binBuilder.gridDivisions(getInputsState())

def feetSize() -> tuple[float, float]:
    return binBuilder.feetSize(getInputsState())

def feetGridSize() -> tuple[int, int]:
    return binBuilder.feetGridSize(getInputsState())

def outlineCellsPerFoot() -> int:
    return binBuilder.outlineCellsPerFoot(getInputsState())

def normalizeShapeCells():
    """Shape cells within the bin, every cell when the shape is first shown"""
    global binShapeCells
    (columns, rows) = feetGridSize()
    if not commandUIState.getState(BIN_SHAPE_CUSTOM_ID):
        binShapeCells = []
        return
    binShapeCells = binShape.normalizeShape(binShapeCells, columns, rows)
    if len(binShapeCells) == 0:
        binShapeCells = binShape.rectangle(columns, rows)

def shapeCells() -> list[tuple[int, int]]:
    return binBuilder.shapeCells(getInputsState())

def outlineCells() -> list[tuple[int, int]]:
    return binBuilder.outlineCells(getInputsState())

def isShaped() -> bool:
    return binBuilder.isShaped(getInputsState())

def shapeError() -> str | None:
    return binBuilder.shapeError(getInputsState())

def creaseLayout() -> list[tuple[wallCreases.WallSide, int]]:
    return binBuilder.creaseLayout(getInputsState())

def shapeDrawingData() -> dict:
    (columns, rows) = feetGridSize()
    return {
        'columns': columns,
        'rows': rows,
        # a half foot is drawn half as wide
        'columnSizes': [size for (_, size) in binGrid.footSpans(feetSize()[0])],
        'rowSizes': [size for (_, size) in binGrid.footSpans(feetSize()[1])],
        'cells': shapeCells(),
        'error': shapeError(),
        'note': SHAPE_NOTE if isShaped() else '',
    }

def refreshShapeDrawing():
    browserPages.sendUpdate(commandUIState.commandInputs.get(BIN_SHAPE_BROWSER_ID), shapeDrawingData())

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
    result = result and bin_width.value > 0 and binGrid.isHalfStep(bin_width.value)
    result = result and bin_length.value > 0 and binGrid.isHalfStep(bin_length.value)
    result = result and bin_height.value >= 1
    result = result and bin_wall_thickness.value >= 0.04 and bin_wall_thickness.value <= 0.2
    if bin_generate_base.value:
        result = result and (not bin_screw_holes.value or bin_screw_hole_diameter.value > 0.1) and (not bin_magnet_cutouts.value or bin_screw_hole_diameter.value < bin_magnet_cutout_diameter.value)
        result = result and bin_magnet_cutout_depth.value > 0

    result = result and shapeError() is None
    if inputs.itemById(BIN_CREASES_INPUT_ID).value:
        result = result and inputs.itemById(BIN_CREASE_DEPTH_INPUT_ID).value > 0
        result = result and inputs.itemById(BIN_CREASE_MAX_PANEL_LENGTH_INPUT_ID).value > 0

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

    args.command.setDialogInitialSize(450, 500)
    applySharedParameterDefaults()
    # a clone keeps its own units
    applyPendingConfig()

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
    binWidthInput = binDimensionsGroup.children.addFloatSpinnerCommandInput(BIN_WIDTH_INPUT_ID, 'Bin width, X (u)', '', 0.5, 100, 0.5, commandUIState.getState(BIN_WIDTH_INPUT_ID))
    binWidthInput.tooltip = 'In whole or half base units'
    commandUIState.registerCommandInput(binWidthInput)
    binLengthInput = binDimensionsGroup.children.addFloatSpinnerCommandInput(BIN_LENGTH_INPUT_ID, 'Bin length, Y (u)', '', 0.5, 100, 0.5, commandUIState.getState(BIN_LENGTH_INPUT_ID))
    binLengthInput.tooltip = 'In whole or half base units'
    commandUIState.registerCommandInput(binLengthInput)
    halfGridInput = binDimensionsGroup.children.addBoolValueInput(BIN_HALF_GRID_INPUT_ID, 'Half grid', True, '', commandUIState.getState(BIN_HALF_GRID_INPUT_ID))
    halfGridInput.tooltip = ('Puts the bin on half size feet, for a half grid baseplate, the bin keeps its size in base units. '
        'Without it a size ending in a half gets whole feet and a row of half feet along the back or right side, halved across the row only. '
        'Half feet have no magnet or screw holes, there is no room for them')
    commandUIState.registerCommandInput(halfGridInput)
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
    creasesInput = binFeaturesGroup.children.addBoolValueInput(BIN_CREASES_INPUT_ID, 'Fold long walls for stiffness', True, '', commandUIState.getState(BIN_CREASES_INPUT_ID))
    creasesInput.tooltip = ('Folds walls of hollow and shelled bins in along shallow creases, origami style, so tall long walls bow less. '
        'Bins from the min height with a wall from the min length get them. Walls are split into even panels up to the max panel length, '
        'walls shorter than a panel of the longest one stay flat. '
        'The scoop wall stays flat, the scoop braces it. A creased bin has a single compartment and a solid label tab')
    commandUIState.registerCommandInput(creasesInput)
    for (inputId, label, units, minimum) in [
        (BIN_CREASE_DEPTH_INPUT_ID, 'Crease depth', defaultLengthUnits, 0.05),
        (BIN_CREASE_MIN_LENGTH_INPUT_ID, 'Creased wall min length (u)', '', 1),
        (BIN_CREASE_MAX_PANEL_LENGTH_INPUT_ID, 'Crease panel max length (u)', '', 1),
        (BIN_CREASE_MIN_HEIGHT_INPUT_ID, 'Creased bin min height (u)', '', 1),
    ]:
        creaseValueInput = binFeaturesGroup.children.addValueInput(inputId, label, units, adsk.core.ValueInput.createByReal(commandUIState.getState(inputId)))
        creaseValueInput.minimumValue = minimum
        creaseValueInput.isMinimumInclusive = True
        commandUIState.registerCommandInput(creaseValueInput)

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
    addButtonRow(userChangesGroup.children, CONFIG_BUTTONS_BROWSER)

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
    global binShapeCells
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
    elif changed_input.id == BIN_HALF_GRID_INPUT_ID:
        # the drawn shape keeps its footprint in the cells of the other grid
        binShapeCells = binShape.splitCells(binShapeCells) if isHalfGrid() else binShape.mergeCells(binShapeCells)
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
    browserPages.handleMessage(args, pageHandlers(args.browserCommandInput.id, args.browserCommandInput.parentCommand))

def pageHandlers(browserId: str, command: adsk.core.Command) -> dict[str, browserPages.Handler]:
    """What the pages of the dialog send, see browserPages.handleMessage"""
    def preview():
        if commandUIState.getInput(SHOW_PREVIEW_INPUT).value:
            command.doExecutePreview()

    def onDefaults(action: str):
        if action == DEFAULTS_SAVE:
            saveUIInputsAsDefaults()
            return
        if action == DEFAULTS_FACTORY_RESET:
            configUtils.deleteConfigFile(UI_INPUT_DEFAULTS_CONFIG_PATH)
        initDefaultUiState()
        refreshUi()
        preview()

    def onShape(cells):
        global binShapeCells
        binShapeCells = cells
        normalizeShapeCells()
        # scoop, tab and compartments inputs depend on the shape
        onChangeValidate()
        preview()
        # the page redraws from the answer, with the error of the shape it sent
        return shapeDrawingData()

    def onPockets(pockets):
        global compartmentPockets
        compartmentPockets = pockets
        normalizeCompartmentPockets()
        # merging cells changes how many compartments there are, which some inputs depend on
        onChangeValidate()
        preview()

    def onGrid(grid):
        try:
            for (inputId, key) in [(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, 'columns'), (BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, 'rows')]:
                commandUIState.updateValue(inputId, max(1, min(GRID_CELLS_MAX, int(grid[key]))))
        except (ValueError, TypeError, KeyError) as err:
            futil.log(f'{CMD_NAME} Ignoring grid size from the drawing, {err}')
        normalizeCompartmentPockets()
        onChangeValidate()
        # the page that changed it redraws from the answer
        refreshCompartmentsDrawing(browserId)
        preview()
        return compartmentsDrawingData(browserId)

    def onLoadConfig(text: str, fileName: str):
        state = readConfig(text, f'Loaded "{fileName}"')
        if state is None:
            return
        applyInputsState(state)
        refreshUi()
        preview()

    if browserId == INPUT_CHANGES_BUTTONS_BROWSER:
        return defaultsButtonsHandlers(onDefaults)
    if browserId == CONFIG_BUTTONS_BROWSER:
        return configButtons.configButtonsHandlers(
            'bin',
            lambda: configJson.configText(configJson.GENERATOR_BIN, configJson.stateToJson(configJson.GENERATOR_BIN, getInputsState()), tagUtils.getGeneratorVersion()),
            lambda: binBuilder.binDisplayName(getInputsState()),
            onLoad=onLoadConfig,
        )
    if browserId == BIN_SHAPE_BROWSER_ID:
        return {browserPages.READY: lambda _: shapeDrawingData(), 'shape': onShape}
    return {browserPages.READY: lambda _: compartmentsDrawingData(browserId), 'pockets': onPockets, 'grid': onGrid}

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event "{args.terminationReason}"')
    global local_handlers
    local_handlers = []
    if args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason:
        # once the command is over, so the selection stays
        selection.showBuiltBodies(builtBodies)

def onChangeValidate():
    global commandUIState

    generateBase: bool = commandUIState.getState(BIN_GENERATE_BASE_INPUT_ID)
    commandUIState.getInput(BIN_JOINT_ORIGINS_INPUT_ID).isEnabled = generateBase
    # half feet have no room for holes
    hasHoles = generateBase and not isHalfGrid()
    for inputId in [BIN_SCREW_HOLES_INPUT_ID, BIN_MAGNET_CUTOUTS_INPUT_ID, BIN_MAGNET_CUTOUTS_TABS_INPUT_ID, BIN_MAGNET_DIAMETER_INPUT, BIN_MAGNET_HEIGHT_INPUT, BIN_SCREW_DIAMETER_INPUT]:
        commandUIState.getInput(inputId).isEnabled = hasHoles

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
    creased = len(creaseLayout()) > 0
    if creased:
        # the folds would run into the hollow of the tab on the back wall
        commandUIState.getInput(BIN_TAB_HOLLOW_INPUT_ID).isEnabled = False
        commandUIState.updateValue(BIN_TAB_HOLLOW_INPUT_ID, False)
    updateTabHollowSidesInput(generateBody and generateTab and not shaped)

    generateLip: bool = commandUIState.getState(BIN_WITH_LIP_INPUT_ID)
    commandUIState.getInput(BIN_WITH_LIP_NOTCHES_INPUT_ID).isEnabled = generateLip

    canCrease = generateBody and not binType == BIN_TYPE_SOLID
    commandUIState.getInput(BIN_CREASES_INPUT_ID).isEnabled = canCrease
    for inputId in [BIN_CREASE_DEPTH_INPUT_ID, BIN_CREASE_MIN_LENGTH_INPUT_ID, BIN_CREASE_MAX_PANEL_LENGTH_INPUT_ID, BIN_CREASE_MIN_HEIGHT_INPUT_ID]:
        commandUIState.getInput(inputId).isEnabled = canCrease and commandUIState.getState(BIN_CREASES_INPUT_ID)

    generateScoop: bool = commandUIState.getState(BIN_HAS_SCOOP_INPUT_ID)
    commandUIState.getInput(BIN_SCOOP_MAX_RADIUS_INPUT_ID).isEnabled = generateScoop and not shaped

    generateTab: bool = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)
    commandUIState.getInput(BIN_TAB_LENGTH_INPUT_ID).isEnabled = generateTab and not shaped
    commandUIState.getInput(BIN_TAB_WIDTH_INPUT_ID).isEnabled = generateTab and not shaped
    commandUIState.getInput(BIN_TAB_ANGLE_INPUT_ID).isEnabled = generateTab and not shaped
    commandUIState.getInput(BIN_TAB_POSITION_INPUT_ID).isEnabled = generateTab and not shaped

    # shaped and creased bins have a single cavity, the compartments drawing is hidden but keeps its layout for later
    singleCavity = shaped or creased
    commandUIState.getInput(BIN_COMPARTMENTS_SHOW_LAYOUT_ID).isEnabled = not singleCavity
    commandUIState.getInput(BIN_COMPARTMENTS_GRID_BROWSER_ID).isVisible = not singleCavity
    commandUIState.getInput(BIN_COMPARTMENTS_BROWSER_ID).isVisible = commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID) and not singleCavity
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
        (columnCount, rowCount) = feetGridSize()
        rows = [
            ''.join('#' if (x, y) in cells else '.' for x in range(columnCount))
            for y in reversed(range(rowCount))
        ]
        settings.append({'title': 'Shape', 'items': [[f'Row {index}', row] for (index, row) in zip(reversed(range(1, len(rows) + 1)), rows)]})
    return settings

def reportConfig(state: InputState | None) -> str | None:
    """The settings of a failed build as a config file, to build it again from the report"""
    if state is None:
        return None
    return configJson.configText(configJson.GENERATOR_BIN, configJson.stateToJson(configJson.GENERATOR_BIN, state), tagUtils.getGeneratorVersion())

def getInputsState() -> InputState:
    def angle(inputId: str) -> float:
        return app.activeProduct.unitsManager.evaluateExpression(str(commandUIState.getState(inputId)), 'deg')
    return InputState(
        **{field: commandUIState.getState(inputId) for (field, inputId) in STATE_INPUT_IDS.items()},
        **{field: angle(inputId) for (field, inputId) in STATE_ANGLE_INPUT_IDS.items()},
        compartmentsX=commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID),
        compartmentsY=commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID),
        showCompartmentsLayout=commandUIState.getState(BIN_COMPARTMENTS_SHOW_LAYOUT_ID),
        compartmentPockets=compartmentPockets,
        hasCustomShape=commandUIState.getState(BIN_SHAPE_CUSTOM_ID),
        shapeCells=binShapeCells,
    )

def applyInputsState(state: InputState):
    """Sets the dialog state to a state from getInputsState, the inputs follow on refreshUi"""
    global compartmentPockets
    global binShapeCells
    for (field, inputId) in STATE_INPUT_IDS.items():
        commandUIState.setValue(inputId, getattr(state, field))
    for (field, inputId) in STATE_ANGLE_INPUT_IDS.items():
        commandUIState.setValue(inputId, f'{math.degrees(getattr(state, field)):g} deg')
    commandUIState.setValue(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, state.compartmentsX)
    commandUIState.setValue(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, state.compartmentsY)
    commandUIState.setValue(BIN_COMPARTMENTS_SHOW_LAYOUT_ID, state.showCompartmentsLayout)
    commandUIState.setValue(BIN_SHAPE_CUSTOM_ID, state.hasCustomShape)
    compartmentPockets = list(state.compartmentPockets)
    binShapeCells = list(state.shapeCells)

def startWithConfig(settings: dict):
    """Opens the dialog with a config by field name, see configJson.stateToJson, settings it doesn't have stay"""
    global pendingConfig
    pendingConfig = settings
    ui.commandDefinitions.itemById(CMD_ID).execute()

def configChoices() -> dict[str, configJson.Choice]:
    """The options of the dropdowns with the dialog's first defaults, see initDefaultUiState"""
    iconNames = [labelGenerator.LABEL_ICON_NONE] + [icon.name for group in labelGenerator.listIconGroups() for icon in group]
    return {
        'binType': configJson.Choice([BIN_TYPE_HOLLOW, BIN_TYPE_SHELLED, BIN_TYPE_SOLID], BIN_TYPE_HOLLOW),
        'labelIcon': configJson.Choice(iconNames, labelGenerator.LABEL_ICON_NONE),
        'labelStyle': configJson.Choice(labelGenerator.LABEL_STYLES, labelGenerator.LABEL_STYLE_OUTLINE),
    }

def readConfig(text: str, source: str) -> InputState | None:
    """The state of a config, none when it can't be read, see configButtons.readConfig"""
    return configButtons.readConfig(text, source, configJson.GENERATOR_BIN, InputState, getInputsState(), configChoices())

def applyPendingConfig():
    global pendingConfig
    if pendingConfig is None:
        return
    state = readConfig(configJson.configText(configJson.GENERATOR_BIN, pendingConfig), 'Cloned')
    pendingConfig = None
    if state is not None:
        applyInputsState(state)

def generateBin(args: adsk.core.CommandEventArgs):
    startTime = time.perf_counter()
    settings = snapshotSettings(args.command.commandInputs)
    # the settings come first, so a failing build can be reproduced from the log
    commonUtils.fileLog(f'{CMD_NAME} generating with settings:\n{settingsUtils.settingsText(settings)}')
    state = None
    global builtBodies
    builtBodies = []

    try:
        state = getInputsState()
        des = adsk.fusion.Design.cast(app.activeProduct)
        builtBodies = binBuilder.buildBin(des, state, settings)
        futil.log(f'{CMD_NAME} {binBuilder.binDisplayName(state)} generated in {time.perf_counter() - startTime:.3f}s')
    except UnsupportedDesignTypeException as err:
        args.executeFailed = True
        args.executeFailedMessage = 'Design type is unsupported. Projects with disabled design history are unsupported, please enable timeline feature to proceed.'
        return False
    except Exception as err:
        args.executeFailed = True
        args.executeFailedMessage = f'{html.escape(errorReport.errorMessage(err))}<br>See the {errorPalette.PALETTE_TITLE} panel to copy a report of it'
        futil.log(f'{CMD_NAME} Error occurred, {err}, {getErrorMessage()}')
        errorPalette.show(f'{CMD_NAME} failed', err, reportConfig(state))
        return False
    return True
