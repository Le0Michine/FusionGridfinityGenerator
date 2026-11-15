import dataclasses
import json
import math
import os

# Shape test cases, one JSON file each, holding the settings of a bin or baseplate InputState that differ from the
# dialog's defaults, see lib/defaultSettings.py, by field name in the config format of lib/configJson.py. A case
# is built the way a new bin is, a default changing changes it too.
# Kept free of Fusion imports so it can be unit tested, the state classes come in as an argument

def _loadLibFile(name: str):
    """A module of lib, when the tests and tools load this file on its own, outside the add-in package"""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'lib', f'{name}.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

try:
    from ...lib import configJson
    from ...lib import defaultSettings
except ImportError:
    configJson = _loadLibFile('configJson')
    defaultSettings = _loadLibFile('defaultSettings')
GENERATOR_BIN = configJson.GENERATOR_BIN
GENERATOR_BASEPLATE = configJson.GENERATOR_BASEPLATE
stateFromJson = configJson.stateFromJson
stateToJson = configJson.stateToJson
# by generator
DEFAULT_SETTINGS = defaultSettings.SETTINGS

# the user parameters a case may change after building, with the setting each stands for. Keep the names literal,
# they're in user documents. A bin has units of its own, the first bin of a case's new document is numbered 1, see
# binBuilder.BIN_PARAMETERS, baseplates share theirs, see lib/gridfinityUtils/sharedParameters.py
PARAMETER_FIELDS = {
    GENERATOR_BIN: {'gfBin1_baseWidth': 'baseWidth', 'gfBin1_baseLength': 'baseLength', 'gfBin1_heightUnit': 'heightUnit'},
    GENERATOR_BASEPLATE: {'gfBaseWidth': 'baseWidth', 'gfBaseLength': 'baseLength'},
}

class TestCaseError(Exception):
    pass

@dataclasses.dataclass
class TestCase:
    # the file name without its extension
    name: str
    description: str
    generator: str
    state: object
    # parameters set after building, in cm, the result has to be the same as built with them, see editedState
    parameters: dict[str, float] = dataclasses.field(default_factory=dict)

def parametersFromJson(generator: str, parameters: dict) -> dict[str, float]:
    """Values in mm of the generator's parameters, in cm"""
    unknown = [name for name in parameters if name not in PARAMETER_FIELDS[generator]]
    if unknown:
        raise TestCaseError(f'unknown parameters {unknown}, a {generator} has {sorted(PARAMETER_FIELDS[generator])}')
    for (name, value) in parameters.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise TestCaseError(f'parameter {name} has to be a length in mm, not {value!r}')
    return {name: value / 10 for (name, value) in parameters.items()}

def editedState(case: TestCase) -> object:
    """The settings the case would have built with its parameters set from the start"""
    fields = PARAMETER_FIELDS[case.generator]
    return dataclasses.replace(case.state, **{fields[name]: value for (name, value) in case.parameters.items()})

def loadCase(path: str, stateClasses: dict[str, type]) -> TestCase:
    """stateClasses: the InputState class of each generator"""
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        with open(path, encoding='utf-8') as file:
            data = json.load(file)
        generator = data['generator']
        if generator not in stateClasses:
            raise TestCaseError(f'unknown generator {generator!r}')
        if not isinstance(data['settings'], dict):
            raise TestCaseError('settings are an object of the settings that differ from the defaults')
        state = stateFromJson(generator, stateClasses[generator], {**DEFAULT_SETTINGS[generator], **data['settings']})
        parameters = parametersFromJson(generator, data.get('parameters', {}))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, TestCaseError, configJson.ConfigError) as err:
        raise TestCaseError(f'case {name}: {err}') from err
    return TestCase(name, data.get('description', ''), generator, state, parameters)

def loadCases(folder: str, stateClasses: dict[str, type]) -> list[TestCase]:
    """Cases of the folder by name"""
    paths = sorted(os.path.join(folder, fileName) for fileName in os.listdir(folder) if fileName.endswith('.json'))
    return [loadCase(path, stateClasses) for path in paths]

def parametersToJson(case: TestCase) -> dict:
    return {name: round(value * 10, 6) for (name, value) in case.parameters.items()}

def changedSettings(generator: str, settings: dict) -> dict:
    """The settings, as stateToJson has them, that differ from the defaults"""
    defaults = DEFAULT_SETTINGS[generator]
    return {name: value for (name, value) in settings.items() if name not in defaults or value != defaults[name]}

def caseJson(case: TestCase) -> str:
    data = {
        'description': case.description,
        'generator': case.generator,
        'settings': changedSettings(case.generator, stateToJson(case.generator, case.state)),
    }
    if case.parameters:
        data['parameters'] = parametersToJson(case)
    return json.dumps(data, indent=4, ensure_ascii=False) + '\n'

