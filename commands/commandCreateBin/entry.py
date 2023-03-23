import adsk.core, adsk.fusion, traceback
import os
import math
import json
from dataclasses import asdict

from ...lib import configUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils import geometryUtils
from ...lib.gridfinityUtils import faceUtils
from ...lib.gridfinityUtils import shellUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils.baseGenerator import createGridfinityBase
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.binBodyGenerator import createGridfinityBinBody, uniformCompartments
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput, BinBodyCompartmentDefinition
from .inputState import InputState, CompartmentTableRow
from .staticInputCache import StaticInputCache

app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBin'
CMD_NAME = 'Gridfinity bin'
CMD_Description = 'Create simple gridfinity bin'

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

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Constants
BIN_BASE_WIDTH_UNIT_INPUT_ID = 'base_width_unit'
BIN_BASE_LENGTH_UNIT_INPUT_ID = 'base_length_unit'
BIN_HEIGHT_UNIT_INPUT_ID = 'height_unit'
BIN_XY_TOLERANCE_INPUT_ID = 'bin_xy_tolerance'
BIN_WIDTH_INPUT_ID = 'bin_width'
BIN_LENGTH_INPUT_ID = 'bin_length'
BIN_HEIGHT_INPUT_ID = 'bin_height'
BIN_WIDTH_INPUT_ID = 'bin_width'
BIN_REAL_DIMENSIONS_TABLE = "real_dimensions"
BIN_WALL_THICKNESS_INPUT_ID = 'bin_wall_thickness'
BIN_GENERATE_BASE_INPUT_ID = 'bin_generate_base'
BIN_GENERATE_BODY_INPUT_ID = 'bin_generate_body'
BIN_SCREW_HOLES_INPUT_ID = 'bin_screw_holes'
BIN_MAGNET_CUTOUTS_INPUT_ID = 'bin_magnet_cutouts'
BIN_SCREW_DIAMETER_INPUT = 'screw_diameter'
BIN_MAGNET_DIAMETER_INPUT = 'magnet_diameter'
BIN_MAGNET_HEIGHT_INPUT = 'magnet_height'
BIN_HAS_SCOOP_INPUT_ID = 'bin_has_scoop'
BIN_HAS_TAB_INPUT_ID = 'bin_has_tab'
BIN_TAB_LENGTH_INPUT_ID = 'bin_tab_length'
BIN_TAB_WIDTH_INPUT_ID = 'bin_tab_width'
BIN_TAB_POSITION_INPUT_ID = 'bin_tab_position'
BIN_TAB_ANGLE_INPUT_ID = 'bin_tab_angle'
BIN_WITH_LIP_INPUT_ID = 'with_lip'
BIN_WITH_LIP_NOTCHES_INPUT_ID = 'with_lip_notches'
BIN_COMPARTMENTS_GROUP_ID = 'compartments_group'
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

BIN_TAB_FEATURES_GROUP_ID = 'bin_tab_features'

PRESERVE_CHAGES_RADIO_GROUP = 'preserve_changes'
PRESERVE_CHAGES_RADIO_GROUP_PRESERVE = 'Preserve inputs'
PRESERVE_CHAGES_RADIO_GROUP_RESET = 'Reset inputs after creation'
RESET_CHAGES_INPUT = 'reset_changes'
SHOW_PREVIEW_INPUT = 'show_preview'
SHOW_PREVIEW_MANUAL_INPUT = 'show_preview_manual'

def defaultUiState():
    return InputState(
        baseWidth=const.DIMENSION_DEFAULT_WIDTH_UNIT,
        baseLength=const.DIMENSION_DEFAULT_WIDTH_UNIT,
        heightUnit=const.DIMENSION_DEFAULT_HEIGHT_UNIT,
        xyTolerance=const.BIN_XY_TOLERANCE,
        binWidth=2,
        binLength=3,
        binHeight=5,
        hasBody=True,
        binBodyType=BIN_TYPE_HOLLOW,
        binWallThickness=const.BIN_WALL_THICKNESS,
        hasLip=True,
        hasLipNotches=False,
        compartmentsGridWidth=1,
        compartmentsGridLength=1,
        compartmentsGridType=BIN_COMPARTMENTS_GRID_TYPE_UNIFORM,
        hasScoop=False,
        hasTab=False,
        tabLength=1,
        tabWidth=const.BIN_TAB_WIDTH,
        tabAngle=45,
        tabOffset=0,
        hasBase=True,
        hasBaseScrewHole=False,
        baseScrewHoleSize=const.DIMENSION_SCREW_HOLE_DIAMETER,
        hasBaseMagnetSockets=False,
        baseMagnetSocketSize=const.DIMENSION_MAGNET_CUTOUT_DIAMETER,
        baseMagnetSocketDepth=const.DIMENSION_MAGNET_CUTOUT_DEPTH,
        preserveChanges=False,
        customCompartments=[],
    )

uiState = defaultUiState()
staticInputCache = StaticInputCache()

# json.dumps(asdict(uiState))

def getErrorMessage():
    stackTrace = traceback.format_exc();
    return f"An unknonwn error occurred, please validate your inputs and try again:\n{stackTrace}"

