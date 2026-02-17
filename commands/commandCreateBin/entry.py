import adsk.core, adsk.fusion, traceback
import os
import math


from ...lib import configUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils import combineUtils
from ...lib.gridfinityUtils import geometryUtils
from ...lib.gridfinityUtils import faceUtils
from ...lib.gridfinityUtils import shellUtils
from ...lib.gridfinityUtils import commonUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils.baseGenerator import createSingleGridfinityBaseBody, createBaseBodyPattern, cutBaseClearance
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.binBodyGenerator import createGridfinityBinBody, uniformCompartments
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput, BinBodyCompartmentDefinition
from ...lib.gridfinityUtils.binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from ...lib.gridfinityUtils.binBodyTabGenerator import createGridfinityBinBodyTab
from ...lib.ui.commandUiState import CommandUiState
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException

app = adsk.core.Application.get()
ui = app.userInterface


# *** The command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBin'
CMD_NAME = 'Gridfinity bin'
CMD_Description = 'Create simple gridfinity bin'

commandUIState = CommandUiState(CMD_NAME)
actualDimensionsTableUiState = CommandUiState(CMD_NAME)
actualCompartmentDimensionsUiState = CommandUiState(CMD_NAME)
commandCompartmentsTableUIState: list[CommandUiState] = []

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
BIN_PADDING_GROUP_ID = 'bin_padding_group'
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
BIN_WIDTH_INPUT_ID = 'bin_width'
BIN_REAL_DIMENSIONS_TABLE = "real_dimensions"
BIN_REAL_DIMENSIONS_TABLE_TOTAL_WIDTH = "total_real_width"
BIN_REAL_DIMENSIONS_TABLE_TOTAL_LENGTH = "total_real_length"
BIN_REAL_DIMENSIONS_TABLE_TOTAL_HEIGHT = "total_real_height"
BIN_WALL_THICKNESS_INPUT_ID = 'bin_wall_thickness'
BIN_GENERATE_BASE_INPUT_ID = 'bin_generate_base'
BIN_GENERATE_BODY_INPUT_ID = 'bin_generate_body'
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
BIN_WITH_LIP_INPUT_ID = 'with_lip'
BIN_WITH_LIP_NOTCHES_INPUT_ID = 'with_lip_notches'
BIN_COMPARTMENT_REAL_DIMENSIONS_TABLE = "compartment_real_dimensions"
BIN_COMPARTMENT_REAL_DIMENSIONS_WIDTH = "compartment_width_u"
BIN_COMPARTMENT_REAL_DIMENSIONS_LENGTH = "compartment_length_u"
BIN_COMPARTMENTS_GRID_TYPE_ID = 'compartments_grid_type'
BIN_COMPARTMENTS_GRID_TYPE_UNIFORM = 'Uniform'
BIN_COMPARTMENTS_GRID_TYPE_CUSTOM = 'Custom grid'
BIN_COMPARTMENTS_GRID_TYPE_INFO = 'grid_type_info'
BIN_COMPARTMENTS_GRID_TYPE_INFO_UNIFORM = 'Divide bin uniformly along length and width dimensions'
BIN_COMPARTMENTS_GRID_TYPE_INFO_CUSTOM = 'Input each compartment size and location. Grid size defines units for each compartment location (x, y) and dimensions (w, l)'
BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID = 'compartments_grid_w'
BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID = 'compartments_grid_l'
BIN_COMPARTMENTS_TABLE_ID = 'compartments_table'
BIN_COMPARTMENTS_TABLE_ADD_ID = 'compartments_table_add'
BIN_COMPARTMENTS_TABLE_REMOVE_ID = 'compartments_table_remove'
BIN_COMPARTMENTS_TABLE_UNIFORM_ID = 'compartments_table_uniform'
BIN_TYPE_DROPDOWN_ID = 'bin_type'
BIN_TYPE_HOLLOW = 'Hollow'
BIN_TYPE_SHELLED = 'Shelled'
BIN_TYPE_SOLID = 'Solid'
BIN_HAS_PADDING_INPUT_ID = 'bin_has_padding'
BIN_PADDING_LEFT_INPUT_ID = 'bin_padding_left'
BIN_PADDING_TOP_INPUT_ID = 'bin_padding_top'
BIN_PADDING_RIGHT_INPUT_ID = 'bin_padding_right'
BIN_PADDING_BOTTOM_INPUT_ID = 'bin_padding_bottom'

INPUT_CHANGES_SAVE_DEFAULTS = 'input_changes_buttons_save_new_defaults'
INPUT_CHANGES_RESET_TO_DEFAULTS = 'input_changes_button_reset_to_defaults'
INPUT_CHANGES_RESET_TO_FACTORY = 'input_changes_button_factory_reset'
PRESERVE_CHAGES_RADIO_GROUP = 'preserve_changes'
PRESERVE_CHAGES_RADIO_GROUP_PRESERVE = 'Preserve inputs'
PRESERVE_CHAGES_RADIO_GROUP_RESET = 'Reset inputs after creation'
RESET_CHAGES_INPUT = 'reset_changes'
SHOW_PREVIEW_INPUT = 'show_preview'
SHOW_PREVIEW_MANUAL_INPUT = 'show_preview_manual'

INFO_TEXT = ("<b>Help:</b> Info for inputs can be found "
             "<a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Bin-generator-options\">"
             "Here on our GitHub</a>.")

def refreshUi():
    global commandUIState
    commandUIState.forceUIRefresh()
    refreshCompartmentsTable()
    update_actual_compartment_unit_dimensions()
    update_actual_bin_dimensions()
    onChangeValidate()

