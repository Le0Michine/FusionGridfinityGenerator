import adsk.core, adsk.fusion
import dataclasses
import math
import os
import re
from typing import Callable

from ...lib import tagUtils
from ...lib import labelFaces
from ...lib import threeMf
from ...lib import stlFile
from ...lib import bedPacking
from ...lib import printBeds
from ...lib import configUtils
from ...lib import fusion360utils as futil
from ...lib.ui import browserPages
from ...lib.gridfinityUtils import labelGenerator
from ...lib.gridfinityUtils import compartmentLayout
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdExport'
CMD_NAME = 'Gridfinity export'
CMD_Description = 'Export bins and baseplates for printing, 3MF with the label letters in a color of their own, or STL and STEP files'
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')
# in the context menu after Fusion's Save As Mesh
SAVE_AS_MESH_COMMAND_ID = 'FusionSaveAsSTLCommand'

ALL_INPUT_ID = 'export_all'
SELECTION_INPUT_ID = 'export_bodies'
FORMAT_INPUT_ID = 'export_format'
PAINT_INPUT_ID = 'export_paint_labels'
FILAMENT_INPUT_ID = 'export_filament'
FOLDER_INPUT_ID = 'export_folder'
BROWSE_INPUT_ID = 'export_browse'
FILE_NAME_INPUT_ID = 'export_file_name'
ARRANGE_INPUT_ID = 'export_arrange'
BED_PRESET_INPUT_ID = 'export_bed_preset'
BED_WIDTH_INPUT_ID = 'export_bed_width'
BED_LENGTH_INPUT_ID = 'export_bed_length'
SPACING_INPUT_ID = 'export_spacing'
MARGIN_INPUT_ID = 'export_margin'
PURGE_INPUT_ID = 'export_purge'
KEEP_PURGE_INPUT_ID = 'export_keep_purge'
FILES_INPUT_ID = 'export_files'
PLATES_INPUT_ID = 'export_plates'
PLATES_HTML_URL = browserPages.pageUrl(__file__, 'plates.html')
SUMMARY_INPUT_ID = 'export_summary'

FORMAT_3MF = '3MF'
FORMAT_STL = 'STL'
FORMAT_STEP = 'STEP'
FORMATS = [FORMAT_3MF, FORMAT_STL, FORMAT_STEP]
FORMAT_EXTENSIONS = {FORMAT_3MF: '3mf', FORMAT_STL: 'stl', FORMAT_STEP: 'step'}
ARRANGE_PACKED = 'Packed on print beds'
ARRANGE_AS_PLACED = 'As placed in the design'
ARRANGEMENTS = [ARRANGE_PACKED, ARRANGE_AS_PLACED]
FILES_ONE = 'One file with all plates'
FILES_PER_PLATE = 'A file per plate'
FILES_CHOICES = [FILES_ONE, FILES_PER_PLATE]
# files named in the question whether to replace them, the rest counted
MAX_LISTED_FILES = 8
# the 3MF file of more than one body
DEFAULT_FILE_NAME = 'Gridfinity bins'
# the 3MF and STL meshes, finer than the STL export's high refinement, which the calculator can't be set to
MESH_QUALITY = adsk.fusion.TriangleMeshQualityOptions.VeryHighQualityTriangleMesh
# cm, a mesh triangle this close to the plane of a letter face can lie on it
PAINT_TOLERANCE = 1e-4

# the dialog's last choices, kept for the next time Fusion runs
CONFIG_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'commandConfig')
CONFIG_SECTION = 'Export'
DEFAULT_FILAMENT = 2
DEFAULT_BED = printBeds.presetLabel('Prusa CORE One')
# mm, between the bodies packed on a bed
DEFAULT_SPACING = 1.0
MIN_SPACING = 0.5
MAX_SPACING = 50.0
SPACING_STEP = 0.5
# mm, kept clear along the bed's edges
DEFAULT_MARGIN = 5.0
# mm, the side of the square kept free for the purge tower when label text is colored, Bambu's tower is 35 mm wide,
# the rest is room for its brim and for moving it
DEFAULT_PURGE = 50.0

# the folder chosen in the dialog open now, and whether its file name was typed or still follows the bodies
dialogFolder = ''
isFileNameTyped = False
# a preset's width alone doesn't match it yet, so its change mustn't switch to custom
isApplyingBedPreset = False
# the purge tower checkbox follows whether label text is colored until it's set by hand, its value set by the dialog
# fires a change too
isKeepPurgeSet = False
isApplyingKeepPurge = False

local_handlers = []
markingMenuHandler = None
# starting a command can clear the selection, so what was selected when the menu opened is kept
menuEntities = []

@dataclasses.dataclass
class ExportItem:
    # native, the occurrence places it
    body: adsk.fusion.BRepBody
    occurrence: adsk.fusion.Occurrence | None

    @property
    def hasOutlineLabels(self) -> bool:
        """Bins built before the label styles had outline labels only"""
        tag = tagUtils.readBodyTag(self.body)
        if tag is None or tag[0] != tagUtils.TAG_BIN:
            return False
        settings = tag[1].get('config')
        style = settings.get('labelStyle', labelGenerator.LABEL_STYLE_OUTLINE) if isinstance(settings, dict) else labelGenerator.LABEL_STYLE_OUTLINE
        return style == labelGenerator.LABEL_STYLE_OUTLINE

    @property
    def hasLabelText(self) -> bool:
        """A bin built with outline labels on its tab, text or an icon, its own or a compartment's"""
        if not self.hasOutlineLabels:
            return False
        settings = tagUtils.readBodyTag(self.body)[1].get('config')
        if not isinstance(settings, dict) or not settings.get('hasTab'):
            return False
        if str(settings.get('labelText', '')).strip() or settings.get('labelIcon', labelGenerator.LABEL_ICON_NONE) != labelGenerator.LABEL_ICON_NONE:
            return True
        pockets = settings.get('compartmentPockets')
        return isinstance(pockets, list) and any(
            isinstance(pocket, dict) and (str(pocket.get('label', '')).strip() or pocket.get('icon', compartmentLayout.DEFAULT_ICON) not in (compartmentLayout.DEFAULT_ICON, labelGenerator.LABEL_ICON_NONE))
            for pocket in pockets
        )

    @property
    def isGridfinity(self) -> bool:
        return tagUtils.readBodyTag(self.body) is not None

@dataclasses.dataclass
class Beds:
    # mm
    size: tuple[float, float]
    # mm between the bodies, none puts them as placed in the design around the middle of one bed
    spacing: float | None
    # mm kept clear along the bed's edges, packed only
    margin: float = 0.0
    # mm, x0, y0, x1, y1 on the bed, the areas the printer keeps free and the purge tower's square, packed only
    excluded: list[tuple[float, float, float, float]] = dataclasses.field(default_factory=list)
    purge: tuple[float, float, float, float] | None = None
    # a 3MF file of each plate instead of one with all of them
    perPlate: bool = False

    def kept(self) -> list[tuple[float, float, float, float]]:
        return self.excluded + ([self.purge] if self.purge is not None else [])

