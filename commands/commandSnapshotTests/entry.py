import adsk.core, adsk.fusion, traceback
import dataclasses
import os
import pathlib
import shutil
import tempfile
import time
from typing import Callable

from ...lib import fusion360utils as futil
from ...lib.ui import viewportPictures
from ... import config
from ..commandCreateBin import binBuilder
from ..commandCreateBin.inputState import InputState as BinInputState
from ..commandCreateBaseplate import baseplateBuilder
from ..commandCreateBaseplate.inputState import InputState as BaseplateInputState
from . import testCases
from . import snapshots
from . import report
from . import reportPalette

# Shape snapshot tests: every case of tests/e2e/cases is built in a new document and compared with its snapshot
# in tests/e2e/snapshots. Running the tests leaves documents of cases that didn't pass open to look at,
# updating builds new snapshots aside and replaces the current ones once the differences are confirmed

app = adsk.core.Application.get()
ui = app.userInterface

RUN_CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdRunSnapshotTests'
RUN_CMD_NAME = 'Gridfinity tests: run'
# shown on hover over the button, the first paragraph says what it does, the second how, like the generator commands
RUN_CMD_Description = ('Checks generated bins and baseplates against their snapshots.\n\n'
    'Opens the test window listing the cases of tests/e2e/cases, run them all or one at a time. Each builds in a new '
    'document and is compared with its snapshot, documents of cases that didn\'t pass are left open.')
UPDATE_CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdUpdateSnapshots'
UPDATE_CMD_NAME = 'Gridfinity tests: update snapshots'
UPDATE_CMD_Description = ('Records new snapshots of the test cases.\n\n'
    'Opens the snapshots window listing the cases of tests/e2e/cases, refresh them all or one at a time. Each shows '
    'how it differs from its current snapshot, the changed ones are replaced once confirmed.')

# Utilities > Add-ins, out of the way of the generator commands
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
FALLBACK_PANEL_ID = 'SolidCreatePanel'

ROOT_FOLDER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E2E_FOLDER = os.path.join(ROOT_FOLDER, 'tests', 'e2e')
CASES_FOLDER = os.path.join(E2E_FOLDER, 'cases')
SNAPSHOTS_FOLDER = os.path.join(E2E_FOLDER, 'snapshots')
README_PATH = os.path.join(E2E_FOLDER, 'README.md')
RESOURCES_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
STATE_CLASSES = {testCases.GENERATOR_BIN: BinInputState, testCases.GENERATOR_BASEPLATE: BaseplateInputState}

# bodies the tests add are tagged with their role and case, apart from the generator's own tag, see tagUtils
TEST_TAG_GROUP = 'LevMishin.GridfinityGenerator.Tests'
ROLE_RECEIVED = 'received'
ROLE_EXPECTED = 'expected'
# what the subtraction leaves, see snapshots.leftover
ROLE_MISSING = 'missing'
ROLE_UNEXPECTED = 'unexpected'
# a failed case's document holds a component for each, see prepareCaseDocument
COMPONENT_NAMES = {
    ROLE_RECEIVED: 'Received (built now)',
    ROLE_EXPECTED: 'Expected (snapshot)',
    ROLE_MISSING: 'Missing (in snapshot, not built)',
    ROLE_UNEXPECTED: 'Unexpected (built, not in snapshot)',
}
BODY_PREFIXES = {
    ROLE_RECEIVED: 'Received',
    ROLE_EXPECTED: 'Expected',
    ROLE_MISSING: 'Missing',
    ROLE_UNEXPECTED: 'Unexpected',
}

# how the documents of failed cases show them, see showView
BUILT_BODY_OPACITY = 0.3
# the previews of snapshots, the documentation's pictures of models made smaller, see takePreview
PREVIEW_OPTIONS = viewportPictures.PictureOptions(width=480, height=480, transparent=True, margin=0.06, supersample=3, exposure=0.85, saturation=1.4)
PREVIEW_STYLE = 'ShadedWithVisibleEdgesOnlyVisualStyle'
PREVIEW_VIEW = 'isoTopRight'
PREVIEW_COLOR = '#4e79a7'
# the tabs of the test documents, before the case name
DOCUMENT_PREFIX = 'Gridfinity test'
TEST_VISUAL_STYLE = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
# appearances the test documents add for the differences, by role
DIFF_APPEARANCES = {
    ROLE_MISSING: ('Gridfinity test missing', (220, 40, 40)),
    ROLE_UNEXPECTED: ('Gridfinity test unexpected', (40, 180, 70)),
}
# a plain appearance to copy and recolor, the first found, names differ between Fusion versions
BASE_APPEARANCE_NAMES = ['Paint - Enamel Glossy (White)', 'Paint - Enamel Glossy (Yellow)', 'Plastic - Matte (White)', 'Plastic - Glossy (White)', 'Plastic - Translucent Matte (White)']
# the color of the appearance, by its kind
COLOR_PROPERTY_IDS = ['opaque_albedo', 'generic_diffuse', 'layered_diffuse', 'metal_f0']

