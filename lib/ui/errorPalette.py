import adsk.core, adsk.fusion
import platform
import subprocess
import webbrowser

from ...lib import fusion360utils as futil
from ...lib import clipboard, errorReport, tagUtils
from ...lib.gridfinityUtils import sharedParameters
from ... import config
from . import browserPages

# A palette with the error of the last failed build, see html/errorReport.html. Fusion's own message for a failed
# command goes away by itself and can't be copied, this one stays until it's closed and copies a report of the error
# with what it was built from, ready to paste into an issue

app = adsk.core.Application.get()
ui = app.userInterface

PALETTE_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_errorReport'
PALETTE_TITLE = 'Gridfinity error'
PAGE_URL = browserPages.pageUrl(__file__, 'errorReport.html')
WIDTH = 520
HEIGHT = 480

COPY = 'copy'
OPEN_ISSUE = 'openIssue'

palette_handlers = []
currentReport: dict | None = None

DESIGN_INTENTS = {
    adsk.fusion.DesignIntentTypes.PartDesignIntentType: 'part',
    adsk.fusion.DesignIntentTypes.AssemblyDesignIntentType: 'assembly',
    adsk.fusion.DesignIntentTypes.HybridDesignIntentType: 'hybrid',
}
ORIENTATIONS = {
    adsk.core.DefaultModelingOrientations.YUpModelingOrientation: 'Y up',
    adsk.core.DefaultModelingOrientations.ZUpModelingOrientation: 'Z up',
}

def environment(design: adsk.fusion.Design | None) -> list[list[str]]:
    """Versions, and what of the design and preferences changes how things get built"""
    def read(describe) -> str:
        # each on its own, one Fusion can't tell doesn't hide the rest
        try:
            return describe()
        except Exception as err:
            return f'unknown, {err}'
    rows = [
        ['Add-in version', tagUtils.getGeneratorVersion() or 'unknown'],
        ['Fusion version', app.version],
        ['OS', platform.platform()],
        # the preference new designs start with, Fusion doesn't tell the orientation of a design
        ['Modeling orientation', read(lambda: ORIENTATIONS.get(app.preferences.generalPreferences.defaultModelingOrientation, 'unknown'))],
    ]
    if design is None:
        return rows + [['Design', 'none active']]
    return rows + [
        ['Length units', read(lambda: design.unitsManager.defaultLengthUnits)],
        ['Design intent', read(lambda: DESIGN_INTENTS.get(design.designIntent, str(design.designIntent)))],
        ['Timeline', read(lambda: f'yes, {design.timeline.count} features' if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else 'no, direct modeling')],
    ]

def show(title: str, err: BaseException, buildConfig: str | None):
    """Shows the error with the design's shared parameters, buildConfig is what was built, see errorReport.createReport"""
    global currentReport
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        currentReport = errorReport.createReport(title, err, sharedParameters.describeSharedParameters(design), buildConfig, environment(design))
        palette = ui.palettes.itemById(PALETTE_ID)
        if palette is None:
            palette = ui.palettes.add(PALETTE_ID, PALETTE_TITLE, PAGE_URL, True, True, True, WIDTH, HEIGHT)
            # beside the model, out of the way of the command dialog
            palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
            futil.add_handler(palette.incomingFromHTML, palette_incoming_from_html, local_handlers=palette_handlers)
            # a new page asks for the report itself
            return
        palette.isVisible = True
        palette.sendInfoToHTML('update', browserPages.encode(currentReport))
    except Exception as err:
        # the error is in the log already, showing it is the extra
        futil.log(f'{PALETTE_TITLE} not shown, {err}', adsk.core.LogLevels.ErrorLogLevel)

def copyToClipboard(text: str) -> bool:
    """False when it couldn't, the page then copies it itself"""
    try:
        clipboard.copyText(text)
        return True
    except (OSError, subprocess.SubprocessError) as err:
        futil.log(f'{PALETTE_TITLE} report not copied, {err}')
        return False

def palette_incoming_from_html(args: adsk.core.HTMLEventArgs):
    answer = None
    if args.action == browserPages.RESPONSE:
        return
    try:
        if args.action == browserPages.READY:
            answer = currentReport
        elif args.action == COPY:
            answer = {'copied': currentReport is not None and copyToClipboard(currentReport['text'])}
        elif args.action == OPEN_ISSUE:
            copied = currentReport is not None and copyToClipboard(currentReport['text'])
            webbrowser.open(currentReport['issueUrl'] if currentReport is not None else errorReport.ISSUES_URL)
            answer = {'copied': copied}
        else:
            futil.log(f'{PALETTE_TITLE} page sent an unknown action {args.action}')
    except Exception as err:
        futil.log(f'{PALETTE_TITLE} {args.action} failed, {err}', adsk.core.LogLevels.ErrorLogLevel)
    args.returnData = browserPages.NO_ANSWER if answer is None else browserPages.encode(answer)

def stop():
    global palette_handlers
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()
    palette_handlers = []
