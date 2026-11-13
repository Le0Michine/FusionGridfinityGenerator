import adsk.core
import json
from typing import Callable

from ...lib import fusion360utils as futil
from ...lib.ui import browserPages, pictureJobs
from ... import config

# A palette showing the last report, see report.py and html/report.html. Unlike a dialog it stays open beside
# the documents of the failed cases. The page asks for the report once loaded and sends the actions of its buttons

app = adsk.core.Application.get()
ui = app.userInterface

PALETTE_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_snapshotTestsReport'
PALETTE_TITLE = 'Gridfinity tests'
PAGE_URL = browserPages.pageUrl(__file__, 'report.html')
WIDTH = 700
HEIGHT = 640

palette_handlers = []
currentReport: dict | None = None
# actions of the page's buttons, they answer with the report to redraw
actions: dict[str, browserPages.Handler] = {}
# adds what the report doesn't keep to what the page gets, the case in the viewport
annotate: Callable[[dict], dict] = lambda data: data

def show(report: dict, handlers: dict[str, browserPages.Handler]):
    global currentReport, actions
    currentReport = report
    actions = handlers
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette is None:
        palette = ui.palettes.add(PALETTE_ID, PALETTE_TITLE, PAGE_URL, True, True, True, WIDTH, HEIGHT)
        # beside the model, out of the way of the documents of failed cases
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        futil.add_handler(palette.incomingFromHTML, palette_incoming_from_html, local_handlers=palette_handlers)
        # a new page asks for the report itself
        return
    palette.isVisible = True
    try:
        palette.sendInfoToHTML('update', encode(report))
    except Exception as err:
        futil.log(f'{PALETTE_TITLE} page not ready yet, {err}')

def encode(report: dict) -> str:
    return browserPages.encode(annotate(report))

def update(report: dict, handleEvents: bool = True):
    """The report redrawn, while a run goes on Fusion handles the page's events between the cases"""
    global currentReport
    currentReport = report
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette is not None:
        try:
            palette.sendInfoToHTML('update', encode(report))
        except Exception as err:
            futil.log(f'{PALETTE_TITLE} report not redrawn, {err}')
    if handleEvents:
        adsk.doEvents()

def finishPicture(name: str, renderPath: str, width: int, height: int, margin: float, transparent: bool,
                  exposure: float = 0, saturation: float = 1) -> dict:
    """The picture of a render, finished by the page, see pictureJobs.finishPicture"""
    return pictureJobs.finishPicture(sendJob, name, renderPath, width, height, margin, transparent, exposure, saturation)

def sendJob(data: dict):
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette is None:
        raise pictureJobs.PageError(f'the {PALETTE_TITLE} palette is closed, nothing to finish the picture')
    palette.sendInfoToHTML('update', browserPages.encode(data))

def coveredWidth() -> int:
    """Pixels of the viewport the palette takes on its right, none while it's hidden or floating"""
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette is None:
        # about to open docked on the right, see show
        return WIDTH
    if not palette.isVisible or palette.dockingState != adsk.core.PaletteDockingStates.PaletteDockStateRight:
        return 0
    return palette.width

def palette_incoming_from_html(args: adsk.core.HTMLEventArgs):
    global currentReport
    answer = None
    if args.action == browserPages.RESPONSE:
        return
    try:
        if args.action == browserPages.READY:
            answer = currentReport
        elif args.action == pictureJobs.PICTURE:
            pictureJobs.answer(json.loads(args.data))
        elif args.action in actions:
            data = json.loads(args.data) if args.data else None
            answer = actions[args.action](data)
            if answer is not None:
                currentReport = answer
        else:
            futil.log(f'{PALETTE_TITLE} page sent an unknown action {args.action}')
    except Exception as err:
        futil.log(f'{PALETTE_TITLE} {args.action} failed, {err}', adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    args.returnData = browserPages.NO_ANSWER if answer is None else encode(answer)

def stop():
    global palette_handlers
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()
    palette_handlers = []