def showErrorInMessageBox():
    if ui:
        ui.messageBox(getErrorMessage(), f"{CMD_NAME} Error")

# Executed when add-in is run.
def start():
    addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)

    # Create a command Definition.
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

# Executed when add-in is stopped.
def stop():
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
    actualDimensionsTable = inputs.addTableCommandInput(BIN_REAL_DIMENSIONS_TABLE, "Actual dimensions (mm)", 3, "1:1:1")
    totalWidth = actualDimensionsTable.commandInputs.addStringValueInput("total_real_width", "", "Total width")
    totalWidth.isReadOnly = True
    totalLength = actualDimensionsTable.commandInputs.addStringValueInput("total_real_length", "", "Total length")
    totalLength.isReadOnly = True
    totalHeight = actualDimensionsTable.commandInputs.addStringValueInput("total_real_height", "", "Total height")
    totalHeight.isReadOnly = True
    actualDimensionsTable.addCommandInput(totalWidth, 0, 0)
    actualDimensionsTable.addCommandInput(totalLength, 0, 1)
    actualDimensionsTable.addCommandInput(totalHeight, 0, 2)
    actualDimensionsTable.tablePresentationStyle = adsk.core.TablePresentationStyles.transparentBackgroundTablePresentationStyle
    actualDimensionsTable.hasGrid = False
    actualDimensionsTable.minimumVisibleRows = 1
    actualDimensionsTable.maximumVisibleRows = 1
    return actualDimensionsTable

def render_actual_compartment_dimension_units_table(inputs: adsk.core.CommandInputs):
    actualDimensionsTable = inputs.addTableCommandInput(BIN_REAL_DIMENSIONS_TABLE, "Actual dimensions (mm)", 2, "1:1")
    totalWidth = actualDimensionsTable.commandInputs.addTextBoxCommandInput("compartment_width_u", "", "Grid cell width", 1, True)
    totalLength = actualDimensionsTable.commandInputs.addTextBoxCommandInput("compartment_length_u", "", "Grid cell length", 1, True)
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

def update_actual_compartment_unit_dimensions(
        actualDimensionsTable: adsk.core.TableCommandInput,
        baseWidth: float,
        baseLength: float,
        binWidth: float,
        binLength: float,
        gridWidth: int,
        gridLength: int,
        wallThickness: float,
        xyTolerance: float,
    ):
    try:
        minCompartmentDimensionLimit = (const.BIN_CORNER_FILLET_RADIUS - wallThickness) * 2 * 10
        gridCellWidthInput: adsk.core.TextBoxCommandInput = actualDimensionsTable.getInputAtPosition(0, 0)
        cellWidth = round((baseWidth * binWidth - wallThickness * 2 - xyTolerance * 2 - wallThickness * (gridWidth - 1)) / gridWidth * 10, 2)
        gridCellWidthInput.formattedText = formatString("Grid cell width: {}mm".format(cellWidth), "" if cellWidth >= minCompartmentDimensionLimit else "red")
        gridCellLengthInput: adsk.core.TextBoxCommandInput = actualDimensionsTable.getInputAtPosition(0, 1)
        cellLength = round((baseLength * binLength - wallThickness * 2 - xyTolerance * 2 - wallThickness * (gridLength - 1)) / gridLength * 10, 2)
        gridCellLengthInput.formattedText = formatString("Grid cell length: {}mm".format(cellLength), "" if cellLength >= minCompartmentDimensionLimit else "red")
    except:
        showErrorInMessageBox()

def update_actual_bin_dimensions(actualBinDimensionsTable: adsk.core.TableCommandInput, width: adsk.core.ValueInput, length: adsk.core.ValueInput, heigh: adsk.core.ValueInput):
    try:
        totalWidth: adsk.core.StringValueCommandInput = actualBinDimensionsTable.getInputAtPosition(0, 0)
        totalWidth.value = "Total width: {}mm".format(round(width.realValue * 10, 2))
        totalLength: adsk.core.StringValueCommandInput = actualBinDimensionsTable.getInputAtPosition(0, 1)
        totalLength.value = "Total length: {}mm".format(round(length.realValue * 10, 2))
        totalHeight: adsk.core.StringValueCommandInput = actualBinDimensionsTable.getInputAtPosition(0, 2)
        totalHeight.value = "Total height: {}mm".format(round(heigh.realValue * 10, 2))
    except:
        showErrorInMessageBox()