@dataclasses.dataclass
class ExportOptions:
    """What the dialog chooses, for exportBodies, see savedOptions for the dialog's last choices"""
    format: str = FORMAT_3MF
    # the 3MF file's, empty after the body for one body
    fileName: str = ''
    # label text of the bins in a filament of its own, 3MF only
    paint: bool = True
    filament: int = DEFAULT_FILAMENT
    # packed on print beds, or as placed in the design
    packed: bool = True
    # a printer of the dialog's list, by its name or label, or custom with the bed size
    printer: str = DEFAULT_BED
    # mm, none for the printer's
    bedSize: tuple[float, float] | None = None
    spacing: float = DEFAULT_SPACING
    margin: float = DEFAULT_MARGIN
    # room for the purge tower on each plate, none when bins have label text to color
    purgeTower: bool | None = None
    purgeSize: float = DEFAULT_PURGE
    # a 3MF file of each plate
    perPlate: bool = False
    # files there already are replaced, else the export fails
    overwrite: bool = False

@dataclasses.dataclass
class ExportResult:
    paths: list[str]
    bodies: int
    # bodies with painted letters, 3MF only
    painted: int = 0
    plates: int = 1
    # names of the bodies bigger than the bed
    tooBig: list[str] = dataclasses.field(default_factory=list)
    # plates, from 0, where a body is on an area kept free
    notClear: list[int] = dataclasses.field(default_factory=list)

# whether the files there already may be replaced, and how far the export got, done of all
MayWrite = Callable[[list[str]], bool]
Progress = Callable[[int, int], None]

def start():
    global markingMenuHandler
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)
    markingMenuHandler = futil.add_handler(ui.markingMenuDisplaying, marking_menu_displaying, local_handlers=local_handlers)

def stop():
    global markingMenuHandler
    if markingMenuHandler is not None:
        ui.markingMenuDisplaying.remove(markingMenuHandler)
        markingMenuHandler = None
    command_definition = ui.commandDefinitions.itemById(CMD_ID)
    if command_definition:
        command_definition.deleteMe()

def selectionEntities(selected: list) -> list:
    """A face stands for its body"""
    entities = []
    for entity in selected:
        face = adsk.fusion.BRepFace.cast(entity)
        entity = face.body if face is not None else entity
        if entity not in entities:
            entities.append(entity)
    return entities

def isTagged(entity) -> bool:
    """
    A generated body, or an occurrence or component with one among its bodies or those of the occurrences in it. The
    browser's root is a component, the others are occurrences
    """
    body = adsk.fusion.BRepBody.cast(entity)
    if body is not None:
        return tagUtils.readBodyTag(body.nativeObject if body.assemblyContext is not None else body) is not None
    occurrence = adsk.fusion.Occurrence.cast(entity)
    if occurrence is not None:
        return isTagged(occurrence.component)
    component = adsk.fusion.Component.cast(entity)
    if component is None:
        return False
    return any(tagUtils.readBodyTag(body) is not None for body in component.bRepBodies) \
        or any(isTagged(child.component) for child in component.occurrences)

def isGridfinityBody(body: adsk.fusion.BRepBody) -> bool:
    """A visible bin or baseplate, the body where it's placed or its native one"""
    native = body.nativeObject if body.assemblyContext is not None else body
    return body.isVisible and tagUtils.readBodyTag(native) is not None

def occurrenceBodies(occurrence: adsk.fusion.Occurrence) -> list[adsk.fusion.BRepBody]:
    """Its visible bins and baseplates and those of the occurrences in it, where they're placed"""
    bodies = [body for body in occurrence.bRepBodies if isGridfinityBody(body)]
    for child in occurrence.childOccurrences:
        bodies += occurrenceBodies(child)
    return bodies

def menuSelection(design: adsk.fusion.Design) -> list[adsk.fusion.BRepBody]:
    """
    The bodies the dialog starts with selected, the visible bins and baseplates of a component or occurrence in its
    place, so the selection counts bodies only. Bodies picked themselves stay, whatever they are
    """
    bodies = []
    for entity in menuEntities:
        if not entity.isValid:
            continue
        body = adsk.fusion.BRepBody.cast(entity)
        occurrence = adsk.fusion.Occurrence.cast(entity)
        component = adsk.fusion.Component.cast(entity)
        if body is not None:
            bodies.append(body)
        elif occurrence is not None:
            bodies += occurrenceBodies(occurrence)
        elif component is not None and design is not None:
            for placed in design.rootComponent.allOccurrencesByComponent(component):
                bodies += occurrenceBodies(placed)
    return bodies

def isRootSelected(design: adsk.fusion.Design) -> bool:
    return design is not None and any(entity.isValid and entity == design.rootComponent for entity in menuEntities)

def marking_menu_displaying(args: adsk.core.MarkingMenuEventArgs):
    """After Save As Mesh, or last, when anything selected is a bin or baseplate or holds one"""
    global menuEntities
    try:
        menuEntities = selectionEntities(args.selectedEntities or [])
        if not any(isTagged(entity) for entity in menuEntities):
            return
        controls = args.linearMarkingMenu.controls
        commandDefinition = ui.commandDefinitions.itemById(CMD_ID)
        saveAsMesh = controls.itemById(SAVE_AS_MESH_COMMAND_ID)
        if saveAsMesh is None:
            # a menu without Save As Mesh
            controls.addCommand(commandDefinition)
            return
        control = controls.addCommand(commandDefinition, SAVE_AS_MESH_COMMAND_ID, False)
        if not saveAsMesh.isVisible:
            # the menu of a face keeps Save As Mesh hidden and the separator before it too, which would join the export
            # to Properties above
            controls.addSeparator('', control.id, True)
    except Exception as err:
        futil.log(f'{CMD_NAME} context menu failed, {err}')

def readChoices() -> dict:
    """The dialog's last choices, the Downloads folder the first time"""
    addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)
    section = addinConfig[CONFIG_SECTION] if addinConfig.has_section(CONFIG_SECTION) else {}
    folder = section.get('folder', '')
    if not os.path.isdir(folder):
        downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
        folder = downloads if os.path.isdir(downloads) else os.path.expanduser('~')
    format = section.get('format', FORMAT_3MF)
    try:
        filament = min(max(int(section.get('colorIndex', DEFAULT_FILAMENT)), 1), threeMf.MAX_FILAMENT)
    except ValueError:
        filament = DEFAULT_FILAMENT
    arrange = section.get('arrange', ARRANGE_PACKED)
    files = section.get('files', FILES_ONE)
    bed = section.get('bed', DEFAULT_BED)
    (presetWidth, presetLength) = printBeds.PRINT_BED_PRESETS.get(bed, printBeds.PRINT_BED_PRESETS[DEFAULT_BED])
    def number(key: str, default: float, isZeroKept: bool = False) -> float:
        try:
            value = float(section.get(key, default))
        except ValueError:
            return default
        return value if value > 0 or (isZeroKept and value == 0) else default
    return {
        'folder': folder,
        'format': format if format in FORMATS else FORMAT_3MF,
        'paint': section.get('paint', 'yes') != 'no',
        'filament': filament,
        'arrange': arrange if arrange in ARRANGEMENTS else ARRANGE_PACKED,
        # a preset gone from the list since keeps its size as custom
        'bed': bed if bed in printBeds.PRINT_BED_PRESETS else printBeds.PRINT_BED_CUSTOM,
        'bedWidth': number('bedWidth', presetWidth),
        'bedLength': number('bedLength', presetLength),
        'spacing': min(max(number('spacing', DEFAULT_SPACING), MIN_SPACING), MAX_SPACING),
        'margin': number('margin', DEFAULT_MARGIN, True),
        'purge': number('purge', DEFAULT_PURGE, True),
        'files': files if files in FILES_CHOICES else FILES_ONE,
    }