local_handlers = []
@dataclasses.dataclass
class CaseView:
    """A case left open by the last run, what its document shows can be switched from the report"""
    name: str
    document: adsk.core.Document
    # built now
    bodies: list[adsk.fusion.BRepBody]
    results: list[snapshots.BodyResult]
    # the snapshot and the differences added to the document, the first time they're shown
    expectedBodies: list[adsk.fusion.BRepBody] | None = None
    diffBodies: list[adsk.fusion.BRepBody] | None = None

# by case name
caseViews: dict[str, CaseView] = {}
# an update waiting for confirmation: its staging folder and the snapshots it replaces and removes
pendingUpdate: dict | None = None
lastReport: dict | None = None
# a run or refresh asked for in the report, its kind and case names, none for all of them. It's done in a custom event
# once the page has its answer, so the page draws the progress meanwhile
QUEUE_EVENT_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_snapshotTestsQueue'
queue_handlers = []
queuedJob: tuple[str, set[str] | None] | None = None
# the name and document of the case being built
building: tuple[str, adsk.core.Document] | None = None
documentActivatedHandler = None

def start():
    for (cmdId, name, description, iconFolder, onExecute) in [
        (RUN_CMD_ID, RUN_CMD_NAME, RUN_CMD_Description, 'run', openTests),
        (UPDATE_CMD_ID, UPDATE_CMD_NAME, UPDATE_CMD_Description, 'update', openUpdate),
    ]:
        addCommand(cmdId, name, description, os.path.join(RESOURCES_FOLDER, iconFolder, ''), onExecute)
    global documentActivatedHandler
    # left over when the add-in wasn't stopped
    app.unregisterCustomEvent(QUEUE_EVENT_ID)
    futil.add_handler(app.registerCustomEvent(QUEUE_EVENT_ID), queue_custom_event, local_handlers=queue_handlers)
    # the report marks the case whose document is in the viewport, whichever way it got there
    documentActivatedHandler = futil.add_handler(app.documentActivated, document_activated, local_handlers=queue_handlers)
    reportPalette.annotate = lambda data: {**data, 'shown': shownCase()}

def addCommand(cmdId: str, name: str, description: str, iconFolder: str, onExecute):
    cmd_def = ui.commandDefinitions.itemById(cmdId)
    if not cmd_def:
        # Fusion titles the hover popup with the name only for buttons with icons
        cmd_def = ui.commandDefinitions.addButtonDefinition(cmdId, name, description, iconFolder)
    # without inputs Fusion executes the command right away, no dialog
    def command_created(args: adsk.core.CommandCreatedEventArgs):
        futil.add_handler(args.command.execute, lambda _: runReporting(name, onExecute), local_handlers=local_handlers)
        futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(cmd_def.commandCreated, command_created)
    try:
        panel = commandPanel()
        control = panel.controls.itemById(cmdId) or panel.controls.addCommand(cmd_def)
        # shown on the toolbar, not only in the panel's dropdown
        control.isPromoted = True
    except Exception as err:
        futil.log(f'{name} button not added, {err}', adsk.core.LogLevels.ErrorLogLevel, force_console=True)

def commandPanel() -> adsk.core.ToolbarPanel:
    """Utilities > Add-ins, the Create panel of the generators when that one isn't found"""
    panels = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels
    panel = panels.itemById(PANEL_ID)
    if panel is None:
        futil.log(f'Gridfinity tests panel {PANEL_ID} not found, using {FALLBACK_PANEL_ID}', force_console=True)
        panel = panels.itemById(FALLBACK_PANEL_ID)
    return panel

def stop():
    global queue_handlers, queuedJob
    reportPalette.stop()
    discardPendingUpdate()
    app.unregisterCustomEvent(QUEUE_EVENT_ID)
    if documentActivatedHandler is not None:
        app.documentActivated.remove(documentActivatedHandler)
    queue_handlers = []
    queuedJob = None
    panels = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels
    for cmdId in [RUN_CMD_ID, UPDATE_CMD_ID]:
        for panelId in [PANEL_ID, FALLBACK_PANEL_ID]:
            panel = panels.itemById(panelId)
            control = panel.controls.itemById(cmdId) if panel is not None else None
            if control:
                control.deleteMe()
        command_definition = ui.commandDefinitions.itemById(cmdId)
        if command_definition:
            command_definition.deleteMe()

def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []

def runReporting(name: str, onExecute):
    """Runs the command, its report goes to the report palette and the text commands window"""
    global lastReport
    try:
        startTime = time.perf_counter()
        (kind, cases, pending, message) = onExecute()
        lastReport = report.report(kind, name, cases, time.perf_counter() - startTime, pending, message)
        futil.log(report.reportText(lastReport), force_console=True)
        reportPalette.show(lastReport, {
            'show': showCaseDocument,
            'view': switchCaseView,
            'apply': applyPendingUpdate,
            'discard': discardUpdate,
            'runAll': runAll,
            'run': runOne,
            'tests': backToTests,
            'refreshAll': refreshAll,
            'refresh': refreshOne,
            'closeAll': closeCaseDocuments,
        })
    except:
        ui.messageBox(f'{name}\n\nFailed:\n{traceback.format_exc()}', name)