def render_compartments_table(inputs: adsk.core.CommandInputs, initiallyVisible: bool):
    compartmentsGroup: adsk.core.GroupCommandInput = inputs.itemById(BIN_COMPARTMENTS_GROUP_ID)
    binCompartmentsTable = compartmentsGroup.children.addTableCommandInput(BIN_COMPARTMENTS_TABLE_ID, "Compartments", 5, "1:1:1:1:1")
    addButton = compartmentsGroup.commandInputs.addBoolValueInput(BIN_COMPARTMENTS_TABLE_ADD_ID, "Add", False, "", False)
    removeButton = compartmentsGroup.commandInputs.addBoolValueInput(BIN_COMPARTMENTS_TABLE_REMOVE_ID, "Remove", False, "", False)
    populateUniform = compartmentsGroup.commandInputs.addBoolValueInput(BIN_COMPARTMENTS_TABLE_UNIFORM_ID, "Reset to uniform", False, "", False)
    binCompartmentsTable.addToolbarCommandInput(addButton)
    binCompartmentsTable.addToolbarCommandInput(removeButton)
    binCompartmentsTable.addToolbarCommandInput(populateUniform)
    binCompartmentsTable.hasGrid = False
    binCompartmentsTable.tablePresentationStyle = adsk.core.TablePresentationStyles.nameValueTablePresentationStyle
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

    for row in uiState.customCompartments:
        append_compartment_table_row(inputs, row.x, row.y, row.width, row.length, row.depth)