# the case list in tests/e2e/README.md, see tests/e2e/write_readme.py
GENERATOR_TITLES = {GENERATOR_BIN: 'Bins', GENERATOR_BASEPLATE: 'Baseplates'}
README_INTRO = """# Shape snapshot tests

Each case is a JSON file in [cases](cases) holding the settings of a bin or baseplate that differ from the dialog's
defaults in [lib/defaultSettings.py](../../lib/defaultSettings.py), lengths in mm and angles in degrees. Its snapshot in
[snapshots](snapshots), a folder named after the case, has the shapes it built, their fingerprints, every setting they
were built with and a preview picture. A run tells when the settings changed, a default changing among them, even
when the shapes stay the same.

Run them in Fusion from Utilities > Add-ins with **Gridfinity tests: run**, record new snapshots with **Gridfinity
tests: update snapshots**. The commands are there when the add-in runs from a git checkout.

A case with parameters sets those user parameters once built, the snapshot is of the bodies Fusion recomputed,
and a run also compares them with the case built with the new values from the start.

This page is written from the case files, run `python3 tests/e2e/write_readme.py` after adding or changing one.
"""

# the name of a snapshot's picture, see commandSnapshotTests/snapshots.py
PREVIEW_FILE = 'preview.png'
# every setting of the case its snapshot was built with, see snapshotSettings
SETTINGS_FILE = 'settings.json'
README_PREVIEW_WIDTH = 120

def casesMarkdown(folder: str) -> str:
    """
    The cases of the folder by generator, each linked to its file, with its description and the preview of its
    snapshot, in the snapshots folder beside it, when there is one
    """
    snapshotsFolder = os.path.join(os.path.dirname(folder), 'snapshots')
    def preview(name: str) -> str:
        if not os.path.isfile(os.path.join(snapshotsFolder, name, PREVIEW_FILE)):
            return ''
        return f'<img src="snapshots/{name}/{PREVIEW_FILE}" width="{README_PREVIEW_WIDTH}" alt="{name}">'
    cases = []
    for fileName in sorted(name for name in os.listdir(folder) if name.endswith('.json')):
        with open(os.path.join(folder, fileName), encoding='utf-8') as file:
            data = json.load(file)
        description = data.get('description', '')
        if data.get('parameters'):
            edits = ', '.join(f'`{name}` {value:g} mm' for (name, value) in data['parameters'].items())
            description += f'. Sets {edits} once built, a run compares that with a build using those values from the start'
        cases.append((os.path.splitext(fileName)[0], fileName, data.get('generator', ''), description))
    lines = [README_INTRO]
    for (generator, title) in GENERATOR_TITLES.items():
        section = [case for case in cases if case[2] == generator]
        if len(section) == 0:
            continue
        lines += [f'## {title}', '', '| Preview | Case | Description |', '| --- | --- | --- |']
        lines += [f'| {preview(name)} | [{name}](cases/{fileName}) | {description} |' for (name, fileName, _, description) in section]
        lines.append('')
    return '\n'.join(lines)

def caseSettings(case: TestCase) -> list[dict]:
    """The case as the settings a generated body is tagged with, so Show settings tells it's a test body and which"""
    return [
        {'title': 'Test case', 'items': [['Case', case.name], ['Description', case.description]]},
        {
            'title': 'Settings, mm and degrees',
            'items': [[name, json.dumps(value, ensure_ascii=False)] for (name, value) in stateToJson(case.generator, case.state).items()],
        },
    ] + ([{
        'title': 'Parameters set after building, mm',
        'items': [[name, json.dumps(value)] for (name, value) in parametersToJson(case).items()],
    }] if case.parameters else [])

def snapshotSettings(case: TestCase) -> dict:
    """Every setting the case is built with, its defaults filled in, as its snapshot keeps them"""
    return stateToJson(case.generator, case.state)

def settingsText(settings: dict) -> str:
    return json.dumps(settings, indent=4, ensure_ascii=False) + '\n'

def settingChanges(expected: dict, actual: dict) -> list[dict]:
    """
    Each setting that differs, as the snapshot was built with it and as the case has it now, none for a setting only
    one of them has. Values that aren't numbers, flags or text are written as JSON, the report shows them as they are
    """
    def shown(value):
        return value if value is None or isinstance(value, (bool, int, float, str)) else json.dumps(value, ensure_ascii=False)
    def same(a, b) -> bool:
        # a flag isn't the number it equals in Python
        if isinstance(a, bool) or isinstance(b, bool):
            return type(a) is type(b) and a == b
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
        return a == b
    names = list(expected) + [name for name in actual if name not in expected]
    return [
        {'key': name, 'expected': shown(expected.get(name)), 'actual': shown(actual.get(name))}
        for name in names
        if name not in expected or name not in actual or not same(expected[name], actual[name])
    ]