def buildCase(case: testCases.TestCase) -> tuple[adsk.core.Document, list[adsk.fusion.BRepBody], list[str]]:
    """The case built in a new document, so nothing else in a design moves it or lends it parameters, with its unhealthy timeline features"""
    global building
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    building = (case.name, document)
    nameDocument(document, f'{DOCUMENT_PREFIX} {case.name}')
    design = adsk.fusion.Design.cast(document.products.itemByProductType('DesignProductType'))
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    # a new document takes the design intent of the preferences, only hybrid has room for a body and components side by side
    if design.designIntent != adsk.fusion.DesignIntentTypes.HybridDesignIntentType:
        try:
            design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
        except Exception as err:
            futil.log(f'{reportPalette.PALETTE_TITLE} test document stays {design.designIntent} design intent, {err}', force_console=True)
    settings = testCases.caseSettings(case)
    if case.generator == testCases.GENERATOR_BIN:
        bodies = binBuilder.buildBin(design, case.state, settings)
    else:
        bodies = baseplateBuilder.buildBaseplate(design, case.state, settings)
    for body in bodies:
        tagTestBody(body, case.name, ROLE_RECEIVED)
    return (document, bodies, unhealthyFeatures(design.timeline))

# what Fusion found wrong with a timeline feature. Groups and some other items are of unknown health, nothing to report
HEALTH_NAMES = {
    adsk.fusion.FeatureHealthStates.WarningFeatureHealthState: 'warning',
    adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState: 'error',
}

def unhealthyFeatures(timeline: adsk.fusion.Timeline) -> list[str]:
    """Timeline features Fusion has a warning or error for, with its message, those in groups too"""
    # by feature and message, a feature in a group may be listed on its own as well, the group's name is kept. Fusion
    # refuses the timeline index of some features, it isn't used
    notes: dict[tuple[str, str], str] = {}
    def look(items, groupName: str):
        for index in range(items.count):
            item = items.item(index)
            group = adsk.fusion.TimelineGroup.cast(item) if item.isGroup else None
            if group is not None:
                look(group, group.name)
            elif item.healthState in HEALTH_NAMES:
                message = item.errorOrWarningMessage or 'no message'
                key = (item.name, message)
                if groupName or key not in notes:
                    place = f'{groupName} > {item.name}' if groupName else item.name
                    notes[key] = f'timeline {place}, {HEALTH_NAMES[item.healthState]}: {message}'
    look(timeline, '')
    return list(notes.values())

