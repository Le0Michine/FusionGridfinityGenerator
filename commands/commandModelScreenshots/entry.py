import adsk.core, adsk.fusion, traceback
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

from ...lib import fusion360utils as futil
from ...lib.ui import viewportPictures
from ... import config
from ..commandCreateBin import binBuilder
from ..commandCreateBin.inputState import InputState as BinInputState
from ..commandCreateBaseplate import baseplateBuilder
from ..commandCreateBaseplate.inputState import InputState as BaseplateInputState
from ..commandSnapshotTests import testCases
from . import presets, picturesPalette

# Model screenshots for the docs: the presets of tools/screenshots/models are listed in a palette with their pictures,
# see picturesPalette.py. A preset asked for is built in a new document and saved as a picture, see presets.py. The
# documents are closed again, nothing is saved but the pictures

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdRenderModelScreenshots'
CMD_NAME = 'Gridfinity docs: render models'
# shown on hover over the button, the first paragraph says what it does, the second how, like the generator commands
CMD_Description = ('Saves pictures of bins and baseplates for the docs.\n\n'
    'Lists the presets of tools/screenshots/models with their pictures. A preset asked for is built in a new '
    'document, shown from the preset\'s view and saved as a picture, by default to documentation/assets/models.')

# Utilities > Add-ins, out of the way of the generator commands
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
FALLBACK_PANEL_ID = 'SolidCreatePanel'

ROOT_FOLDER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESETS_FOLDER = os.path.join(ROOT_FOLDER, 'tools', 'screenshots', 'models')
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')
STATE_CLASSES = {testCases.GENERATOR_BIN: BinInputState, testCases.GENERATOR_BASEPLATE: BaseplateInputState}
# what the pictures since the palette was opened did, with the tracebacks of what failed
LOG_PATH = os.path.join(ROOT_FOLDER, 'tools', 'screenshots', 'models-render.log')
# GIFs of the pictures and of the dialog going through the same options are made by the screenshot tool, with its own
# Python, set up as in tools/screenshots/README.md, Fusion's has no imaging. How long they may take
SCREENSHOTS_FOLDER = os.path.join(ROOT_FOLDER, 'tools', 'screenshots')
GIF_PYTHON = os.path.join(SCREENSHOTS_FOLDER, '.venv', 'Scripts', 'python.exe') if sys.platform == 'win32' else os.path.join(SCREENSHOTS_FOLDER, '.venv', 'bin', 'python')
GIF_COMMAND = [GIF_PYTHON, os.path.join(SCREENSHOTS_FOLDER, 'modelGifs.py'), '--dialogs']
GIFS_FILE = os.path.join(SCREENSHOTS_FOLDER, 'modelGifs.json')
GIF_FOLDER = os.path.join(ROOT_FOLDER, 'documentation', 'assets', 'gif')
GIF_THEMES = ['light', 'dark']
GIF_TIMEOUT = 15 * 60
# Fusion's Python settings would make the tool's Python load Fusion's libraries
FUSION_PYTHON_VARIABLES = ['PYTHONHOME', 'PYTHONPATH', 'PYTHONEXECUTABLE', '__PYVENV_LAUNCHER__']
# runs the pictures asked for outside of the palette's message, which has to answer right away
QUEUE_EVENT_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_modelPicturesQueue'
# lighting of the pictures
VIEWPORT_LIGHTING = 'PhotoBoothLightingEnvironment'

local_handlers = []
queue_handlers = []
# presets whose pictures are asked for, and if they are being made
queue: list[str] = []
# GIFs asked for, by name, made after the pictures
gifQueue: list[str] = []
isRunning = False

