import html
import re
import adsk.core
if __package__:
    from . import i18n
else:
    # loaded on its own, as the unit tests load it, the translations come from the file beside it
    import importlib.util as _importlib_util
    import os as _os
    _i18n_spec = _importlib_util.spec_from_file_location('i18n', _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'i18n.py'))
    i18n = _importlib_util.module_from_spec(_i18n_spec)
    _i18n_spec.loader.exec_module(i18n)

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
        return i18n.key(dropDownInput.selectedItem.name) if dropDownInput.selectedItem is not None else None
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
                collect(group.children, i18n.key(group.name))
                continue
            table = adsk.core.TableCommandInput.cast(input)
            if table is not None:
                section['items'].extend(_tableRows(table, i18n.key(table.name).rstrip('s') or 'Row'))
                continue
            if not input.isEnabled:
                continue
            value = _displayValue(input)
            if value is not None:
                section['items'].append([i18n.key(input.name), value])
    collect(inputs, i18n.key(title))
    return [section for section in sections if len(section['items']) > 0]

def settingsText(settings: list[dict]) -> str:
    """Settings as plain text, a line per item under its section title, for the log"""
    lines = []
    for section in settings:
        lines.append(f'[{section.get("title", "")}]')
        for (label, value) in section.get('items', []):
            lines.append(f'  {label}: {value}')
    return '\n'.join(lines)

def _label(text: str) -> str:
    """A setting's or parameter's name as shown, the numbered ones of compartments and shape rows too"""
    for (pattern, key) in [(r'Compartment (\d+) label', 'Compartment {index} label'), (r'Compartment (\d+)', 'Compartment {index}'), (r'Row (\d+)', 'Row {index}')]:
        match = re.fullmatch(pattern, text)
        if match:
            return i18n.t(key, index=match.group(1))
    return i18n.t(text)

def settingsHtml(tag: dict, parameterExpression=None) -> str:
    """Tag settings for the settings page, with the user parameters the body is tied to
    and their current expressions looked up by name, none when one is gone"""
    version = tag.get('generatorVersion') or i18n.t('unknown')
    lines = [f'<span style="color:#808080">{i18n.t("Generated with version {version}", version=html.escape(str(version)))}</span>']
    parameters = tag.get('parameters')
    if isinstance(parameters, list) and len(parameters) > 0:
        lines.append(f'<br><br><b>{i18n.t("Parameters")}</b>')
        for item in parameters:
            if isinstance(item, list) and len(item) == 2:
                (label, name) = item
                expression = parameterExpression(name) if parameterExpression is not None else None
                current = html.escape(str(expression)) if expression is not None else f'<span style="color:#808080">{i18n.t("missing, deleted or renamed")}</span>'
                lines.append(f'<br>{html.escape(_label(str(label)))}: {html.escape(str(name))} = {current}')
    settings = tag.get('settings')
    if not isinstance(settings, list) or len(settings) == 0:
        lines.append('<br>' + i18n.t("Settings weren't recorded, this was generated before the generator kept them."))
        return ''.join(lines)
    for section in settings:
        if not isinstance(section, dict):
            continue
        lines.append(f'<br><br><b>{html.escape(i18n.t(str(section.get("title", ""))))}</b>')
        for item in section.get('items', []):
            if isinstance(item, list) and len(item) == 2:
                lines.append(f'<br>{html.escape(_label(str(item[0])))}: {html.escape(i18n.t(str(item[1])))}')
    return ''.join(lines)
