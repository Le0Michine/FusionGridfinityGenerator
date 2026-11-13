"""
The command inputs of adsk.core as a dialog builds them. They keep what a dialog sets, so the dialog can be drawn from
them, see dialogRecorder.py. Values are kept in Fusion's internal units, centimeters and radians
"""

import math
import re

from .anything import Anything, moduleFallback

__getattr__ = moduleFallback(__name__)

# internal units are centimeters, expressions and displayed values use the input's own
LENGTH_UNITS_IN_CM = {'mm': 0.1, 'cm': 1.0, 'm': 100.0, 'in': 2.54, 'ft': 30.48}


def toInternal(number: float, units: str) -> float:
    if units == 'deg':
        return math.radians(number)
    return number * LENGTH_UNITS_IN_CM.get(units, 1.0)


def fromInternal(value: float, units: str) -> float:
    if units == 'deg':
        return math.degrees(value)
    return value / LENGTH_UNITS_IN_CM.get(units, 1.0)


def parseExpression(expression: str, defaultUnits: str) -> float:
    """A number with optional units, like '45 deg' or '4.2', in internal units"""
    match = re.fullmatch(r'\s*(-?[\d.]+)\s*([a-z]*)\s*', str(expression))
    if match is None:
        raise ValueError(f'Can\'t read the expression "{expression}"')
    return toInternal(float(match.group(1)), match.group(2) or defaultUnits)


def formatValue(value: float, units: str) -> str:
    """As Fusion shows a value, two decimals for lengths and plain numbers, one for angles"""
    if units == 'deg':
        return f'{fromInternal(value, units):.1f} deg'
    number = f'{fromInternal(value, units):.2f}'
    return f'{number} {units}' if units else number


class ValueInput:
    def __init__(self, real: float = None, expression: str = None):
        self.realValue = real
        self.stringValue = expression

    @staticmethod
    def createByReal(value: float) -> 'ValueInput':
        return ValueInput(real=value)

    @staticmethod
    def createByString(expression: str) -> 'ValueInput':
        return ValueInput(expression=expression)


class CommandInput:
    def __init__(self, inputs: 'CommandInputs', inputId: str, name: str):
        self.id = inputId
        self.name = name
        self.parentInputs = inputs
        self.isVisible = True
        self.isEnabled = True
        self.isFullWidth = False
        self.tooltip = ''
        self.tooltipDescription = ''

    @property
    def parentCommand(self) -> 'Command':
        return self.parentInputs.command

    @classmethod
    def classType(cls) -> str:
        return f'adsk::core::{cls.__name__}'

    @property
    def objectType(self) -> str:
        return type(self).classType()

    @classmethod
    def cast(cls, obj):
        return obj if isinstance(obj, cls) else None

    def deleteMe(self):
        self.parentInputs.remove(self)
        return True


class ValueCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, unitType: str, initialValue: ValueInput):
        super().__init__(inputs, inputId, name)
        self.unitType = unitType
        self.minimumValue = None
        self.maximumValue = None
        self.isMinimumInclusive = True
        self.isMaximumInclusive = True
        self.isReadOnly = False
        self._value = 0.0
        if initialValue.stringValue is not None:
            self.expression = initialValue.stringValue
        else:
            self.value = initialValue.realValue

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = float(value)

    @property
    def expression(self) -> str:
        return formatValue(self._value, self.unitType)

    @expression.setter
    def expression(self, expression: str):
        self._value = parseExpression(expression, self.unitType)

    @property
    def isValidExpression(self) -> bool:
        return True


class FloatSpinnerCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, unitType: str, minimum: float, maximum: float, spinStep: float, initialValue: float):
        super().__init__(inputs, inputId, name)
        self.unitType = unitType
        self.minimumValue = minimum
        self.maximumValue = maximum
        self.spinStep = spinStep
        self.value = float(initialValue)

    @property
    def expression(self) -> str:
        return formatValue(toInternal(self.value, self.unitType), self.unitType)


class IntegerSpinnerCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, minimum: int, maximum: int, spinStep: int, initialValue: int):
        super().__init__(inputs, inputId, name)
        self.minimumValue = minimum
        self.maximumValue = maximum
        self.spinStep = spinStep
        self.value = int(initialValue)

    @property
    def expression(self) -> str:
        return str(self.value)


class BoolValueCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, isCheckBox: bool, resourceFolder: str = '', initialValue: bool = False):
        super().__init__(inputs, inputId, name)
        self.isCheckBox = isCheckBox
        self.resourceFolder = resourceFolder
        self.value = bool(initialValue)
        self.text = ''


class StringValueCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, initialValue: str):
        super().__init__(inputs, inputId, name)
        self.value = initialValue
        self.isReadOnly = False
        self.isPassword = False


class TextBoxCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, formattedText: str, numRows: int, isReadOnly: bool):
        super().__init__(inputs, inputId, name)
        self.formattedText = formattedText
        self.numRows = numRows
        self.isReadOnly = isReadOnly

    # plain text replaces the formatted one, as in Fusion
    @property
    def text(self) -> str:
        return re.sub(r'<[^>]+>', '', self.formattedText)

    @text.setter
    def text(self, value: str):
        self.formattedText = value


class ListItem:
    def __init__(self, items: 'ListItems', name: str, isSelected: bool, icon: str = '', isSeparator: bool = False):
        self._items = items
        self.name = name
        self.icon = icon
        self.isSeparator = isSeparator
        self._isSelected = False
        self.isSelected = isSelected

    @property
    def isSelected(self) -> bool:
        return self._isSelected

    @isSelected.setter
    def isSelected(self, isSelected: bool):
        # a dropdown has a single selected item
        if isSelected:
            for item in self._items._items:
                item._isSelected = False
        self._isSelected = bool(isSelected)

    @property
    def index(self) -> int:
        return self._items._items.index(self)

    def deleteMe(self):
        self._items._items.remove(self)
        return True


class ListItems:
    def __init__(self):
        self._items: list[ListItem] = []

    def add(self, name: str, isSelected: bool, icon: str = '', beforeIndex: int = -1) -> ListItem:
        item = ListItem(self, name, isSelected, icon)
        self._items.insert(len(self._items) if beforeIndex < 0 else beforeIndex, item)
        return item

    def addSeparator(self, beforeIndex: int = -1) -> ListItem:
        item = ListItem(self, '', False, isSeparator=True)
        self._items.insert(len(self._items) if beforeIndex < 0 else beforeIndex, item)
        return item

    @property
    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> ListItem:
        return self._items[index]

    def clear(self):
        self._items = []

    def __iter__(self):
        return iter(self._items)


class DropDownCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, dropDownStyle):
        super().__init__(inputs, inputId, name)
        self.dropDownStyle = dropDownStyle
        self.listItems = ListItems()
        self.maxVisibleItems = 20

    @property
    def selectedItem(self) -> ListItem | None:
        return next((item for item in self.listItems if item.isSelected), None)


class BrowserCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, htmlFileURL: str, minimumHeight: int, maximumHeight: int):
        super().__init__(inputs, inputId, name)
        self.htmlFileURL = htmlFileURL
        self.minimumHeight = minimumHeight
        self.maximumHeight = maximumHeight
        # what the dialog last sent, the page draws the answer to its ready message instead
        self.sentInfo: list[tuple[str, str]] = []

    def sendInfoToHTML(self, action: str, data: str):
        self.sentInfo.append((action, data))
        return True


class GroupCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name):
        super().__init__(inputs, inputId, name)
        self.children = CommandInputs(inputs.command, self)
        self.isExpanded = True
        self.isEnabledCheckBoxDisplayed = False
        self.isEnabledCheckBoxChecked = True


class TableCommandInput(CommandInput):
    def __init__(self, inputs, inputId, name, numberOfColumns: int, columnRatio: str):
        super().__init__(inputs, inputId, name)
        self.numberOfColumns = numberOfColumns
        self.columnRatio = columnRatio
        # inputs added here only show once they are placed in a cell
        self.commandInputs = CommandInputs(inputs.command, self)
        self.cells: dict[tuple[int, int], CommandInput] = {}
        self.tablePresentationStyle = None
        self.hasGrid = True
        self.minimumVisibleRows = 1
        self.maximumVisibleRows = 1

    def addCommandInput(self, input: CommandInput, row: int, column: int, rowSpan: int = 0, columnSpan: int = 0):
        self.cells[(row, column)] = input
        return True

    def getInputAtPosition(self, row: int, column: int) -> CommandInput | None:
        return self.cells.get((row, column))

    @property
    def rowCount(self) -> int:
        return max((row for (row, _) in self.cells), default=-1) + 1

    def clear(self):
        self.cells = {}


