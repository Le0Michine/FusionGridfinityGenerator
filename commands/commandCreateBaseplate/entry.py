import adsk.core, adsk.fusion, traceback
import os



from ...lib import configUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils.const import DIMENSION_DEFAULT_WIDTH_UNIT
from ...lib.gridfinityUtils.baseplateGenerator import createGridfinityBaseplate
from ...lib.gridfinityUtils.baseplateGeneratorInput import BaseplateGeneratorInput
from ...lib.gridfinityUtils import const
from .inputState import InputState
from ...lib.ui.commandUiState import CommandUiState
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException

app = adsk.core.Application.get()
ui = app.userInterface


# The command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBaseplate'
CMD_NAME = 'Gridfinity baseplate'
CMD_Description = 'Create gridfinity baseplate'

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
BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT = 'connection_hole_diameter'

INPUT_CHANGES_SAVE_DEFAULTS = 'input_changes_buttons_save_new_defaults'
INPUT_CHANGES_RESET_TO_DEFAULTS = 'input_changes_button_reset_to_defaults'
INPUT_CHANGES_RESET_TO_FACTORY = 'input_changes_button_factory_reset'

SHOW_PREVIEW_INPUT = 'show_preview'

INFO_TEXT = ("<b>Help:</b> Info for inputs can be found "
             "<a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Baseplate-generator-options\">"
             "Here on our GitHub</a>.")

