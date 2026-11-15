import adsk.core, adsk.fusion
import os

from ...lib import tagUtils
from ...lib import settingsUtils
from ...lib import configJson
from ...lib import fusion360utils as futil
from ...lib.ui import browserPages
from ...lib.ui import configButtons
from ...lib.ui.buttonRow import Button
from ... import config
from ..commandCreateBin import entry as binEntry
from ..commandCreateBaseplate import entry as baseplateEntry

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdShowSettings'
CMD_NAME = 'Gridfinity settings'
CMD_Description = 'Show the settings this bin or baseplate was generated with'
# a bin with a cog, shown beside the context menu item
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')
# the context menu item opening the generator's dialog to rebuild the body, as the Rebuild button of the window does
REBUILD_CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdRebuild'
REBUILD_CMD_NAME = 'Gridfinity rebuild'
# a bin with a wrench
REBUILD_ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'rebuild', '')
REBUILD_CMD_DESCRIPTION = 'Open the generator dialog with the settings of this bin or baseplate to build it again in its place, keeping the features after it'

SETTINGS_TEXT_INPUT = 'settings_text'
SETTINGS_BROWSER = 'settings'
SETTINGS_HTML_URL = browserPages.pageUrl(__file__, 'settings.html')
TAG_TITLES = {
    tagUtils.TAG_BIN: 'Gridfinity bin',
    tagUtils.TAG_BASEPLATE: 'Gridfinity baseplate',
}
# the dialog each generator opens with a cloned config, see startWithConfig
CLONE_COMMANDS = {
    tagUtils.TAG_BIN: binEntry,
    tagUtils.TAG_BASEPLATE: baseplateEntry,
}
# generators that rebuild a body in place, see binEntry.startRebuild and baseplateEntry.startRebuild
REBUILD_COMMANDS = {
    tagUtils.TAG_BIN: binEntry,
    tagUtils.TAG_BASEPLATE: baseplateEntry,
}
REBUILD_ACTION = 'rebuild'
# the page's height, what the dialog has room for at its initial size. Fusion makes a page as tall as its content up
# to its maximum height and scrolls the dialog then, the page scrolls the settings itself, see html/settings.html
PAGE_HEIGHT = 340

local_handlers = []
markingMenuHandler = None
# starting a command can clear the selection, so the body and its tag are kept from when the menu opened
menuTag = None

def selectedTag() -> tuple[adsk.fusion.BRepBody, str, dict] | None:
    """The single selected generated body, native, with its tag, also when one of its faces is selected"""
    if ui.activeSelections.count != 1:
        return None
    entity = ui.activeSelections.item(0).entity
    body = adsk.fusion.BRepBody.cast(entity)
    if body is None:
        face = adsk.fusion.BRepFace.cast(entity)
        body = face.body if face is not None else None
    if body is None:
        return None
    # bins in their own component are selected through an occurrence, the tag sits on the body itself
    if body.assemblyContext is not None:
        body = body.nativeObject
    tag = tagUtils.readBodyTag(body)
    return (body, *tag) if tag is not None else None

def canRebuild(tag: tuple[adsk.fusion.BRepBody, str, dict] | None) -> bool:
    """Bodies generated before the generator kept the config can't be rebuilt"""
    return tag is not None and tag[1] in REBUILD_COMMANDS and isinstance(tag[2].get('config'), dict)

def startRebuild(tag: tuple[adsk.fusion.BRepBody, str, dict]):
    (body, tagName, value) = tag
    REBUILD_COMMANDS[tagName].startRebuild(body, value)

def parameterExpression(name: str) -> str | None:
    design = adsk.fusion.Design.cast(app.activeProduct)
    parameter = design.userParameters.itemByName(name) if design is not None else None
    return parameter.expression if parameter is not None else None

def start():
    global markingMenuHandler
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)
    rebuild_def = ui.commandDefinitions.itemById(REBUILD_CMD_ID)
    if not rebuild_def:
        rebuild_def = ui.commandDefinitions.addButtonDefinition(REBUILD_CMD_ID, REBUILD_CMD_NAME, REBUILD_CMD_DESCRIPTION, REBUILD_ICON_FOLDER)
    futil.add_handler(rebuild_def.commandCreated, rebuild_command_created)
    markingMenuHandler = futil.add_handler(ui.markingMenuDisplaying, marking_menu_displaying, local_handlers=local_handlers)

