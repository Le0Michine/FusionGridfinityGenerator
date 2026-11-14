import adsk.core
import os
from typing import Callable

from ...lib import clipboard
from ...lib import configJson
from ...lib import fusion360utils as futil
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
    buttons = [Button(CONFIG_SAVE, 'Save to file', f'Save these {generatorTitle} settings to a JSON file')]
    if canLoad:
        buttons.append(Button(CONFIG_LOAD, 'Load from file', f'Set the inputs from {generatorTitle} settings saved to a file'))
    buttons.append(Button(CONFIG_COPY, 'Copy', f'Copy these {generatorTitle} settings to the clipboard as JSON'))
    if canClone:
        buttons.append(Button(CONFIG_CLONE, f'Clone into new {generatorTitle}', f'Open the {generatorTitle} dialog with these settings'))
    return buttons

def configButtonsHandlers(
    generatorTitle: str,
    configText: Callable[[], str],
    fileName: Callable[[], str],
    onLoad: Callable[[str, str], None] = None,
    onClone: Callable[[], None] = None,
) -> dict[str, browserPages.Handler]:
    """
    Messages of a button row, see buttonRow.addButtonRow. configText is the config to save or copy, fileName the
    name a saved file starts with, onLoad gets the text and name of a file opened, onClone opens the dialog with the
    config.
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
        return None
    return buttonRowHandlers(configButtons(generatorTitle, onLoad is not None, onClone is not None), onClick)

def saveConfigFile(text: str, fileName: str) -> None:
    global _lastFolder
    dialog = ui.createFileDialog()
    dialog.title = 'Save Gridfinity config'
    dialog.filter = FILE_FILTER
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
        ui.messageBox(f'Couldn\'t save the config to {dialog.filename}:\n{err}', 'Gridfinity config')

def openConfigFile() -> tuple[str, str] | None:
    """Text and name of the file picked, none when the dialog was cancelled or the file can't be read"""
    global _lastFolder
    dialog = ui.createFileDialog()
    dialog.title = 'Load Gridfinity config'
    dialog.filter = FILE_FILTER
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
        ui.messageBox(f'Couldn\'t read {dialog.filename}:\n{err}', 'Gridfinity config')
        return None

def copyConfig(text: str) -> str | None:
    """What the button shows once it's copied"""
    try:
        clipboard.copyText(text)
        return COPIED
    except Exception as err:
        futil.log(f'Couldn\'t copy the config, {err}')
        ui.messageBox(f'Couldn\'t copy to the clipboard:\n{err}', 'Gridfinity config')
        return None

def readConfig(
    text: str,
    source: str,
    generator: str,
    stateClass: type,
    current: object,
    choices: dict[str, configJson.Choice],
) -> object | None:
    """
    The state of a config for a dialog, see configJson.readConfig, none when it can't be read. Shows why, or what
    reading it changed when it did. source names it in the message, like Loaded "bin.json" or Cloned
    """
    try:
        (state, notes) = configJson.readConfig(text, generator, stateClass, current, choices)
    except configJson.ConfigError as err:
        ui.messageBox(f'Couldn\'t read the config. {err}', 'Gridfinity config')
        return None
    if not notes.isEmpty():
        details = configJson.notesText(generator, notes)
        futil.log(f'{source} config with changes:\n{details}')
        ui.messageBox(f'{source} with changes:\n\n{details}', 'Gridfinity config', adsk.core.MessageBoxButtonTypes.OKButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
    return state