def initDefaultUiState():
    global commandUIState
    global actualDimensionsTableUiState
    global commandCompartmentsTableUIState
    commandUIState.initValue(INFO_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_BASIC_SIZES_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_DIMENSIONS_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_FEATURES_GROUP, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_COMPARTMENTS_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_SCOOP_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_TAB_FEATURES_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_BASE_FEATURES_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(BIN_PADDING_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(USER_CHANGES_GROUP_ID, True, adsk.core.GroupCommandInput.classType())
    commandUIState.initValue(PREVIEW_GROUP_ID, True, adsk.core.GroupCommandInput.classType())

    commandUIState.initValue(BIN_BASE_WIDTH_UNIT_INPUT_ID, const.DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_BASE_LENGTH_UNIT_INPUT_ID, const.DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_HEIGHT_UNIT_INPUT_ID, const.DIMENSION_DEFAULT_HEIGHT_UNIT, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_XY_CLEARANCE_INPUT_ID, const.BIN_XY_CLEARANCE, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_WIDTH_INPUT_ID, 2, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_LENGTH_INPUT_ID, 3, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_HEIGHT_INPUT_ID, 5, adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_GENERATE_BODY_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TYPE_DROPDOWN_ID, BIN_TYPE_HOLLOW, adsk.core.DropDownCommandInput.classType())
    commandUIState.initValue(BIN_WALL_THICKNESS_INPUT_ID, const.BIN_WALL_THICKNESS, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_WITH_LIP_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_WITH_LIP_NOTCHES_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())

    commandUIState.initValue(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, 1, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, 1, adsk.core.IntegerSpinnerCommandInput.classType())
    commandUIState.initValue(BIN_COMPARTMENTS_GRID_TYPE_ID, BIN_COMPARTMENTS_GRID_TYPE_UNIFORM, adsk.core.DropDownCommandInput.classType())

    commandUIState.initValue(BIN_HAS_SCOOP_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCOOP_MAX_RADIUS_INPUT_ID, const.BIN_SCOOP_MAX_RADIUS, adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_HAS_TAB_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_LENGTH_INPUT_ID, 1, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_WIDTH_INPUT_ID, const.BIN_TAB_WIDTH, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_POSITION_INPUT_ID, 0, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_TAB_ANGLE_INPUT_ID, '45 deg', adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_GENERATE_BASE_INPUT_ID, True, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCREW_HOLES_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_SCREW_DIAMETER_INPUT, const.DIMENSION_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_SCREW_DIAMETER_INPUT, const.DIMENSION_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_CUTOUTS_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_DIAMETER_INPUT, const.DIMENSION_MAGNET_CUTOUT_DIAMETER, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_MAGNET_HEIGHT_INPUT, const.DIMENSION_MAGNET_CUTOUT_DEPTH, adsk.core.ValueCommandInput.classType())

    commandUIState.initValue(BIN_HAS_PADDING_INPUT_ID, False, adsk.core.BoolValueCommandInput.classType())
    commandUIState.initValue(BIN_PADDING_LEFT_INPUT_ID, 0, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_PADDING_TOP_INPUT_ID, 0, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_PADDING_RIGHT_INPUT_ID, 0, adsk.core.ValueCommandInput.classType())
    commandUIState.initValue(BIN_PADDING_BOTTOM_INPUT_ID, 0, adsk.core.ValueCommandInput.classType())

    commandCompartmentsTableUIState = []
    recordedDefaults = configUtils.readJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH)
    if recordedDefaults is not None and 'static_ui' in recordedDefaults and 'compartments_table' in recordedDefaults:
        staticUiState = recordedDefaults['static_ui']
        compartmentsTableState = recordedDefaults['compartments_table']
        if staticUiState is not None:
            futil.log(f'{CMD_NAME} Found previously saved default values, restoring {staticUiState}')

            try:
                commandUIState.initValues(staticUiState)
                futil.log(f'{CMD_NAME} Successfully restored default values')
            except Exception as err:
                futil.log(f'{CMD_NAME} Failed to restore default values, err: {err}')
        if compartmentsTableState is not None and isinstance(compartmentsTableState, list):
            futil.log(f'{CMD_NAME} Found previously saving default values for compartments table, restoring {compartmentsTableState}')
            try:
                for row in compartmentsTableState:
                    commandCompartmentsTableUIState.append(CommandUiState(CMD_NAME))
                    commandCompartmentsTableUIState[-1].initValues(row)
                futil.log(f'{CMD_NAME} Successfully restored compartments table default values')
            except Exception as err:
                futil.log(f'{CMD_NAME} Failed to restore default values, err: {err}')
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

def render_actual_compartment_dimension_units_table(inputs: adsk.core.CommandInputs):
    global actualCompartmentDimensionsUiState
    actualDimensionsTable = inputs.addTableCommandInput(BIN_COMPARTMENT_REAL_DIMENSIONS_TABLE, "Actual dimensions (mm)", 2, "1:1")
    totalWidth = actualDimensionsTable.commandInputs.addTextBoxCommandInput(BIN_COMPARTMENT_REAL_DIMENSIONS_WIDTH, "", "Grid cell width", 1, True)
    actualCompartmentDimensionsUiState.registerCommandInput(totalWidth)
    actualCompartmentDimensionsUiState.initValue(totalWidth.id, "", totalWidth.objectType)
    totalLength = actualDimensionsTable.commandInputs.addTextBoxCommandInput(BIN_COMPARTMENT_REAL_DIMENSIONS_LENGTH, "", "Grid cell length", 1, True)
    actualCompartmentDimensionsUiState.registerCommandInput(totalLength)
    actualCompartmentDimensionsUiState.initValue(totalLength.id, "", totalLength.objectType)
    actualDimensionsTable.addCommandInput(totalWidth, 0, 0)
    actualDimensionsTable.addCommandInput(totalLength, 0, 1)
    actualDimensionsTable.tablePresentationStyle = adsk.core.TablePresentationStyles.transparentBackgroundTablePresentationStyle
    actualDimensionsTable.hasGrid = False
    actualDimensionsTable.minimumVisibleRows = 1
    actualDimensionsTable.maximumVisibleRows = 1
    return actualDimensionsTable

def formatString(text: str, color: str=""):
    if len(color) > 0:
        return f"<p style='color:{color}'>{text}</p>"
    return text

def update_actual_compartment_unit_dimensions():
    global commandUIState
    global actualCompartmentDimensionsUiState
    baseWidth: float = commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID)
    baseLength: float = commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID)
    binWidth: float = commandUIState.getState(BIN_WIDTH_INPUT_ID)
    binLength: float = commandUIState.getState(BIN_LENGTH_INPUT_ID)
    binPaddingLeft: float = commandUIState.getState(BIN_PADDING_LEFT_INPUT_ID) if commandUIState.getState(BIN_HAS_PADDING_INPUT_ID) else 0
    binPaddingTop: float = commandUIState.getState(BIN_PADDING_TOP_INPUT_ID) if commandUIState.getState(BIN_HAS_PADDING_INPUT_ID) else 0
    binPaddingRight: float = commandUIState.getState(BIN_PADDING_RIGHT_INPUT_ID) if commandUIState.getState(BIN_HAS_PADDING_INPUT_ID) else 0
    binPaddingBottom: float = commandUIState.getState(BIN_PADDING_BOTTOM_INPUT_ID) if commandUIState.getState(BIN_HAS_PADDING_INPUT_ID) else 0
    gridWidth: int = commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)
    gridLength: int = commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)
    wallThickness: float = commandUIState.getState(BIN_WALL_THICKNESS_INPUT_ID)
    xyClearance: float = commandUIState.getState(BIN_WITH_LIP_INPUT_ID)
    try:
        minCompartmentDimensionLimit = (const.BIN_CORNER_FILLET_RADIUS - wallThickness) * 2 * 10
        cellWidth = round((baseWidth * binWidth + binPaddingLeft + binPaddingRight - wallThickness * 2 - xyClearance * 2 - wallThickness * (gridWidth - 1)) / gridWidth * 10, 2)
        actualCompartmentDimensionsUiState.updateValue(BIN_COMPARTMENT_REAL_DIMENSIONS_WIDTH, formatString(f'Grid cell width: {cellWidth}mm', '' if cellWidth >= minCompartmentDimensionLimit else 'red'))
        cellLength = round((baseLength * binLength + binPaddingTop + binPaddingBottom - wallThickness * 2 - xyClearance * 2 - wallThickness * (gridLength - 1)) / gridLength * 10, 2)
        actualCompartmentDimensionsUiState.updateValue(BIN_COMPARTMENT_REAL_DIMENSIONS_LENGTH, formatString(f'Grid cell length: {cellLength}mm', '' if cellLength >= minCompartmentDimensionLimit else 'red'))
    except:
        showErrorInMessageBox()

