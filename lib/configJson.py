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

def _kind(value) -> str:
    if isinstance(value, bool):
        return 'yes or no'
    if isinstance(value, (int, float)):
        return 'a number'
    if isinstance(value, str):
        return 'text'
    if isinstance(value, list):
        return 'a list'
    return type(value).__name__

def readConfig(text: str, generator: str, stateClass: type, current: object) -> tuple[object, list[str]]:
    """
    The state of a config file for the generator, with the notes on what was left as it is. Settings the file doesn't
    have, saved by an older version, keep their value from current, ones this version doesn't know are skipped
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
    settings = stateToJson(generator, current)
    loaded = data['settings']
    wrongKinds = [
        f'{name} has to be {_kind(settings[name])}, not {json.dumps(value)}'
        for (name, value) in loaded.items()
        if name in settings and _kind(value) != _kind(settings[name])
    ]
    if wrongKinds:
        raise ConfigError(', '.join(wrongKinds))
    notes = []
    missing = [name for name in settings if name not in loaded]
    if missing:
        notes.append(f'kept the current {", ".join(missing)}')
    unknown = [name for name in loaded if name not in settings]
    if unknown:
        notes.append(f'skipped unknown {", ".join(unknown)}')
    settings.update({name: value for (name, value) in loaded.items() if name in settings})
    try:
        return (stateFromJson(generator, stateClass, settings), notes)
    except (TypeError, ValueError) as err:
        raise ConfigError(str(err)) from err