def stop():
    global markingMenuHandler
    if markingMenuHandler is not None:
        ui.markingMenuDisplaying.remove(markingMenuHandler)
        markingMenuHandler = None
    for cmdId in [CMD_ID, REBUILD_CMD_ID]:
        command_definition = ui.commandDefinitions.itemById(cmdId)
        if command_definition:
            command_definition.deleteMe()

def marking_menu_displaying(args: adsk.core.MarkingMenuEventArgs):
    global menuTag
    try:
        menuTag = selectedTag()
        if menuTag is None:
            return
        controls = args.linearMarkingMenu.controls
        controls.addSeparator()
        controls.addCommand(ui.commandDefinitions.itemById(CMD_ID))
        if canRebuild(menuTag):
            controls.addCommand(ui.commandDefinitions.itemById(REBUILD_CMD_ID))
    except Exception as err:
        futil.log(f'{CMD_NAME} context menu failed, {err}')

def command_created(args: adsk.core.CommandCreatedEventArgs):
    tag = selectedTag() or menuTag
    command = args.command
    command.isOKButtonVisible = False
    command.cancelButtonText = 'Close'
    if tag is None:
        command.commandInputs.addTextBoxCommandInput(SETTINGS_TEXT_INPUT, '', 'Select a generated bin or baseplate.', 1, True)
        return
    (body, tagName, value) = tag
    command.setDialogInitialSize(450, 500)
    # the settings and their buttons in one page, the buttons stay above the settings as they scroll
    browser = command.commandInputs.addBrowserCommandInput(SETTINGS_BROWSER, '', SETTINGS_HTML_URL, PAGE_HEIGHT, PAGE_HEIGHT)
    browser.isFullWidth = True
    futil.add_handler(command.incomingFromHTML, lambda args: command_incoming_from_html(args, body, tagName, value), local_handlers=local_handlers)
    futil.add_handler(command.destroy, command_destroy, local_handlers=local_handlers)

def rebuild_command_created(args: adsk.core.CommandCreatedEventArgs):
    """Opens the generator's dialog in place of this command, which has nothing to show"""
    tag = selectedTag() or menuTag
    try:
        if not canRebuild(tag):
            ui.messageBox('Select a generated bin or baseplate to rebuild.', REBUILD_CMD_NAME)
            return
        startRebuild(tag)
    except Exception as err:
        futil.handle_error(f'{REBUILD_CMD_NAME} failed, {err}', show_message_box=True)

def command_incoming_from_html(args: adsk.core.HTMLEventArgs, body: adsk.fusion.BRepBody, tagName: str, value: dict):
    browserPages.handleMessage(args, pageHandlers(body, tagName, value))

def pageHandlers(body: adsk.fusion.BRepBody, tagName: str, value: dict) -> dict[str, browserPages.Handler]:
    """
    The page gets the settings and the config buttons, bodies generated before the generator kept the config have
    none, see html/settings.html
    """
    page = {
        'title': TAG_TITLES.get(tagName, CMD_NAME),
        'settings': settingsUtils.settingsHtml(value, parameterExpression),
        'buttons': [],
    }
    if not isinstance(value.get('config'), dict):
        return {browserPages.READY: lambda _: page}
    # tag names are the generator names of configJson
    generatorTitle = configJson.GENERATOR_TITLES[tagName]
    moreButtons = []
    if tagName in REBUILD_COMMANDS:
        moreButtons.append((
            Button(REBUILD_ACTION, 'Rebuild', f'Open the {generatorTitle} dialog with these settings to build this {generatorTitle} again in its place, keeping the features after it'),
            lambda: startRebuild((body, tagName, value)),
        ))
    configText = configJson.configText(tagName, value['config'], str(value.get('generatorVersion') or ''))
    handlers = configButtons.configButtonsHandlers(
        generatorTitle,
        lambda: configText,
        lambda: configFileName(tagName, value['config']),
        onClone=lambda: CLONE_COMMANDS[tagName].startWithConfig(value['config']),
        moreButtons=moreButtons,
    )
    buttons = handlers[browserPages.READY]
    return {**handlers, browserPages.READY: lambda data: {**page, 'buttons': buttons(data)}}

def configFileName(tagName: str, settings: dict) -> str:
    """The name the generator's dialog gives a saved file of these settings, the tag's title when it can't be read"""
    try:
        return CLONE_COMMANDS[tagName].configFileName(settings)
    except Exception as err:
        futil.log(f'{CMD_NAME} config file name not made, {err}')
        return TAG_TITLES[tagName]

def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    # the context menu handler stays for the next menu
    local_handlers = [handler for handler in local_handlers if handler is markingMenuHandler]
