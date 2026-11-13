"""
Builds a command's dialog outside Fusion, changes it as a person would and describes what it shows, for
page/dialog.js to draw.

The command's own entry runs against the fake API in fakeAdsk: it sets up its defaults, the shot's values replace
some of them, and command_created adds the inputs as it does in Fusion, enabling, hiding and filling them. Changes go
through the command's input changed handler and pages in browser inputs talk to its HTML handler, so the dialog reacts
and the pages draw the same data as in Fusion.
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


class DialogSession:
    """
    A command's dialog with the given input values, by input id as the dialog saves its defaults, open to be changed
    as a person would and drawn after every change. Without a defaults file the dialog has its original defaults, not
    the ones saved in Fusion
    """

    def __init__(self, command: str, values: dict = None, moduleGlobals: dict = None, defaultsFile: str = None):
        self.module = loadCommand(command)
        import adsk.core
        self.module.UI_INPUT_DEFAULTS_CONFIG_PATH = os.path.abspath(defaultsFile) if defaultsFile else os.path.join(SCREENSHOTS_DIR, 'no-saved-defaults.json')
        _find(self.module, INIT_NAMES)()
        applyValues(self.module, values or {}, moduleGlobals or {})

        self.command = adsk.core.Command()
        self.module.command_created(adsk.core.CommandCreatedEventArgs(self.command))
        _checkDropdowns(self.command.commandInputs, values or {})
        # pages ask for their data once loaded, what the dialog sent before is stale
        self.takeSentInfo()

    @property
    def inputs(self):
        return self.command.commandInputs

    def input(self, inputId: str):
        input = self.inputs.itemById(inputId)
        if input is None:
            raise KeyError(f'The dialog has no input "{inputId}"')
        return input

    def describe(self) -> dict:
        import adsk.core
        (width, height) = self.command.dialogSize
        validation = adsk.core.ValidateInputsEventArgs(self.inputs)
        self.module.command_validate_input(validation)
        return {
            'title': self.module.CMD_NAME,
            'width': width,
            'height': height,
            'okText': self.command.okButtonText,
            'cancelText': self.command.cancelButtonText,
            'okEnabled': validation.areInputsValid,
            'inputs': _describeAll(self.inputs),
        }

    def pageMessage(self, inputId: str, action: str, data: str) -> str:
        """What the dialog answers a page, see lib/ui/browserPages.py"""
        import adsk.core
        args = adsk.core.HTMLEventArgs(self.input(inputId), action, data)
        self.module.command_incoming_from_html(args)
        return args.returnData

    def change(self, inputId: str, value):
        """Sets an input as typed or picked in the dialog, the dialog hears of it as in Fusion"""
        import adsk.core
        input = self.input(inputId)
        if isinstance(input, adsk.core.ValueCommandInput):
            if isinstance(value, str):
                input.expression = value
            else:
                input.value = value
        elif isinstance(input, adsk.core.DropDownCommandInput):
            items = [item for item in input.listItems if item.name == value]
            if not items:
                names = ', '.join(f'"{item.name}"' for item in input.listItems if not item.isSeparator)
                raise ValueError(f'{inputId} has no item "{value}", it has {names}')
            items[0].isSelected = True
        elif isinstance(input, adsk.core.GroupCommandInput):
            input.isExpanded = bool(value)
        elif isinstance(input, adsk.core.IntegerSpinnerCommandInput):
            input.value = int(value)
        elif isinstance(input, adsk.core.FloatSpinnerCommandInput):
            input.value = float(value)
        else:
            input.value = value
        self.module.command_input_changed(adsk.core.InputChangedEventArgs(input, self.inputs))

    def click(self, inputId: str):
        """A click on a checkbox, button or group header"""
        import adsk.core
        input = self.input(inputId)
        if isinstance(input, adsk.core.GroupCommandInput):
            self.change(inputId, not input.isExpanded)
        elif isinstance(input, adsk.core.BoolValueCommandInput):
            # a button is pressed for the event and lets go
            self.change(inputId, True if not input.isCheckBox else not input.value)
        else:
            raise TypeError(f'{inputId} is a {type(input).__name__}, click a checkbox, a button or a group')

    def spin(self, inputId: str, steps: int):
        """Clicks on the arrows of a spinner, up for positive steps"""
        input = self.input(inputId)
        value = input.value + input.spinStep * steps
        self.change(inputId, max(input.minimumValue, min(input.maximumValue, value)))

    def takeSentInfo(self) -> list[tuple[str, str, str]]:
        """What the dialog sent its pages since the last call, by page"""
        import adsk.core
        sent = []
        for input in _allInputs(self.inputs):
            if isinstance(input, adsk.core.BrowserCommandInput):
                sent.extend((input.id, action, data) for (action, data) in input.sentInfo)
                input.sentInfo = []
        return sent


def _allInputs(inputs):
    for input in inputs:
        yield input
        nested = getattr(input, 'children', None)
        if nested is not None:
            yield from _allInputs(nested)


def _checkDropdowns(inputs, values: dict):
    """A dialog selects its first item for a name it doesn't list, a shot would show it without saying"""
    import adsk.core
    for (inputId, value) in values.items():
        dropdown = inputs.itemById(inputId)
        if isinstance(dropdown, adsk.core.DropDownCommandInput) and (dropdown.selectedItem is None or dropdown.selectedItem.name != value):
            names = ', '.join(f'"{item.name}"' for item in dropdown.listItems if not item.isSeparator)
            raise ValueError(f'{inputId} has no item "{value}", it has {names}')


def _describeAll(inputs) -> list[dict]:
    return [_describe(input) for input in inputs]


def _describe(input) -> dict:
    """An input as it is drawn, hidden ones too, so pages keep their place and state while hidden"""
    import adsk.core
    common = {
        'id': input.id,
        'name': input.name,
        'visible': input.isVisible,
        'enabled': input.isEnabled,
        'fullWidth': input.isFullWidth,
    }
    if isinstance(input, adsk.core.GroupCommandInput):
        return {**common, 'type': 'group', 'expanded': input.isExpanded, 'children': _describeAll(input.children)}
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
        items = [{'name': item.name, 'icon': _icon(item.icon), 'separator': item.isSeparator} for item in input.listItems]
        return {**common, 'type': 'dropdown', 'text': selected.name if selected else '', 'icon': _icon(selected.icon if selected else ''), 'items': items}
    if isinstance(input, adsk.core.BrowserCommandInput):
        return {**common, 'type': 'browser', 'url': input.htmlFileURL, 'height': input.minimumHeight}
    if isinstance(input, adsk.core.TableCommandInput):
        rows = [[_describe(input.getInputAtPosition(row, column)) if input.getInputAtPosition(row, column) else None
                 for column in range(input.numberOfColumns)] for row in range(input.rowCount)]
        return {**common, 'type': 'table', 'rows': rows, 'columnRatio': input.columnRatio}
    raise TypeError(f'Can\'t draw {input.id}, a {type(input).__name__}')


def _icon(folder: str) -> str:
    """The icon an item shows from its resource folder"""
    path = os.path.join(folder, '16x16.png') if folder else ''
    return pathlib.Path(path).as_uri() if path and os.path.isfile(path) else ''


if __name__ == '__main__':
    # the model of a command's dialog with its defaults, to see what a shot can set
    print(json.dumps(DialogSession(sys.argv[1] if len(sys.argv) > 1 else 'bin').describe(), indent=2))
