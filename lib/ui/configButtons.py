import adsk.core
import os
from typing import Callable

from ...lib import clipboard
from ...lib import configJson
from ...lib import fusion360utils as futil
from ...lib import i18n
from . import browserPages
from .buttonRow import Button, buttonRowHandlers

# Buttons to save a bin or baseplate config to a file, load or copy it, see configJson for the format
CONFIG_SAVE = 'saveConfig'
CONFIG_LOAD = 'loadConfig'
CONFIG_COPY = 'copyConfig'
CONFIG_CLONE = 'cloneConfig'
FILE_FILTER = 'Gridfinity config (*.json);;All files (*.*)'
COPIED = 'Copied'

app = adsk.core.Application.get()
ui = app.userInterface

# the folder last saved to or opened from, so the next file dialog starts there
_lastFolder = ''

def configButtons(generatorTitle: str, canLoad: bool, canClone: bool) -> list[Button]:
    title = i18n.t(generatorTitle)
    buttons = [Button(CONFIG_SAVE, i18n.t('Save to file'), i18n.t('Save these {title} settings to a JSON file', title=title))]
    if canLoad:
        buttons.append(Button(CONFIG_LOAD, i18n.t('Load from file'), i18n.t('Set the inputs from {title} settings saved to a file', title=title)))
    buttons.append(Button(CONFIG_COPY, i18n.t('Copy'), i18n.t('Copy these {title} settings to the clipboard as JSON', title=title)))
    if canClone:
        buttons.append(Button(CONFIG_CLONE, i18n.t('Clone into new {title}', title=title), i18n.t('Open the {title} dialog with these settings', title=title)))
    return buttons

def configButtonsHandlers(
    generatorTitle: str,
    configText: Callable[[], str],
    fileName: Callable[[], str],
    onLoad: Callable[[str, str], None] = None,
    onClone: Callable[[], None] = None,
    moreButtons: list[tuple[Button, Callable[[], None]]] = [],
) -> dict[str, browserPages.Handler]:
    """
    Messages of a button row, see buttonRow.addButtonRow. configText is the config to save or copy, fileName the
    name a saved file starts with, onLoad gets the text and name of a file opened, onClone opens the dialog with the
    config. More buttons come after with what their click does.
    Load and clone have their buttons only when they're given
    """
    def onClick(action: str) -> str | None:
        if action == CONFIG_SAVE:
            saveConfigFile(configText(), fileName())
        elif action == CONFIG_LOAD:
            opened = openConfigFile()
            if opened is not None:
                onLoad(*opened)
        elif action == CONFIG_COPY:
            return copyConfig(configText())
        elif action == CONFIG_CLONE:
            onClone()
        else:
            for (button, onMoreClick) in moreButtons:
                if action == button.action:
                    onMoreClick()
        return None
    buttons = configButtons(generatorTitle, onLoad is not None, onClone is not None) + [button for (button, _) in moreButtons]
    return buttonRowHandlers(buttons, onClick)

def saveConfigFile(text: str, fileName: str) -> None:
    global _lastFolder
    dialog = ui.createFileDialog()
    dialog.title = i18n.t('Save Gridfinity config')
    dialog.filter = i18n.t(FILE_FILTER)
    dialog.initialFilename = f'{fileName}.json'
    if _lastFolder:
        dialog.initialDirectory = _lastFolder
    if dialog.showSave() != adsk.core.DialogResults.DialogOK:
        return
    _lastFolder = os.path.dirname(dialog.filename)
    try:
        with open(dialog.filename, 'w', encoding='utf-8') as file:
            file.write(text)
        futil.log(f'Saved config to {dialog.filename}')
    except OSError as err:
        ui.messageBox(i18n.t("Couldn't save the config to {fileName}:\n{err}", fileName=dialog.filename, err=err), i18n.t('Gridfinity config'))

def openConfigFile() -> tuple[str, str] | None:
    """Text and name of the file picked, none when the dialog was cancelled or the file can't be read"""
    global _lastFolder
    dialog = ui.createFileDialog()
    dialog.title = i18n.t('Load Gridfinity config')
    dialog.filter = i18n.t(FILE_FILTER)
    dialog.isMultiSelectEnabled = False
    if _lastFolder:
        dialog.initialDirectory = _lastFolder
    if dialog.showOpen() != adsk.core.DialogResults.DialogOK:
        return None
    _lastFolder = os.path.dirname(dialog.filename)
    try:
        with open(dialog.filename, encoding='utf-8') as file:
            return (file.read(), os.path.basename(dialog.filename))
    except (OSError, UnicodeDecodeError) as err:
        ui.messageBox(i18n.t("Couldn't read {fileName}:\n{err}", fileName=dialog.filename, err=err), i18n.t('Gridfinity config'))
        return None

def copyConfig(text: str) -> str | None:
    """What the button shows once it's copied"""
    try:
        clipboard.copyText(text)
        return i18n.t(COPIED)
    except Exception as err:
        futil.log(f'Couldn\'t copy the config, {err}')
        ui.messageBox(i18n.t("Couldn't copy to the clipboard:\n{err}", err=err), i18n.t('Gridfinity config'))
        return None

def readConfig(
    text: str,
    source: str,
    generator: str,
    stateClass: type,
    current: object,
    choices: dict[str, configJson.Choice],
    isFromTag: bool = False,
) -> object | None:
    """
    The state of a config for a dialog, see configJson.readConfig, none when it can't be read. Shows why, or what
    reading it changed when it did. source names it in the message, like Loaded "bin.json" or Cloned
    """
    try:
        (state, notes) = configJson.readConfig(text, generator, stateClass, current, choices, isFromTag)
    except configJson.ConfigError as err:
        ui.messageBox(i18n.t("Couldn't read the config. {err}", err=err), i18n.t('Gridfinity config'))
        return None
    if not notes.isEmpty():
        details = configJson.notesText(generator, notes)
        futil.log(f'{source} config with changes:\n{details}')
        ui.messageBox(i18n.t('{source} with changes:\n\n{details}', source=source, details=details), i18n.t('Gridfinity config'), adsk.core.MessageBoxButtonTypes.OKButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
    return state
