import dataclasses
import json
import os

# Shape test cases, one JSON file each, holding every setting of a bin or baseplate InputState by its field name,
# in the config format of lib/configJson.py.
# Kept free of Fusion imports so it can be unit tested, the state classes come in as an argument

def _loadConfigJson():
    """lib/configJson.py, also when the tests and tools load this file on its own, outside the add-in package"""
    try:
        from ...lib import configJson
        return configJson
    except ImportError:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'lib', 'configJson.py')
        spec = importlib.util.spec_from_file_location('configJson', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

configJson = _loadConfigJson()
GENERATOR_BIN = configJson.GENERATOR_BIN
GENERATOR_BASEPLATE = configJson.GENERATOR_BASEPLATE
stateFromJson = configJson.stateFromJson
stateToJson = configJson.stateToJson

# the shared user parameters a case may change after building, see lib/gridfinityUtils/sharedParameters.py, with the
# setting each stands for. Keep the names literal, they're in user documents
PARAMETER_FIELDS = {
    GENERATOR_BIN: {'gfBaseWidth': 'baseWidth', 'gfBaseLength': 'baseLength', 'gfHeightUnit': 'heightUnit'},
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
    # shared parameters set after building, in cm, the result has to be the same as built with them, see editedState
    parameters: dict[str, float] = dataclasses.field(default_factory=dict)

def parametersFromJson(generator: str, parameters: dict) -> dict[str, float]:
    """Values in mm of the generator's shared parameters, in cm"""
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
        state = stateFromJson(generator, stateClasses[generator], data['settings'])
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

def caseJson(case: TestCase) -> str:
    data = {
        'description': case.description,
        'generator': case.generator,
        'settings': stateToJson(case.generator, case.state),
    }
    if case.parameters:
        data['parameters'] = parametersToJson(case)
    return json.dumps(data, indent=4, ensure_ascii=False) + '\n'

# the case list in tests/e2e/README.md, see tests/e2e/write_readme.py
GENERATOR_TITLES = {GENERATOR_BIN: 'Bins', GENERATOR_BASEPLATE: 'Baseplates'}
README_INTRO = """# Shape snapshot tests

Each case is a JSON file in [cases](cases) holding every setting of a bin or baseplate, lengths in mm and angles in
degrees. Its snapshot in [snapshots](snapshots), a folder named after the case, has the shapes it built, their
fingerprints and a preview picture.

Run them in Fusion from Utilities > Add-ins with **Gridfinity tests: run**, record new snapshots with **Gridfinity
tests: update snapshots**. The commands are there when the add-in runs from a git checkout.

A case with parameters sets those shared user parameters once built, the snapshot is of the bodies Fusion recomputed,
and a run also compares them with the case built with the new values from the start.

This page is written from the case files, run `python3 tests/e2e/write_readme.py` after adding or changing one.
"""

# the name of a snapshot's picture, see commandSnapshotTests/snapshots.py
PREVIEW_FILE = 'preview.png'
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
