"""
Minimal stub for adsk.core sufficient to run CommandUiState outside Fusion 360.

Only the types and attributes actually exercised by CommandUiState and its tests
are implemented.  Everything else is left as a no-op so that `import adsk.core`
succeeds and isinstance() checks behave correctly.
"""


class LogLevels:
    InfoLogLevel = 0
    ErrorLogLevel = 1


class LogTypes:
    FileLogType = 0
    ConsoleLogType = 1


# ---------------------------------------------------------------------------
# Base command-input stub
# ---------------------------------------------------------------------------

class CommandInput:
    """Base class for all input stubs."""

    def __init__(self, input_id: str, value=None):
        self.id = input_id
        self._value = value

    @classmethod
    def classType(cls) -> str:
        return cls.__name__

    @property
    def objectType(self) -> str:
        return type(self).classType()


# ---------------------------------------------------------------------------
# Concrete input stubs — each mirrors the real adsk.core type just enough
# for isinstance() checks and the attribute accesses inside CommandUiState.
# ---------------------------------------------------------------------------

class BoolValueCommandInput(CommandInput):
    @property
    def value(self) -> bool:
        return bool(self._value)

    @value.setter
    def value(self, v: bool):
        self._value = v


class IntegerSpinnerCommandInput(CommandInput):
    @property
    def value(self) -> int:
        return int(self._value)

    @value.setter
    def value(self, v: int):
        self._value = v


class ValueCommandInput(CommandInput):
    """Covers both plain-value and degree (expression) inputs."""

    def __init__(self, input_id: str, value=None, unit_type: str = ""):
        super().__init__(input_id, value)
        self.unitType = unit_type
        self.expression = str(value) if value is not None else ""

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v


class _ListItem:
    def __init__(self, name: str, selected: bool = False):
        self.name = name
        self.isSelected = selected


class _ListItems:
    def __init__(self, items: list):
        self._items = [_ListItem(n) for n in items]

    def count(self):
        return len(self._items)

    def item(self, i: int) -> _ListItem:
        return self._items[i]


class DropDownCommandInput(CommandInput):
    def __init__(self, input_id: str, options: list, selected: str = None):
        super().__init__(input_id, selected or (options[0] if options else None))
        self.listItems = _ListItems(options)
        # mark the initially selected item
        for item in self.listItems._items:
            item.isSelected = item.name == self._value

    @property
    def selectedItem(self) -> _ListItem:
        for item in self.listItems._items:
            if item.isSelected:
                return item
        return self.listItems._items[0]


class GroupCommandInput(CommandInput):
    def __init__(self, input_id: str, is_expanded: bool = True):
        super().__init__(input_id, is_expanded)

    @property
    def isExpanded(self) -> bool:
        return bool(self._value)

    @isExpanded.setter
    def isExpanded(self, v: bool):
        self._value = v


class TextBoxCommandInput(CommandInput):
    def __init__(self, input_id: str, text: str = ""):
        super().__init__(input_id, text)

    @property
    def formattedText(self) -> str:
        return str(self._value)

    @formattedText.setter
    def formattedText(self, v: str):
        self._value = v


class StringValueCommandInput(CommandInput):
    @property
    def value(self) -> str:
        return str(self._value)

    @value.setter
    def value(self, v: str):
        self._value = v


# ---------------------------------------------------------------------------
# Application stub — satisfies `adsk.core.Application.get()` at import time
# ---------------------------------------------------------------------------

class _UI:
    def messageBox(self, *args, **kwargs):
        pass


class _App:
    userInterface = _UI()

    def log(self, *args, **kwargs):
        pass


class Application:
    @staticmethod
    def get() -> "_App":
        return _App()
