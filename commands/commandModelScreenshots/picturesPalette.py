import adsk.core
import json
import os
import subprocess
import sys
from typing import Callable

from ...lib import fusion360utils as futil
from ...lib.ui import browserPages, pictureJobs
from ... import config

# A palette docked beside the model listing the presets with their saved pictures, see html/pictures.html. Its buttons
# ask for pictures, the page also finishes them: Fusion's Python has no imaging, the page cuts a render to the model,
# fits it in the picture and scales it down in a canvas. Pictures are made while Fusion waits for the page's answers

app = adsk.core.Application.get()
ui = app.userInterface

PALETTE_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_modelPictures'
PALETTE_TITLE = 'Gridfinity model pictures'
PAGE_URL = browserPages.pageUrl(__file__, 'pictures.html')
WIDTH = 380
HEIGHT = 700

STATUS_QUEUED = 'queued'
STATUS_BUILDING = 'building'
STATUS_RENDERING = 'rendering'
STATUS_SAVED = 'saved'
# saved, with something to look at
STATUS_WARNING = 'warning'
STATUS_FAILED = 'failed'

palette_handlers = []
# the rows of the page in sections: presets with a name, description, picture with file and url, status and message,
# and GIFs with their files by kind and theme
ITEMS = 'items'
GIFS = 'gifs'
state: dict = {ITEMS: [], GIFS: [], 'message': '', 'busy': False}
# set by the command, gets the names of the presets whose pictures are asked for and if the GIFs are, and asks for the
# presets to be read again.
# They are called while the page waits for its answer, they change the state without sending it, the answer has it
onRequest: Callable[[list[str], list[str]], None] = lambda names, gifs: None
onReload: Callable[[], None] = lambda: None
# set by the command, the folders the pictures are saved to
pictureFolders: Callable[[], list[str]] = lambda: []

def show():
    """Shows the palette, the page asks for the rows when it's loaded"""
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette is None:
        palette = ui.palettes.add(PALETTE_ID, PALETTE_TITLE, PAGE_URL, True, True, True, WIDTH, HEIGHT)
        # beside the model, the viewport keeps the rest of the window
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        futil.add_handler(palette.incomingFromHTML, palette_incoming_from_html, local_handlers=palette_handlers)
    palette.isVisible = True
    send()

def setItems(items: list[dict], section: str = ITEMS, notify: bool = True):
    """New rows of a section, a row keeps its status while it's still there"""
    previous = {item['name']: item for item in state[section]}
    state[section] = [{
        'status': previous.get(item['name'], {}).get('status', ''),
        'message': previous.get(item['name'], {}).get('message', ''),
        **item,
    } for item in items]
    if notify:
        send()

def item(name: str, section: str = ITEMS) -> dict | None:
    return next((row for row in state[section] if row['name'] == name), None)

def setStatus(name: str, status: str, message: str = '', picture: dict | None = None, section: str = ITEMS, notify: bool = True):
    row = item(name, section)
    if row is not None:
        row.update(status=status, message=message)
        if picture is not None:
            row['picture'] = picture
    if notify:
        send()

def setBusy(busy: bool, message: str = '', notify: bool = True):
    state['busy'] = busy
    state['message'] = message
    if notify:
        send()

def send(data: dict | None = None):
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette is not None:
        palette.sendInfoToHTML('update', browserPages.encode(data if data is not None else {'state': state}))
    # the page draws while the pictures are being taken
    adsk.doEvents()

def finishPicture(name: str, renderPath: str, width: int, height: int, margin: float, transparent: bool,
                  exposure: float = 0, saturation: float = 1) -> dict:
    """The picture of a render, finished by the page, see pictureJobs.finishPicture"""
    return pictureJobs.finishPicture(send, name, renderPath, width, height, margin, transparent, exposure, saturation)

def openWithSystem(path: str):
    """A file in its app, a folder in Finder or Explorer"""
    if sys.platform == 'win32':
        os.startfile(path)
    else:
        subprocess.Popen(['open', path])

def openSaved(name: str, section: str, which: str | None):
    """
    A preset's saved picture, or a GIF's file by kind and theme, in the computer's viewer. By name, the page doesn't
    pick files
    """
    row = item(name, section) or {}
    saved = row.get('files', {}).get(which) if section == GIFS else row.get('picture')
    if saved is not None and os.path.exists(saved['file']):
        openWithSystem(saved['file'])

def openFolders():
    """The folders of the pictures, made when there's no picture in one yet"""
    for folder in pictureFolders():
        os.makedirs(folder, exist_ok=True)
        openWithSystem(folder)

def palette_incoming_from_html(args: adsk.core.HTMLEventArgs):
    answer = None
    try:
        data = json.loads(args.data) if args.data else None
        if args.action == browserPages.READY:
            answer = {'state': state}
        elif args.action == pictureJobs.PICTURE:
            pictureJobs.answer(data)
        elif args.action == 'render':
            onRequest(data.get('names', []), data.get('gifs', []))
            answer = {'state': state}
        elif args.action == 'reload':
            onReload()
            answer = {'state': state}
        elif args.action == 'open':
            openSaved(data['name'], data.get('section', ITEMS), data.get('which'))
        elif args.action == 'openFolder':
            openFolders()
        else:
            futil.log(f'{PALETTE_TITLE} page sent an unknown action {args.action}')
    except Exception as err:
        futil.log(f'{PALETTE_TITLE} {args.action} failed, {err}', adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    args.returnData = browserPages.NO_ANSWER if answer is None else browserPages.encode(answer)

def stop():
    global palette_handlers
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()
    palette_handlers = []