def saveChoices(folder: str, format: str, paint: bool, filament: int, arrange: str, bed: str, beds: Beds, purge: float, files: str):
    addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)
    previous = addinConfig[CONFIG_SECTION] if addinConfig.has_section(CONFIG_SECTION) else {}
    addinConfig[CONFIG_SECTION] = {
        'folder': folder,
        'format': format,
        'paint': 'yes' if paint else 'no',
        'colorIndex': str(filament),
        'arrange': arrange,
        'bed': bed,
        'bedWidth': f'{beds.size[0]:g}',
        'bedLength': f'{beds.size[1]:g}',
        # kept while the bodies go as placed
        'spacing': f'{beds.spacing:g}' if beds.spacing is not None else previous.get('spacing', f'{DEFAULT_SPACING:g}'),
        'margin': f'{beds.margin:g}' if beds.spacing is not None else previous.get('margin', f'{DEFAULT_MARGIN:g}'),
        'purge': f'{purge:g}',
        'files': files,
    }
    if not configUtils.writeConfig(addinConfig, CONFIG_FOLDER_PATH):
        futil.log(f'{CMD_NAME} choices not saved to {CONFIG_FOLDER_PATH}')

def command_created(args: adsk.core.CommandCreatedEventArgs):
    global dialogFolder, isFileNameTyped, isKeepPurgeSet
    command = args.command
    inputs = command.commandInputs
    choices = readChoices()
    dialogFolder = choices['folder']
    isFileNameTyped = False
    isKeepPurgeSet = False
    design = adsk.fusion.Design.cast(app.activeProduct)
    # the whole design when its root was picked
    allInput = inputs.addBoolValueInput(ALL_INPUT_ID, 'All Gridfinity bodies', True, '', isRootSelected(design))
    allInput.tooltip = 'Selects all visible bins and baseplates'
    selectionInput = inputs.addSelectionInput(SELECTION_INPUT_ID, 'Bodies', 'Bins and baseplates')
    # bodies only, Fusion puts a selected component in too as the command starts, beside its bodies
    selectionInput.addSelectionFilter(adsk.core.SelectionCommandInput.SolidBodies)
    selectionInput.setSelectionLimits(0, 0)
    selectAll(inputs, allInput.value)
    formatInput = inputs.addDropDownCommandInput(FORMAT_INPUT_ID, 'Format', adsk.core.DropDownStyles.TextListDropDownStyle)
    for name in FORMATS:
        formatInput.listItems.add(name, name == choices['format'])
    formatInput.tooltip = 'Export file format'
    folderInput = inputs.addTextBoxCommandInput(FOLDER_INPUT_ID, 'Folder', dialogFolder, 2, True)
    folderInput.tooltip = 'Where the files go, the last folder chosen is kept'
    browseInput = inputs.addBoolValueInput(BROWSE_INPUT_ID, '', False, '', False)
    browseInput.text = 'Choose folder...'
    fileNameInput = inputs.addStringValueInput(FILE_NAME_INPUT_ID, 'File name', '')
    fileNameInput.tooltip = 'Export file name'
    arrangeInput = inputs.addDropDownCommandInput(ARRANGE_INPUT_ID, 'Arrange', adsk.core.DropDownStyles.TextListDropDownStyle)
    for name in ARRANGEMENTS:
        arrangeInput.listItems.add(name, name == choices['arrange'])
    arrangeInput.tooltip = 'Keep design arrangement or split by print plates'
    bedInput = inputs.addDropDownCommandInput(BED_PRESET_INPUT_ID, 'Printer', adsk.core.DropDownStyles.TextListDropDownStyle)
    for name in [printBeds.PRINT_BED_CUSTOM] + list(printBeds.PRINT_BED_PRESETS.keys()):
        bedInput.listItems.add(name, name == choices['bed'])
    bedInput.tooltip = 'The bed size the plates are filled to'
    units = design.unitsManager.defaultLengthUnits if design is not None else 'mm'
    for (inputId, name, value) in ((BED_WIDTH_INPUT_ID, 'Bed width, X', choices['bedWidth']), (BED_LENGTH_INPUT_ID, 'Bed length, Y', choices['bedLength'])):
        bedSizeInput = inputs.addValueInput(inputId, name, units, adsk.core.ValueInput.createByReal(value / 10))
        bedSizeInput.minimumValue = 0
        bedSizeInput.isMinimumInclusive = False
    # a number of mm whatever the design's units, it steps by half a millimeter
    spacingInput = inputs.addFloatSpinnerCommandInput(SPACING_INPUT_ID, 'Spacing (mm)', '', MIN_SPACING, MAX_SPACING, SPACING_STEP, choices['spacing'])
    spacingInput.tooltip = 'The space between bodies packed on a plate'
    marginInput = inputs.addValueInput(MARGIN_INPUT_ID, 'Bed margin', units, adsk.core.ValueInput.createByReal(choices['margin'] / 10))
    marginInput.minimumValue = 0
    marginInput.tooltip = 'The space kept clear along every edge of the bed'
    keepPurgeInput = inputs.addBoolValueInput(KEEP_PURGE_INPUT_ID, 'Purge tower', True, '', False)
    keepPurgeInput.tooltip = 'Leave room for the purge tower'
    purgeInput = inputs.addValueInput(PURGE_INPUT_ID, 'Purge tower area', units, adsk.core.ValueInput.createByReal(choices['purge'] / 10))
    purgeInput.minimumValue = 0
    purgeInput.isMinimumInclusive = False
    purgeInput.tooltip = 'The side of the square kept free for the purge tower'
    filesInput = inputs.addDropDownCommandInput(FILES_INPUT_ID, '3MF files', adsk.core.DropDownStyles.TextListDropDownStyle)
    for name in FILES_CHOICES:
        filesInput.listItems.add(name, name == choices['files'])
    filesInput.tooltip = '1 file for everything or 1 file for each plate'
    inputs.addBrowserCommandInput(PLATES_INPUT_ID, '', PLATES_HTML_URL, 240, 240)
    paintInput = inputs.addBoolValueInput(PAINT_INPUT_ID, 'Color text', True, '', choices['paint'])
    paintInput.tooltip = 'Assign different color to use on text'
    filamentInput = inputs.addIntegerSpinnerCommandInput(FILAMENT_INPUT_ID, 'Label color index', 1, threeMf.MAX_FILAMENT, 1, choices['filament'])
    filamentInput.tooltip = 'Pick color/extruder index to be used for text on labels'
    inputs.addTextBoxCommandInput(SUMMARY_INPUT_ID, '', '', 2, True)
    # as wide as the bin dialog, the minimum widens one Fusion kept narrower from before
    command.setDialogInitialSize(450, 400)
    command.setDialogMinimumSize(450, 300)
    updateInputs(inputs)
    futil.add_handler(command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(command.incomingFromHTML, command_incoming_from_html, local_handlers=local_handlers)
    futil.add_handler(command.destroy, command_destroy, local_handlers=local_handlers)

def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global dialogFolder, isFileNameTyped, isApplyingBedPreset, isKeepPurgeSet
    if args.input.id == KEEP_PURGE_INPUT_ID and not isApplyingKeepPurge:
        isKeepPurgeSet = True
    if args.input.id == ALL_INPUT_ID:
        selectAll(args.inputs, adsk.core.BoolValueCommandInput.cast(args.input).value)
    elif args.input.id == BROWSE_INPUT_ID:
        folder = askFolder(dialogFolder)
        if folder is not None:
            dialogFolder = folder
            adsk.core.TextBoxCommandInput.cast(args.inputs.itemById(FOLDER_INPUT_ID)).text = folder
    elif args.input.id == FILE_NAME_INPUT_ID:
        isFileNameTyped = True
        updateInputs(args.inputs)
        return
    elif args.input.id == BED_PRESET_INPUT_ID:
        size = printBeds.presetBedSize(adsk.core.DropDownCommandInput.cast(args.input).selectedItem.name)
        if size is not None:
            isApplyingBedPreset = True
            try:
                adsk.core.ValueCommandInput.cast(args.inputs.itemById(BED_WIDTH_INPUT_ID)).value = size[0]
                adsk.core.ValueCommandInput.cast(args.inputs.itemById(BED_LENGTH_INPUT_ID)).value = size[1]
            finally:
                isApplyingBedPreset = False
    elif args.input.id in (BED_WIDTH_INPUT_ID, BED_LENGTH_INPUT_ID) and not isApplyingBedPreset:
        # a bed size edited by hand no longer is the preset's
        bedInput = adsk.core.DropDownCommandInput.cast(args.inputs.itemById(BED_PRESET_INPUT_ID))
        size = printBeds.presetBedSize(bedInput.selectedItem.name)
        if size is not None and not all(math.isclose(mm, cm * 10) for (mm, cm) in zip(dialogBeds(args.inputs).size, size)):
            bedInput.listItems.item(0).isSelected = True
    updateInputs(args.inputs)
    if args.input.id not in (ALL_INPUT_ID, SELECTION_INPUT_ID):
        # kept as soon as they change, a cancelled dialog too
        saveDialogChoices(args.inputs, dialogFolder)

def command_incoming_from_html(args: adsk.core.HTMLEventArgs):
    """The plates drawing asks for its data once loaded"""
    inputs = args.browserCommandInput.parentCommand.commandInputs
    browserPages.handleMessage(args, {browserPages.READY: lambda _: platesData(exportItems(inputs), dialogBeds(inputs))})

def selectAll(inputs: adsk.core.CommandInputs, isAll: bool):
    """Every visible bin and baseplate in the selection, or what was selected as the dialog opened"""
    selectionInput = adsk.core.SelectionCommandInput.cast(inputs.itemById(SELECTION_INPUT_ID))
    selectionInput.clearSelection()
    design = adsk.fusion.Design.cast(app.activeProduct)
    entities = gridfinityBodies(design) if isAll and design is not None else menuSelection(design)
    for entity in entities:
        selectionInput.addSelection(entity)

def gridfinityBodies(design: adsk.fusion.Design) -> list[adsk.fusion.BRepBody]:
    """The visible bins and baseplates where they're placed, those of a component in each of its occurrences"""
    root = design.rootComponent
    bodies = []
    for tagName in (tagUtils.TAG_BIN, tagUtils.TAG_BASEPLATE):
        for (body, _) in tagUtils.findTaggedBodies(design, tagName):
            component = body.parentComponent
            if component == root:
                placed = [body]
            else:
                placed = [body.createForAssemblyContext(occurrence) for occurrence in root.allOccurrencesByComponent(component)]
            bodies += [placedBody for placedBody in placed if placedBody.isVisible]
    return bodies

def selectedFormat(inputs: adsk.core.CommandInputs) -> str:
    return adsk.core.DropDownCommandInput.cast(inputs.itemById(FORMAT_INPUT_ID)).selectedItem.name

def selectedArrangement(inputs: adsk.core.CommandInputs) -> str:
    return adsk.core.DropDownCommandInput.cast(inputs.itemById(ARRANGE_INPUT_ID)).selectedItem.name

def dialogOptions(inputs: adsk.core.CommandInputs) -> ExportOptions:
    """What the dialog has chosen, lengths in mm rounded off the cm Fusion keeps them in"""
    def mm(inputId: str) -> float:
        if inputId == SPACING_INPUT_ID:
            return round(adsk.core.FloatSpinnerCommandInput.cast(inputs.itemById(inputId)).value, 6)
        return round(adsk.core.ValueCommandInput.cast(inputs.itemById(inputId)).value * 10, 6)
    return ExportOptions(
        format=selectedFormat(inputs),
        fileName=adsk.core.StringValueCommandInput.cast(inputs.itemById(FILE_NAME_INPUT_ID)).value,
        paint=adsk.core.BoolValueCommandInput.cast(inputs.itemById(PAINT_INPUT_ID)).value,
        filament=adsk.core.IntegerSpinnerCommandInput.cast(inputs.itemById(FILAMENT_INPUT_ID)).value,
        packed=selectedArrangement(inputs) == ARRANGE_PACKED,
        printer=adsk.core.DropDownCommandInput.cast(inputs.itemById(BED_PRESET_INPUT_ID)).selectedItem.name,
        bedSize=(mm(BED_WIDTH_INPUT_ID), mm(BED_LENGTH_INPUT_ID)),
        spacing=mm(SPACING_INPUT_ID),
        margin=mm(MARGIN_INPUT_ID),
        purgeTower=adsk.core.BoolValueCommandInput.cast(inputs.itemById(KEEP_PURGE_INPUT_ID)).value,
        purgeSize=mm(PURGE_INPUT_ID),
        perPlate=adsk.core.DropDownCommandInput.cast(inputs.itemById(FILES_INPUT_ID)).selectedItem.name == FILES_PER_PLATE,
    )

def dialogBeds(inputs: adsk.core.CommandInputs) -> Beds:
    return bedsOf(dialogOptions(inputs), [])

def bedsOf(options: ExportOptions, items: list['ExportItem']) -> Beds:
    """The beds of the options, the purge tower's room when bins of the items have label text to color unless told"""
    label = printBeds.presetLabelOf(options.printer)
    size = options.bedSize or (printBeds.PRINT_BED_PRESETS.get(label) if label is not None else None)
    if size is None:
        raise ValueError(f'unknown printer {options.printer!r}, give its bed size')
    size = (float(size[0]), float(size[1]))
    if not options.packed:
        return Beds(size, None)
    isPurgeKept = options.purgeTower if options.purgeTower is not None else options.paint and any(item.hasLabelText for item in items)
    purge = printBeds.purgeSquare(size, options.purgeSize, printBeds.purgeAnchor(label or '')) if isPurgeKept else None
    return Beds(size, options.spacing, options.margin, printBeds.excludedAreas(label or ''), purge, options.perPlate)

def updateInputs(inputs: adsk.core.CommandInputs):
    """Painting and arranging are for 3MF only, the summary says what goes out"""
    global isApplyingKeepPurge
    format = selectedFormat(inputs)
    for inputId in (ARRANGE_INPUT_ID, BED_PRESET_INPUT_ID, BED_WIDTH_INPUT_ID, BED_LENGTH_INPUT_ID, PLATES_INPUT_ID):
        inputs.itemById(inputId).isVisible = format == FORMAT_3MF
    isPacked = format == FORMAT_3MF and selectedArrangement(inputs) == ARRANGE_PACKED
    for inputId in (SPACING_INPUT_ID, MARGIN_INPUT_ID, FILES_INPUT_ID):
        inputs.itemById(inputId).isVisible = isPacked
    paintInput = adsk.core.BoolValueCommandInput.cast(inputs.itemById(PAINT_INPUT_ID))
    paintInput.isVisible = format == FORMAT_3MF
    keepPurgeInput = adsk.core.BoolValueCommandInput.cast(inputs.itemById(KEEP_PURGE_INPUT_ID))
    keepPurgeInput.isVisible = isPacked
    inputs.itemById(PURGE_INPUT_ID).isVisible = isPacked and keepPurgeInput.value
    inputs.itemById(FILAMENT_INPUT_ID).isVisible = format == FORMAT_3MF and paintInput.value
    fileNameInput = adsk.core.StringValueCommandInput.cast(inputs.itemById(FILE_NAME_INPUT_ID))
    fileNameInput.isVisible = format == FORMAT_3MF
    try:
        items = exportItems(inputs)
        if not isKeepPurgeSet:
            # the slicer adds a purge tower to print the label text in its color
            isKeepPurge = paintInput.value and any(item.hasLabelText for item in items)
            if keepPurgeInput.value != isKeepPurge:
                isApplyingKeepPurge = True
                try:
                    keepPurgeInput.value = isKeepPurge
                finally:
                    isApplyingKeepPurge = False
            inputs.itemById(PURGE_INPUT_ID).isVisible = isPacked and keepPurgeInput.value
        if not isFileNameTyped:
            fileNameInput.value = defaultFileName(items)
        # the files OK writes, the drawing tells the bodies and plates
        extension = FORMAT_EXTENSIONS[format]
        if format == FORMAT_3MF:
            plates = platesData(items, dialogBeds(inputs))
            browserPages.sendUpdate(inputs.itemById(PLATES_INPUT_ID), plates)
            count = len(plates.get('plates', []))
            fileName = safeFileName(fileNameInput.value) or defaultFileName(items)
            fileName = fileName if fileName.lower().endswith('.3mf') else f'{fileName}.3mf'
            summary = f'Writes {count} files, one per plate' if dialogBeds(inputs).perPlate and count > 1 else f'Writes {fileName}'
        elif len(items) == 1:
            summary = f'Writes {fileNames(items)[0]}.{extension}'
        else:
            summary = f'Writes {len(items)} {format} files, one per body'
        summary = summary if items else 'Select bodies to export'
    except Exception as err:
        summary = f'Bodies not found, {err}'
    adsk.core.TextBoxCommandInput.cast(inputs.itemById(SUMMARY_INPUT_ID)).text = summary

def selectedEntities(inputs: adsk.core.CommandInputs) -> list:
    selectionInput = adsk.core.SelectionCommandInput.cast(inputs.itemById(SELECTION_INPUT_ID))
    return [selectionInput.selection(index).entity for index in range(selectionInput.selectionCount)]

def exportItems(inputs: adsk.core.CommandInputs) -> list[ExportItem]:
    return itemsOf(selectedEntities(inputs))

def itemsOf(entities: list) -> list[ExportItem]:
    """The bodies and those of the occurrences, each once"""
    items: list[ExportItem] = []
    def add(body: adsk.fusion.BRepBody):
        item = ExportItem(body.nativeObject, body.assemblyContext) if body.assemblyContext is not None else ExportItem(body, None)
        if not any(other.body == item.body and other.occurrence == item.occurrence for other in items):
            items.append(item)
    def addOccurrence(occurrence: adsk.fusion.Occurrence):
        for body in occurrence.bRepBodies:
            add(body)
        for child in occurrence.childOccurrences:
            addOccurrence(child)

    for entity in entities:
        body = adsk.fusion.BRepBody.cast(entity)
        if body is not None:
            add(body)
            continue
        occurrence = adsk.fusion.Occurrence.cast(entity)
        if occurrence is not None:
            addOccurrence(occurrence)
    return items

def command_execute(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
    try:
        options = dialogOptions(inputs)
        folder = dialogFolder
        if not os.path.isdir(folder):
            folder = askFolder(folder)
            if folder is None:
                return
        saveDialogChoices(inputs, folder)
        items = exportItems(inputs)
        if len(items) == 0:
            ui.messageBox('Nothing to export, select bodies or turn on All Gridfinity bodies.', CMD_NAME)
            return
        progress = DialogProgress()
        try:
            result = exportFiles(items, folder, options, mayReplace, progress)
        finally:
            progress.hide()
        if result is None:
            return
        if options.format == FORMAT_3MF:
            where = result.paths[0] if len(result.paths) == 1 else f'{len(result.paths)} files in {folder}, a plate each'
            ui.messageBox(f'Exported {len(items)} bod{"y" if len(items) == 1 else "ies"} to {where}.{plateNote(result)}{paintNote(options.paint, result.painted, options.filament)}', CMD_NAME)
        else:
            ui.messageBox(f'Exported {len(items)} {options.format} file{"" if len(items) == 1 else "s"} to {folder}.', CMD_NAME)
    except Exception as err:
        futil.handle_error(f'{CMD_NAME} failed, {err}', show_message_box=True)

def saveDialogChoices(inputs: adsk.core.CommandInputs, folder: str):
    bedName = adsk.core.DropDownCommandInput.cast(inputs.itemById(BED_PRESET_INPUT_ID)).selectedItem.name
    saveChoices(
        folder,
        selectedFormat(inputs),
        adsk.core.BoolValueCommandInput.cast(inputs.itemById(PAINT_INPUT_ID)).value,
        adsk.core.IntegerSpinnerCommandInput.cast(inputs.itemById(FILAMENT_INPUT_ID)).value,
        selectedArrangement(inputs),
        bedName,
        dialogBeds(inputs),
        round(adsk.core.ValueCommandInput.cast(inputs.itemById(PURGE_INPUT_ID)).value * 10, 6),
        adsk.core.DropDownCommandInput.cast(inputs.itemById(FILES_INPUT_ID)).selectedItem.name,
    )

def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    # the context menu handler stays for the next menu
    local_handlers = [handler for handler in local_handlers if handler is markingMenuHandler]

def listed(names: list[str]) -> str:
    return ', '.join(names[:MAX_LISTED_FILES]) + (f' and {len(names) - MAX_LISTED_FILES} more' if len(names) > MAX_LISTED_FILES else '')

def plateNote(result: ExportResult) -> str:
    """
    How many plates the bodies were packed on, which are bigger than the bed and the plates where an area couldn't be
    kept free, after the export's message
    """
    note = f'\n\nPacked on {result.plates} plates.' if result.plates > 1 and len(result.paths) == 1 else ''
    if result.tooBig:
        note += f'\n\nBigger than the bed, each on a plate of its own: {listed(result.tooBig)}.'
    if result.notClear:
        plates = ', '.join(str(plate + 1) for plate in result.notClear)
        note += f'\n\nNo room to keep the purge tower area or the area the printer keeps free clear on plate{"" if len(result.notClear) == 1 else "s"} {plates}, move the bodies or the tower in the slicer.'
    return note

def paintNote(paint: bool, painted: int, filament: int) -> str:
    """What of the labels was colored, after the export's message"""
    if not paint:
        return ''
    if painted == 0:
        return '\n\nNo outline label text to color.'
    bodies = 'the body' if painted == 1 else f'{painted} bodies'
    return f'\n\nLabel text of {bodies} is assigned color {filament}.'

def mayReplace(paths: list[str]) -> bool:
    """Whether the files there already may be replaced, asked once for all of them"""
    existing = [path for path in paths if os.path.exists(path)]
    if len(existing) == 0:
        return True
    shown = [os.path.basename(path) for path in existing[:MAX_LISTED_FILES]]
    if len(existing) > MAX_LISTED_FILES:
        shown.append(f'and {len(existing) - MAX_LISTED_FILES} more')
    folder = os.path.dirname(existing[0])
    question = f'Replace {"the existing file" if len(existing) == 1 else f"{len(existing)} existing files"} in {folder}?\n\n' + '\n'.join(shown)
    answer = ui.messageBox(question, CMD_NAME, adsk.core.MessageBoxButtonTypes.YesNoButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
    return answer == adsk.core.DialogResults.DialogYes

def safeFileName(name: str) -> str:
    """Without the characters file systems refuse"""
    return re.sub(r'[\\/:*?"<>|]+', '_', name).strip()

def defaultFileName(items: list[ExportItem]) -> str:
    return fileNames(items)[0] if len(items) == 1 else DEFAULT_FILE_NAME

def fileNames(items: list[ExportItem]) -> list[str]:
    """By body name, numbered when the same"""
    names = []
    for item in items:
        name = safeFileName(item.body.name) or 'Body'
        unique = name
        number = 2
        while unique.lower() in (other.lower() for other in names):
            unique = f'{name} ({number})'
            number += 1
        names.append(unique)
    return names

def askFolder(folder: str) -> str | None:
    dialog = ui.createFolderDialog()
    dialog.title = f'{CMD_NAME}, a folder for the files'
    if os.path.isdir(folder):
        dialog.initialDirectory = folder
    return dialog.folder if dialog.showDialog() == adsk.core.DialogResults.DialogOK else None

class DialogProgress:
    """Fusion's progress dialog, shown once the export starts, see Progress"""
    def __init__(self):
        self.dialog: adsk.core.ProgressDialog | None = None

    def __call__(self, done: int, count: int):
        if self.dialog is None:
            self.dialog = ui.createProgressDialog()
            self.dialog.isCancelButtonShown = False
            self.dialog.show(CMD_NAME, 'Exporting %v of %m', 0, count)
        self.dialog.progressValue = done

    def hide(self):
        if self.dialog is not None:
            self.dialog.hide()
            self.dialog = None

def noProgress(done: int, count: int):
    pass

def refuseExisting(paths: list[str]) -> bool:
    """An export not to replace files, see MayWrite"""
    existing = [path for path in paths if os.path.exists(path)]
    if existing:
        raise FileExistsError(f'{listed([os.path.basename(path) for path in existing])} already in {os.path.dirname(existing[0])}, set overwrite to replace')
    return True

def replaceExisting(paths: list[str]) -> bool:
    return True

def exportFiles(items: list[ExportItem], folder: str, options: ExportOptions, mayWrite: MayWrite, progress: Progress) -> ExportResult | None:
    """The items in files of the options' format in the folder, none when the files there may not be replaced"""
    names = fileNames(items)
    if options.format == FORMAT_3MF:
        fileName = safeFileName(options.fileName) or defaultFileName(items)
        path = os.path.join(folder, fileName if fileName.lower().endswith('.3mf') else f'{fileName}.3mf')
        return export3mf(items, names, path, options.filament if options.paint else None, bedsOf(options, items), mayWrite, progress)
    if options.format not in FORMATS:
        raise ValueError(f'unknown format {options.format!r}, one of {FORMATS}')
    paths = [os.path.join(folder, f'{name}.{FORMAT_EXTENSIONS[options.format]}') for name in names]
    if not mayWrite(paths):
        return None
    exportEach(items, names, folder, options.format, progress)
    return ExportResult(paths, len(items))

def savedOptions() -> ExportOptions:
    """The dialog's last choices, the purge tower's room when bins have label text to color"""
    choices = readChoices()
    return ExportOptions(
        format=choices['format'],
        paint=choices['paint'],
        filament=choices['filament'],
        packed=choices['arrange'] == ARRANGE_PACKED,
        printer=choices['bed'],
        bedSize=(choices['bedWidth'], choices['bedLength']),
        spacing=choices['spacing'],
        margin=choices['margin'],
        purgeSize=choices['purge'],
        perPlate=choices['files'] == FILES_PER_PLATE,
    )

def exportBodies(bodies: list | None = None, folder: str = '', options: ExportOptions | None = None, progress: Progress = noProgress) -> ExportResult:
    """
    The export without dialogs, for scripts. Bodies and occurrences, none for every visible bin and baseplate of the
    active design, into the folder, the dialog's last one when none, with the options, the dialog's last choices when
    none, see savedOptions. Fails on files there already unless the options overwrite them
    """
    options = options or savedOptions()
    folder = folder or readChoices()['folder']
    if not os.path.isdir(folder):
        raise NotADirectoryError(f'no folder {folder}')
    if bodies is None:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            raise ValueError('no design to export from')
        bodies = gridfinityBodies(design)
    items = itemsOf(bodies)
    if len(items) == 0:
        raise ValueError('nothing to export')
    return exportFiles(items, folder, options, replaceExisting if options.overwrite else refuseExisting, progress)

def exportEach(items: list[ExportItem], names: list[str], folder: str, format: str, progress: Progress):
    """
    A file of each body in the folder, files of the same name are replaced. Each body at the origin, centered on x and
    y with its bottom at z 0, as made on its own, whatever its place in the design, upright, see meshTransform
    """
    # Fusion's STEP export writes a whole component where it is, and Fusion can't open a design hidden, so each body
    # goes alone into a design opened for a moment, which is closed without saving
    previous = app.activeDocument
    scratch = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType) if format == FORMAT_STEP else None
    try:
        for (index, (item, name)) in enumerate(zip(items, names)):
            path = os.path.join(folder, f'{name}.{FORMAT_EXTENSIONS[format]}')
            if format == FORMAT_STL:
                # the mesh the 3MF takes, Fusion's STL export writes a body where it is
                meshObject = meshOf(item, name, False, meshTransform(item, True))
                stlFile.write(path, name, stlFile.atOrigin(meshObject.vertices), meshObject.triangles)
            else:
                exportStep(scratch, item, name, path)
            progress(index + 1, len(items))
    finally:
        if scratch is not None:
            scratch.close(False)
            if previous is not None and previous.isValid:
                previous.activate()

def exportStep(document: adsk.core.Document, item: ExportItem, name: str, path: str):
    """The body alone in the document, at the origin"""
    brepManager = adsk.fusion.TemporaryBRepManager.get()
    copy = brepManager.copy(item.body)
    transform = meshTransform(item, True)
    if transform is not None:
        brepManager.transform(copy, transform)
    brepManager.transform(copy, toOrigin(copy.boundingBox))
    design = adsk.fusion.Design.cast(document.products.itemByProductType('DesignProductType'))
    # a body is added as it is without a base feature
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    body = design.rootComponent.bRepBodies.add(copy)
    body.name = name
    try:
        exportManager = design.exportManager
        if not exportManager.execute(exportManager.createSTEPExportOptions(path, design.rootComponent)):
            raise RuntimeError(f'{name} not written to {path}')
    finally:
        body.deleteMe()

def toOrigin(box: adsk.core.BoundingBox3D) -> adsk.core.Matrix3D:
    """The move putting the box centered on x and y at 0 with its bottom at z 0, see stlFile.atOrigin"""
    move = adsk.core.Matrix3D.create()
    move.translation = adsk.core.Vector3D.create(
        -(box.minPoint.x + box.maxPoint.x) / 2,
        -(box.minPoint.y + box.maxPoint.y) / 2,
        -box.minPoint.z,
    )
    return move

def plateFilePath(path: str, plate: int) -> str:
    """The file of a plate, numbered from 1, beside the path named for all of them"""
    (base, extension) = os.path.splitext(path)
    return f'{base}, plate {plate + 1}{extension}'

def stalePlateFiles(path: str, count: int) -> list[str]:
    """Plate files of an earlier export to the path that an export of count plates doesn't write"""
    (folder, fileName) = os.path.split(path)
    (base, extension) = os.path.splitext(fileName)
    pattern = re.compile(re.escape(f'{base}, plate ') + r'(\d+)' + re.escape(extension) + '$', re.IGNORECASE)
    stale = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        match = pattern.match(name)
        if match and int(match.group(1)) > count:
            stale.append(os.path.join(folder, name))
    return stale

def export3mf(items: list[ExportItem], names: list[str], path: str, filament: int | None, beds: Beds, mayWrite: MayWrite, progress: Progress) -> ExportResult | None:
    """
    The bodies packed on plates or as placed, see Beds, in one file, or a file per plate named after the path when
    there are several. None when the files there may not be replaced
    """
    objects = []
    paintedCount = 0
    isPacked = beds.spacing is not None
    for (index, (item, name)) in enumerate(zip(items, names)):
        meshObject = meshOf(item, name, filament is not None and item.hasOutlineLabels, meshTransform(item, isPacked))
        paintedCount += 1 if meshObject.painted else 0
        objects.append(meshObject)
        progress(index + 1, len(items))
    title = os.path.splitext(os.path.basename(path))[0]
    version = tagUtils.getGeneratorVersion()
    if not isPacked:
        if not mayWrite([path]):
            return None
        threeMf.write(path, threeMf.placeOnPlate(objects, beds.size), filament, title, version)
        return ExportResult([path], len(items), paintedCount)
    sizes = [threeMf.footprint(meshObject) for meshObject in objects]
    placements = bedPacking.arrange(sizes, beds.size, beds.spacing, beds.margin, beds.kept())
    count = bedPacking.bedCount(placements)
    tooBig = [name for (name, placement) in zip(names, placements) if not placement.fits]
    notClear = sorted(set(placement.bed for placement in placements if not placement.clear))
    if not beds.perPlate or count == 1:
        if not mayWrite([path]):
            return None
        placed = threeMf.placeOnBeds(objects, placements, beds.size)
        threeMf.write(path, placed, filament, title, version, [placement.bed for placement in placements])
        return ExportResult([path], len(items), paintedCount, count, tooBig, notClear)
    paths = [plateFilePath(path, plate) for plate in range(count)]
    stale = stalePlateFiles(path, count)
    if not mayWrite(paths + stale):
        return None
    for plate in range(count):
        onPlate = [index for (index, placement) in enumerate(placements) if placement.bed == plate]
        placed = threeMf.placeOnBeds([objects[index] for index in onPlate], [dataclasses.replace(placements[index], bed=0) for index in onPlate], beds.size)
        threeMf.write(paths[plate], placed, filament, f'{title}, plate {plate + 1}', version)
    for stalePath in stale:
        os.remove(stalePath)
    return ExportResult(paths, len(items), paintedCount, count, tooBig, notClear)

def isYUp() -> bool:
    """Fusion set to model with y up, which a design takes as it's made"""
    return app.preferences.generalPreferences.defaultModelingOrientation == adsk.core.DefaultModelingOrientations.YUpModelingOrientation

def meshTransform(item: ExportItem, isUpright: bool) -> adsk.core.Matrix3D | None:
    """
    Where the body's triangles go, none keeps them as they are. Upright, a bin or baseplate is as it was built, standing on
    its bottom in its component whatever its place in the design. Otherwise the body goes where it's placed, turned so
    y points up when Fusion models with y up
    """
    if isUpright and item.isGridfinity:
        return None
    transform = item.occurrence.transform2.copy() if item.occurrence is not None else adsk.core.Matrix3D.create()
    if isYUp():
        turn = adsk.core.Matrix3D.create()
        turn.setToRotation(math.pi / 2, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
        transform.transformBy(turn)
    return transform

def boxCorners(item: ExportItem, isUpright: bool) -> list[tuple[float, float, float]]:
    """The corners of the body's box where it goes, see meshTransform, in mm"""
    box = item.body.boundingBox
    transform = meshTransform(item, isUpright)
    corners = []
    for x in (box.minPoint.x, box.maxPoint.x):
        for y in (box.minPoint.y, box.maxPoint.y):
            for z in (box.minPoint.z, box.maxPoint.z):
                point = adsk.core.Point3D.create(x, y, z)
                if transform is not None:
                    point.transformBy(transform)
                corners.append((point.x * 10, point.y * 10, point.z * 10))
    return corners

def footprint(corners: list[tuple[float, float, float]]) -> tuple[float, float]:
    return (max(x for (x, _, _) in corners) - min(x for (x, _, _) in corners), max(y for (_, y, _) in corners) - min(y for (_, y, _) in corners))

def gridSize(item: ExportItem) -> tuple[float, float] | None:
    """A bin's or baseplate's width and length in grid units, none for other bodies"""
    tag = tagUtils.readBodyTag(item.body)
    settings = tag[1].get('config') if tag is not None else None
    if not isinstance(settings, dict):
        return None
    (widthKey, lengthKey) = ('binWidth', 'binLength') if tag[0] == tagUtils.TAG_BIN else ('plateWidth', 'plateLength')
    (width, length) = (settings.get(widthKey), settings.get(lengthKey))
    return (width, length) if isinstance(width, (int, float)) and isinstance(length, (int, float)) else None

def sizeLabel(item: ExportItem) -> str:
    """A bin's or baseplate's size in grid units, as 1x2, nothing for other bodies"""
    size = gridSize(item)
    return f'{size[0]:g}x{size[1]:g}' if size is not None else ''

def bodyKind(item: ExportItem) -> str:
    """bin or baseplate as its tag says, nothing for other bodies"""
    tag = tagUtils.readBodyTag(item.body)
    return tag[0] if tag is not None else ''

def bodiesCount(items: list[ExportItem]) -> str:
    """As 40 bins and 1 baseplate, bodies when some aren't bins or baseplates"""
    kinds = [bodyKind(item) for item in items]
    def counted(count: int, single: str, plural: str) -> str:
        return f'{count} {single if count == 1 else plural}'
    if '' in kinds:
        return counted(len(items), 'body', 'bodies')
    parts = [counted(kinds.count(kind), kind, f'{kind}s') for kind in (tagUtils.TAG_BIN, tagUtils.TAG_BASEPLATE) if kind in kinds]
    return ' and '.join(parts)

def platesData(items: list[ExportItem], beds: Beds) -> dict:
    """
    What the plates drawing shows, each plate's bodies by their boxes in mm from the bed's corner, packed as the export
    packs their triangles or as placed around the middle of one bed
    """
    if len(items) == 0:
        return {'error': 'Select bodies to export'}
    if beds.size[0] <= 0 or beds.size[1] <= 0:
        return {'error': 'The bed size has to be more than 0'}
    isPacked = beds.spacing is not None
    boxes = [boxCorners(item, isPacked) for item in items]
    sizes = [footprint(corners) for corners in boxes]
    areas = [{'area': list(area), 'name': 'Kept free by the printer'} for area in beds.excluded]
    if beds.purge is not None:
        areas.append({'area': list(beds.purge), 'name': 'Purge tower'})
    if isPacked:
        placements = bedPacking.arrange(sizes, beds.size, beds.spacing, beds.margin, beds.kept())
    else:
        # the layout's middle in the middle of the bed, as the 3MF has it
        (minX, minY) = (min(x for corners in boxes for (x, _, _) in corners), min(y for corners in boxes for (_, y, _) in corners))
        (maxX, maxY) = (max(x for corners in boxes for (x, _, _) in corners), max(y for corners in boxes for (_, y, _) in corners))
        (shiftX, shiftY) = ((beds.size[0] - minX - maxX) / 2, (beds.size[1] - minY - maxY) / 2)
        placements = [
            bedPacking.Placement(0, min(x for (x, _, _) in corners) + shiftX, min(y for (_, y, _) in corners) + shiftY, False,
                size[0] <= beds.size[0] and size[1] <= beds.size[1])
            for (corners, size) in zip(boxes, sizes)
        ]
    plates: list[list[dict]] = [[] for _ in range(bedPacking.bedCount(placements))]
    for (item, size, placement) in zip(items, sizes, placements):
        (width, length) = size[::-1] if placement.turned else size
        # a baseplate's cells are drawn on it, across and along as it lies on the plate
        units = gridSize(item) if bodyKind(item) == tagUtils.TAG_BASEPLATE else None
        cells = list(units[::-1] if placement.turned else units) if units is not None else None
        plates[placement.bed].append({
            'x': placement.x, 'y': placement.y, 'width': width, 'length': length,
            'name': item.body.name, 'label': sizeLabel(item), 'kind': bodyKind(item), 'cells': cells,
            'turned': placement.turned, 'fits': placement.fits, 'clear': placement.clear,
        })
    count = bodiesCount(items)
    tooBig = sum(not placement.fits for placement in placements)
    notClear = len(set(placement.bed for placement in placements if not placement.clear))
    return {
        'bed': list(beds.size),
        'margin': beds.margin,
        'areas': areas,
        'plates': plates,
        'caption': [
            f'{count} on {len(plates)} plate{"" if len(plates) == 1 else "s"}' if isPacked else f'{count} as placed',
            f'{beds.size[0]:g}x{beds.size[1]:g}mm' + (f', {beds.margin:g}mm margin, {beds.spacing:g}mm apart' if isPacked else '')
            + (f', {tooBig} bigger than the bed' if tooBig else '')
            + (f', {notClear} plate{"" if notClear == 1 else "s"} without room to keep an area free' if notClear else ''),
        ],
    }

def meshOf(item: ExportItem, name: str, paint: bool, transform: adsk.core.Matrix3D | None) -> threeMf.MeshObject:
    """
    The body's triangles in mm moved by the transform, see meshTransform, the nodes Fusion repeats for each face joined
    into one. With paint, the triangles on the letter faces of its outline labels are marked, see labelFaces
    """
    calculator = item.body.meshManager.createMeshCalculator()
    calculator.setQuality(MESH_QUALITY)
    mesh = calculator.calculate()
    coordinates = mesh.nodeCoordinatesAsDouble
    nodeIndices = mesh.nodeIndices

    nodes: list[tuple[float, float, float]] = []
    vertices: list[tuple[float, float, float]] = []
    joined: dict[tuple, int] = {}
    nodeVertex = []
    for index in range(len(coordinates) // 3):
        node = (coordinates[index * 3], coordinates[index * 3 + 1], coordinates[index * 3 + 2])
        key = tuple(round(value, 7) for value in node)
        if key not in joined:
            joined[key] = len(vertices)
            nodes.append(node)
            point = adsk.core.Point3D.create(*node)
            if transform is not None:
                point.transformBy(transform)
            vertices.append((point.x * 10, point.y * 10, point.z * 10))
        nodeVertex.append(joined[key])

    triangles = []
    painted = set()
    letters = letterPlanes(item.body) if paint else []
    for index in range(len(nodeIndices) // 3):
        triangle = tuple(nodeVertex[node] for node in nodeIndices[index * 3:index * 3 + 3])
        if len(set(triangle)) < 3:
            continue
        if letters and isOnLetter([nodes[vertex] for vertex in triangle], letters):
            painted.add(len(triangles))
        triangles.append(triangle)
    return threeMf.MeshObject(name, vertices, triangles, painted)

@dataclasses.dataclass
class LetterPlane:
    face: adsk.fusion.BRepFace
    normal: tuple[float, float, float]
    offset: float
    # min and max corner
    box: tuple[tuple[float, float, float], tuple[float, float, float]]

def letterPlanes(body: adsk.fusion.BRepBody) -> list[LetterPlane]:
    planes = []
    for face in labelFaces.outlineLetterFaces(body):
        (_, normal) = face.evaluator.getNormalAtPoint(face.pointOnFace)
        normal.normalize()
        point = face.pointOnFace
        box = face.boundingBox
        planes.append(LetterPlane(
            face,
            (normal.x, normal.y, normal.z),
            normal.x * point.x + normal.y * point.y + normal.z * point.z,
            ((box.minPoint.x, box.minPoint.y, box.minPoint.z), (box.maxPoint.x, box.maxPoint.y, box.maxPoint.z)),
        ))
    return planes

def isOnLetter(corners: list[tuple[float, float, float]], letters: list[LetterPlane]) -> bool:
    """A triangle lies on one face only, so its middle tells which"""
    middle = tuple(sum(corner[axis] for corner in corners) / 3 for axis in range(3))
    for letter in letters:
        if abs(sum(n * m for (n, m) in zip(letter.normal, middle)) - letter.offset) > PAINT_TOLERANCE:
            continue
        if any(middle[axis] < letter.box[0][axis] - PAINT_TOLERANCE or middle[axis] > letter.box[1][axis] + PAINT_TOLERANCE for axis in range(3)):
            continue
        evaluator = letter.face.evaluator
        (isOk, parameter) = evaluator.getParameterAtPoint(adsk.core.Point3D.create(*middle))
        if isOk and evaluator.isParameterOnFace(parameter):
            return True
    return False
