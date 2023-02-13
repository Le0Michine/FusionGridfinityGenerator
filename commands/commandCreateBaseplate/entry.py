import adsk.core, adsk.fusion, traceback
import os


from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils.const import BASE_TOTAL_HEIGHT, BIN_CORNER_FILLET_RADIUS, BIN_XY_TOLERANCE, DIMENSION_DEFAULT_WIDTH_UNIT
from ...lib.gridfinityUtils.baseGenerator import createGridfinityBase
from ...lib.gridfinityUtils.binBodyGenerator import chamferEdgesByLength, createBox, createGridfinityBinBody, filletEdgesByLength
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput

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

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
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
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

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

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    inputs.addValueInput('base_width_unit', 'Base width', defaultLengthUnits, adsk.core.ValueInput.createByReal(DIMENSION_DEFAULT_WIDTH_UNIT))
    inputs.addValueInput('plate_width', 'Plate width', '', adsk.core.ValueInput.createByString('2'))
    inputs.addValueInput('plate_length', 'Plate length', '', adsk.core.ValueInput.createByString('3'))

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

    # Get a reference to command's inputs.
    inputs = args.command.commandInputs
    base_width_unit: adsk.core.ValueCommandInput = inputs.itemById('base_width_unit')
    height_unit: adsk.core.ValueCommandInput = inputs.itemById('height_unit')
    plate_width: adsk.core.ValueCommandInput = inputs.itemById('plate_width')
    plate_length: adsk.core.ValueCommandInput = inputs.itemById('plate_length')

    # Do something interesting
    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        root = adsk.fusion.Component.cast(des.rootComponent)
        binName = 'Gridfinity baseplate {}x{}'.format(int(plate_length.value), int(plate_width.value))

        # create new component
        newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())

        newCmpOcc.component.name = binName
        newCmpOcc.activate()
        gridfinityBaseplateComponent: adsk.fusion.Component = newCmpOcc.component
        features: adsk.fusion.Features = gridfinityBaseplateComponent.features
        baseGeneratorInput = BaseGeneratorInput()
        baseGeneratorInput.baseWidth = base_width_unit.value
        baseGeneratorInput.xyTolerance = 0
        baseBody = createGridfinityBase(baseGeneratorInput, gridfinityBaseplateComponent)

        # replicate base in rectangular pattern
        rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
        patternInputBodies = adsk.core.ObjectCollection.create()
        patternInputBodies.add(baseBody)
        patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
            gridfinityBaseplateComponent.xConstructionAxis,
            adsk.core.ValueInput.createByReal(plate_width.value),
            adsk.core.ValueInput.createByReal(base_width_unit.value),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        patternInput.directionTwoEntity = gridfinityBaseplateComponent.yConstructionAxis
        patternInput.quantityTwo = adsk.core.ValueInput.createByReal(plate_length.value)
        patternInput.distanceTwo = adsk.core.ValueInput.createByReal(base_width_unit.value)
        rectangularPattern = rectangularPatternFeatures.add(patternInput)
        

        # create bin body
        mainBody = createBox(
            plate_width.value * base_width_unit.value,
            plate_length.value * base_width_unit.value,
            -BASE_TOTAL_HEIGHT,
            gridfinityBaseplateComponent,
            gridfinityBaseplateComponent.xYConstructionPlane,
            )

        filletEdgesByLength(
            mainBody.faces,
            BIN_CORNER_FILLET_RADIUS,
            BASE_TOTAL_HEIGHT,
            gridfinityBaseplateComponent,
            )
        
        chamferEdgesByLength(
            mainBody.endFaces,
            0.05,
            plate_length.value * base_width_unit.value,
            BIN_CORNER_FILLET_RADIUS * 3,
            gridfinityBaseplateComponent,
        )


        # cut everything
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(baseBody)
        for body in rectangularPattern.bodies:
            toolBodies.add(body)
        combineFeatures = gridfinityBaseplateComponent.features.combineFeatures
        combineFeatureInput = combineFeatures.createInput(mainBody.bodies.item(0), toolBodies)
        combineFeatureInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combineFeatures.add(combineFeatureInput)
        gridfinityBaseplateComponent.bRepBodies.item(0).name = binName
        

        
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs


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
