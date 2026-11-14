import dataclasses
import json
import math

# Bin and baseplate settings as JSON, every field of a generator's InputState by its name. Lengths are in mm and
# angles in degrees to read easily, the state keeps Fusion's cm and radians. Shape test cases and the config files
# users save are in this format, see commandSnapshotTests/testCases.py.
# Kept free of Fusion imports so it can be unit tested, the state classes come in as an argument

GENERATOR_BIN = 'bin'
GENERATOR_BASEPLATE = 'baseplate'

# the rest are counts, base or height units, flags and names, kept as they are
MM_FIELDS = {
    GENERATOR_BIN: {
        'baseWidth', 'baseLength', 'heightUnit', 'xyClearance', 'wallThickness', 'screwHoleDiameter',
        'magnetCutoutDiameter', 'magnetCutoutDepth', 'scoopMaxRadius', 'tabWidth', 'creaseDepth',
    },
    GENERATOR_BASEPLATE: {
        'baseWidth', 'baseLength', 'xyClearance', 'magnetSocketSize', 'magnetSocketDepth', 'screwHoleSize',
        'screwHeadSize', 'paddingLeft', 'paddingTop', 'paddingRight', 'paddingBottom', 'extraBottomThickness',
        'verticalClearance', 'connectionHoleSize', 'areaWidth', 'areaLength', 'fitTolerance', 'bedWidth',
        'bedLength', 'bedMargin',
    },
}
DEGREE_FIELDS = {
    GENERATOR_BIN: {'tabOverhangAngle', 'tabTopAngle'},
    GENERATOR_BASEPLATE: set(),
}
# lists of cells, JSON has no tuples
CELL_LIST_FIELDS = {
    GENERATOR_BIN: {'shapeCells'},
    GENERATOR_BASEPLATE: set(),
}

GENERATOR_TITLES = {GENERATOR_BIN: 'bin', GENERATOR_BASEPLATE: 'baseplate'}

class ConfigError(Exception):
    pass

def stateFromJson(generator: str, stateClass: type, settings: dict) -> object:
    """Every field of the state has to be there and nothing else, so it never falls back to a default"""
    fieldNames = [field.name for field in dataclasses.fields(stateClass)]
    missing = [name for name in fieldNames if name not in settings]
    unknown = [name for name in settings if name not in fieldNames]
    if missing or unknown:
        raise ConfigError(f'missing settings {missing}, unknown settings {unknown}')
    def value(name: str):
        if name in MM_FIELDS[generator]:
            return settings[name] / 10
        if name in DEGREE_FIELDS[generator]:
            return settings[name] / 180 * math.pi
        if name in CELL_LIST_FIELDS[generator]:
            return [tuple(cell) for cell in settings[name]]
        return settings[name]
    return stateClass(**{name: value(name) for name in fieldNames})

def stateToJson(generator: str, state: object) -> dict:
    """Settings by field name, rounded so float noise from the unit change doesn't show"""
    def value(name: str, fieldValue):
        if name in MM_FIELDS[generator]:
            return round(fieldValue * 10, 6)
        if name in DEGREE_FIELDS[generator]:
            return round(fieldValue * 180 / math.pi, 6)
        if name in CELL_LIST_FIELDS[generator]:
            return [list(cell) for cell in fieldValue]
        return fieldValue
    return {field.name: value(field.name, getattr(state, field.name)) for field in dataclasses.fields(state)}

def configText(generator: str, settings: dict, generatorVersion: str = '') -> str:
    """A config file of settings from stateToJson, a test case without its description"""
    data = {'generator': generator}
    if generatorVersion:
        data['generatorVersion'] = generatorVersion
    data['settings'] = settings
    return json.dumps(data, indent=4, ensure_ascii=False) + '\n'

@dataclasses.dataclass
class Choice:
    """The options a dropdown setting has, and the one a value it doesn't have becomes"""
    options: list[str]
    default: str

@dataclasses.dataclass
class ConfigNotes:
    """What reading a config changed, see readConfig"""
    # settings this version doesn't know
    unknown: list[str] = dataclasses.field(default_factory=list)
    # settings the file doesn't have with the current value they keep, as stateToJson has it
    missing: list[tuple[str, object]] = dataclasses.field(default_factory=list)
    # dropdown settings with an option they don't have, the value in the file and the default used
    replaced: list[tuple[str, str, str]] = dataclasses.field(default_factory=list)

    def isEmpty(self) -> bool:
        return not (self.unknown or self.missing or self.replaced)