def update_actual_bin_dimensions():
    global actualDimensionsTableUiState
    try:
        actualWidth = commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID) * commandUIState.getState(BIN_WIDTH_INPUT_ID) - const.BIN_XY_CLEARANCE * 2
        actualLength = commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID) * commandUIState.getState(BIN_LENGTH_INPUT_ID) - const.BIN_XY_CLEARANCE * 2
        actualHeight = commandUIState.getState(BIN_HEIGHT_UNIT_INPUT_ID) * commandUIState.getState(BIN_HEIGHT_INPUT_ID) + ((const.BIN_LIP_EXTRA_HEIGHT - const.BIN_LIP_TOP_RECESS_HEIGHT) if commandUIState.getState(BIN_WITH_LIP_INPUT_ID) else 0)        
        if commandUIState.getState(BIN_HAS_PADDING_INPUT_ID):
            actualWidth += commandUIState.getState(BIN_PADDING_LEFT_INPUT_ID) + commandUIState.getState(BIN_PADDING_RIGHT_INPUT_ID)
            actualLength += commandUIState.getState(BIN_PADDING_TOP_INPUT_ID) + commandUIState.getState(BIN_PADDING_BOTTOM_INPUT_ID)

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

def render_compartments_table(inputs: adsk.core.CommandInputs):
    global commandUIState
    initiallyVisible: bool = commandUIState.getState(BIN_COMPARTMENTS_GRID_TYPE_ID) == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM
    compartmentsGroup: adsk.core.GroupCommandInput = commandUIState.getInput(BIN_COMPARTMENTS_GROUP_ID)
    binCompartmentsTable = compartmentsGroup.children.addTableCommandInput(BIN_COMPARTMENTS_TABLE_ID, "Compartments", 5, "1:1:1:1:1")
    addButton = compartmentsGroup.commandInputs.addBoolValueInput(BIN_COMPARTMENTS_TABLE_ADD_ID, "Add", False, "", False)
    removeButton = compartmentsGroup.commandInputs.addBoolValueInput(BIN_COMPARTMENTS_TABLE_REMOVE_ID, "Remove", False, "", False)
    populateUniform = compartmentsGroup.commandInputs.addBoolValueInput(BIN_COMPARTMENTS_TABLE_UNIFORM_ID, "Reset to uniform", False, "", False)
    binCompartmentsTable.addToolbarCommandInput(addButton)
    binCompartmentsTable.addToolbarCommandInput(removeButton)
    binCompartmentsTable.addToolbarCommandInput(populateUniform)
    binCompartmentsTable.hasGrid = False
    binCompartmentsTable.tablePresentationStyle = adsk.core.TablePresentationStyles.nameValueTablePresentationStyle
    commandUIState.registerCommandInput(binCompartmentsTable)
    x_input_label = binCompartmentsTable.commandInputs.addStringValueInput("x_input_0_label", "", "X position")
    x_input_label.isReadOnly = True
    x_input_label.isFullWidth = True
    y_input_label = binCompartmentsTable.commandInputs.addStringValueInput("y_input_0_label", "", "Y position")
    y_input_label.isReadOnly = True
    y_input_label.isFullWidth = True
    w_input_label = binCompartmentsTable.commandInputs.addStringValueInput("w_input_0_label", "", "Width")
    w_input_label.isFullWidth = True
    w_input_label.isReadOnly = True
    l_input_label = binCompartmentsTable.commandInputs.addStringValueInput("l_input_0_label", "", "Length")
    l_input_label.isReadOnly = True
    l_input_label.isFullWidth = True
    d_input_label = binCompartmentsTable.commandInputs.addStringValueInput("d_input_0_label", "", "Depth")
    d_input_label.isReadOnly = True
    d_input_label.isFullWidth = True
    binCompartmentsTable.addCommandInput(x_input_label, 0, 0)
    binCompartmentsTable.addCommandInput(y_input_label, 0, 1)
    binCompartmentsTable.addCommandInput(w_input_label, 0, 2)
    binCompartmentsTable.addCommandInput(l_input_label, 0, 3)
    binCompartmentsTable.addCommandInput(d_input_label, 0, 4)
    binCompartmentsTable.maximumVisibleRows = 20
    binCompartmentsTable.isVisible = initiallyVisible
    addButton.isVisible = initiallyVisible
    removeButton.isVisible = initiallyVisible
    populateUniform.isVisible = initiallyVisible

    append_compartments_from_state()