INPUTS_VALID = True

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
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')
    global uiState

    args.command.setDialogInitialSize(400, 500)

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs
    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

    infoGroup = inputs.addGroupCommandInput(INFO_GROUP, 'Info')
    infoGroup.isExpanded = uiState.getState(INFO_GROUP)
    uiState.registerCommandInput(infoGroup)
    infoGroup.children.addTextBoxCommandInput("info_text", "Info", INFO_TEXT, 3, True)

    basicSizesGroup = inputs.addGroupCommandInput(BASIC_SIZES_GROUP, 'Basic size')
    basicSizesGroup.isExpanded = uiState.getState(BASIC_SIZES_GROUP)
    uiState.registerCommandInput(basicSizesGroup)
    baseWidthUnitInput = basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_WIDTH_INPUT, 'Base width unit, X (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BASE_UNIT_WIDTH_INPUT)))
    baseWidthUnitInput.minimumValue = 1
    baseWidthUnitInput.isMinimumInclusive = True
    uiState.registerCommandInput(baseWidthUnitInput)
    baseLengthUnitInput = basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_LENGTH_INPUT, 'Base length unit, Y (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BASE_UNIT_LENGTH_INPUT)))
    baseLengthUnitInput.minimumValue = 1
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
    baseplateWidthInput = mainDimensionsGroup.children.addIntegerSpinnerCommandInput(BASEPLATE_WIDTH_INPUT, 'Plate width, X (u)', 1, 100, 1, uiState.getState(BASEPLATE_WIDTH_INPUT))
    uiState.registerCommandInput(baseplateWidthInput)
    baseplateLengthInput = mainDimensionsGroup.children.addIntegerSpinnerCommandInput(BASEPLATE_LENGTH_INPUT, 'Plate length, Y (u)', 1, 100, 1, uiState.getState(BASEPLATE_LENGTH_INPUT))
    uiState.registerCommandInput(baseplateLengthInput)

    plateFeaturesGroup = inputs.addGroupCommandInput(PLATE_FEATURES_GROUP, 'Features')
    plateFeaturesGroup.isExpanded = uiState.getState(PLATE_FEATURES_GROUP)
    uiState.registerCommandInput(plateFeaturesGroup)
    plateTypeDropdown = plateFeaturesGroup.children.addDropDownCommandInput(BASEPLATE_TYPE_DROPDOWN, 'Baseplate type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    plateTypeDropdownInitialState = uiState.getState(BASEPLATE_TYPE_DROPDOWN)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_LIGHT, plateTypeDropdownInitialState == BASEPLATE_TYPE_LIGHT)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_SKELETONIZED, plateTypeDropdownInitialState == BASEPLATE_TYPE_SKELETONIZED)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_FULL, plateTypeDropdownInitialState == BASEPLATE_TYPE_FULL)
    uiState.registerCommandInput(plateTypeDropdown)

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
    generateSidePaddingInput = sidePaddingGroup.children.addBoolValueInput(BASEPLATE_WITH_SIDE_PADDING_INPUT, 'Add padding', True, '', uiState.getState(BASEPLATE_WITH_SIDE_PADDING_INPUT))
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

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


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
            generateBaseplate(args)
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

    if isinstance(changed_input, adsk.core.GroupCommandInput) and changed_input.isExpanded == True:
        for input in changed_input.children:
            uiState.registerCommandInput(input)
        uiState.forceUIRefresh()

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
    INPUTS_VALID = inputsState.baseWidth >= 1 \
        and inputsState.baseLength >= 1 \
        and inputsState.xyClearance >= 0.01 \
        and inputsState.xyClearance <= 0.05 \
        and inputsState.plateWidth > 0 \
        and inputsState.plateLength > 0 \
        and (not inputsState.hasMagnetSockets or (inputsState.magnetSocketSize <= 1 and inputsState.magnetSocketSize > 0 and inputsState.magnetSocketDepth > 0)) \
        and (not inputsState.hasScrewHoles or (inputsState.screwHoleSize > 0 and inputsState.screwHoleSize <= 1 and inputsState.screwHeadSize > inputsState.screwHoleSize and inputsState.screwHeadSize <= 1.5)) \
        and (not inputsState.hasConnectionHoles or (inputsState.connectionHoleSize > 0 and inputsState.connectionHoleSize <= 0.5)) \
        and (inputsState.extraBottomThickness > 0)


    args.areInputsValid = INPUTS_VALID
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []
    global uiState


def generateBaseplate(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Generating baseplate')
    inputsState = getInputsState()

    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        if des.designType == 0:
            raise UnsupportedDesignTypeException('Timeline must be enabled for the generator to work, projects with disabled design history currently are not supported')
        root = adsk.fusion.Component.cast(des.rootComponent)
        baseplateName = 'Gridfinity baseplate {}x{}'.format(int(inputsState.plateLength), int(inputsState.plateWidth))

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

        baseplateGeneratorInput.baseWidth = inputsState.baseWidth
        baseplateGeneratorInput.baseLength = inputsState.baseLength
        baseplateGeneratorInput.xyClearance = inputsState.xyClearance
        baseplateGeneratorInput.baseplateWidth = inputsState.plateWidth
        baseplateGeneratorInput.baseplateLength = inputsState.plateLength
        baseplateGeneratorInput.hasExtendedBottom = not inputsState.plateType == BASEPLATE_TYPE_LIGHT
        baseplateGeneratorInput.hasSkeletonizedBottom = inputsState.plateType == BASEPLATE_TYPE_SKELETONIZED
        baseplateGeneratorInput.hasMagnetCutouts = inputsState.hasMagnetSockets
        baseplateGeneratorInput.magnetCutoutsDiameter = inputsState.magnetSocketSize
        baseplateGeneratorInput.magnetCutoutsDepth = inputsState.magnetSocketDepth
        baseplateGeneratorInput.hasScrewHoles = inputsState.hasScrewHoles
        baseplateGeneratorInput.screwHolesDiameter = inputsState.screwHoleSize
        baseplateGeneratorInput.screwHeadCutoutDiameter = inputsState.screwHeadSize
        baseplateGeneratorInput.hasPadding = inputsState.hasPadding
        baseplateGeneratorInput.paddingLeft = inputsState.paddingLeft
        baseplateGeneratorInput.paddingTop = inputsState.paddingTop
        baseplateGeneratorInput.paddingRight = inputsState.paddingRight
        baseplateGeneratorInput.paddingBottom = inputsState.paddingBottom
        baseplateGeneratorInput.bottomExtensionHeight = inputsState.extraBottomThickness
        baseplateGeneratorInput.binZClearance = inputsState.verticalClearance
        baseplateGeneratorInput.hasConnectionHoles = inputsState.hasConnectionHoles
        baseplateGeneratorInput.connectionScrewHolesDiameter = inputsState.connectionHoleSize
        baseplateGeneratorInput.cornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS

        baseplateBody = createGridfinityBaseplate(baseplateGeneratorInput, gridfinityBaseplateComponent)
        baseplateBody.name = baseplateName

        if des.designType == adsk.fusion.DesignTypes.ParametricDesignType:
            # group features in timeline
            plateGroup = des.timeline.timelineGroups.add(originalTimelineCount, des.timeline.count - 1)
            plateGroup.name = baseplateName
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
    )