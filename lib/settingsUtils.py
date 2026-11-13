import html
import adsk.core

def _displayValue(input: adsk.core.CommandInput) -> str | None:
    """The value as the dialog shows it, none for inputs that only act, like buttons"""
    boolInput = adsk.core.BoolValueCommandInput.cast(input)
    if boolInput is not None:
        return ('Yes' if boolInput.value else 'No') if boolInput.isCheckBox else None
    valueInput = adsk.core.ValueCommandInput.cast(input)
    if valueInput is not None:
        return valueInput.expression
    spinnerInput = adsk.core.IntegerSpinnerCommandInput.cast(input)
    if spinnerInput is not None:
        return str(spinnerInput.value)
    floatSpinnerInput = adsk.core.FloatSpinnerCommandInput.cast(input)
    if floatSpinnerInput is not None:
        return f'{floatSpinnerInput.value:g}'
    dropDownInput = adsk.core.DropDownCommandInput.cast(input)
    if dropDownInput is not None:
        return dropDownInput.selectedItem.name if dropDownInput.selectedItem is not None else None
    stringInput = adsk.core.StringValueCommandInput.cast(input)
    if stringInput is not None and not stringInput.isReadOnly:
        return stringInput.value
    return None

def _tableRows(table: adsk.core.TableCommandInput, rowName: str) -> list[list[str]]:
    """A row per item, the first table row holds the column names"""
    columns = [_cellText(table.getInputAtPosition(0, column)) for column in range(table.numberOfColumns)]
    rows = []
    for row in range(1, table.rowCount):
        cells = []
        for column in range(table.numberOfColumns):
            cell = table.getInputAtPosition(row, column)
            value = _displayValue(cell) if cell is not None else None
            if value not in (None, ''):
                cells.append(f'{columns[column]}: {value}' if columns[column] else value)
        rows.append([f'{rowName} {row}', ', '.join(cells)])
    return rows

def _cellText(input: adsk.core.CommandInput) -> str:
    stringInput = adsk.core.StringValueCommandInput.cast(input) if input is not None else None
    return stringInput.value if stringInput is not None else ''

def snapshotInputs(inputs: adsk.core.CommandInputs, ignoreIds: list[str], title: str) -> list[dict]:
    """Visible and enabled dialog inputs as sections named after their groups, each a list of label and value pairs"""
    sections = []
    def collect(inputs: adsk.core.CommandInputs, sectionTitle: str):
        section = {'title': sectionTitle, 'items': []}
        sections.append(section)
        for input in inputs:
            if input.id in ignoreIds or not input.isVisible:
                continue
            group = adsk.core.GroupCommandInput.cast(input)
            if group is not None:
                collect(group.children, group.name)
                continue
            table = adsk.core.TableCommandInput.cast(input)
            if table is not None:
                section['items'].extend(_tableRows(table, table.name.rstrip('s') or 'Row'))
                continue
            if not input.isEnabled:
                continue
            value = _displayValue(input)
            if value is not None:
                section['items'].append([input.name, value])
    collect(inputs, title)
    return [section for section in sections if len(section['items']) > 0]

def settingsText(settings: list[dict]) -> str:
    """Settings as plain text, a line per item under its section title, for the log"""
    lines = []
    for section in settings:
        lines.append(f'[{section.get("title", "")}]')
        for (label, value) in section.get('items', []):
            lines.append(f'  {label}: {value}')
    return '\n'.join(lines)

def settingsHtml(tag: dict, parameterExpression=None) -> str:
    """Tag settings for a read only text box, with the user parameters the body is tied to
    and their current expressions looked up by name, none when one is gone"""
    version = tag.get('generatorVersion') or 'unknown'
    lines = [f'<span style="color:#808080">Generated with version {html.escape(str(version))}</span>']
    parameters = tag.get('parameters')
    if isinstance(parameters, list) and len(parameters) > 0:
        lines.append('<br><br><b>Parameters</b>')
        for item in parameters:
            if isinstance(item, list) and len(item) == 2:
                (label, name) = item
                expression = parameterExpression(name) if parameterExpression is not None else None
                current = html.escape(str(expression)) if expression is not None else '<span style="color:#808080">missing, deleted or renamed</span>'
                lines.append(f'<br>{html.escape(str(label))}: {html.escape(str(name))} = {current}')
    settings = tag.get('settings')
    if not isinstance(settings, list) or len(settings) == 0:
        lines.append('<br>Settings weren\'t recorded, this was generated before the generator kept them.')
        return ''.join(lines)
    for section in settings:
        if not isinstance(section, dict):
            continue
        lines.append(f'<br><br><b>{html.escape(str(section.get("title", "")))}</b>')
        for item in section.get('items', []):
            if isinstance(item, list) and len(item) == 2:
                lines.append(f'<br>{html.escape(str(item[0]))}: {html.escape(str(item[1]))}')
    return ''.join(lines)

def settingsLineCount(tag: dict) -> int:
    parameters = tag.get('parameters')
    parameterLines = 2 + len(parameters) if isinstance(parameters, list) and len(parameters) > 0 else 0
    settings = tag.get('settings')
    if not isinstance(settings, list):
        return 3 + parameterLines
    return 1 + parameterLines + sum(2 + len(section.get('items', [])) for section in settings if isinstance(section, dict))