def start():
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        # Fusion titles the hover popup with the name only for buttons with icons
        cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)
    try:
        panel = commandPanel()
        control = panel.controls.itemById(CMD_ID) or panel.controls.addCommand(cmd_def)
        # shown on the toolbar, not only in the panel's dropdown
        control.isPromoted = True
    except Exception as err:
        futil.log(f'{CMD_NAME} button not added, {err}', adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    # left over when the add-in wasn't stopped
    app.unregisterCustomEvent(QUEUE_EVENT_ID)
    futil.add_handler(app.registerCustomEvent(QUEUE_EVENT_ID), queue_custom_event, local_handlers=queue_handlers)
    picturesPalette.onRequest = request
    picturesPalette.onReload = lambda: reloadItems(notify=False)
    picturesPalette.pictureFolders = pictureFolders

def commandPanel() -> adsk.core.ToolbarPanel:
    """Utilities > Add-ins, the Create panel of the generators when that one isn't found"""
    panels = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels
    panel = panels.itemById(PANEL_ID)
    if panel is None:
        futil.log(f'{CMD_NAME} panel {PANEL_ID} not found, using {FALLBACK_PANEL_ID}', force_console=True)
        panel = panels.itemById(FALLBACK_PANEL_ID)
    return panel

def stop():
    global queue_handlers
    panels = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels
    for panelId in [PANEL_ID, FALLBACK_PANEL_ID]:
        panel = panels.itemById(panelId)
        control = panel.controls.itemById(CMD_ID) if panel is not None else None
        if control:
            control.deleteMe()
    command_definition = ui.commandDefinitions.itemById(CMD_ID)
    if command_definition:
        command_definition.deleteMe()
    picturesPalette.stop()
    app.unregisterCustomEvent(QUEUE_EVENT_ID)
    queue_handlers = []
    queue.clear()

# without inputs Fusion executes the command right away, no dialog
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []

def command_execute(args: adsk.core.CommandEventArgs):
    try:
        if not isRunning:
            # a new log every time the palette opens, Fusion's console is cleared easily and its log files don't keep
            # add-in errors
            with open(LOG_PATH, 'w', encoding='utf-8') as file:
                file.write(f'{CMD_NAME}, {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        reloadItems()
        picturesPalette.show()
    except:
        writeLog(traceback.format_exc())
        ui.messageBox(f'{CMD_NAME}\n\nFailed:\n{traceback.format_exc()}', CMD_NAME)

def writeLog(text: str):
    with open(LOG_PATH, 'a', encoding='utf-8') as file:
        file.write(text + '\n')

def picturePath(preset: presets.Preset) -> str:
    return os.path.join(ROOT_FOLDER, preset.output, f'{preset.name}.png')

def savedFile(path: str) -> dict | None:
    """A file on disk for the page, its url changes with the file so the page shows a new one"""
    if not os.path.exists(path):
        return None
    version = int(os.path.getmtime(path) * 1000)
    return {'file': path, 'url': f'{pathlib.Path(path).as_uri()}?v={version}', 'path': os.path.relpath(path, ROOT_FOLDER)}

def savedPicture(preset: presets.Preset) -> dict | None:
    return savedFile(picturePath(preset))

def gifRows() -> list[dict]:
    """
    The GIFs of modelGifs.json: their files by kind and theme, model or dialog, the pictures they show, the ones
    still missing, and if a picture changed after the GIF was made
    """
    with open(GIFS_FILE, encoding='utf-8') as file:
        gifs = json.load(file)['gifs']
    rows = []
    for gif in gifs:
        pictures = [frame['picture'] for frame in gif['frames']]
        # modelGifs.py takes the pictures from the default folder of presets
        picturePaths = [os.path.join(ROOT_FOLDER, presets.DEFAULT_OUTPUT, f'{picture}.png') for picture in pictures]
        files = {}
        for theme in GIF_THEMES:
            files[f'model-{theme}'] = savedFile(os.path.join(GIF_FOLDER, f'{gif["name"]}-{theme}.gif'))
            if gif.get('loopWith'):
                files[f'dialog-{theme}'] = savedFile(os.path.join(GIF_FOLDER, f'{gif["loopWith"]}-{theme}.gif'))
        made = files['model-light']
        rows.append({
            'name': gif['name'],
            'description': ' · '.join(frame.get('caption') or frame['picture'] for frame in gif['frames']),
            'pictures': pictures,
            'missing': [picture for (picture, path) in zip(pictures, picturePaths) if not os.path.exists(path)],
            'outdated': bool(made) and any(os.path.exists(path) and os.path.getmtime(path) > os.path.getmtime(made['file']) for path in picturePaths),
            'files': files,
        })
    return rows

def pictureFolders() -> list[str]:
    """The folders the presets save to, the default one when the presets can't be read"""
    try:
        folders = [preset.output for preset in presets.loadPresets(PRESETS_FOLDER)]
    except presets.PresetError:
        folders = []
    return [os.path.join(ROOT_FOLDER, folder) for folder in dict.fromkeys(folders or [presets.DEFAULT_OUTPUT])]

def reloadItems(notify: bool = True):
    """The presets read again from their files, a broken one is shown in the palette's message"""
    try:
        items = presets.loadPresets(PRESETS_FOLDER)
    except presets.PresetError as err:
        picturesPalette.setBusy(isRunning, str(err), notify)
        return
    picturesPalette.setItems([{'name': preset.name, 'description': preset.description, 'picture': savedPicture(preset)} for preset in items], notify=False)
    try:
        picturesPalette.setItems(gifRows(), section=picturesPalette.GIFS, notify=notify)
    except (OSError, ValueError, KeyError) as err:
        picturesPalette.setBusy(isRunning, f'{os.path.relpath(GIFS_FILE, ROOT_FOLDER)}: {err}', notify)

def request(names: list[str], gifs: list[str]):
    """
    Pictures and GIFs asked for in the palette, made one after the other, the palette's answer shows them waiting. GIFs
    are made after the pictures, with the pictures they still miss
    """
    for gif in picturesPalette.state[picturesPalette.GIFS]:
        if gif['name'] in gifs:
            names = [*names, *(picture for picture in gif['missing'] if picture not in names)]
            if gif['name'] not in gifQueue:
                gifQueue.append(gif['name'])
                picturesPalette.setStatus(gif['name'], picturesPalette.STATUS_QUEUED, section=picturesPalette.GIFS, notify=False)
    for name in names:
        if name not in queue:
            queue.append(name)
            picturesPalette.setStatus(name, picturesPalette.STATUS_QUEUED, notify=False)
    if not isRunning:
        app.fireCustomEvent(QUEUE_EVENT_ID)

def queue_custom_event(args: adsk.core.CustomEventArgs):
    global isRunning
    if isRunning:
        return
    isRunning = True
    originalDocument = app.activeDocument
    originalLighting = app.lightingEnvironment
    done = 0
    message = ''
    try:
        app.lightingEnvironment = getattr(adsk.core.LightingEnvironments, VIEWPORT_LIGHTING)
        # GIFs asked for while pictures are made wait for them, they show the pictures
        while queue or gifQueue:
            if queue:
                name = queue.pop(0)
                picturesPalette.setBusy(True, f'Making picture {done + 1} of {done + 1 + len(queue)}')
                makePicture(name)
                done += 1
            else:
                names = gifQueue[:]
                gifQueue.clear()
                message = makeGifs(names)
    except:
        writeLog(traceback.format_exc())
    finally:
        app.lightingEnvironment = originalLighting
        if originalDocument is not None and originalDocument.isValid:
            originalDocument.activate()
        isRunning = False
        picturesPalette.setBusy(False, message)

def makeGifs(names: list[str]) -> str:
    """
    GIFs of modelGifs.json with the dialog animations they loop with, one at a time so their rows say which is being
    made and how each went. The result says how all did
    """
    if not os.path.exists(GIF_PYTHON):
        message = f'no {os.path.relpath(GIF_PYTHON, ROOT_FOLDER)}, set up the screenshot tool as in tools/screenshots/README.md'
        for name in names:
            picturesPalette.setStatus(name, picturesPalette.STATUS_FAILED, message, section=picturesPalette.GIFS, notify=False)
        return f'GIFs not made, {message}'
    for name in names:
        picturesPalette.setStatus(name, picturesPalette.STATUS_QUEUED, section=picturesPalette.GIFS, notify=False)
    started = time.monotonic()
    (made, failed) = (0, [])
    for (index, name) in enumerate(names):
        if time.monotonic() - started > GIF_TIMEOUT:
            picturesPalette.setStatus(name, picturesPalette.STATUS_FAILED, 'not made, the GIFs took too long', section=picturesPalette.GIFS, notify=False)
            failed.append(name)
            continue
        picturesPalette.setStatus(name, picturesPalette.STATUS_RENDERING, section=picturesPalette.GIFS, notify=False)
        failure = makeGif(name, f'Making GIF {index + 1} of {len(names)}', started)
        # the row gets the new files
        reloadItems(notify=False)
        if failure:
            failed.append(name)
        else:
            made += 1
        picturesPalette.setStatus(name, picturesPalette.STATUS_FAILED if failure else picturesPalette.STATUS_SAVED, failure or '', section=picturesPalette.GIFS, notify=False)
    seconds = int(time.monotonic() - started)
    if failed:
        return f'Made {made} GIFs in {seconds} s, {len(failed)} failed: {", ".join(failed)}'
    return f'Made {made} GIFs in {seconds} s, in documentation/assets/gif'

def makeGif(name: str, message: str, started: float) -> str | None:
    """A GIF with its dialog animation by running modelGifs.py, what kept it from being made, if anything"""
    environment = {key: value for (key, value) in os.environ.items() if key not in FUSION_PYTHON_VARIABLES}
    outputPath = os.path.join(tempfile.gettempdir(), 'gridfinity-gifs.log')
    with open(outputPath, 'w', encoding='utf-8') as output:
        # no console window flashing up on Windows
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        process = subprocess.Popen([*GIF_COMMAND, '--only', name], cwd=ROOT_FOLDER, env=environment, stdout=output, stderr=subprocess.STDOUT, creationflags=flags)
        (shown, elapsed) = (-1, 0)
        # Fusion keeps drawing and the palette answering while it is made
        while process.poll() is None:
            elapsed = int(time.monotonic() - started)
            if elapsed > GIF_TIMEOUT:
                process.kill()
                process.wait()
                break
            if elapsed != shown:
                shown = elapsed
                picturesPalette.setBusy(True, f'{message}, {elapsed} s')
            adsk.doEvents()
            time.sleep(0.1)
    with open(outputPath, encoding='utf-8', errors='replace') as file:
        lines = [line.strip() for line in file if line.strip()]
    writeLog(f'GIF {name}\n' + '\n'.join(lines))
    if elapsed > GIF_TIMEOUT:
        return 'took too long and was stopped'
    # the script says what kept a GIF from being made on a line starting with its name
    failure = next((line[len(name) + 2:] for line in lines if line.startswith(f'{name}: ')), None)
    if failure:
        return failure
    if process.returncode != 0 or not any(os.path.basename(line).startswith(f'{name}-') and line.endswith('.gif') for line in lines):
        # the last lines say what went wrong, a traceback ends with its error
        problems = [line for line in lines if not line.endswith('.gif')]
        return ' '.join(problems[-3:]) or 'not made'
    return None

def makePicture(name: str):
    """The picture of a preset, read again from its file, its row says how it went"""
    document = None
    try:
        picturesPalette.setStatus(name, picturesPalette.STATUS_BUILDING)
        preset = presets.loadPreset(PRESETS_FOLDER, f'{name}.json')
        state = testCases.stateFromJson(preset.generator, STATE_CLASSES[preset.generator], preset.settings)
        document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(document.products.itemByProductType('DesignProductType'))
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        if preset.generator == testCases.GENERATOR_BIN:
            bodies = binBuilder.buildBin(design, state, [])
        else:
            bodies = baseplateBuilder.buildBaseplate(design, state, [])
        path = picturePath(preset)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        picturesPalette.setStatus(name, picturesPalette.STATUS_RENDERING)
        prepareView(design, bodies, preset)
        warnings = viewportPicture(preset, path)
        relativePath = os.path.relpath(path, ROOT_FOLDER)
        status = picturesPalette.STATUS_WARNING if warnings else picturesPalette.STATUS_SAVED
        picturesPalette.setStatus(name, status, ', '.join([relativePath, *warnings]), savedPicture(preset))
        writeLog(f'{name}: {", ".join([relativePath, *warnings])}')
    except Exception as err:
        message = f'{err} ({failurePlace(err)})'
        futil.log(f'{CMD_NAME} {name} failed\n{traceback.format_exc()}', adsk.core.LogLevels.ErrorLogLevel, force_console=True)
        writeLog(f'{name} failed\n{traceback.format_exc()}')
        picturesPalette.setStatus(name, picturesPalette.STATUS_FAILED, message)
    if document is not None:
        document.close(False)
    adsk.doEvents()

def failurePlace(err: Exception) -> str:
    """Where in the add-in an error came from, the last line of its code in the traceback"""
    frames = [frame for frame in traceback.extract_tb(err.__traceback__) if frame.filename.startswith(ROOT_FOLDER)]
    if not frames:
        return 'outside the add-in'
    frame = frames[-1]
    return f'{os.path.relpath(frame.filename, ROOT_FOLDER)}:{frame.lineno} {frame.line}'

def modelAppearance(design: adsk.fusion.Design, preset: presets.Preset) -> adsk.core.Appearance:
    """The preset's appearance, or a matte plastic, in the preset's color"""
    base = viewportPictures.libraryAppearance(preset.appearance) if preset.appearance else viewportPictures.firstLibraryAppearance(viewportPictures.COLOR_BASE_PREFIXES)
    return viewportPictures.colorAppearance(design, base, preset.color)

def prepareView(design: adsk.fusion.Design, bodies: list[adsk.fusion.BRepBody], preset: presets.Preset):
    """The bodies alone from the preset's view, the new document's viewport is the active one"""
    viewportPictures.hideHelpers(design)
    if preset.appearance or preset.color:
        appearance = modelAppearance(design, preset)
        for body in bodies:
            body.appearance = appearance
    viewportPictures.frame(app.activeViewport, presets.STYLES[preset.style], preset.camera == 'orthographic', preset.view)

def viewportPicture(preset: presets.Preset, path: str) -> list[str]:
    """The viewport as it is, moved back while the model touches the edge, the warnings of the picture"""
    options = viewportPictures.PictureOptions(preset.width, preset.height, preset.transparent, preset.margin, preset.supersample, preset.exposure, preset.saturation)
    return viewportPictures.viewportPicture(app.activeViewport, preset.name, path, options, picturesPalette.finishPicture)
