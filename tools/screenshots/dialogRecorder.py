"""
Builds a command's dialog outside Fusion and describes what it shows, for page/dialog.js to draw.

The command's own entry runs against the fake API in fakeAdsk: it sets up its defaults, the shot's values replace
some of them, and command_created adds the inputs as it does in Fusion, enabling, hiding and filling them. Pages in
browser inputs get the answer the dialog gives to their ready message, so they draw the same data as in Fusion.
"""

import importlib
import json
import os
import pathlib
import sys
import types

SCREENSHOTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(SCREENSHOTS_DIR))
# the add-in is loaded as this package, so the entries' relative imports resolve
PACKAGE = 'gridfinityAddin'

COMMANDS = {
    'bin': 'commandCreateBin',
    'baseplate': 'commandCreateBaseplate',
}
# what the commands call the state of their inputs and the function setting its defaults
UI_STATE_NAMES = ['commandUIState', 'uiState']
INIT_NAMES = ['initDefaultUiState', 'initUiState']

# where length values typed with units in a shot are converted from, the dialogs keep centimeters
LENGTH_UNITS_IN_CM = {'mm': 0.1, 'cm': 1.0, 'in': 2.54}


def _installFakeApi():
    fakeDir = os.path.join(SCREENSHOTS_DIR, 'fakeAdsk')
    if fakeDir not in sys.path:
        sys.path.insert(0, fakeDir)
    import adsk.core
    if not adsk.core.__file__.startswith(fakeDir):
        raise RuntimeError(f'adsk was imported from {adsk.core.__file__}, the recorder needs the fake one in {fakeDir}')


def _package(name: str, path: str) -> types.ModuleType:
    """A package from a folder without running its __init__, commands/__init__ would import every command"""
    module = types.ModuleType(name)
    module.__path__ = [path]
    module.__package__ = name
    sys.modules[name] = module
    return module


def loadCommand(command: str) -> types.ModuleType:
    """A fresh copy of a command's entry, the entries keep their state in module globals"""
    _installFakeApi()
    folder = COMMANDS.get(command, command)
    for name in [name for name in sys.modules if name.startswith(f'{PACKAGE}.commands.')]:
        del sys.modules[name]
    if PACKAGE not in sys.modules:
        _package(PACKAGE, ROOT_DIR)
        _package(f'{PACKAGE}.commands', os.path.join(ROOT_DIR, 'commands'))
        futil = importlib.import_module(f'{PACKAGE}.lib.fusion360utils')
        # quiet, and nothing fires the events
        futil.log = lambda *args, **kwargs: None
        futil.add_handler = lambda *args, **kwargs: None
    return importlib.import_module(f'{PACKAGE}.commands.{folder}.entry')


def _find(module: types.ModuleType, names: list[str]):
    for name in names:
        if hasattr(module, name):
            return getattr(module, name)
    raise RuntimeError(f'{module.__name__} has none of {names}')


def _stateValue(current, value):
    """A shot's value as the state keeps it, lengths like '42 mm' in centimeters, angles stay expressions"""
    if isinstance(value, str) and not isinstance(current, str):
        (number, _, units) = value.strip().partition(' ')
        if units in LENGTH_UNITS_IN_CM:
            return float(number) * LENGTH_UNITS_IN_CM[units]
        return type(current)(float(number)) if isinstance(current, (int, float)) and not isinstance(current, bool) else value
    return value


def applyValues(module: types.ModuleType, values: dict, moduleGlobals: dict):
    uiState = _find(module, UI_STATE_NAMES)
    for (inputId, value) in values.items():
        if inputId not in uiState.inputState:
            known = ', '.join(sorted(uiState.inputState))
            raise KeyError(f'{module.__name__} has no input "{inputId}", it has {known}')
        uiState.inputState[inputId].value = _stateValue(uiState.getState(inputId), value)
    for (name, value) in moduleGlobals.items():
        if not hasattr(module, name):
            raise KeyError(f'{module.__name__} has no global "{name}"')
        setattr(module, name, value)


