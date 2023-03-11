import adsk.core, adsk.fusion, traceback
import os


from ...lib import configUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils.const import DIMENSION_DEFAULT_WIDTH_UNIT
from ...lib.gridfinityUtils.baseplateGenerator import createGridfinityBaseplate
from ...lib.gridfinityUtils.baseplateGeneratorInput import BaseplateGeneratorInput
from ...lib.gridfinityUtils import const

app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBaseplate'
CMD_NAME = 'Gridfinity baseplate'
CMD_Description = 'Create gridfinity baseplate'

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

# Input ids
BASEPLATE_BASE_UNIT_WIDTH_INPUT = 'base_width_unit'
BIN_XY_TOLERANCE_INPUT_ID = 'bin_xy_tolerance'
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

BASEPLATE_EXTRA_THICKNESS_INPUT = 'extra_bottom_thickness'
BASEPLATE_BIN_Z_CLEARANCE_INPUT = 'bin_z_clearance'
BASEPLATE_HAS_CONNECTION_HOLE_INPUT = 'has_connection_hole'
BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT = 'connection_hole_diameter'

SHOW_PREVIEW_INPUT = 'show_preview'

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
    # control.isPromoted = IS_PROMOTED


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
    basicSizesGroup = inputs.addGroupCommandInput('basic_sizes', 'Basic size')
    basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_WIDTH_INPUT, 'Base width unit (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(DIMENSION_DEFAULT_WIDTH_UNIT))
    basicSizesGroup.children.addValueInput(BIN_XY_TOLERANCE_INPUT_ID, 'Bin xy tolerance (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.BIN_XY_TOLERANCE))

    mainDimensionsGroup = inputs.addGroupCommandInput('xy_dimensions', 'Main dimensions')
    mainDimensionsGroup.children.addValueInput(BASEPLATE_WIDTH_INPUT, 'Plate width (u)', '', adsk.core.ValueInput.createByString('2'))
    mainDimensionsGroup.children.addValueInput(BASEPLATE_LENGTH_INPUT, 'Plate length (u)', '', adsk.core.ValueInput.createByString('3'))

    plateFeaturesGroup = inputs.addGroupCommandInput('plate_features', 'Features')
    plateTypeDropdown = plateFeaturesGroup.children.addDropDownCommandInput(BASEPLATE_TYPE_DROPDOWN, 'Baseplate type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_LIGHT, True)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_SKELETONIZED, False)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_FULL, False)

    magnetCutoutGroup = plateFeaturesGroup.children.addGroupCommandInput('magnet_cutout_group', 'Magnet cutouts')
    magnetCutoutGroup.children.addBoolValueInput(BASEPLATE_WITH_MAGNETS_INPUT, 'Add magnet cutouts', True, '', True)
    magnetCutoutGroup.children.addValueInput(BASEPLATE_MAGNET_DIAMETER_INPUT, 'Magnet cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_MAGNET_CUTOUT_DIAMETER))
    magnetCutoutGroup.children.addValueInput(BASEPLATE_MAGNET_HEIGHT_INPUT, 'Magnet cutout depth', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_MAGNET_CUTOUT_DEPTH))

    screwHoleGroup = plateFeaturesGroup.children.addGroupCommandInput('screw_hole_group', 'Screw holes')
    screwHoleGroup.children.addBoolValueInput(BASEPLATE_WITH_SCREWS_INPUT, 'Add screw holes', True, '', True)
    screwHoleGroup.children.addValueInput(BASEPLATE_SCREW_DIAMETER_INPUT, 'Screw hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_PLATE_SCREW_HOLE_DIAMETER))
    screwHoleGroup.children.addValueInput(BASEPLATE_SCREW_HEIGHT_INPUT, 'Screw head cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_SCREW_HEAD_CUTOUT_DIAMETER))

    advancedPlateSizeGroup = plateFeaturesGroup.children.addGroupCommandInput('advanced_plate_size_group', 'Advanced plate size options')
    advancedPlateSizeGroup.children.addValueInput(BASEPLATE_EXTRA_THICKNESS_INPUT, 'Extra bottom thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.BASEPLATE_EXTRA_HEIGHT))
    advancedPlateSizeGroup.children.addValueInput(BASEPLATE_BIN_Z_CLEARANCE_INPUT, 'Clearance between baseplate and bin', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.BASEPLATE_BIN_Z_CLEARANCE))
    advancedPlateSizeGroup.children.addBoolValueInput(BASEPLATE_HAS_CONNECTION_HOLE_INPUT, 'Add connection holes',  True, '', False)
    advancedPlateSizeGroup.children.addValueInput(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT, 'Connection hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_PLATE_CONNECTION_SCREW_HOLE_DIAMETER))

    previewGroup = inputs.addGroupCommandInput('preview_group', 'Preview')
    previewGroup.children.addBoolValueInput(SHOW_PREVIEW_INPUT, 'Show preview (slow)', True, '', False)

    # TODO Connect to the events that are needed by this command.
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
        generateBaseplate(args)


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    valueInput = inputs.itemById('value_input')
    if valueInput.value >= 0:
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


def generateBaseplate(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Generating baseplate')
     # Get a reference to command's inputs.
    inputs = args.command.commandInputs
    base_width_unit: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_BASE_UNIT_WIDTH_INPUT)
    xy_tolerance: adsk.core.ValueCommandInput = inputs.itemById(BIN_XY_TOLERANCE_INPUT_ID)
    plate_width: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_WIDTH_INPUT)
    plate_length: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_LENGTH_INPUT)

    plateTypeDropdown: adsk.core.DropDownCommandInput = inputs.itemById(BASEPLATE_TYPE_DROPDOWN)
    withMagnets: adsk.core.BoolValueCommandInput = inputs.itemById(BASEPLATE_WITH_MAGNETS_INPUT)
    magnetDiameter: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_MAGNET_DIAMETER_INPUT)
    magnetHeight: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_MAGNET_HEIGHT_INPUT)

    withScrews: adsk.core.BoolValueCommandInput = inputs.itemById(BASEPLATE_WITH_SCREWS_INPUT)
    screwDiameter: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_SCREW_DIAMETER_INPUT)
    screwHeadDiameter: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_SCREW_HEIGHT_INPUT)

    extraThickness: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_EXTRA_THICKNESS_INPUT)
    binZClearance: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_BIN_Z_CLEARANCE_INPUT)
    hasConnectionHoles: adsk.core.BoolValueCommandInput = inputs.itemById(BASEPLATE_HAS_CONNECTION_HOLE_INPUT)
    connectionHoleDiameter: adsk.core.ValueCommandInput = inputs.itemById(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT)

    # Do something interesting
    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        root = adsk.fusion.Component.cast(des.rootComponent)
        baseplateName = 'Gridfinity baseplate {}x{}'.format(int(plate_length.value), int(plate_width.value))

        # create new component
        newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())

        newCmpOcc.component.name = baseplateName
        newCmpOcc.activate()
        gridfinityBaseplateComponent: adsk.fusion.Component = newCmpOcc.component
        baseplateGeneratorInput = BaseplateGeneratorInput()

        baseplateGeneratorInput.baseWidth = base_width_unit.value
        baseplateGeneratorInput.baseLength = base_width_unit.value
        baseplateGeneratorInput.baseplateWidth = plate_width.value
        baseplateGeneratorInput.baseplateLength = plate_length.value
        baseplateGeneratorInput.hasExtendedBottom = not plateTypeDropdown.selectedItem.name == BASEPLATE_TYPE_LIGHT
        baseplateGeneratorInput.hasSkeletonizedBottom = plateTypeDropdown.selectedItem.name == BASEPLATE_TYPE_SKELETONIZED
        baseplateGeneratorInput.hasMagnetCutouts = withMagnets.value
        baseplateGeneratorInput.magnetCutoutsDiameter = magnetDiameter.value
        baseplateGeneratorInput.magnetCutoutsDepth = magnetHeight.value
        baseplateGeneratorInput.hasScrewHoles = withScrews.value
        baseplateGeneratorInput.screwHolesDiameter = screwDiameter.value
        baseplateGeneratorInput.screwHeadCutoutDiameter = screwHeadDiameter.value
        baseplateGeneratorInput.binZClearance = binZClearance.value
        baseplateGeneratorInput.bottomExtensionHeight = extraThickness.value
        baseplateGeneratorInput.hasConnectionHoles = hasConnectionHoles.value
        baseplateGeneratorInput.connectionScrewHolesDiameter = connectionHoleDiameter.value
        baseplateGeneratorInput.xyTolerance = xy_tolerance.value

        baseplateBody = createGridfinityBaseplate(baseplateGeneratorInput, gridfinityBaseplateComponent)
        baseplateBody.name = baseplateName
        
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))