def buildFailure(case: testCases.TestCase, err: Exception) -> str:
    """
    The error with the last line of the add-in's code it went through, Fusion's own errors don't say what was called.
    The whole traceback goes to the text commands window
    """
    futil.log(f'{reportPalette.PALETTE_TITLE} {case.name} build failed\n{"".join(traceback.format_exception(err))}', adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    frames = [frame for frame in traceback.extract_tb(err.__traceback__) if frame.filename.startswith(ROOT_FOLDER)]
    if not frames:
        return str(err)
    frame = frames[-1]
    return f'{err} ({os.path.relpath(frame.filename, ROOT_FOLDER)}:{frame.lineno} {frame.line})'

def loadCases() -> list[testCases.TestCase]:
    return testCases.loadCases(CASES_FOLDER, STATE_CLASSES)

# what a test result means for an update
UPDATE_STATUSES = {
    snapshots.STATUS_PASS: report.STATUS_UNCHANGED,
    snapshots.STATUS_REVIEW: report.STATUS_REVIEW,
    snapshots.STATUS_FAIL: report.STATUS_CHANGED,
}

def bodyReports(results: list[snapshots.BodyResult], statuses: dict[str, str] = None) -> list[dict]:
    """statuses: the report's status of each test result, see UPDATE_STATUSES"""
    return [
        report.body(
            result.name,
            (statuses or {}).get(result.status, result.status),
            result.changes,
            snapshots.leftoverData(result.missing),
            snapshots.leftoverData(result.extra),
            result.notes,
        )
        for result in results
    ]

def openTests() -> tuple:
    """
    The test window lists the cases to run one at a time or all together. Cases run before keep their results, as long
    as the last report is of a run. An update waiting for confirmation is discarded, its report goes
    """
    discardPendingUpdate()
    previous = {}
    if lastReport is not None and lastReport['kind'] == report.KIND_RUN:
        previous = {item['name']: item for item in lastReport['cases']}
    cases = [previous.get(case.name) or listedCase(case, report.STATUS_UNTESTED) for case in loadCases()]
    return (report.KIND_RUN, cases, None, '')

def runAll(_) -> dict | None:
    """The report's Run all button"""
    return queueJob(report.KIND_RUN, None)

def runOne(data) -> dict | None:
    """The Run button of a case"""
    name = data.get('case') if isinstance(data, dict) else None
    return queueJob(report.KIND_RUN, {name}) if name else None

def queueJob(kind: str, names: set[str] | None) -> dict | None:
    """
    The report's run and refresh buttons, for the cases of these names, all of them for none. The page's answer has
    them queued, they're built in a custom event after it, see queue_custom_event
    """
    global lastReport, queuedJob
    if queuedJob is not None:
        return lastReport
    if names is None or lastReport is None or lastReport['kind'] != kind:
        (_, cases, pending, message) = openTests() if kind == report.KIND_RUN else openUpdate()
        lastReport = report.report(kind, RUN_CMD_NAME if kind == report.KIND_RUN else UPDATE_CMD_NAME, cases, 0, pending, message)
    cases = [case for case in loadCases() if names is None or case.name in names]
    if len(cases) == 0:
        return lastReport
    # refreshing all of them starts the update waiting for confirmation over, refreshing some adds to it
    if kind == report.KIND_RUN or names is None:
        discardPendingUpdate()
    queued = [listedCase(case, report.STATUS_QUEUED) for case in cases]
    lastReport = {**report.withCases(lastReport, queued, 0, '', report.progress(0, len(cases), cases[0].name)), 'pending': None}
    queuedJob = (kind, names)
    app.fireCustomEvent(QUEUE_EVENT_ID)
    return lastReport

def queue_custom_event(args: adsk.core.CustomEventArgs):
    global queuedJob, lastReport
    if queuedJob is None:
        return
    (kind, names) = queuedJob
    try:
        if kind == report.KIND_RUN:
            runSelected(names)
        else:
            refreshSelected(names)
    finally:
        queuedJob = None
        if lastReport is not None:
            lastReport = {**lastReport, 'progress': None}
            reportPalette.update(lastReport)

def shownCase() -> str | None:
    """The case whose document is in the viewport, the one being built too"""
    active = app.activeDocument
    if active is None:
        return None
    documents = [(view.name, view.document) for view in caseViews.values()] + ([building] if building is not None else [])
    return next((name for (name, document) in documents if document.isValid and document == active), None)

def document_activated(args: adsk.core.DocumentEventArgs):
    if lastReport is not None:
        reportPalette.update(lastReport, handleEvents=False)

def runSelected(names: set[str] | None) -> dict | None:
    """Runs the cases of these names, all of them for none, their results replace theirs in the report, see queueJob"""
    global lastReport
    try:
        startTime = time.perf_counter()
        cases = [case for case in loadCases() if names is None or case.name in names]
        caseReports = runCases(cases, progressShower(cases, startTime))
        message = ''
        if len(caseViews) > 0:
            message = f'{len(caseViews)} document(s) of cases that did not pass are left open, switch what they show with Diff, Built and Snapshot'
        lastReport = report.withCases(lastReport, caseReports, time.perf_counter() - startTime, message)
        futil.log(report.reportText(lastReport), force_console=True)
    except:
        ui.messageBox(f'{RUN_CMD_NAME}\n\nFailed:\n{traceback.format_exc()}', RUN_CMD_NAME)
    return lastReport

def progressShower(cases: list[testCases.TestCase], startTime: float) -> Callable[[int, list[dict]], None]:
    """Redraws the report before each case, with the cases done so far, the one about to be built and those after it"""
    def showProgress(index: int, done: list[dict]):
        global lastReport
        waiting = [listedCase(case, report.STATUS_RUNNING if position == 0 else report.STATUS_QUEUED) for (position, case) in enumerate(cases[index:])]
        runProgress = report.progress(index, len(cases), cases[index].name)
        lastReport = report.withCases(lastReport, done + waiting, time.perf_counter() - startTime, '', runProgress)
        reportPalette.update(lastReport)
    return showProgress

def runCases(cases: list[testCases.TestCase], showProgress: Callable[[int, list[dict]], None]) -> list[dict]:
    """
    Each case built and compared with its snapshot. The document of a case run before is closed first, the document of
    one that doesn't pass is left open showing the differences. showProgress gets the index of the case about to be
    built and the reports of those before it
    """
    originalDocument = app.activeDocument
    caseReports = []
    for (index, case) in enumerate(cases):
        showProgress(index, caseReports)
        previous = caseViews.pop(case.name, None)
        if previous is not None and previous.document.isValid:
            if originalDocument == previous.document:
                originalDocument = None
            previous.document.close(False)
        caseReports.append(runCase(case))
        adsk.doEvents()
    openDocuments = [caseViews[case.name].document for case in cases if case.name in caseViews]
    if len(openDocuments) > 0:
        openDocuments[0].activate()
        frameBesidePalette()
    elif originalDocument is not None and originalDocument.isValid:
        originalDocument.activate()
    return caseReports

def runCase(case: testCases.TestCase) -> dict:
    document = None
    notes = []
    try:
        (document, bodies, unhealthy) = buildCase(case)
        results = snapshots.compareSnapshot(os.path.join(SNAPSHOTS_FOLDER, case.name), bodies)
        # the shape may match all the same, the case fails for what Fusion found wrong in building it
        notes += unhealthy
    except Exception as err:
        results = [snapshots.BodyResult('', snapshots.STATUS_FAIL, [f'build failed, {buildFailure(case, err)}'])]
    status = snapshots.worstStatus([result.status for result in results] + ([snapshots.STATUS_FAIL] if notes else []))
    view = None
    if document is not None:
        if status == snapshots.STATUS_PASS:
            document.close(False)
        else:
            caseViews[case.name] = CaseView(case.name, document, bodies, results)
            view = report.VIEW_DIFF
            try:
                prepareCaseDocument(caseViews[case.name])
                showView(caseViews[case.name], view)
                frameBesidePalette()
            except Exception as err:
                notes.append(f'differences not shown, {err}')
    return report.case(case.name, case.description, status, bodyReports(results), notes, view, snapshotPreviews(case.name))

def listedCase(case: testCases.TestCase, status: str) -> dict:
    """A case waiting to be run or refreshed, or being run"""
    return report.case(case.name, case.description, status, previews=snapshotPreviews(case.name))

def previewUrl(folder: str) -> str | None:
    """The preview in a snapshot folder for the page, changed with the file so the page doesn't show an old one"""
    path = os.path.join(folder, snapshots.PREVIEW_FILE)
    if not os.path.isfile(path):
        return None
    return f'{pathlib.Path(path).as_uri()}?v={os.stat(path).st_mtime_ns}'

def snapshotPreviews(name: str) -> dict:
    return {'snapshot': previewUrl(os.path.join(SNAPSHOTS_FOLDER, name))}

def takePreview(document: adsk.core.Document, bodies: list[adsk.fusion.BRepBody], name: str, folder: str) -> list[str]:
    """
    A picture of the bodies into the folder as the documentation pictures them, finished by the report's page. The
    case's document is the active one, it's closed after, its look can change. The warnings of the picture
    """
    design = adsk.fusion.Design.cast(document.products.itemByProductType('DesignProductType'))
    viewportPictures.hideHelpers(design)
    base = viewportPictures.firstLibraryAppearance(viewportPictures.COLOR_BASE_PREFIXES)
    appearance = viewportPictures.colorAppearance(design, base, PREVIEW_COLOR)
    for body in bodies:
        body.appearance = appearance
    viewport = app.activeViewport
    viewportPictures.frame(viewport, PREVIEW_STYLE, False, PREVIEW_VIEW)
    return viewportPictures.viewportPicture(viewport, name, os.path.join(folder, snapshots.PREVIEW_FILE), PREVIEW_OPTIONS, reportPalette.finishPicture)

def writeReadme():
    """The case list, with the previews of the snapshots, see testCases.casesMarkdown"""
    with open(README_PATH, 'w', encoding='utf-8') as file:
        file.write(testCases.casesMarkdown(CASES_FOLDER))

def diffAppearance(design: adsk.fusion.Design, role: str, fallback: adsk.core.Appearance | None) -> adsk.core.Appearance | None:
    """
    The red or green appearance of the differences, a library appearance copied into the design and recolored,
    as Autodesk's own sample does it. fallback: copied when none of the library ones is found
    """
    (name, color) = DIFF_APPEARANCES[role]
    appearance = design.appearances.itemByName(name)
    if appearance is not None:
        return appearance
    source = libraryAppearance() or fallback
    if source is None:
        futil.log(f'{reportPalette.PALETTE_TITLE} no appearance to color the {role} material', adsk.core.LogLevels.WarningLogLevel, force_console=True)
        return None
    appearance = design.appearances.addByCopy(source, name)
    colorProperty = appearanceColor(appearance)
    if colorProperty is None:
        futil.log(f'{reportPalette.PALETTE_TITLE} appearance {source.name} has no color to set', adsk.core.LogLevels.WarningLogLevel, force_console=True)
        return appearance
    colorProperty.value = adsk.core.Color.create(*color, 255)
    futil.log(f'{reportPalette.PALETTE_TITLE} {role} material colored by {source.name}, its {colorProperty.name} ({colorProperty.id})', force_console=True)
    return appearance

def libraryAppearance() -> adsk.core.Appearance | None:
    """The first of BASE_APPEARANCE_NAMES found, the appearance library first, a lookup some libraries refuse is skipped"""
    libraries = [app.materialLibraries.item(index) for index in range(app.materialLibraries.count)]
    libraries.sort(key=lambda library: 'Appearance' not in library.name)
    for library in libraries:
        for baseName in BASE_APPEARANCE_NAMES:
            try:
                found = library.appearances.itemByName(baseName)
            except Exception:
                found = None
            if found is not None:
                return found
    return None

def appearanceColor(appearance: adsk.core.Appearance) -> adsk.core.ColorProperty | None:
    """The color it's drawn with, named Color in most appearances, else by its id, else the first color it has"""
    properties = appearance.appearanceProperties
    lookups = [lambda: properties.itemByName('Color')] + [lambda propertyId=propertyId: properties.itemById(propertyId) for propertyId in COLOR_PROPERTY_IDS]
    lookups += [lambda index=index: properties.item(index) for index in range(properties.count)]
    for lookup in lookups:
        try:
            found = adsk.core.ColorProperty.cast(lookup())
        except Exception:
            found = None
        if found is not None:
            return found
    return None

def tagTestBody(body: adsk.fusion.BRepBody, caseName: str, role: str):
    body.attributes.add(TEST_TAG_GROUP, 'role', role)
    body.attributes.add(TEST_TAG_GROUP, 'case', caseName)

def prepareCaseDocument(view: CaseView):
    """
    The built bodies and their component named as received, once compared, the comparison pairs them with the
    snapshot by the generator's names. The root is active again for the components of the other test bodies
    """
    design = adsk.fusion.Design.cast(view.document.products.itemByProductType('DesignProductType'))
    design.activateRootComponent()
    for body in view.bodies:
        if body.parentComponent != design.rootComponent:
            body.parentComponent.name = COMPONENT_NAMES[ROLE_RECEIVED]
        body.name = f'{BODY_PREFIXES[ROLE_RECEIVED]}: {body.name}'

def addTestBodies(design: adsk.fusion.Design, caseName: str, role: str, shapes: list[tuple[adsk.fusion.BRepBody, str]]) -> list[adsk.fusion.BRepBody]:
    """
    Shapes in memory added as real bodies, in a component of their own when the design takes one, in a base feature
    at the end of the timeline. Fusion draws a whole bin as custom graphics slowly, real bodies it draws as fast as the built ones
    """
    root = design.rootComponent
    try:
        component = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
        component.name = COMPONENT_NAMES[role]
    except Exception as err:
        futil.log(f'{reportPalette.PALETTE_TITLE} {role} bodies go to the root, {err}', force_console=True)
        component = root
    baseFeature = component.features.baseFeatures.add()
    baseFeature.name = COMPONENT_NAMES[role]
    baseFeature.startEdit()
    for (shape, _) in shapes:
        component.bRepBodies.add(shape, baseFeature)
    baseFeature.finishEdit()
    # named and tagged once the edit is finished, Fusion may rebuild a body then and drop what was set before
    bodies = [baseFeature.bodies.item(index) for index in range(baseFeature.bodies.count)]
    if len(bodies) != len(shapes):
        futil.log(f'{reportPalette.PALETTE_TITLE} {caseName} {role}: {len(shapes)} shape(s) added, {len(bodies)} bodies made', adsk.core.LogLevels.WarningLogLevel, force_console=True)
    for (body, (_, name)) in zip(bodies, shapes):
        body.name = f'{BODY_PREFIXES[role]}: {name}'
    for body in bodies:
        tagTestBody(body, caseName, role)
    return bodies

def addExpectedBodies(view: CaseView, design: adsk.fusion.Design) -> list[adsk.fusion.BRepBody]:
    return addTestBodies(design, view.name, ROLE_EXPECTED, [(result.reference, result.name) for result in view.results if result.reference is not None])

def addDiffBodies(view: CaseView, design: adsk.fusion.Design) -> list[adsk.fusion.BRepBody]:
    """The material missing from the received bodies shaded red, the unexpected material in them green"""
    bodies = []
    for (role, attribute) in [(ROLE_MISSING, 'missing'), (ROLE_UNEXPECTED, 'extra')]:
        shapes = [(getattr(result, attribute), result.name) for result in view.results if getattr(result, attribute) is not None]
        if len(shapes) == 0:
            continue
        added = addTestBodies(design, view.name, role, shapes)
        try:
            appearance = diffAppearance(design, role, view.bodies[0].appearance if len(view.bodies) > 0 else None)
            for body in added:
                if appearance is not None:
                    body.appearance = appearance
        except Exception as err:
            # shown on the first run, before the report the notes would go to
            futil.log(f'{reportPalette.PALETTE_TITLE} {view.name} {role} material not colored, {err}', adsk.core.LogLevels.WarningLogLevel, force_console=True)
        bodies.extend(added)
    return bodies

def showView(view: CaseView, mode: str):
    """
    The document shows the differences over the see-through received bodies, or the received or the expected bodies
    alone. Each is a component of bodies, only those of the mode are shown
    """
    design = adsk.fusion.Design.cast(view.document.products.itemByProductType('DesignProductType'))
    if mode == report.VIEW_DIFF and view.diffBodies is None:
        view.diffBodies = addDiffBodies(view, design)
    if mode == report.VIEW_SNAPSHOT and view.expectedBodies is None:
        view.expectedBodies = addExpectedBodies(view, design)
    for body in view.bodies:
        body.isLightBulbOn = mode != report.VIEW_SNAPSHOT
        body.opacity = 1.0 if mode == report.VIEW_BUILT else BUILT_BODY_OPACITY
    for body in view.expectedBodies or []:
        body.isLightBulbOn = mode == report.VIEW_SNAPSHOT
    for body in view.diffBodies or []:
        body.isLightBulbOn = mode == report.VIEW_DIFF
    # the edges show where faces meet, shading alone hides small steps
    app.activeViewport.visualStyle = TEST_VISUAL_STYLE
    app.activeViewport.refresh()

def frameBesidePalette():
    """
    The active document's model fit into the part of the viewport left of the report palette, zoomed out to fit there
    and panned left by half the palette, so none of it is under the palette
    """
    viewport = app.activeViewport
    covered = reportPalette.coveredWidth()
    camera = viewport.camera
    camera.isFitView = True
    camera.isSmoothTransition = False
    viewport.camera = camera
    if covered <= 0 or covered >= viewport.width:
        return
    camera = viewport.camera
    camera.viewExtents = camera.viewExtents * viewport.width / (viewport.width - covered)
    camera.isSmoothTransition = False
    viewport.camera = camera
    # moving the camera right by the model length of half the palette moves the model left by as much on screen
    camera = viewport.camera
    center = viewport.viewToModelSpace(adsk.core.Point2D.create(viewport.width / 2, viewport.height / 2))
    shifted = viewport.viewToModelSpace(adsk.core.Point2D.create(viewport.width / 2 + covered / 2, viewport.height / 2))
    offset = center.vectorTo(shifted)
    eye = camera.eye
    target = camera.target
    eye.translateBy(offset)
    target.translateBy(offset)
    camera.eye = eye
    camera.target = target
    camera.isSmoothTransition = False
    viewport.camera = camera
    viewport.refresh()

def caseView(data) -> CaseView | None:
    """The case the report asks about, while its document is still open"""
    view = caseViews.get(data.get('case', '')) if isinstance(data, dict) else None
    if view is None or not view.document.isValid:
        ui.messageBox('The document of this case is closed already, run the tests again to see it', reportPalette.PALETTE_TITLE)
        return None
    return view

def nameDocument(document: adsk.core.Document, name: str):
    """The tab named after the case instead of Untitled, the document stays unsaved, where Fusion lets it be named"""
    try:
        document.name = name
    except Exception as err:
        futil.log(f'{reportPalette.PALETTE_TITLE} document stays {document.name}, {err}', adsk.core.LogLevels.WarningLogLevel, force_console=True)

def closeCaseDocuments(_) -> dict | None:
    """The report's Close test documents button, the documents of the cases that didn't pass are closed unsaved"""
    global lastReport
    for view in caseViews.values():
        if view.document.isValid:
            view.document.close(False)
    caseViews.clear()
    if lastReport is None:
        return None
    cases = [{**item, 'hasDocument': False, 'view': None} for item in lastReport['cases']]
    lastReport = {**lastReport, 'cases': cases, 'message': 'Test documents closed'}
    return lastReport

def showCaseDocument(data) -> None:
    """The report's Show button, the case's document comes to the front"""
    view = caseView(data)
    if view is not None:
        view.document.activate()
        frameBesidePalette()

def switchCaseView(data) -> dict | None:
    """The report's Diff, Built and Snapshot buttons"""
    view = caseView(data)
    mode = data.get('mode') if isinstance(data, dict) else None
    if view is None or mode not in report.VIEWS or lastReport is None:
        return None
    view.document.activate()
    showView(view, mode)
    for item in lastReport['cases']:
        if item['name'] == data['case']:
            item['view'] = mode
    return lastReport

def openUpdate() -> tuple:
    """The update window lists the cases, nothing is built until it's asked to refresh them"""
    discardPendingUpdate()
    cases = [listedCase(case, report.STATUS_UNTESTED) for case in loadCases()]
    return (report.KIND_UPDATE, cases, None, '')

def refreshAll(_) -> dict | None:
    """The update report's Refresh all button, snapshots of deleted cases go too"""
    return queueJob(report.KIND_UPDATE, None)

def refreshOne(data) -> dict | None:
    """The Refresh button of a case"""
    name = data.get('case') if isinstance(data, dict) else None
    return queueJob(report.KIND_UPDATE, {name}) if name else None

def refreshSelected(names: set[str] | None) -> dict | None:
    """
    New snapshots of the cases of these names, all of them for none, go to a temporary folder first, compared with the
    ones in place the same way the tests do. The report asks to confirm, only new and changed ones replace them then,
    unchanged ones keep their files. Refreshing some cases adds them to the update waiting for confirmation, in place
    of what it had for them, refreshing all starts it over, see queueJob
    """
    global lastReport, pendingUpdate
    previous = pendingUpdate if names is not None else None
    if previous is None:
        discardPendingUpdate()
    try:
        startTime = time.perf_counter()
        allCases = loadCases()
        cases = [case for case in allCases if names is None or case.name in names]
        stagingFolder = previous['staging'] if previous is not None else tempfile.mkdtemp(prefix='gridfinity_snapshots_')
        (caseReports, toApply, toPreview) = stageSnapshots(cases, stagingFolder, progressShower(cases, startTime))
        if previous is not None:
            refreshed = {case.name for case in cases}
            toApply = [name for name in previous['apply'] if name not in refreshed] + toApply
            toPreview = [name for name in previous['previews'] if name not in refreshed] + toPreview

        # snapshots of deleted cases go too
        toRemove = previous['remove'] if previous is not None else []
        if names is None and os.path.isdir(SNAPSHOTS_FOLDER):
            caseNames = {case.name for case in allCases}
            toRemove = [name for name in sorted(os.listdir(SNAPSHOTS_FOLDER)) if os.path.isdir(os.path.join(SNAPSHOTS_FOLDER, name)) and name not in caseNames]
        caseReports.extend(report.case(name, '', report.STATUS_REMOVED, [], ['no case left']) for name in toRemove)

        pending = None
        message = ''
        if len(toApply) == 0 and len(toRemove) == 0 and len(toPreview) == 0:
            shutil.rmtree(stagingFolder, ignore_errors=True)
            pendingUpdate = None
            message = 'All snapshots are up to date, nothing to replace'
        else:
            pendingUpdate = {'staging': stagingFolder, 'apply': toApply, 'remove': toRemove, 'previews': toPreview}
            pending = {'replace': len(toApply), 'remove': len(toRemove), 'previews': len(toPreview), 'folder': SNAPSHOTS_FOLDER}
        lastReport = {**report.withCases(lastReport, caseReports, time.perf_counter() - startTime, message), 'pending': pending}
        futil.log(report.reportText(lastReport), force_console=True)
    except:
        ui.messageBox(f'{UPDATE_CMD_NAME}\n\nFailed:\n{traceback.format_exc()}', UPDATE_CMD_NAME)
    return lastReport

def stageSnapshots(cases: list[testCases.TestCase], stagingFolder: str, showProgress: Callable[[int, list[dict]], None]) -> tuple[list[dict], list[str], list[str]]:
    """
    The reports of the cases with their new snapshots in the staging folder, the names of those to copy in place, and
    of the unchanged ones whose snapshot has no preview yet, only the preview is copied. A preview of the same shape
    is left as it is, it would change with how Fusion draws
    """
    originalDocument = app.activeDocument
    caseReports = []
    toApply = []
    toPreview = []
    for (index, case) in enumerate(cases):
        showProgress(index, caseReports)
        document = None
        currentFolder = os.path.join(SNAPSHOTS_FOLDER, case.name)
        try:
            (document, bodies, unhealthy) = buildCase(case)
            stagedFolder = os.path.join(stagingFolder, case.name)
            snapshots.saveSnapshot(stagedFolder, bodies)
            # saved all the same, the warning is for whoever reviews the change
            notes = [f'warning, {note}' for note in unhealthy]
            try:
                notes += [f'preview, {warning}' for warning in takePreview(document, bodies, case.name, stagedFolder)]
            except Exception as err:
                notes.append(f'preview not taken, {err}')
            previews = {**snapshotPreviews(case.name), 'new': previewUrl(stagedFolder)}
            if not snapshots.hasSnapshot(currentFolder):
                caseReports.append(report.case(case.name, case.description, report.STATUS_NEW, [report.body(body.name, report.STATUS_NEW) for body in bodies], notes, previews=previews))
                toApply.append(case.name)
            else:
                results = snapshots.compareSnapshot(currentFolder, bodies)
                status = UPDATE_STATUSES[snapshots.worstStatus([result.status for result in results])]
                if status != report.STATUS_UNCHANGED:
                    toApply.append(case.name)
                elif previews['snapshot'] is None and previews['new'] is not None:
                    toPreview.append(case.name)
                    notes.append('preview added')
                caseReports.append(report.case(case.name, case.description, status, bodyReports(results, UPDATE_STATUSES), notes, previews=previews))
        except Exception as err:
            caseReports.append(report.case(case.name, case.description, report.STATUS_FAIL, [], [f'build failed, its snapshot stays as it is, {buildFailure(case, err)}']))
        if document is not None:
            document.close(False)
        adsk.doEvents()
    if originalDocument is not None and originalDocument.isValid:
        originalDocument.activate()
    return (caseReports, toApply, toPreview)

def applyPendingUpdate(_) -> dict | None:
    """The report's Replace button"""
    global lastReport
    if pendingUpdate is None or lastReport is None:
        return None
    for name in pendingUpdate['apply']:
        target = os.path.join(SNAPSHOTS_FOLDER, name)
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(os.path.join(pendingUpdate['staging'], name), target)
    for name in pendingUpdate['remove']:
        shutil.rmtree(os.path.join(SNAPSHOTS_FOLDER, name))
    for name in pendingUpdate['previews']:
        shutil.copyfile(os.path.join(pendingUpdate['staging'], name, snapshots.PREVIEW_FILE), os.path.join(SNAPSHOTS_FOLDER, name, snapshots.PREVIEW_FILE))
    message = f'Replaced {len(pendingUpdate["apply"])} and removed {len(pendingUpdate["remove"])} snapshot(s)'
    if pendingUpdate['previews']:
        message += f', added {len(pendingUpdate["previews"])} preview(s)'
    message += ', review them with git diff'
    try:
        writeReadme()
    except Exception as err:
        message += f'. {os.path.relpath(README_PATH, E2E_FOLDER)} not written, {err}'
    discardPendingUpdate()
    lastReport = {**lastReport, 'pending': None, 'message': message, 'cases': withSnapshotPreviews(lastReport['cases'])}
    futil.log(message, force_console=True)
    return lastReport

def withSnapshotPreviews(cases: list[dict]) -> list[dict]:
    """The cases showing the previews of the snapshots in place, the new ones are gone with the staging folder"""
    return [{**item, 'previews': snapshotPreviews(item['name'])} for item in cases]

def backToTests(_) -> dict:
    """The update report's Back to tests button, the cases listed to run again"""
    global lastReport
    discardPendingUpdate()
    (kind, cases, pending, message) = openTests()
    lastReport = report.report(kind, RUN_CMD_NAME, cases, 0, pending, message)
    return lastReport

def discardUpdate(_) -> dict | None:
    """The report's Discard button"""
    global lastReport
    if lastReport is None:
        return None
    discardPendingUpdate()
    lastReport = {**lastReport, 'pending': None, 'message': 'Nothing replaced, the new snapshots are discarded', 'cases': withSnapshotPreviews(lastReport['cases'])}
    return lastReport

def discardPendingUpdate():
    global pendingUpdate
    if pendingUpdate is not None:
        shutil.rmtree(pendingUpdate['staging'], ignore_errors=True)
    pendingUpdate = None
