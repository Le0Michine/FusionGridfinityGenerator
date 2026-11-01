import adsk.core, adsk.fusion, traceback
from ...lib import fusion360utils as futil

class SingleInputState:
    def __init__(self, inputId: str, inputValue: any, inputType: str):
        self.id = inputId
        self.value = inputValue
        self.type = inputType

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

    def removeValue(self, inputId: str):
        if inputId in self.inputState:
            del self.inputState[inputId]
        if inputId in self.commandInputs:
            del self.commandInputs[inputId]

    def initValue(self, inputId: str, inputValue: any, inputType: str):
        if inputId not in self.inputState:
            self.inputState[inputId] = SingleInputState(inputId, inputValue, inputType)

    def updateValue(self, inputId: str, inputValue: any):
        if inputId in self.inputState:
            self.inputState[inputId].value = inputValue
        if inputId in self.commandInputs:
            self.updateInputFromState(self.commandInputs[inputId])

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
            if input.unitType == 'deg':
                self.inputState[inputId] = SingleInputState(inputId, input.expression, input.objectType)
            else:
                self.inputState[inputId] = SingleInputState(inputId, input.value, input.objectType)
        elif isinstance(input, adsk.core.DropDownCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.selectedItem.name, input.objectType)
        elif isinstance(input, adsk.core.GroupCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.isExpanded, input.objectType)
        elif isinstance(input, adsk.core.BoolValueCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.value, input.objectType)
        elif isinstance(input, adsk.core.TextBoxCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.formattedText, input.objectType)
        elif isinstance(input, adsk.core.StringValueCommandInput):
            self.inputState[inputId] = SingleInputState(inputId, input.value, input.objectType)
        else:
            futil.log(f'{self.commandName} Unknonwn input type: {input.id} [{input.objectType}]')

    def forceUIRefresh(self):
        futil.log(f'{self.commandName} Forcing UI input state refresh')
        for input in self.inputState.values():
            if input.id in self.commandInputs:
                commandInput = self.commandInputs[input.id]
                futil.log(f'{self.commandName} Input {input.id}, {commandInput}')
                try:
                    self.updateInputFromState(commandInput)
                except Exception as err:
                    futil.log(f'{self.commandName} Skipping {input.id} due to error: {err}')

            else:
                futil.log(f'{self.commandName} Skipping {input.id} as it wasn\'t registered')


    def updateInputFromState(self, input: adsk.core.CommandInput):
        inputId = input.id
        value = self.getState(inputId)
        if isinstance(input, adsk.core.IntegerSpinnerCommandInput):
            input.value = value
        elif isinstance(input, adsk.core.ValueCommandInput):
            if isinstance(value, str):
                input.expression = value
            else:
                input.value = value
        elif isinstance(input, adsk.core.DropDownCommandInput):
            for i in range(0, input.listItems.count):
                input.listItems.item(i).isSelected = input.listItems.item(i).name == value
        elif isinstance(input, adsk.core.GroupCommandInput):
            input.isExpanded = value
        elif isinstance(input, adsk.core.BoolValueCommandInput):
            input.value = value
        elif isinstance(input, adsk.core.TextBoxCommandInput):
            input.formattedText = value
        elif isinstance(input, adsk.core.StringValueCommandInput):
            input.value = value
        else:
            futil.log(f'{self.commandName} Unknown input type: {input.id} [{input.objectType}]')

    def getState(self, inputId: str):
        return self.inputState[inputId].value

    def getInput(self, inputId: str):
        return self.commandInputs[inputId]
    
    def toDict(self, ignoreKeys: list[str] = []):
        result = {}
        for key in self.inputState.keys():
            if key not in ignoreKeys:
                result[key] = self.inputState[key].toDict()
        return result