def _typeName(fieldType) -> str:
    if fieldType is bool:
        return 'yes or no'
    if fieldType is int:
        return 'a whole number'
    if fieldType is float:
        return 'a number'
    if fieldType is str:
        return 'text'
    if fieldType == list[tuple[int, int]]:
        return 'a list of [x, y] cells'
    if fieldType == list[dict]:
        return 'a list of objects'
    return str(fieldType)

def _isNumber(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def _fitsType(value, fieldType) -> bool:
    """A JSON value for a state field of the type. Whole numbers may be written as 2.0"""
    if fieldType is bool:
        return isinstance(value, bool)
    if fieldType is int:
        return _isNumber(value) and float(value).is_integer()
    if fieldType is float:
        return _isNumber(value)
    if fieldType is str:
        return isinstance(value, str)
    if fieldType == list[tuple[int, int]]:
        return isinstance(value, list) and all(
            isinstance(cell, list) and len(cell) == 2 and all(_fitsType(item, int) for item in cell) for cell in value
        )
    if fieldType == list[dict]:
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)
    return False

def _withType(value, fieldType):
    if fieldType is int:
        return int(value)
    if fieldType == list[tuple[int, int]]:
        return [[int(x), int(y)] for (x, y) in value]
    return value

def readConfig(text: str, generator: str, stateClass: type, current: object, choices: dict[str, Choice] = None) -> tuple[object, ConfigNotes]:
    """
    The state of a config file for the generator and what reading it changed. A value of the wrong type refuses the
    file, ranges are left to the dialog. Settings the file doesn't have, saved by an older version, keep their value
    from current, ones this version doesn't know are skipped, and a dropdown option that isn't in choices becomes
    its default
    """
    try:
        data = json.loads(text)
    except ValueError as err:
        raise ConfigError(f'It isn\'t a JSON file, {err}') from err
    if not isinstance(data, dict) or not isinstance(data.get('settings'), dict):
        raise ConfigError('It has no settings of a bin or a baseplate')
    if data.get('generator') != generator:
        title = GENERATOR_TITLES.get(data.get('generator'))
        raise ConfigError(f'It\'s the config of a {title}, not of a {GENERATOR_TITLES[generator]}' if title else f'It isn\'t the config of a {GENERATOR_TITLES[generator]}')
    fieldTypes = {field.name: field.type for field in dataclasses.fields(stateClass)}
    loaded = data['settings']
    wrongTypes = [
        f'{name} has to be {_typeName(fieldTypes[name])}, not {json.dumps(value)}'
        for (name, value) in loaded.items()
        if name in fieldTypes and not _fitsType(value, fieldTypes[name])
    ]
    if wrongTypes:
        raise ConfigError(', '.join(wrongTypes))
    settings = stateToJson(generator, current)
    notes = ConfigNotes(
        unknown=[name for name in loaded if name not in fieldTypes],
        missing=[(name, settings[name]) for name in fieldTypes if name not in loaded],
    )
    for (name, value) in loaded.items():
        if name not in fieldTypes:
            continue
        choice = (choices or {}).get(name)
        if choice is not None and value not in choice.options:
            notes.replaced.append((name, value, choice.default))
            value = choice.default
        settings[name] = _withType(value, fieldTypes[name])
    return (stateFromJson(generator, stateClass, settings), notes)

def _displayValue(generator: str, name: str, value) -> str:
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, list):
        return f'{len(value)} items'
    if isinstance(value, str):
        return f'"{value}"'
    if name in MM_FIELDS[generator]:
        return f'{value:g} mm'
    if name in DEGREE_FIELDS[generator]:
        return f'{value:g} deg'
    return f'{value:g}'

def notesText(generator: str, notes: ConfigNotes) -> str:
    """What reading a config changed, a section per kind of change"""
    sections = []
    if notes.unknown:
        sections.append('Not recognised, skipped:\n' + '\n'.join(f'  • {name}' for name in notes.unknown))
    if notes.missing:
        sections.append('Not in the file, kept the current value:\n' + '\n'.join(
            f'  • {name} ({_displayValue(generator, name, value)})' for (name, value) in notes.missing
        ))
    if notes.replaced:
        sections.append('Unknown option, used the default:\n' + '\n'.join(
            f'  • {name} "{value}" → {default}' for (name, value, default) in notes.replaced
        ))
    return '\n\n'.join(sections)
