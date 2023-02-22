import adsk.core, adsk.fusion, traceback
import os
import math




from ...lib import configUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils.const import BIN_LIP_WALL_THICKNESS, BIN_WALL_THICKNESS, BIN_XY_TOLERANCE, DEFAULT_FILTER_TOLERANCE, DIMENSION_DEFAULT_HEIGHT_UNIT, DIMENSION_DEFAULT_WIDTH_UNIT
from ...lib.gridfinityUtils import geometryUtils
from ...lib.gridfinityUtils import faceUtils
from ...lib.gridfinityUtils import shellUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils.baseGenerator import createGridfinityBase
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from ...lib.gridfinityUtils.binBodyGenerator import createGridfinityBinBody
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput

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
BIN_HEIGHT_UNIT_INPUT_ID = 'height_unit'
BIN_WIDTH_INPUT_ID = 'bin_width'
BIN_LENGTH_INPUT_ID = 'bin_length'
BIN_HEIGHT_INPUT_ID = 'bin_height'
BIN_WIDTH_INPUT_ID = 'bin_width'
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
BIN_TAB_POSITION_INPUT_ID = 'bin_tab_position'
BIN_TAB_ANGLE_INPUT_ID = 'bin_tab_angle'
BIN_WITH_LIP_INPUT_ID = 'with_lip'
BIN_TYPE_DROPDOWN_ID = 'bin_type'
BIN_TYPE_HOLLOW = 'Hollow'
BIN_TYPE_SHELLED = 'Shelled'
BIN_TYPE_SOLID = 'Solid'