def append_compartments_from_state():
    global commandCompartmentsTableUIState
    for i, rowState in enumerate(commandCompartmentsTableUIState, 1):
        append_compartment_table_row(rowState.getState(f'x_input_{i}'), rowState.getState(f'y_input_{i}'), rowState.getState(f'w_input_{i}'), rowState.getState(f'l_input_{i}'), rowState.getState(f'd_input_{i}'))

def append_compartment_table_row(x: int, y: int, w: int, l: int, defaultDepth: float):
    global commandUIState
    binCompartmentsTable: adsk.core.TableCommandInput = commandUIState.getInput(BIN_COMPARTMENTS_TABLE_ID)
    commandUIState.registerCommandInput(binCompartmentsTable)
    newRow = binCompartmentsTable.rowCount
    x_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput(f'x_input_{newRow}', 'X (u)', 0, 100, 1, x)
    x_input.isFullWidth = True
    y_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput(f'y_input_{newRow}', 'Y (u)', 0, 100, 1, y)
    y_input.isFullWidth = True
    w_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput(f'w_input_{newRow}', 'W (u)', 1, 100, 1, w)
    w_input.isFullWidth = True
    l_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput(f'l_input_{newRow}', 'L (u)', 1, 100, 1, l)
    l_input.isFullWidth = True
    d_input = binCompartmentsTable.commandInputs.addValueInput(f'd_input_{newRow}', 'Depth (mm)', app.activeProduct.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(defaultDepth))
    d_input.isFullWidth = True
    binCompartmentsTable.addCommandInput(x_input, newRow, 0)
    binCompartmentsTable.addCommandInput(y_input, newRow, 1)
    binCompartmentsTable.addCommandInput(w_input, newRow, 2)
    binCompartmentsTable.addCommandInput(l_input, newRow, 3)
    binCompartmentsTable.addCommandInput(d_input, newRow, 4)

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
    binCompartmentGridTypeDropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_TYPE_ID)
    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)
    compartmentsX: adsk.core.IntegerSpinnerCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)
    compartmentsY: adsk.core.IntegerSpinnerCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)
    has_padding: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_PADDING_INPUT_ID)
    padding_left: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_LEFT_INPUT_ID)
    padding_top: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_TOP_INPUT_ID)
    padding_right: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_RIGHT_INPUT_ID)
    padding_bottom: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_BOTTOM_INPUT_ID)

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

    if bin_generate_body.value and binTypeDropdownInput.selectedItem.name == BIN_TYPE_HOLLOW:
        if has_scoop.value:
            result = result and binScoopMaxRadius.value > 0
        if hasTabInput.value:
            result = result and binTabLength.value > 0
            result = result and binTabWidth.value > 0
            result = result and binTabPosition.value >= 0
            result = result and binTabAngle.value >= math.radians(30) and binTabAngle.value <= math.radians(65)
        if binCompartmentGridTypeDropdownInput.selectedItem.name == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM:
            for i in range(1, binCompartmentsTable.rowCount):
                posX: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 0)
                posY: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 1)
                width: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 2)
                length: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 3)

                result = result and posX.value >= 0 and (posX.value + width.value) <= compartmentsX.value
                result = result and posY.value >= 0 and (posY.value + length.value) <= compartmentsY.value
                result = result and width.value > 0 and (posX.value + width.value) <= compartmentsX.value
                result = result and length.value > 0 and (posY.value + length.value) <= compartmentsY.value

    return result

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')
    global commandUIState
    global actualDimensionsTableUiState

    args.command.setDialogInitialSize(400, 500)

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs
    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

    infoGroup = inputs.addGroupCommandInput(INFO_GROUP, 'Info')
    infoGroup.children.addTextBoxCommandInput("info_text", "Info", INFO_TEXT, 3, True)
    infoGroup.isExpanded = commandUIState.getState(INFO_GROUP)
    commandUIState.registerCommandInput(infoGroup)

    basicSizesGroup = inputs.addGroupCommandInput(BIN_BASIC_SIZES_GROUP, 'Basic sizes')
    basicSizesGroup.isExpanded = commandUIState.getState(BIN_BASIC_SIZES_GROUP)
    commandUIState.registerCommandInput(basicSizesGroup)
    baseWidthUnitInput = basicSizesGroup.children.addValueInput(BIN_BASE_WIDTH_UNIT_INPUT_ID, 'Base width unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_BASE_WIDTH_UNIT_INPUT_ID)))
    baseWidthUnitInput.minimumValue = 1
    baseWidthUnitInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(baseWidthUnitInput)
    baseLengthUnitInput = basicSizesGroup.children.addValueInput(BIN_BASE_LENGTH_UNIT_INPUT_ID, 'Base length unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_BASE_LENGTH_UNIT_INPUT_ID)))
    baseLengthUnitInput.minimumValue = 1
    baseLengthUnitInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(baseLengthUnitInput)
    binHeightUnitInput = basicSizesGroup.children.addValueInput(BIN_HEIGHT_UNIT_INPUT_ID, 'Bin height unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_HEIGHT_UNIT_INPUT_ID)))
    binHeightUnitInput.minimumValue = 0.5
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
    binCompartmentsWidthInput = compartmentsGroup.children.addIntegerSpinnerCommandInput(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, "Grid width, X (n per bin width)", 1, 100, 1, commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID))
    commandUIState.registerCommandInput(binCompartmentsWidthInput)
    binCompartmentsLengthInput = compartmentsGroup.children.addIntegerSpinnerCommandInput(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, "Grid length, Y (n per bin length)", 1, 100, 1, commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID))
    commandUIState.registerCommandInput(binCompartmentsLengthInput)
    render_actual_compartment_dimension_units_table(compartmentsGroup.children)

    compartmentGridDropdown = compartmentsGroup.children.addDropDownCommandInput(BIN_COMPARTMENTS_GRID_TYPE_ID, "Grid type", adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    compartmentGridDropdownDefaultValue = commandUIState.getState(BIN_COMPARTMENTS_GRID_TYPE_ID)
    compartmentGridDropdown.listItems.add(BIN_COMPARTMENTS_GRID_TYPE_UNIFORM, compartmentGridDropdownDefaultValue == BIN_COMPARTMENTS_GRID_TYPE_UNIFORM)
    compartmentGridDropdown.listItems.add(BIN_COMPARTMENTS_GRID_TYPE_CUSTOM, compartmentGridDropdownDefaultValue == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM)
    commandUIState.registerCommandInput(compartmentGridDropdown)
    render_compartments_table(inputs)

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
    for input in binTabFeaturesGroup.children:
        if not input.id == BIN_HAS_TAB_INPUT_ID:
            input.isEnabled = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)

    baseFeaturesGroup = inputs.addGroupCommandInput(BIN_BASE_FEATURES_GROUP_ID, 'Base interface features')
    baseFeaturesGroup.isExpanded = commandUIState.getState(BIN_BASE_FEATURES_GROUP_ID)
    commandUIState.registerCommandInput(baseFeaturesGroup)
    generateBaseCheckboxInput = baseFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BASE_INPUT_ID, 'Generate base', True, '', commandUIState.getState(BIN_GENERATE_BASE_INPUT_ID))
    commandUIState.registerCommandInput(generateBaseCheckboxInput)
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

    paddingGroup = inputs.addGroupCommandInput(BIN_PADDING_GROUP_ID, 'Side padding')
    paddingGroup.isExpanded = commandUIState.getState(BIN_PADDING_GROUP_ID)
    commandUIState.registerCommandInput(paddingGroup)
    hasPaddingCheckboxInput = paddingGroup.children.addBoolValueInput(BIN_HAS_PADDING_INPUT_ID, 'Add padding', True, '', commandUIState.getState(BIN_HAS_PADDING_INPUT_ID))
    commandUIState.registerCommandInput(hasPaddingCheckboxInput)
    paddingLeftInput = paddingGroup.children.addValueInput(BIN_PADDING_LEFT_INPUT_ID, 'Padding left', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_PADDING_LEFT_INPUT_ID)))
    paddingLeftInput.minimumValue = 0
    paddingLeftInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(paddingLeftInput)
    paddingTopInput = paddingGroup.children.addValueInput(BIN_PADDING_TOP_INPUT_ID, 'Padding top', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_PADDING_TOP_INPUT_ID)))
    paddingTopInput.minimumValue = 0
    paddingTopInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(paddingTopInput)
    paddingRightInput = paddingGroup.children.addValueInput(BIN_PADDING_RIGHT_INPUT_ID, 'Padding right', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_PADDING_RIGHT_INPUT_ID)))
    paddingRightInput.minimumValue = 0
    paddingRightInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(paddingRightInput)
    paddingBottomInput = paddingGroup.children.addValueInput(BIN_PADDING_BOTTOM_INPUT_ID, 'Padding bottom', defaultLengthUnits, adsk.core.ValueInput.createByReal(commandUIState.getState(BIN_PADDING_BOTTOM_INPUT_ID)))
    paddingBottomInput.minimumValue = 0
    paddingBottomInput.isMinimumInclusive = True
    commandUIState.registerCommandInput(paddingBottomInput)

    userChangesGroup = inputs.addGroupCommandInput(USER_CHANGES_GROUP_ID, 'Changes')
    userChangesGroup.isExpanded = commandUIState.getState(USER_CHANGES_GROUP_ID)
    commandUIState.registerCommandInput(userChangesGroup)
    saveAsDefaultsButtonInput = userChangesGroup.children.addBoolValueInput(INPUT_CHANGES_SAVE_DEFAULTS, 'Save as new defaults', False, '', False)
    saveAsDefaultsButtonInput.text = 'Save'
    resetToDefaultsButtonInput = userChangesGroup.children.addBoolValueInput(INPUT_CHANGES_RESET_TO_DEFAULTS, 'Reset to defaults', False, '', False)
    resetToDefaultsButtonInput.text = 'Reset'
    factoryResetButtonInput = userChangesGroup.children.addBoolValueInput(INPUT_CHANGES_RESET_TO_FACTORY, 'Wipe saved settings', False, '', False)
    factoryResetButtonInput.text = 'Factory reset'

    previewGroup = inputs.addGroupCommandInput(PREVIEW_GROUP_ID, 'Preview')
    previewGroup.isExpanded = commandUIState.getState(PREVIEW_GROUP_ID)
    commandUIState.registerCommandInput(userChangesGroup)
    showPreviewCheckboxInput =  previewGroup.children.addBoolValueInput(SHOW_PREVIEW_INPUT, 'Show auto update preview (slow)', True, '', False)
    commandUIState.registerCommandInput(showPreviewCheckboxInput)
    showPreviewManual = previewGroup.children.addBoolValueInput(SHOW_PREVIEW_MANUAL_INPUT, 'Update preview once', False, '', False)
    showPreviewManual.isFullWidth = True
    commandUIState.registerCommandInput(showPreviewManual)

    refreshUi()

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


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
            args.isValidResult = generateBin(args)
            showPreviewManual.value = False
    else:
        args.executeFailed = True
        args.executeFailedMessage = "Some inputs are invalid, unable to generate preview"

