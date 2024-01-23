import adsk.core, adsk.fusion, traceback
from ...lib import fusion360utils as futil

class SingleInputState:
    def __init__(self, inputId: str, inputValue: any, inutType: str):
        self.id = inputId
        self.value = inputValue
        self.type = inutType

    def toDict(self):
        return {
            'id': self.id,
            'value': self.value,
            'type': self.type,
        }

class CommandUiState:
    def __init__(self, commandName):
        self.inputState: dict[str, SingleInputState] = {}
        self.commandInputs: dict[str, adsk.core.CommandInput] = {}
        self.commandName = commandName

    def initValue(self, inputId: str, inputValue: any, inputType: str):
        self.inputState[inputId] = SingleInputState(inputId, inputValue, inputType)

    def initValues(self, inputValues: dict[str, any]):
        for v in inputValues.values():
            self.inputState[v['id']] = SingleInputState(v['id'], v['value'], v['type'])

    def registerCommandInput(self, input: adsk.core.CommandInput):
        futil.log(f'{self.commandName} Registering command input {input.id}')
        self.commandInputs[input.id] = input

    def onInputUpdate(self, input: adsk.core.CommandInput):
        inputId = input.id
        self.commandInputs[inputId] = input
        if isinstance(input, adsk.core.IntegerSpinnerCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.value, input.objectType)
        elif isinstance(input, adsk.core.ValueCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.value, input.objectType)
        elif isinstance(input, adsk.core.DropDownCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.selectedItem.name, input.objectType)
        elif isinstance(input, adsk.core.GroupCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.isExpanded, input.objectType)
        elif isinstance(input, adsk.core.BoolValueCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.value, input.objectType)
        else:
            futil.log(f'{self.commandName} Unknonwn input type: {input.id} [{input.objectType}]')

    def forceUIRefresh(self):
        futil.log(f'{self.commandName} Forcing UI input state refresh')
        for input in self.inputState.values():
            if input.id in self.commandInputs:
                commandInput = self.commandInputs[input.id]
                futil.log(f'{self.commandName} Input {input.id}, {commandInput}')
                self.updateInputFromState(commandInput)
            else:
                futil.log(f'{self.commandName} Skipping {input.id} as it wasn\'t registered')


    def updateInputFromState(self, input: adsk.core.CommandInput):
        inputId = input.id
        value = self.getState(inputId)
        if isinstance(input, adsk.core.IntegerSpinnerCommandInput):
            input.value = value
        elif isinstance(input, adsk.core.ValueCommandInput):
            input.value = value
        elif isinstance(input, adsk.core.DropDownCommandInput):
            for i in range(0, input.listItems.count):
                input.listItems.item(i).isSelected = input.listItems.item(i).name == value
        elif isinstance(input, adsk.core.GroupCommandInput):
            input.isExpanded = value
        elif isinstance(input, adsk.core.BoolValueCommandInput):
            input.value = value
        else:
            futil.log(f'{self.commandName} Unknonwn input type: {input.id} [{input.objectType}]')

    def getState(self, inputId: str):
        return self.inputState[inputId].value
    
    def toDict(self):
        result = {}
        for key in self.inputState.keys():
            result[key] = self.inputState[key].toDict()
        return result