BIN_TAB_FEATURES_GROUP_ID = 'bin_tab_features'

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
    basicSizesGroup = inputs.addGroupCommandInput('basic_sizes', 'Basic sizes')
    basicSizesGroup.children.addValueInput(BIN_BASE_WIDTH_UNIT_INPUT_ID, 'Base width unit', defaultLengthUnits, adsk.core.ValueInput.createByReal(DIMENSION_DEFAULT_WIDTH_UNIT))
    basicSizesGroup.children.addValueInput(BIN_HEIGHT_UNIT_INPUT_ID, 'Bin height unit', defaultLengthUnits, adsk.core.ValueInput.createByReal(DIMENSION_DEFAULT_HEIGHT_UNIT))

    binDimensionsGroup = inputs.addGroupCommandInput('bin_dimensions', 'Main dimensions')
    binDimensionsGroup.tooltipDescription = 'Set in base units'
    binDimensionsGroup.children.addValueInput(BIN_WIDTH_INPUT_ID, 'Bin width (u)', '', adsk.core.ValueInput.createByString('2'))
    binDimensionsGroup.children.addValueInput(BIN_LENGTH_INPUT_ID, 'Bin length (u)', '', adsk.core.ValueInput.createByString('3'))
    binDimensionsGroup.children.addValueInput(BIN_HEIGHT_INPUT_ID, 'Bin height (u)', '', adsk.core.ValueInput.createByString('10'))

    binFeaturesGroup = inputs.addGroupCommandInput('bin_features', 'Bin features')
    binFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BODY_INPUT_ID, 'Generate body', True, '', True)
    binTypeDropdown = binFeaturesGroup.children.addDropDownCommandInput(BIN_TYPE_DROPDOWN_ID, 'Bin type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    binTypeDropdown.listItems.add(BIN_TYPE_HOLLOW, True)
    binTypeDropdown.listItems.add(BIN_TYPE_SHELLED, False)
    binTypeDropdown.listItems.add(BIN_TYPE_SOLID, False)

    binFeaturesGroup.children.addValueInput(BIN_WALL_THICKNESS_INPUT_ID, 'Bin wall thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(BIN_WALL_THICKNESS))
    binFeaturesGroup.children.addBoolValueInput(BIN_WITH_LIP_INPUT_ID, 'Generate lip for stackability', True, '', True)
    binFeaturesGroup.children.addBoolValueInput(BIN_HAS_SCOOP_INPUT_ID, 'Add scoop', True, '', False)

    binTabFeaturesGroup = binFeaturesGroup.children.addGroupCommandInput(BIN_TAB_FEATURES_GROUP_ID, 'Label tab')
    binTabFeaturesGroup.children.addBoolValueInput(BIN_HAS_TAB_INPUT_ID, 'Add label tab', True, '', False)
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_LENGTH_INPUT_ID, 'Tab length (u)', '', adsk.core.ValueInput.createByString('1'))
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_POSITION_INPUT_ID, 'Tab offset (u)', '', adsk.core.ValueInput.createByString('0'))
    binTabFeaturesGroup.children.addValueInput(BIN_TAB_ANGLE_INPUT_ID, 'Tab overhang angle', 'deg', adsk.core.ValueInput.createByString('45'))
    for input in binTabFeaturesGroup.children:
        if not input.id == BIN_HAS_TAB_INPUT_ID:
            input.isEnabled = False

    baseFeaturesGroup = inputs.addGroupCommandInput('base_features', 'Base interface features')
    baseFeaturesGroup.children.addBoolValueInput(BIN_GENERATE_BASE_INPUT_ID, 'Generate base', True, '', True)
    baseFeaturesGroup.children.addBoolValueInput(BIN_SCREW_HOLES_INPUT_ID, 'Add screw holes', True, '', False)
    baseFeaturesGroup.children.addValueInput(BIN_SCREW_DIAMETER_INPUT, 'Screw hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_SCREW_HOLE_DIAMETER))
    baseFeaturesGroup.children.addBoolValueInput(BIN_MAGNET_CUTOUTS_INPUT_ID, 'Add magnet cutouts', True, '', False)
    baseFeaturesGroup.children.addValueInput(BIN_MAGNET_DIAMETER_INPUT, 'Magnet cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_MAGNET_CUTOUT_DIAMETER))
    baseFeaturesGroup.children.addValueInput(BIN_MAGNET_HEIGHT_INPUT, 'Magnet cutout depth', defaultLengthUnits, adsk.core.ValueInput.createByReal(const.DIMENSION_MAGNET_CUTOUT_DEPTH))
    
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

    # Get a reference to command's inputs.
    generateBin(args)

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs
    showPreview: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_INPUT)
    if showPreview.value:
        generateBin(args)


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    wallThicknessInput = inputs.itemById(BIN_WALL_THICKNESS_INPUT_ID)
    hasScrewHolesInput = inputs.itemById(BIN_SCREW_HOLES_INPUT_ID)
    hasBase: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BASE_INPUT_ID)
    hasBody: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_GENERATE_BODY_INPUT_ID)
    dropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TYPE_DROPDOWN_ID)
    hasMagnetCutoutsInput = inputs.itemById(BIN_MAGNET_CUTOUTS_INPUT_ID)
    magnetCutoutDiameterInput = inputs.itemById(BIN_MAGNET_DIAMETER_INPUT)
    magnetCutoutDepthInput = inputs.itemById(BIN_MAGNET_HEIGHT_INPUT)
    screwHoleDiameterInput = inputs.itemById(BIN_SCREW_DIAMETER_INPUT)
    withLipInput = inputs.itemById(BIN_WITH_LIP_INPUT_ID)
    hasScoopInput = inputs.itemById(BIN_HAS_SCOOP_INPUT_ID)
    hasTabInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_TAB_INPUT_ID)
    tabLengthInput = inputs.itemById(BIN_TAB_LENGTH_INPUT_ID)
    tabPositionInput = inputs.itemById(BIN_TAB_ANGLE_INPUT_ID)
    tabAngleInput = inputs.itemById(BIN_TAB_POSITION_INPUT_ID)
    binTabFeaturesGroup: adsk.core.GroupCommandInput = inputs.itemById(BIN_TAB_FEATURES_GROUP_ID)


    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    if changed_input.id == BIN_TYPE_DROPDOWN_ID:
        selectedItem = dropdownInput.selectedItem.name
        if selectedItem == BIN_TYPE_HOLLOW:
            wallThicknessInput.isEnabled = True
            hasScrewHolesInput.isEnabled = True
            hasMagnetCutoutsInput.isEnabled = True
            withLipInput.isEnabled = True
            hasScoopInput.isEnabled = True
            hasTabInput.isEnabled = True
        elif selectedItem == BIN_TYPE_SHELLED:
            wallThicknessInput.isEnabled = True
            hasScrewHolesInput.isEnabled = False
            hasMagnetCutoutsInput.isEnabled = False
            withLipInput.isEnabled = True
            hasScoopInput.isEnabled = False
            hasTabInput.isEnabled = False
        elif selectedItem == BIN_TYPE_SOLID:
            wallThicknessInput.isEnabled = False
            hasScrewHolesInput.isEnabled = True
            hasMagnetCutoutsInput.isEnabled = True
            withLipInput.isEnabled = True
            hasScoopInput.isEnabled = False
            hasTabInput.isEnabled = False
    elif changed_input.id == BIN_GENERATE_BASE_INPUT_ID:
        hasScrewHolesInput.isEnabled = hasBase.value
        hasMagnetCutoutsInput.isEnabled = hasBase.value
        magnetCutoutDiameterInput.isEnabled = hasBase.value
        magnetCutoutDepthInput.isEnabled = hasBase.value
        screwHoleDiameterInput.isEnabled = hasBase.value
    elif changed_input.id == BIN_GENERATE_BODY_INPUT_ID:
        dropdownInput.isEnabled = hasBody.value
        wallThicknessInput.isEnabled = hasBody.value
        withLipInput.isEnabled = hasBody.value
        hasScoopInput.isEnabled = hasBody.value
        binTabFeaturesGroup.isEnabled = hasBody.value
        for input in binTabFeaturesGroup.children:
            if input.id == BIN_HAS_TAB_INPUT_ID:
                hasTabInput = input
                input.isEnabled = hasBody.value
            else:
                input.isEnabled = hasBody.value and hasTabInput.value
    elif changed_input.id == BIN_HAS_TAB_INPUT_ID:
        tabLengthInput.isEnabled = hasTabInput.value
        tabPositionInput.isEnabled = hasTabInput.value
        tabAngleInput.isEnabled = hasTabInput.value


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