def append_compartment_table_row(inputs: adsk.core.CommandInputs, x: int, y: int, w: int, l: int, defaultDepth: float):
    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)
    newRow = binCompartmentsTable.rowCount
    x_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput("x_input_{}".format(newRow), "X (u)", 0, 100, 1, x)
    x_input.isFullWidth = True
    y_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput("y_input_{}".format(newRow), "Y (u)", 0, 100, 1, y)
    y_input.isFullWidth = True
    w_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput("w_input_{}".format(newRow), "W (u)", 1, 100, 1, w)
    w_input.isFullWidth = True
    l_input = binCompartmentsTable.commandInputs.addIntegerSpinnerCommandInput("l_input_{}".format(newRow), "L (u)", 1, 100, 1, l)
    l_input.isFullWidth = True
    d_input = binCompartmentsTable.commandInputs.addValueInput("d_input_{}".format(newRow), "Depth (mm)", app.activeProduct.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(defaultDepth))
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
    xy_tolerance: adsk.core.ValueCommandInput = inputs.itemById(BIN_XY_TOLERANCE_INPUT_ID)
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

    result = result and base_width_unit.value > 0
    result = result and base_length_unit.value > 0
    result = result and height_unit.value > 0
    result = result and xy_tolerance.value > 0 and xy_tolerance.value <= 0.5
    result = result and bin_width.value > 0
    result = result and bin_length.value > 0
    result = result and bin_height.value >= 0
    result = result and bin_wall_thickness.value > 0.04 and bin_wall_thickness.value <= 0.2
    if bin_generate_base.value:
        result = result and (not bin_screw_holes.value or bin_screw_hole_diameter.value > 0) and (not bin_magnet_cutouts.value or bin_screw_hole_diameter.value < bin_magnet_cutout_diameter.value)
        result = result and bin_magnet_cutout_depth.value > 0

    if bin_generate_body.value and binTypeDropdownInput.selectedItem.name == BIN_TYPE_HOLLOW:
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

    args.command.setDialogInitialSize(400, 500)

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    basicSizesGroup = inputs.addGroupCommandInput('basic_sizes', 'Basic sizes')
    basicSizesGroup.children.addValueInput(BIN_BASE_WIDTH_UNIT_INPUT_ID, 'Base width unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.baseWidth))
    basicSizesGroup.children.addValueInput(BIN_BASE_LENGTH_UNIT_INPUT_ID, 'Base length unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.baseLength))
    basicSizesGroup.children.addValueInput(BIN_HEIGHT_UNIT_INPUT_ID, 'Bin height unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.heightUnit))
    basicSizesGroup.children.addValueInput(BIN_XY_TOLERANCE_INPUT_ID, 'Bin xy tolerance (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.xyTolerance))

    binDimensionsGroup = inputs.addGroupCommandInput('bin_dimensions', 'Main dimensions')
    binDimensionsGroup.tooltipDescription = 'Set in base units'
    binDimensionsGroup.children.addValueInput(BIN_WIDTH_INPUT_ID, 'Bin width (u)', '', adsk.core.ValueInput.createByReal(uiState.binWidth))
    binDimensionsGroup.children.addValueInput(BIN_LENGTH_INPUT_ID, 'Bin length (u)', '', adsk.core.ValueInput.createByReal(uiState.binLength))
    binDimensionsGroup.children.addValueInput(BIN_HEIGHT_INPUT_ID, 'Bin height (u)', '', adsk.core.ValueInput.createByReal(uiState.binHeight))

    actualDimensionsTable = render_actual_bin_dimensions_table(binDimensionsGroup.children)
    update_actual_bin_dimensions(
        actualDimensionsTable,
        adsk.core.ValueInput.createByReal(const.DIMENSION_DEFAULT_WIDTH_UNIT * 2 - const.BIN_XY_TOLERANCE * 2),
        adsk.core.ValueInput.createByReal(const.DIMENSION_DEFAULT_WIDTH_UNIT * 3 - const.BIN_XY_TOLERANCE * 2),
        adsk.core.ValueInput.createByReal(const.DIMENSION_DEFAULT_HEIGHT_UNIT * 6 + const.BIN_LIP_EXTRA_HEIGHT - const.BIN_LIP_TOP_RECESS_HEIGHT))
    staticInputCache.actualBinDimensionsTable = actualDimensionsTable

    binFeaturesGroup = inputs.addGroupCommandInput('bin_features', 'Bin features')
    binFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BODY_INPUT_ID, 'Generate body', True, '', uiState.hasBody)
    binTypeDropdown = binFeaturesGroup.children.addDropDownCommandInput(BIN_TYPE_DROPDOWN_ID, 'Bin type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    binTypeDropdown.listItems.add(BIN_TYPE_HOLLOW, uiState.binBodyType == BIN_TYPE_HOLLOW)
    binTypeDropdown.listItems.add(BIN_TYPE_SHELLED, uiState.binBodyType == BIN_TYPE_SHELLED)
    binTypeDropdown.listItems.add(BIN_TYPE_SOLID, uiState.binBodyType == BIN_TYPE_SOLID)

    binFeaturesGroup.children.addValueInput(BIN_WALL_THICKNESS_INPUT_ID, 'Bin wall thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.binWallThickness))
    binFeaturesGroup.children.addBoolValueInput(BIN_WITH_LIP_INPUT_ID, 'Generate lip for stackability', True, '', uiState.hasLip)
    binFeaturesGroup.children.addBoolValueInput(BIN_WITH_LIP_NOTCHES_INPUT_ID, 'Generate lip notches', True, '', uiState.hasLipNotches)

    compartmentsGroup: adsk.core.GroupCommandInput = inputs.addGroupCommandInput(BIN_COMPARTMENTS_GROUP_ID, 'Bin compartments')
    compartmentsGroup.children.addIntegerSpinnerCommandInput(BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID, "Grid width (n per bin width)", 1, 100, 1, uiState.compartmentsGridWidth)
    compartmentsGroup.children.addIntegerSpinnerCommandInput(BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID, "Grid length (n per bin length)", 1, 100, 1, uiState.compartmentsGridLength)
    compartmentsGridDimensionsTable = render_actual_compartment_dimension_units_table(compartmentsGroup.children)
    staticInputCache.actualCompartmentDimensionUnitsTable = compartmentsGridDimensionsTable
    update_actual_compartment_unit_dimensions(
        compartmentsGridDimensionsTable,
        uiState.baseWidth,
        uiState.baseLength,
        uiState.binWidth,
        uiState.binLength,
        uiState.compartmentsGridWidth,
        uiState.compartmentsGridLength,
        uiState.binWallThickness,
        uiState.xyTolerance,
        )

    compartmentGridDropdown = compartmentsGroup.children.addDropDownCommandInput(BIN_COMPARTMENTS_GRID_TYPE_ID, "Grid type", adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    compartmentGridDropdown.listItems.add(BIN_COMPARTMENTS_GRID_TYPE_UNIFORM, uiState.compartmentsGridType == BIN_COMPARTMENTS_GRID_TYPE_UNIFORM)
    compartmentGridDropdown.listItems.add(BIN_COMPARTMENTS_GRID_TYPE_CUSTOM, uiState.compartmentsGridType == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM)
    # textBox = compartmentsGroup.children.addTextBoxCommandInput(BIN_COMPARTMENTS_GRID_TYPE_INFO, "", BIN_COMPARTMENTS_GRID_TYPE_INFO_UNIFORM, 2, True)
    render_compartments_table(inputs, uiState.compartmentsGridType == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM)

    compartmentsGroup.children.addBoolValueInput(BIN_HAS_SCOOP_INPUT_ID, 'Add scoop (along bin width)', True, '', uiState.hasScoop)
    binTabFeaturesGroup = compartmentsGroup.children.addGroupCommandInput(BIN_TAB_FEATURES_GROUP_ID, 'Label tab')
    binTabFeaturesGroup.children.addBoolValueInput(BIN_HAS_TAB_INPUT_ID, 'Add label tab (along bin width)', True, '', uiState.hasTab)
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_LENGTH_INPUT_ID, 'Tab length (u)', '', adsk.core.ValueInput.createByReal(uiState.tabLength))
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_WIDTH_INPUT_ID, 'Tab width (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.tabWidth))
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_POSITION_INPUT_ID, 'Tab offset (u)', '', adsk.core.ValueInput.createByReal(uiState.tabOffset))
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_ANGLE_INPUT_ID, 'Tab overhang angle', 'deg', adsk.core.ValueInput.createByString(str(uiState.tabAngle)))
    for input in binTabFeaturesGroup.children:
        if not input.id == BIN_HAS_TAB_INPUT_ID:
            input.isEnabled = False

    baseFeaturesGroup = inputs.addGroupCommandInput('base_features', 'Base interface features')
    baseFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BASE_INPUT_ID, 'Generate base', True, '', uiState.hasBase)
    baseFeaturesGroup.children.addBoolValueInput(BIN_SCREW_HOLES_INPUT_ID, 'Add screw holes', True, '', uiState.hasBaseScrewHole)
    baseFeaturesGroup.children.addValueInput(BIN_SCREW_DIAMETER_INPUT, 'Screw hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.baseScrewHoleSize))
    baseFeaturesGroup.children.addBoolValueInput(BIN_MAGNET_CUTOUTS_INPUT_ID, 'Add magnet cutouts', True, '', uiState.hasBaseMagnetSockets)
    baseFeaturesGroup.children.addValueInput(BIN_MAGNET_DIAMETER_INPUT, 'Magnet cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.baseMagnetSocketSize))
    baseFeaturesGroup.children.addValueInput(BIN_MAGNET_HEIGHT_INPUT, 'Magnet cutout depth', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.baseMagnetSocketDepth))

    userChangesGroup = inputs.addGroupCommandInput('user_changes_group', 'Changes')
    preserveInputsRadioGroup = userChangesGroup.children.addRadioButtonGroupCommandInput(PRESERVE_CHAGES_RADIO_GROUP, 'Preserve inputs')
    preserveInputsRadioGroup.listItems.add(PRESERVE_CHAGES_RADIO_GROUP_RESET, not uiState.preserveChanges)
    preserveInputsRadioGroup.listItems.add(PRESERVE_CHAGES_RADIO_GROUP_PRESERVE, uiState.preserveChanges)
    preserveInputsRadioGroup.isFullWidth = True
    # preserveChangesDescription = userChangesGroup.children.addTextBoxCommandInput(PRESERVE_CHAGES_RADIO_GROUP + "_description", "", "Inputs will be persisted until Fusion is closed or reset option is selected", 2, True)
    # preserveChangesDescription.isFullWidth = True
    # showPreviewManual = userChangesGroup.children.addBoolValueInput(SHOW_PREVIEW_MANUAL_INPUT, 'Update preview once', False, '', False)


    previewGroup = inputs.addGroupCommandInput('preview_group', 'Preview')
    previewGroup.children.addBoolValueInput(SHOW_PREVIEW_INPUT, 'Show auto update preview (slow)', True, '', False)
    showPreviewManual = previewGroup.children.addBoolValueInput(SHOW_PREVIEW_MANUAL_INPUT, 'Update preview once', False, '', False)
    showPreviewManual.isFullWidth = True

    # TODO Connect to the events that are needed by this command.
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

def record_input_change(changed_input: adsk.core.CommandInput):
    if changed_input.id == BIN_BASE_WIDTH_UNIT_INPUT_ID:
        uiState.baseWidth = changed_input.value
    elif changed_input.id == BIN_BASE_LENGTH_UNIT_INPUT_ID:
        uiState.baseLength = changed_input.value
    elif changed_input.id == BIN_HEIGHT_UNIT_INPUT_ID:
        uiState.heightUnit = changed_input.value
    elif changed_input.id == BIN_HEIGHT_UNIT_INPUT_ID:
        uiState.xyTolerance = changed_input.value
    elif changed_input.id == BIN_WIDTH_INPUT_ID:
        uiState.binWidth = changed_input.value
    elif changed_input.id == BIN_LENGTH_INPUT_ID:
        uiState.binLength = changed_input.value
    elif changed_input.id == BIN_HEIGHT_INPUT_ID:
        uiState.binHeight = changed_input.value
    elif changed_input.id == BIN_GENERATE_BODY_INPUT_ID:
        uiState.hasBody = changed_input.value
    elif changed_input.id == BIN_TYPE_DROPDOWN_ID:
        uiState.binBodyType = changed_input.selectedItem.name
    elif changed_input.id == BIN_WALL_THICKNESS_INPUT_ID:
        uiState.binBodyType = changed_input.value
    elif changed_input.id == BIN_WITH_LIP_INPUT_ID:
        uiState.hasLip = changed_input.value
    elif changed_input.id == BIN_WITH_LIP_NOTCHES_INPUT_ID:
        uiState.hasLipNotches = changed_input.value
    elif changed_input.id == BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID:
        uiState.compartmentsGridWidth = changed_input.value
    elif changed_input.id == BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID:
        uiState.compartmentsGridLength = changed_input.value
    elif changed_input.id == BIN_COMPARTMENTS_GRID_TYPE_ID:
        uiState.compartmentsGridType = changed_input.selectedItem.name
    elif changed_input.id == BIN_HAS_SCOOP_INPUT_ID:
        uiState.hasScoop = changed_input.value
    elif changed_input.id == BIN_HAS_TAB_INPUT_ID:
        uiState.hasTab = changed_input.value
    elif changed_input.id == BIN_TAB_LENGTH_INPUT_ID:
        uiState.tabLength = changed_input.value
    elif changed_input.id == BIN_TAB_WIDTH_INPUT_ID:
        uiState.tabWidth = changed_input.value
    elif changed_input.id == BIN_TAB_ANGLE_INPUT_ID:
        uiState.tabAngle = changed_input.value
    elif changed_input.id == BIN_TAB_POSITION_INPUT_ID:
        uiState.tabOffset = changed_input.value
    elif changed_input.id == BIN_GENERATE_BASE_INPUT_ID:
        uiState.hasBase = changed_input.value
    elif changed_input.id == BIN_SCREW_HOLES_INPUT_ID:
        uiState.hasBaseScrewHole = changed_input.value
    elif changed_input.id == BIN_SCREW_DIAMETER_INPUT:
        uiState.baseScrewHoleSize = changed_input.value
    elif changed_input.id == BIN_MAGNET_CUTOUTS_INPUT_ID:
        uiState.hasBaseMagnetSockets = changed_input.value
    elif changed_input.id == BIN_MAGNET_DIAMETER_INPUT:
        uiState.baseMagnetSocketSize = changed_input.value
    elif changed_input.id == BIN_MAGNET_HEIGHT_INPUT:
        uiState.baseMagnetSocketDepth = changed_input.value
    elif changed_input.id == PRESERVE_CHAGES_RADIO_GROUP:
        uiState.preserveChanges = changed_input.selectedItem.name == PRESERVE_CHAGES_RADIO_GROUP_PRESERVE

def cache_compartments_table_state(inputs: adsk.core.CommandInputs):
    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)
    uiState.customCompartments = []
    for i in range(1, binCompartmentsTable.rowCount):
        uiState.customCompartments.append(CompartmentTableRow(
            binCompartmentsTable.getInputAtPosition(i, 0).value,
            binCompartmentsTable.getInputAtPosition(i, 1).value,
            binCompartmentsTable.getInputAtPosition(i, 2).value,
            binCompartmentsTable.getInputAtPosition(i, 3).value,
            binCompartmentsTable.getInputAtPosition(i, 4).value,
        ))

def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    record_input_change(changed_input)
    inputs = args.inputs
    
    showPreview: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_INPUT)
    showPreviewManual: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_MANUAL_INPUT)
    wallThicknessInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_WALL_THICKNESS_INPUT_ID)
    hasScrewHolesInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCREW_HOLES_INPUT_ID)
    hasBase: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BASE_INPUT_ID)
    hasBody: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BODY_INPUT_ID)
    binTypeDropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TYPE_DROPDOWN_ID)
    hasMagnetCutoutsInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_CUTOUTS_INPUT_ID)
    magnetCutoutDiameterInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_DIAMETER_INPUT)
    magnetCutoutDepthInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_HEIGHT_INPUT)
    screwHoleDiameterInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCREW_DIAMETER_INPUT)
    withLipInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_INPUT_ID)
    withLipNotchesInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_NOTCHES_INPUT_ID)
    hasScoopInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_SCOOP_INPUT_ID)
    hasTabInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_TAB_INPUT_ID)
    tabLengthInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_LENGTH_INPUT_ID)
    tabWidthInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_WIDTH_INPUT_ID)
    tabPositionInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_ANGLE_INPUT_ID)
    tabAngleInput: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_POSITION_INPUT_ID)
    binTabFeaturesGroup: adsk.core.GroupCommandInput = inputs.itemById(BIN_TAB_FEATURES_GROUP_ID)
    binCompartmentsTable: adsk.core.TableCommandInput = inputs.itemById(BIN_COMPARTMENTS_TABLE_ID)
    binCompartmentsGridType: adsk.core.DropDownCommandInput = inputs.itemById(BIN_COMPARTMENTS_GRID_TYPE_ID)


    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    try:
        if changed_input.id in [
            BIN_BASE_WIDTH_UNIT_INPUT_ID,
            BIN_BASE_LENGTH_UNIT_INPUT_ID,
            BIN_HEIGHT_UNIT_INPUT_ID,
            BIN_XY_TOLERANCE_INPUT_ID,
            BIN_WIDTH_INPUT_ID,
            BIN_LENGTH_INPUT_ID,
            BIN_HEIGHT_INPUT_ID,
            BIN_WITH_LIP_INPUT_ID
        ]:
            actualWidth = uiState.baseWidth * uiState.binWidth - uiState.xyTolerance * 2
            actualLength = uiState.baseLength * uiState.binLength - uiState.xyTolerance * 2
            actualHeight = uiState.heightUnit * (uiState.binHeight + 1) + ((const.BIN_LIP_EXTRA_HEIGHT - const.BIN_LIP_TOP_RECESS_HEIGHT) if uiState.hasLip else 0)
            update_actual_bin_dimensions(
                staticInputCache.actualBinDimensionsTable,
                adsk.core.ValueInput.createByReal(actualWidth),
                adsk.core.ValueInput.createByReal(actualLength),
                adsk.core.ValueInput.createByReal(actualHeight),
                )
            
        elif changed_input.id in [
            BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID,
            BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID,
        ]:
            update_actual_compartment_unit_dimensions(
                staticInputCache.actualCompartmentDimensionUnitsTable,
                uiState.baseWidth,
                uiState.baseLength,
                uiState.binWidth,
                uiState.binLength,
                uiState.compartmentsGridWidth,
                uiState.compartmentsGridLength,
                uiState.binWallThickness,
                uiState.xyTolerance,
                )
            
        elif changed_input.id == BIN_TYPE_DROPDOWN_ID:
            selectedItem = binTypeDropdownInput.selectedItem.name
            if selectedItem == BIN_TYPE_HOLLOW:
                wallThicknessInput.isEnabled = True
            elif selectedItem == BIN_TYPE_SHELLED:
                wallThicknessInput.isEnabled = True
            elif selectedItem == BIN_TYPE_SOLID:
                wallThicknessInput.isEnabled = False
        elif changed_input.id == BIN_GENERATE_BASE_INPUT_ID:
            hasScrewHolesInput.isEnabled = hasBase.value
            hasMagnetCutoutsInput.isEnabled = hasBase.value
            magnetCutoutDiameterInput.isEnabled = hasBase.value
            magnetCutoutDepthInput.isEnabled = hasBase.value
            screwHoleDiameterInput.isEnabled = hasBase.value
        elif changed_input.id == BIN_GENERATE_BODY_INPUT_ID:
            wallThicknessInput.isEnabled = hasBody.value
            withLipInput.isEnabled = hasBody.value
            withLipNotchesInput.isEnabled = hasBody.value
            if not binTabFeaturesGroup == None:
                for input in binTabFeaturesGroup.children:
                    if input.id == BIN_HAS_TAB_INPUT_ID:
                        hasTabInput = input
                        input.isEnabled = hasBody.value
                    else:
                        input.isEnabled = hasBody.value and hasTabInput.value
        elif changed_input.id == BIN_WITH_LIP_INPUT_ID:
            withLipNotchesInput.isEnabled = withLipInput.value
        elif changed_input.id == BIN_HAS_TAB_INPUT_ID:
            tabLengthInput.isEnabled = hasTabInput.value
            tabWidthInput.isEnabled = hasTabInput.value
            tabPositionInput.isEnabled = hasTabInput.value
            tabAngleInput.isEnabled = hasTabInput.value
        elif changed_input.id == BIN_COMPARTMENTS_TABLE_ADD_ID:
            append_compartment_table_row(inputs, 0, 0, 1, 1, (uiState.binHeight + 1) * uiState.heightUnit - const.BIN_BASE_HEIGHT)
        elif changed_input.id == BIN_COMPARTMENTS_TABLE_REMOVE_ID:
            if binCompartmentsTable.selectedRow > 0:
                binCompartmentsTable.deleteRow(binCompartmentsTable.selectedRow)
            elif binCompartmentsTable.rowCount > 1:
                binCompartmentsTable.deleteRow(binCompartmentsTable.rowCount - 1)
        elif changed_input.id == BIN_COMPARTMENTS_TABLE_UNIFORM_ID:
            for i in range(binCompartmentsTable.rowCount - 1, 0, -1):
                binCompartmentsTable.deleteRow(i)
            for i in range(uiState.compartmentsGridWidth):
                for j in range(uiState.compartmentsGridLength):
                    append_compartment_table_row(inputs, i, j, 1, 1, (uiState.binHeight + 1) * uiState.heightUnit - const.BIN_BASE_HEIGHT)
        elif changed_input.id == BIN_COMPARTMENTS_GRID_TYPE_ID:
            showTable = binCompartmentsGridType.selectedItem.name == BIN_COMPARTMENTS_GRID_TYPE_CUSTOM
            binCompartmentsTable.isVisible = showTable
        elif changed_input.id == SHOW_PREVIEW_INPUT:
            showPreviewManual.isVisible = not showPreview.value


        if changed_input.parentCommandInput.id == BIN_COMPARTMENTS_TABLE_ID:
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
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event "{args.terminationReason}"')
    global local_handlers
    local_handlers = []
    global uiState
    if not uiState.preserveChanges and args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason:
        uiState = defaultUiState()