def record(command: str, values: dict = None, moduleGlobals: dict = None, defaultsFile: str = None) -> dict:
    """
    The dialog of a command with the given input values, by input id as the dialog saves its defaults. Without a
    defaults file the dialog has its original defaults, not the ones saved in Fusion
    """
    module = loadCommand(command)
    import adsk.core
    module.UI_INPUT_DEFAULTS_CONFIG_PATH = os.path.abspath(defaultsFile) if defaultsFile else os.path.join(SCREENSHOTS_DIR, 'no-saved-defaults.json')
    _find(module, INIT_NAMES)()
    applyValues(module, values or {}, moduleGlobals or {})

    fusionCommand = adsk.core.Command()
    module.command_created(adsk.core.CommandCreatedEventArgs(fusionCommand))
    _checkDropdowns(fusionCommand.commandInputs, values or {})
    (width, height) = fusionCommand.dialogSize
    return {
        'title': module.CMD_NAME,
        'width': width,
        'height': height,
        'okText': fusionCommand.okButtonText,
        'cancelText': fusionCommand.cancelButtonText,
        'inputs': _describeAll(module, fusionCommand.commandInputs),
    }


def _checkDropdowns(inputs, values: dict):
    """A dialog selects its first item for a name it doesn't list, a shot would show it without saying"""
    import adsk.core
    for (inputId, value) in values.items():
        dropdown = inputs.itemById(inputId)
        if isinstance(dropdown, adsk.core.DropDownCommandInput) and (dropdown.selectedItem is None or dropdown.selectedItem.name != value):
            names = ', '.join(f'"{item.name}"' for item in dropdown.listItems if not item.isSeparator)
            raise ValueError(f'{inputId} has no item "{value}", it has {names}')


def _describeAll(module, inputs) -> list[dict]:
    return [description for description in (_describe(module, input) for input in inputs) if description is not None]


def _describe(module, input) -> dict | None:
    import adsk.core
    if not input.isVisible:
        return None
    common = {
        'id': input.id,
        'name': input.name,
        'enabled': input.isEnabled,
        'fullWidth': input.isFullWidth,
    }
    if isinstance(input, adsk.core.GroupCommandInput):
        return {**common, 'type': 'group', 'expanded': input.isExpanded, 'children': _describeAll(module, input.children)}
    if isinstance(input, adsk.core.ValueCommandInput):
        return {**common, 'type': 'value', 'text': input.expression}
    if isinstance(input, (adsk.core.FloatSpinnerCommandInput, adsk.core.IntegerSpinnerCommandInput)):
        return {**common, 'type': 'spinner', 'text': input.expression}
    if isinstance(input, adsk.core.BoolValueCommandInput):
        return {**common, 'type': 'checkbox' if input.isCheckBox else 'button', 'checked': input.value}
    if isinstance(input, adsk.core.StringValueCommandInput):
        return {**common, 'type': 'string', 'text': input.value, 'readOnly': input.isReadOnly}
    if isinstance(input, adsk.core.TextBoxCommandInput):
        return {**common, 'type': 'textbox', 'html': input.formattedText, 'rows': input.numRows}
    if isinstance(input, adsk.core.DropDownCommandInput):
        selected = input.selectedItem
        return {**common, 'type': 'dropdown', 'text': selected.name if selected else '', 'icon': _icon(selected.icon if selected else '')}
    if isinstance(input, adsk.core.BrowserCommandInput):
        return {**common, 'type': 'browser', 'url': input.htmlFileURL, 'height': input.minimumHeight, 'answer': _pageAnswer(module, input)}
    if isinstance(input, adsk.core.TableCommandInput):
        rows = [[_describe(module, input.getInputAtPosition(row, column)) if input.getInputAtPosition(row, column) else None
                 for column in range(input.numberOfColumns)] for row in range(input.rowCount)]
        return {**common, 'type': 'table', 'rows': rows, 'columnRatio': input.columnRatio}
    raise TypeError(f'Can\'t draw {input.id}, a {type(input).__name__}')


def _icon(folder: str) -> str:
    """The icon an item shows from its resource folder"""
    path = os.path.join(folder, '16x16.png') if folder else ''
    return pathlib.Path(path).as_uri() if path and os.path.isfile(path) else ''


def _pageAnswer(module, browserInput) -> str:
    """What the dialog answers when its page asks for its data, see lib/ui/browserPages.py"""
    import adsk.core
    args = adsk.core.HTMLEventArgs(browserInput, 'ready', json.dumps(None))
    module.command_incoming_from_html(args)
    return args.returnData


if __name__ == '__main__':
    # the model of a command's dialog with its defaults, to see what a shot can set
    print(json.dumps(record(sys.argv[1] if len(sys.argv) > 1 else 'bin'), indent=2))