def generateBin(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
    base_width_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_BASE_WIDTH_UNIT_INPUT_ID)
    height_unit: adsk.core.ValueCommandInput = inputs.itemById(BIN_HEIGHT_UNIT_INPUT_ID)
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
    has_scoop: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_SCOOP_INPUT_ID)
    hasTabInput: adsk.core.BoolValueCommandInput = inputs.itemById(BIN_HAS_TAB_INPUT_ID)
    binTabLength: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_LENGTH_INPUT_ID)
    binTabPosition: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_POSITION_INPUT_ID)
    binTabAngle: adsk.core.ValueCommandInput = inputs.itemById(BIN_TAB_ANGLE_INPUT_ID)
    dropdownInput: adsk.core.DropDownCommandInput = inputs.itemById(BIN_TYPE_DROPDOWN_ID)

    isHollow = dropdownInput.selectedItem.name == BIN_TYPE_HOLLOW
    isSolid = dropdownInput.selectedItem.name == BIN_TYPE_SOLID
    isShelled = dropdownInput.selectedItem.name == BIN_TYPE_SHELLED

    # Do something interesting
    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        root = adsk.fusion.Component.cast(des.rootComponent)
        tolerance = BIN_XY_TOLERANCE
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
            patternInput.distanceTwo = adsk.core.ValueInput.createByReal(base_width_unit.value)
            rectangularPattern = rectangularPatternFeatures.add(patternInput)


        # create bin body
        binBodyInput = BinBodyGeneratorInput()
        binBodyInput.hasLip = with_lip.value
        binBodyInput.binWidth = bin_width.value
        binBodyInput.binLength = bin_length.value
        binBodyInput.binHeight = bin_height.value
        binBodyInput.baseWidth = base_width_unit.value
        binBodyInput.heightUnit = height_unit.value
        binBodyInput.xyTolerance = tolerance
        binBodyInput.isSolid = isSolid or isShelled
        binBodyInput.wallThickness = bin_wall_thickness.value
        binBodyInput.hasScoop = has_scoop.value and isHollow
        binBodyInput.hasTab = hasTabInput.value and isHollow
        binBodyInput.tabLength = binTabLength.value
        binBodyInput.tabPosition = binTabPosition.value
        binBodyInput.tabOverhangAngle = binTabAngle.value

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
                and math.isclose(edge.boundingBox.minPoint.z, topFaceMinPoint.z, abs_tol=DEFAULT_FILTER_TOLERANCE)
                and math.isclose(edge.boundingBox.minPoint.x, topFaceMinPoint.x, abs_tol=DEFAULT_FILTER_TOLERANCE)][0]
            if binBodyInput.hasLip and BIN_LIP_WALL_THICKNESS - binBodyInput.wallThickness > 0:
                chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
                chamferInput = chamferFeatures.createInput2()
                chamfer_edges = adsk.core.ObjectCollection.create()
                chamfer_edges.add(chamferEdge)
                chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
                    adsk.core.ValueInput.createByReal(BIN_LIP_WALL_THICKNESS - binBodyInput.wallThickness),
                    True)
                chamferFeatures.add(chamferInput)
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))