import adsk.core, adsk.fusion

from ...lib import tagUtils
from ...lib import settingsUtils
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdShowSettings'
CMD_NAME = 'Gridfinity settings'
CMD_Description = 'Show the settings this bin or baseplate was generated with'

SETTINGS_TEXT_INPUT = 'settings_text'
TAG_TITLES = {
    tagUtils.TAG_BIN: 'Gridfinity bin',
    tagUtils.TAG_BASEPLATE: 'Gridfinity baseplate',
}
# rows of the settings text box before it scrolls
MAX_VISIBLE_ROWS = 30

local_handlers = []
markingMenuHandler = None
# starting a command can clear the selection, so the tag is kept from when the menu opened
menuTag = None

def selectedTag() -> tuple[str, dict] | None:
    """Tag of the single selected generated body, also when one of its faces is selected"""
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
    return tagUtils.readBodyTag(body)

def parameterExpression(name: str) -> str | None:
    design = adsk.fusion.Design.cast(app.activeProduct)
    parameter = design.userParameters.itemByName(name) if design is not None else None
    return parameter.expression if parameter is not None else None

def start():
    global markingMenuHandler
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description)
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

def marking_menu_displaying(args: adsk.core.MarkingMenuEventArgs):
    global menuTag
    try:
        menuTag = selectedTag()
        if menuTag is None:
            return
        controls = args.linearMarkingMenu.controls
        controls.addSeparator()
        controls.addCommand(ui.commandDefinitions.itemById(CMD_ID))
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
    (tagName, value) = tag
    command.setDialogInitialSize(400, 500)
    textBox = command.commandInputs.addTextBoxCommandInput(
        SETTINGS_TEXT_INPUT,
        TAG_TITLES.get(tagName, CMD_NAME),
        settingsUtils.settingsHtml(value, parameterExpression),
        min(MAX_VISIBLE_ROWS, settingsUtils.settingsLineCount(value)),
        True,
    )
    textBox.isFullWidth = True