def cache_compartments_table_state(inputs: adsk.core.CommandInputs):
    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)
    global commandCompartmentsTableUIState
    commandCompartmentsTableUIState = []
    for i in range(1, binCompartmentsTable.rowCount):
        commandCompartmentsTableUIState.append(CommandUiState(CMD_NAME))
        for j in range(binCompartmentsTable.numberOfColumns):
            input = binCompartmentsTable.getInputAtPosition(i, j)
            commandCompartmentsTableUIState[-1].initValue(input.id, input.value, input.objectType)
            commandCompartmentsTableUIState[-1].registerCommandInput(input)

def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    global commandUIState
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')
    if changed_input.id == INPUT_CHANGES_SAVE_DEFAULTS:
        saveUIInputsAsDefaults()
    elif changed_input.id == INPUT_CHANGES_RESET_TO_DEFAULTS:
        initDefaultUiState()
        refreshUi()
    elif changed_input.id == INPUT_CHANGES_RESET_TO_FACTORY:
        configUtils.deleteConfigFile(UI_INPUT_DEFAULTS_CONFIG_PATH)
        initDefaultUiState()
        refreshUi()
    elif changed_input.parentCommandInput and changed_input.parentCommandInput.id == BIN_COMPARTMENTS_TABLE_ID:
        cache_compartments_table_state(inputs)
    else:
        commandUIState.onInputUpdate(changed_input)
        refreshUi()

    if isinstance(changed_input, adsk.core.GroupCommandInput) and changed_input.isExpanded == True:
        for input in changed_input.children:
            commandUIState.registerCommandInput(input)
        refreshUi()

    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)

    try:
        binHeightUnit = commandUIState.getState(BIN_HEIGHT_UNIT_INPUT_ID)
        binHeight = commandUIState.getState(BIN_HEIGHT_INPUT_ID)
        compartmentsGridWidth = commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)
        compartmentsGridLength = commandUIState.getState(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)

        if changed_input.id == BIN_COMPARTMENTS_TABLE_ADD_ID:
            append_compartment_table_row(0, 0, 1, 1, (binHeight + 1) * binHeightUnit - const.BIN_BASE_HEIGHT)
            cache_compartments_table_state(inputs)
        elif changed_input.id == BIN_COMPARTMENTS_TABLE_REMOVE_ID:
            if binCompartmentsTable.selectedRow > 0:
                deleteTableRow(binCompartmentsTable.selectedRow, binCompartmentsTable, commandCompartmentsTableUIState)
            elif binCompartmentsTable.rowCount > 1:
                deleteTableRow(binCompartmentsTable.rowCount - 1, binCompartmentsTable, commandCompartmentsTableUIState)
        elif changed_input.id == BIN_COMPARTMENTS_TABLE_UNIFORM_ID:
            for i in range(binCompartmentsTable.rowCount - 1, 0, -1):
                deleteTableRow(i, binCompartmentsTable, commandCompartmentsTableUIState)
            for i in range(compartmentsGridWidth):
                for j in range(compartmentsGridLength):
                    append_compartment_table_row(i, j, 1, 1, (binHeight + 1) * binHeightUnit - const.BIN_BASE_HEIGHT)
                cache_compartments_table_state(inputs)

    except:
        showErrorInMessageBox()



# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs

    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    args.areInputsValid = is_all_input_valid(inputs)
    futil.log(f'{CMD_NAME} Inputs are {"valid" if args.areInputsValid else "invalid"}')


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event "{args.terminationReason}"')
    global local_handlers
    local_handlers = []

def deleteTableRow(rowToDelete: int, tableInput: adsk.core.TableCommandInput, inputState: list[CommandUiState]):
    inputState.pop(rowToDelete - 1)
    tableInput.deleteRow(rowToDelete)

def refreshCompartmentsTable():
    global commandUIState
    binCompartmentsTable: adsk.core.TableCommandInput = commandUIState.getInput(BIN_COMPARTMENTS_TABLE_ID)
    for i in range(binCompartmentsTable.rowCount - 1, 0, -1):
        binCompartmentsTable.deleteRow(i)
    append_compartments_from_state()


def onChangeValidate():
    global commandUIState

    generateBase: bool = commandUIState.getState(BIN_GENERATE_BASE_INPUT_ID)
    commandUIState.getInput(BIN_SCREW_HOLES_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_CUTOUTS_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_CUTOUTS_TABS_INPUT_ID).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_DIAMETER_INPUT).isEnabled = generateBase
    commandUIState.getInput(BIN_MAGNET_HEIGHT_INPUT).isEnabled = generateBase
    commandUIState.getInput(BIN_SCREW_DIAMETER_INPUT).isEnabled = generateBase

    generateBody: bool = commandUIState.getState(BIN_GENERATE_BODY_INPUT_ID)
    binType: str = commandUIState.getState(BIN_TYPE_DROPDOWN_ID)
    commandUIState.getInput(BIN_WALL_THICKNESS_INPUT_ID).isEnabled = generateBody and not binType == BIN_TYPE_SOLID
    commandUIState.getInput(BIN_WITH_LIP_INPUT_ID).isEnabled = generateBody
    commandUIState.getInput(BIN_WITH_LIP_NOTCHES_INPUT_ID).isEnabled = generateBody
    commandUIState.getInput(BIN_HAS_TAB_INPUT_ID).isEnabled = generateBody
    generateTab: bool = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)
    for input in commandUIState.getInput(BIN_TAB_FEATURES_GROUP_ID).children:
        if not input.id == BIN_HAS_TAB_INPUT_ID:
            input.isEnabled = generateBody and generateTab

    generateLip: bool = commandUIState.getState(BIN_WITH_LIP_INPUT_ID)
    commandUIState.getInput(BIN_WITH_LIP_NOTCHES_INPUT_ID).isEnabled = generateLip

    generateScoop: bool = commandUIState.getState(BIN_HAS_SCOOP_INPUT_ID)
    commandUIState.getInput(BIN_SCOOP_MAX_RADIUS_INPUT_ID).isEnabled = generateScoop

    generateTab: bool = commandUIState.getState(BIN_HAS_TAB_INPUT_ID)
    commandUIState.getInput(BIN_TAB_LENGTH_INPUT_ID).isEnabled = generateTab
    commandUIState.getInput(BIN_TAB_WIDTH_INPUT_ID).isEnabled = generateTab
    commandUIState.getInput(BIN_TAB_ANGLE_INPUT_ID).isEnabled = generateTab
    commandUIState.getInput(BIN_TAB_POSITION_INPUT_ID).isEnabled = generateTab

    compartmentsGridType: str = commandUIState.getState(BIN_COMPARTMENTS_GRID_TYPE_ID)
    commandUIState.getInput(BIN_COMPARTMENTS_TABLE_ID).isVisible = compartmentsGridType == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM

    showPreview: bool = commandUIState.getInput(SHOW_PREVIEW_INPUT).value
    commandUIState.getInput(SHOW_PREVIEW_MANUAL_INPUT).isVisible = not showPreview