def generateBin(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
    base_width_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_WIDTH_UNIT_INPUT_ID)
    base_length_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_LENGTH_UNIT_INPUT_ID)
    height_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_UNIT_INPUT_ID)
    xy_tolerance: adsk.core.ValueCommandInput = inputs.itemById(BIN_XY_TOLERANCE_INPUT_ID)
    bin_width: adsk.core.ValueCommandInput = inputs.itemById(BIN_WIDTH_INPUT_ID)
    bin_length: adsk.core.ValueCommandInput = inputs.itemById(BIN_LENGTH_INPUT_ID)
    bin_height: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_INPUT_ID)
    bin_wall_thickness: adsk.core.ValueCommandInput = inputs.itemById(BIN_WALL_THICKNESS_INPUT_ID)
    bin_screw_holes: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_SCREW_HOLES_INPUT_ID)
    bin_generate_base: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BASE_INPUT_ID)
    bin_generate_body: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BODY_INPUT_ID)
    bin_magnet_cutouts: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_MAGNET_CUTOUTS_INPUT_ID)
    bin_screw_hole_diameter: adsk.core.ValueCommandInput = inputs.itemById(BIN_SCREW_DIAMETER_INPUT)
    bin_magnet_cutout_diameter: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_DIAMETER_INPUT)
    bin_magnet_cutout_depth: adsk.core.ValueCommandInput = inputs.itemById(BIN_MAGNET_HEIGHT_INPUT)
    with_lip: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_INPUT_ID)
    with_lip_notches: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_WITH_LIP_NOTCHES_INPUT_ID)
    has_scoop: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_SCOOP_INPUT_ID)
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

    isHollow = binTypeDropdownInput.selectedItem.name == BIN_TYPE_HOLLOW
    isSolid = binTypeDropdownInput.selectedItem.name == BIN_TYPE_SOLID
    isShelled = binTypeDropdownInput.selectedItem.name == BIN_TYPE_SHELLED

    # Do something interesting
    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        root = adsk.fusion.Component.cast(des.rootComponent)
        tolerance = xy_tolerance.value
        binName = 'Gridfinity bin {}x{}x{}'.format(int(bin_length.value), int(bin_width.value), int(bin_height.value))

        # create new component
        newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())
        newCmpOcc.component.name = binName
        newCmpOcc.activate()
        gridfinityBinComponent: adsk.fusion.Component = newCmpOcc.component
        features: adsk.fusion.Features = gridfinityBinComponent.features

        # create base interface
        baseGeneratorInput = BaseGeneratorInput()
        baseGeneratorInput.baseWidth = base_width_unit.value
        baseGeneratorInput.baseLength = base_length_unit.value
        baseGeneratorInput.xyTolerance = tolerance
        baseGeneratorInput.hasScrewHoles = bin_screw_holes.value and not isShelled
        baseGeneratorInput.hasMagnetCutouts = bin_magnet_cutouts.value and not isShelled
        baseGeneratorInput.screwHolesDiameter = bin_screw_hole_diameter.value
        baseGeneratorInput.magnetCutoutsDiameter = bin_magnet_cutout_diameter.value
        baseGeneratorInput.magnetCutoutsDepth = bin_magnet_cutout_depth.value

        baseBody: adsk.fusion.BRepBody
        
        if bin_generate_base.value:
            baseBody = createGridfinityBase(baseGeneratorInput, gridfinityBinComponent)
            # replicate base in rectangular pattern
            rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
            patternInputBodies = adsk.core.ObjectCollection.create()
            patternInputBodies.add(baseBody)
            patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
                gridfinityBinComponent.xConstructionAxis,
                adsk.core.ValueInput.createByReal(bin_width.value),
                adsk.core.ValueInput.createByReal(base_width_unit.value),
                adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
            patternInput.directionTwoEntity = gridfinityBinComponent.yConstructionAxis
            patternInput.quantityTwo = adsk.core.ValueInput.createByReal(bin_length.value)
            patternInput.distanceTwo = adsk.core.ValueInput.createByReal(base_length_unit.value)
            rectangularPattern = rectangularPatternFeatures.add(patternInput)


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
        binBodyInput.xyTolerance = tolerance
        binBodyInput.isSolid = isSolid or isShelled
        binBodyInput.wallThickness = bin_wall_thickness.value
        binBodyInput.hasScoop = has_scoop.value and isHollow
        binBodyInput.hasTab = hasTabInput.value and isHollow
        binBodyInput.tabLength = binTabLength.value
        binBodyInput.tabWidth = binTabWidth.value
        binBodyInput.tabPosition = binTabPosition.value
        binBodyInput.tabOverhangAngle = binTabAngle.value
        binBodyInput.compartmentsByX = compartmentsX.value
        binBodyInput.compartmentsByY = compartmentsY.value

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

        # merge everything
        if bin_generate_body.value and bin_generate_base.value:
            toolBodies = adsk.core.ObjectCollection.create()
            toolBodies.add(baseBody)
            for body in rectangularPattern.bodies:
                toolBodies.add(body)
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
                shellUtils.simpleShell([topFace], binBodyInput.wallThickness, gridfinityBinComponent)
                toolBodies = adsk.core.ObjectCollection.create()
                toolBodies.add(topBody)
                combineAfterShellFeatureInput = combineFeatures.createInput(bottomBody, toolBodies)
                combineFeatures.add(combineAfterShellFeatureInput)
                binBody = gridfinityBinComponent.bRepBodies.item(0)
            else:
                shellUtils.simpleShell([topFace], binBodyInput.wallThickness, gridfinityBinComponent)

            chamferEdge = [edge for edge in binBody.edges if geometryUtils.isHorizontal(edge)
                and math.isclose(edge.boundingBox.minPoint.z, topFaceMinPoint.z, abs_tol=const.DEFAULT_FILTER_TOLERANCE)
                and math.isclose(edge.boundingBox.minPoint.x, topFaceMinPoint.x, abs_tol=const.DEFAULT_FILTER_TOLERANCE)][0]
            if binBodyInput.hasLip and const.BIN_LIP_WALL_THICKNESS - binBodyInput.wallThickness > 0:
                chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
                chamferInput = chamferFeatures.createInput2()
                chamfer_edges = adsk.core.ObjectCollection.create()
                chamfer_edges.add(chamferEdge)
                chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
                    adsk.core.ValueInput.createByReal(const.BIN_LIP_WALL_THICKNESS - binBodyInput.wallThickness),
                    True)
                chamferFeatures.add(chamferInput)
    except:
        args.executeFailed = True
        args.executeFailedMessage = getErrorMessage()
        return False
    return True