class CommandInputs:
    def __init__(self, command: 'Command', owner: CommandInput = None):
        self.command = command
        self.owner = owner
        self._inputs: list[CommandInput] = []

    def _add(self, input: CommandInput) -> CommandInput:
        self._inputs.append(input)
        return input

    def remove(self, input: CommandInput):
        self._inputs.remove(input)

    def addValueInput(self, inputId, name, unitType, initialValue):
        return self._add(ValueCommandInput(self, inputId, name, unitType, initialValue))

    def addFloatSpinnerCommandInput(self, inputId, name, unitType, minimum, maximum, spinStep, initialValue):
        return self._add(FloatSpinnerCommandInput(self, inputId, name, unitType, minimum, maximum, spinStep, initialValue))

    def addIntegerSpinnerCommandInput(self, inputId, name, minimum, maximum, spinStep, initialValue):
        return self._add(IntegerSpinnerCommandInput(self, inputId, name, minimum, maximum, spinStep, initialValue))

    def addBoolValueInput(self, inputId, name, isCheckBox, resourceFolder='', initialValue=False):
        return self._add(BoolValueCommandInput(self, inputId, name, isCheckBox, resourceFolder, initialValue))

    def addStringValueInput(self, inputId, name, initialValue=''):
        return self._add(StringValueCommandInput(self, inputId, name, initialValue))

    def addTextBoxCommandInput(self, inputId, name, formattedText, numRows, isReadOnly):
        return self._add(TextBoxCommandInput(self, inputId, name, formattedText, numRows, isReadOnly))

    def addDropDownCommandInput(self, inputId, name, dropDownStyle):
        return self._add(DropDownCommandInput(self, inputId, name, dropDownStyle))

    def addBrowserCommandInput(self, inputId, name, htmlFileURL, minimumHeight, maximumHeight=0):
        return self._add(BrowserCommandInput(self, inputId, name, htmlFileURL, minimumHeight, maximumHeight))

    def addGroupCommandInput(self, inputId, name):
        return self._add(GroupCommandInput(self, inputId, name))

    def addTableCommandInput(self, inputId, name, numberOfColumns, columnRatio):
        return self._add(TableCommandInput(self, inputId, name, numberOfColumns, columnRatio))

    def itemById(self, inputId: str) -> CommandInput | None:
        """Inputs in groups and tables are found too, as in Fusion"""
        for input in self._inputs:
            if input.id == inputId:
                return input
            nested = getattr(input, 'children', None) or getattr(input, 'commandInputs', None)
            found = nested.itemById(inputId) if isinstance(nested, CommandInputs) else None
            if found is not None:
                return found
        return None

    @property
    def count(self) -> int:
        return len(self._inputs)

    def item(self, index: int) -> CommandInput:
        return self._inputs[index]

    def __iter__(self):
        return iter(list(self._inputs))

    def __len__(self):
        return len(self._inputs)


class Command:
    def __init__(self):
        self.commandInputs = CommandInputs(self)
        self.dialogSize = (450, 500)
        self.isOKButtonVisible = True
        self.okButtonText = 'OK'
        self.cancelButtonText = 'Cancel'

    def setDialogInitialSize(self, width: int, height: int):
        self.dialogSize = (width, height)
        return True

    def setDialogMinimumSize(self, width: int, height: int):
        return True

    def doExecutePreview(self):
        return True

    # execute, inputChanged and the other events, nothing fires them here
    def __getattr__(self, name: str):
        if name.startswith('__'):
            raise AttributeError(name)
        return Anything()


class CommandCreatedEventArgs:
    def __init__(self, command: Command):
        self.command = command


class HTMLEventArgs:
    def __init__(self, browserInput: BrowserCommandInput, action: str, data: str):
        self.browserCommandInput = browserInput
        self.action = action
        self.data = data
        self.returnData = ''


class _UnitsManager:
    defaultLengthUnits = 'mm'

    def evaluateExpression(self, expression: str, units: str = '') -> float:
        return parseExpression(expression, units or self.defaultLengthUnits)


class _Product:
    unitsManager = _UnitsManager()


class _Application(Anything):
    activeProduct = _Product()

    def log(self, *args, **kwargs):
        pass


_app = _Application()


class Application:
    @staticmethod
    def get() -> _Application:
        return _app