def saveUIInputsAsDefaults():
    futil.log(f'{CMD_NAME} Saving UI state to file')
    result = configUtils.dumpJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH, {
        'static_ui': commandUIState.toDict(ignoreKeys=[SHOW_PREVIEW_MANUAL_INPUT, SHOW_PREVIEW_INPUT]),
        'compartments_table': [x.toDict() for x in commandCompartmentsTableUIState]
        })
    if result:
        futil.log(f'{CMD_NAME} Saved successfully')
    else:
        futil.log(f'{CMD_NAME} UI state failed to save')

def generateBin(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
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
    binTypeDropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TYPE_DROPDOWN_ID)
    binCompartmentGridTypeDropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_TYPE_ID)
    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)
    compartmentsX: adsk.core.IntegerSpinnerCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID)
    compartmentsY: adsk.core.IntegerSpinnerCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID)
    bin_padding: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_PADDING_INPUT_ID)
    bin_padding_left: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_LEFT_INPUT_ID)
    bin_padding_top: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_TOP_INPUT_ID)
    bin_padding_right: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_RIGHT_INPUT_ID)
    bin_padding_bottom: adsk.core.ValueCommandInput = inputs.itemById(BIN_PADDING_BOTTOM_INPUT_ID)


    isHollow = binTypeDropdownInput.selectedItem.name == BIN_TYPE_HOLLOW
    isSolid = binTypeDropdownInput.selectedItem.name == BIN_TYPE_SOLID
    isShelled = binTypeDropdownInput.selectedItem.name == BIN_TYPE_SHELLED

    try:
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

        # create base interface
        baseGeneratorInput = BaseGeneratorInput()
        baseGeneratorInput.originPoint = geometryUtils.createOffsetPoint(
            gridfinityBinComponent.originConstructionPoint.geometry,
            byX=-xyClearance,
            byY=-xyClearance,
        )
        baseGeneratorInput.baseWidth = base_width_unit.value
        baseGeneratorInput.baseLength = base_length_unit.value
        baseGeneratorInput.xyClearance = xyClearance
        baseGeneratorInput.hasScrewHoles = bin_screw_holes.value and not isShelled
        baseGeneratorInput.hasMagnetCutouts = bin_magnet_cutouts.value and not isShelled
        baseGeneratorInput.hasMagnetCutoutsTabs = bin_magnet_cutouts_tabs.value and not isShelled
        baseGeneratorInput.screwHolesDiameter = bin_screw_hole_diameter.value
        baseGeneratorInput.magnetCutoutsDiameter = bin_magnet_cutout_diameter.value
        baseGeneratorInput.magnetCutoutsDepth = bin_magnet_cutout_depth.value
        # Needed to calculate base clearance
        baseGeneratorInput.hasPadding = bin_padding.value
        baseGeneratorInput.paddingLeft = bin_padding_left.value
        baseGeneratorInput.paddingTop = bin_padding_top.value
        baseGeneratorInput.paddingRight = bin_padding_right.value
        baseGeneratorInput.paddingBottom = bin_padding_bottom.value        

        baseBodies: list[adsk.fusion.BRepBody]
        if bin_generate_base.value:
            baseBodies = createBaseBodyPattern(
                baseGeneratorInput,
                bin_width.value,
                bin_length.value,
                gridfinityBinComponent,
            )

        # create bin body
        binBodyInput = BinBodyGeneratorInput()
        binBodyInput.hasLip = with_lip.value
        binBodyInput.hasLipNotches = with_lip_notches.value
        binBodyInput.binWidth = bin_width.value
        binBodyInput.binLength = bin_length.value
        binBodyInput.binHeight = bin_height.value
        binBodyInput.baseWidth = base_width_unit.value
        binBodyInput.baseLength = base_length_unit.value
        binBodyInput.heightUnit = height_unit.value
        binBodyInput.xyClearance = xyClearance
        binBodyInput.binCornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS - xyClearance
        binBodyInput.isSolid = isSolid or isShelled
        binBodyInput.wallThickness = bin_wall_thickness.value
        binBodyInput.hasScoop = has_scoop.value and isHollow
        binBodyInput.scoopMaxRadius = binScoopMaxRadius.value
        binBodyInput.hasTab = hasTabInput.value and isHollow
        binBodyInput.tabLength = binTabLength.value
        binBodyInput.tabWidth = binTabWidth.value
        binBodyInput.tabPosition = binTabPosition.value
        binBodyInput.tabOverhangAngle = binTabAngle.value
        binBodyInput.compartmentsByX = compartmentsX.value
        binBodyInput.compartmentsByY = compartmentsY.value
        binBodyInput.hasPadding = bin_padding.value
        binBodyInput.paddingLeft = bin_padding_left.value
        binBodyInput.paddingTop = bin_padding_top.value
        binBodyInput.paddingRight = bin_padding_right.value
        binBodyInput.paddingBottom = bin_padding_bottom.value

        if binCompartmentGridTypeDropdownInput.selectedItem.name == BIN_COMPARTMENTS_GRID_TYPE_UNIFORM:
            binBodyInput.compartments = uniformCompartments(binBodyInput.compartmentsByX, binBodyInput.compartmentsByY)
        else:
            binBodyInput.compartments = []
            for i in range(1, binCompartmentsTable.rowCount):
                positionX: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 0)
                positionY: adsk.core.IntegerSpinnerCommandInput  = binCompartmentsTable.getInputAtPosition(i, 1)
                width: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 2)
                length: adsk.core.IntegerSpinnerCommandInput = binCompartmentsTable.getInputAtPosition(i, 3)
                depth: adsk.core.ValueCommandInput = binCompartmentsTable.getInputAtPosition(i, 4)
                binBodyInput.compartments.append(BinBodyCompartmentDefinition(positionX.value, positionY.value, width.value, length.value, depth.value))

        binBody: adsk.fusion.BRepBody

        if bin_generate_body.value:
            binBody = createGridfinityBinBody(
                binBodyInput,
                gridfinityBinComponent,
            )
        if bin_generate_body.value or bin_generate_base.value:
            cutBaseClearance(
                baseGeneratorInput,
                bin_width.value,
                bin_length.value,
                gridfinityBinComponent,
            )

        # merge everything
        if bin_generate_body.value and bin_generate_base.value:
            toolBodies = commonUtils.objectCollectionFromList(baseBodies)
            combineFeatures = gridfinityBinComponent.features.combineFeatures
            combineFeatureInput = combineFeatures.createInput(binBody, toolBodies)
            combineFeatures.add(combineFeatureInput)
            gridfinityBinComponent.bRepBodies.item(0).name = binName

        if isShelled and bin_generate_body.value:
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
                bottomBody = min(splitBodies.bodies, key=lambda x: x.boundingBox.minPoint.z)
                topBody = max(splitBodies.bodies, key=lambda x: x.boundingBox.minPoint.z)
                horizontalFaces = [face for face in bottomBody.faces if geometryUtils.isHorizontal(face)]
                topFace = faceUtils.maxByArea(horizontalFaces)
                shellUtils.simpleShell([topFace], binBodyInput.wallThickness - xyClearance, gridfinityBinComponent)
                toolBodies = adsk.core.ObjectCollection.create()
                toolBodies.add(topBody)
                combineAfterShellFeatureInput = combineFeatures.createInput(bottomBody, toolBodies)
                combineFeatures.add(combineAfterShellFeatureInput)
                binBody = gridfinityBinComponent.bRepBodies.item(0)
            else:
                shellUtils.simpleShell([topFace], binBodyInput.wallThickness - xyClearance, gridfinityBinComponent)

            if hasTabInput.value:
                compartmentTabInput = BinBodyTabGeneratorInput()
                tabOriginPoint = adsk.core.Point3D.create(
                    binBodyInput.wallThickness + max(0, min(binBodyInput.tabPosition, binBodyInput.binWidth - binBodyInput.tabLength)) * binBodyInput.baseWidth,
                    const.BIN_LIP_WALL_THICKNESS if binBodyInput.hasLip and binBodyInput.hasScoop else binBodyInput.wallThickness + binBodyInput.binLength * binBodyInput.baseLength - binBodyInput.wallThickness - binBodyInput.xyClearance * 2,
                    (binBodyInput.binHeight - 1) * binBodyInput.heightUnit + max(0, binBodyInput.heightUnit - const.BIN_BASE_HEIGHT),
                )
                compartmentTabInput.origin = tabOriginPoint
                compartmentTabInput.length = max(0, min(binBodyInput.tabLength, binBodyInput.binWidth)) * binBodyInput.baseWidth - binBodyInput.wallThickness * 2 - binBodyInput.xyClearance * 2
                compartmentTabInput.width = binBodyInput.tabWidth
                compartmentTabInput.overhangAngle = binBodyInput.tabOverhangAngle
                compartmentTabInput.topClearance = const.BIN_TAB_TOP_CLEARANCE
                tabBody = createGridfinityBinBodyTab(compartmentTabInput, gridfinityBinComponent)
                combineInput = combineFeatures.createInput(tabBody, commonUtils.objectCollectionFromList([binBody]))
                combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
                combineInput.isKeepToolBodies = True
                combineFeature = combineFeatures.add(combineInput)
                tabBodies = [body for body in combineFeature.bodies if body.faces != binBody.faces]
                tabMainBody = max([body for body in tabBodies], key=lambda x: x.edges.count)
                bodiesToRemove = [body for body in tabBodies if body is not tabMainBody]
                for body in bodiesToRemove:
                    gridfinityBinComponent.features.removeFeatures.add(body)
                combineUtils.joinBodies(binBody, commonUtils.objectCollectionFromList([tabMainBody]), gridfinityBinComponent)

        # group features in timeline
        binGroup = des.timeline.timelineGroups.add(originalTimelineCount, des.timeline.count - 1)
        binGroup.name = binName
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
