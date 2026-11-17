import adsk.core, adsk.fusion
import dataclasses
import os
import re

from ...lib import tagUtils
from ...lib import labelFaces
from ...lib import threeMf
from ...lib import stlFile
from ...lib import configUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import labelGenerator
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
SUMMARY_INPUT_ID = 'export_summary'

FORMAT_3MF = '3MF'
FORMAT_STL = 'STL'
FORMAT_STEP = 'STEP'
FORMATS = [FORMAT_3MF, FORMAT_STL, FORMAT_STEP]
FORMAT_EXTENSIONS = {FORMAT_3MF: '3mf', FORMAT_STL: 'stl', FORMAT_STEP: 'step'}
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

# the folder chosen in the dialog open now, and whether its file name was typed or still follows the bodies
dialogFolder = ''
isFileNameTyped = False

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
    return {
        'folder': folder,
        'format': format if format in FORMATS else FORMAT_3MF,
        'paint': section.get('paint', 'yes') != 'no',
        'filament': filament,
    }

def saveChoices(folder: str, format: str, paint: bool, filament: int):
    addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)
    addinConfig[CONFIG_SECTION] = {
        'folder': folder,
        'format': format,
        'paint': 'yes' if paint else 'no',
        'colorIndex': str(filament),
    }
    if not configUtils.writeConfig(addinConfig, CONFIG_FOLDER_PATH):
        futil.log(f'{CMD_NAME} choices not saved to {CONFIG_FOLDER_PATH}')

def command_created(args: adsk.core.CommandCreatedEventArgs):
    global dialogFolder, isFileNameTyped
    command = args.command
    inputs = command.commandInputs
    choices = readChoices()
    dialogFolder = choices['folder']
    isFileNameTyped = False
    design = adsk.fusion.Design.cast(app.activeProduct)
    # the whole design when its root was picked
    allInput = inputs.addBoolValueInput(ALL_INPUT_ID, 'All Gridfinity bodies', True, '', isRootSelected(design))
    allInput.tooltip = 'Selects every visible bin and baseplate of the design, off goes back to what was selected'
    selectionInput = inputs.addSelectionInput(SELECTION_INPUT_ID, 'Bodies', 'Bins, baseplates or any other bodies to export')
    # bodies only, Fusion puts a selected component in too as the command starts, beside its bodies
    selectionInput.addSelectionFilter(adsk.core.SelectionCommandInput.SolidBodies)
    selectionInput.setSelectionLimits(0, 0)
    selectAll(inputs, allInput.value)
    formatInput = inputs.addDropDownCommandInput(FORMAT_INPUT_ID, 'Format', adsk.core.DropDownStyles.TextListDropDownStyle)
    for name in FORMATS:
        formatInput.listItems.add(name, name == choices['format'])
    formatInput.tooltip = '3MF puts every body in one file, STL and STEP give each body a file of its own in the folder'
    folderInput = inputs.addTextBoxCommandInput(FOLDER_INPUT_ID, 'Folder', dialogFolder, 2, True)
    folderInput.tooltip = 'Where the files go, the last folder chosen is kept'
    browseInput = inputs.addBoolValueInput(BROWSE_INPUT_ID, '', False, '', False)
    browseInput.text = 'Choose folder...'
    fileNameInput = inputs.addStringValueInput(FILE_NAME_INPUT_ID, 'File name', '')
    fileNameInput.tooltip = 'The 3MF file\'s name, the body\'s name for one body'
    paintInput = inputs.addBoolValueInput(PAINT_INPUT_ID, 'Color label text', True, '', choices['paint'])
    paintInput.tooltip = 'Assigns a color index to the text on outline labels so the slicer paints it automatically'
    filamentInput = inputs.addIntegerSpinnerCommandInput(FILAMENT_INPUT_ID, 'Label color index', 1, threeMf.MAX_FILAMENT, 1, choices['filament'])
    filamentInput.tooltip = 'The slicer\'s color the label text prints in, counting from 1 as the slicer lists them'
    inputs.addTextBoxCommandInput(SUMMARY_INPUT_ID, '', '', 2, True)
    # as wide as the bin dialog, the minimum widens one Fusion kept narrower from before
    command.setDialogInitialSize(450, 400)
    command.setDialogMinimumSize(450, 300)
    updateInputs(inputs)
    futil.add_handler(command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(command.destroy, command_destroy, local_handlers=local_handlers)

def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global dialogFolder, isFileNameTyped
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

def updateInputs(inputs: adsk.core.CommandInputs):
    """Painting is for 3MF only, the summary says what goes out"""
    format = selectedFormat(inputs)
    paintInput = adsk.core.BoolValueCommandInput.cast(inputs.itemById(PAINT_INPUT_ID))
    paintInput.isVisible = format == FORMAT_3MF
    inputs.itemById(FILAMENT_INPUT_ID).isVisible = format == FORMAT_3MF and paintInput.value
    fileNameInput = adsk.core.StringValueCommandInput.cast(inputs.itemById(FILE_NAME_INPUT_ID))
    fileNameInput.isVisible = format == FORMAT_3MF
    try:
        items = exportItems(inputs)
        if not isFileNameTyped:
            fileNameInput.value = defaultFileName(items)
        files = 'one file' if format == FORMAT_3MF else 'a file each'
        summary = f'{len(items)} bod{"y" if len(items) == 1 else "ies"}, {files}' if items else 'Select bodies to export'
    except Exception as err:
        summary = f'Bodies not found, {err}'
    adsk.core.TextBoxCommandInput.cast(inputs.itemById(SUMMARY_INPUT_ID)).text = summary

def selectedEntities(inputs: adsk.core.CommandInputs) -> list:
    selectionInput = adsk.core.SelectionCommandInput.cast(inputs.itemById(SELECTION_INPUT_ID))
    return [selectionInput.selection(index).entity for index in range(selectionInput.selectionCount)]

def exportItems(inputs: adsk.core.CommandInputs) -> list[ExportItem]:
    """The selected bodies and those of the selected occurrences"""
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

    for entity in selectedEntities(inputs):
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
        format = selectedFormat(inputs)
        paint = adsk.core.BoolValueCommandInput.cast(inputs.itemById(PAINT_INPUT_ID)).value
        filament = adsk.core.IntegerSpinnerCommandInput.cast(inputs.itemById(FILAMENT_INPUT_ID)).value
        folder = dialogFolder
        if not os.path.isdir(folder):
            folder = askFolder(folder)
            if folder is None:
                return
        saveChoices(folder, format, paint, filament)
        items = exportItems(inputs)
        if len(items) == 0:
            ui.messageBox('Nothing to export, select bodies or turn on All Gridfinity bodies.', CMD_NAME)
            return
        names = fileNames(items)
        if format == FORMAT_3MF:
            fileName = safeFileName(adsk.core.StringValueCommandInput.cast(inputs.itemById(FILE_NAME_INPUT_ID)).value) or defaultFileName(items)
            path = os.path.join(folder, fileName if fileName.lower().endswith('.3mf') else f'{fileName}.3mf')
            if not mayReplace([path]):
                return
            painted = export3mf(items, names, path, filament if paint else None)
            ui.messageBox(f'Exported {len(items)} bod{"y" if len(items) == 1 else "ies"} to {path}.{paintNote(paint, painted, filament)}', CMD_NAME)
        else:
            if not mayReplace([os.path.join(folder, f'{name}.{FORMAT_EXTENSIONS[format]}') for name in names]):
                return
            exportEach(items, names, folder, format)
            ui.messageBox(f'Exported {len(items)} {format} file{"" if len(items) == 1 else "s"} to {folder}.', CMD_NAME)
    except Exception as err:
        futil.handle_error(f'{CMD_NAME} failed, {err}', show_message_box=True)

def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    # the context menu handler stays for the next menu
    local_handlers = [handler for handler in local_handlers if handler is markingMenuHandler]

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

def progressDialog(count: int) -> adsk.core.ProgressDialog:
    progress = ui.createProgressDialog()
    progress.isCancelButtonShown = False
    progress.show(CMD_NAME, 'Exporting %v of %m', 0, count)
    return progress

def exportEach(items: list[ExportItem], names: list[str], folder: str, format: str):
    """
    A file of each body in the folder, files of the same name are replaced. Each body at the origin, centered on x and
    y with its bottom at z 0, as made on its own, whatever its place in the design
    """
    progress = progressDialog(len(items))
    # Fusion's STEP export writes a whole component where it is, and Fusion can't open a design hidden, so each body
    # goes alone into a design opened for a moment, which is closed without saving
    previous = app.activeDocument
    scratch = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType) if format == FORMAT_STEP else None
    try:
        for (index, (item, name)) in enumerate(zip(items, names)):
            path = os.path.join(folder, f'{name}.{FORMAT_EXTENSIONS[format]}')
            if format == FORMAT_STL:
                # the mesh the 3MF takes, Fusion's STL export writes a body where it is
                meshObject = meshOf(item, name, False)
                stlFile.write(path, name, stlFile.atOrigin(meshObject.vertices), meshObject.triangles)
            else:
                exportStep(scratch, item, name, path)
            progress.progressValue = index + 1
    finally:
        progress.hide()
        if scratch is not None:
            scratch.close(False)
            if previous is not None and previous.isValid:
                previous.activate()

