import dataclasses
import json
import math
import os

# Shape test cases, one JSON file each, holding every setting of a bin or baseplate InputState by its field name.
# Lengths are in mm and angles in degrees to read easily, the state keeps Fusion's cm and radians.
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

class TestCaseError(Exception):
    pass

@dataclasses.dataclass
class TestCase:
    # the file name without its extension
    name: str
    description: str
    generator: str
    state: object

def stateFromJson(generator: str, stateClass: type, settings: dict) -> object:
    """Every field of the state has to be there and nothing else, so a case never falls back to a default"""
    fieldNames = [field.name for field in dataclasses.fields(stateClass)]
    missing = [name for name in fieldNames if name not in settings]
    unknown = [name for name in settings if name not in fieldNames]
    if missing or unknown:
        raise TestCaseError(f'missing settings {missing}, unknown settings {unknown}')
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
    """Settings of a case file, rounded so float noise from the unit change doesn't show"""
    def value(name: str, fieldValue):
        if name in MM_FIELDS[generator]:
            return round(fieldValue * 10, 6)
        if name in DEGREE_FIELDS[generator]:
            return round(fieldValue * 180 / math.pi, 6)
        if name in CELL_LIST_FIELDS[generator]:
            return [list(cell) for cell in fieldValue]
        return fieldValue
    return {field.name: value(field.name, getattr(state, field.name)) for field in dataclasses.fields(state)}

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
    except (OSError, ValueError, KeyError, TypeError, TestCaseError) as err:
        raise TestCaseError(f'case {name}: {err}') from err
    return TestCase(name, data.get('description', ''), generator, state)

def loadCases(folder: str, stateClasses: dict[str, type]) -> list[TestCase]:
    """Cases of the folder by name"""
    paths = sorted(os.path.join(folder, fileName) for fileName in os.listdir(folder) if fileName.endswith('.json'))
    return [loadCase(path, stateClasses) for path in paths]

def caseJson(case: TestCase) -> str:
    return json.dumps({
        'description': case.description,
        'generator': case.generator,
        'settings': stateToJson(case.generator, case.state),
    }, indent=4, ensure_ascii=False) + '\n'

# the case list in tests/e2e/README.md, see tests/e2e/write_readme.py
GENERATOR_TITLES = {GENERATOR_BIN: 'Bins', GENERATOR_BASEPLATE: 'Baseplates'}
README_INTRO = """# Shape snapshot tests

Each case is a JSON file in [cases](cases) holding every setting of a bin or baseplate, lengths in mm and angles in
degrees. Its snapshot in [snapshots](snapshots), a folder named after the case, has the shapes it built, their
fingerprints and a preview picture.

Run them in Fusion from Utilities > Add-ins with **Gridfinity tests: run**, record new snapshots with **Gridfinity
tests: update snapshots**. The commands are there when the add-in runs from a git checkout.

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
        cases.append((os.path.splitext(fileName)[0], fileName, data.get('generator', ''), data.get('description', '')))
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
    ]