def exportStep(document: adsk.core.Document, item: ExportItem, name: str, path: str):
    """The body alone in the document, at the origin"""
    brepManager = adsk.fusion.TemporaryBRepManager.get()
    copy = brepManager.copy(item.body)
    if item.occurrence is not None:
        brepManager.transform(copy, item.occurrence.transform2)
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

def export3mf(items: list[ExportItem], names: list[str], path: str, filament: int | None) -> int:
    """All bodies in one file, returns how many have painted letters"""
    objects = []
    paintedCount = 0
    progress = progressDialog(len(items))
    try:
        for (index, (item, name)) in enumerate(zip(items, names)):
            meshObject = meshOf(item, name, filament is not None and item.hasOutlineLabels)
            paintedCount += 1 if meshObject.painted else 0
            objects.append(meshObject)
            progress.progressValue = index + 1
    finally:
        progress.hide()
    title = os.path.splitext(os.path.basename(path))[0]
    threeMf.write(path, objects, filament, title, tagUtils.getGeneratorVersion())
    return paintedCount

def meshOf(item: ExportItem, name: str, paint: bool) -> threeMf.MeshObject:
    """
    The body's triangles in mm where it's placed, the nodes Fusion repeats for each face joined into one. With paint, the
    triangles on the letter faces of its outline labels are marked, see labelFaces
    """
    calculator = item.body.meshManager.createMeshCalculator()
    calculator.setQuality(MESH_QUALITY)
    mesh = calculator.calculate()
    coordinates = mesh.nodeCoordinatesAsDouble
    nodeIndices = mesh.nodeIndices
    transform = item.occurrence.transform2 if item.occurrence is not None else None

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
