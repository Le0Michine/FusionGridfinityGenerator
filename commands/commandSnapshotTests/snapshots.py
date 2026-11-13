import adsk.core, adsk.fusion
import dataclasses
import json
import os
import shutil

from . import testCases

# Snapshot of a test case: each body it built saved to .smt, with a fingerprint of all of them in fingerprint.json.
# A body is compared by its fingerprint and by subtracting it from its snapshot and the other way round,
# see compareSnapshot for what each outcome means

FINGERPRINT_FILE = 'fingerprint.json'
# a picture of the shapes to look at, not compared, see entry.takePreview
PREVIEW_FILE = testCases.PREVIEW_FILE
# a leftover of a subtraction smaller than this counts as nothing, mm³
LEFTOVER_TOLERANCE = 0.001
# fingerprint numbers this close count as the same, relative to their size
RELATIVE_TOLERANCE = 1e-6

STATUS_PASS = 'pass'
# the same shape built differently, faces split another way or numbers drifting, mostly after a Fusion update
STATUS_REVIEW = 'review'
STATUS_FAIL = 'fail'
STATUS_ORDER = [STATUS_PASS, STATUS_REVIEW, STATUS_FAIL]

@dataclasses.dataclass
class BodyResult:
    name: str
    status: str
    notes: list[str]
    # fingerprint values that differ, see fingerprintChanges
    changes: list[dict] = dataclasses.field(default_factory=list)
    # in memory only, see leftover
    missing: adsk.fusion.BRepBody | None = None
    extra: adsk.fusion.BRepBody | None = None
    # the body loaded from the snapshot, in memory only
    reference: adsk.fusion.BRepBody | None = None

def worstStatus(statuses: list[str]) -> str:
    return max(statuses, key=STATUS_ORDER.index, default=STATUS_PASS)

def fingerprint(body: adsk.fusion.BRepBody) -> dict:
    """Lengths in mm, areas in mm², volumes in mm³"""
    box = body.boundingBox
    return {
        'volume': round(body.volume * 1000, 6),
        'area': round(body.area * 100, 6),
        'bboxMin': [round(v * 10, 6) for v in box.minPoint.asArray()],
        'bboxMax': [round(v * 10, 6) for v in box.maxPoint.asArray()],
        'lumps': body.lumps.count,
        'faces': body.faces.count,
        'edges': body.edges.count,
        'vertices': body.vertices.count,
    }

def hasSnapshot(folder: str) -> bool:
    return os.path.isfile(os.path.join(folder, FINGERPRINT_FILE))

def saveSnapshot(folder: str, bodies: list[adsk.fusion.BRepBody]):
    """Replaces the snapshot in the folder with the bodies"""
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    tbm = adsk.fusion.TemporaryBRepManager.get()
    entries = []
    for (index, body) in enumerate(bodies):
        fileName = f'body{index + 1}.smt'
        tbm.exportToFile([tbm.copy(body)], os.path.join(folder, fileName))
        entries.append({'name': body.name, 'file': fileName, **fingerprint(body)})
    with open(os.path.join(folder, FINGERPRINT_FILE), 'w', encoding='utf-8') as file:
        file.write(json.dumps({'bodies': entries}, indent=4, ensure_ascii=False) + '\n')

def isClose(expected, actual) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(isClose(e, a) for (e, a) in zip(expected, actual))
    if isinstance(expected, float) or isinstance(actual, float):
        return abs(expected - actual) <= RELATIVE_TOLERANCE * max(abs(expected), abs(actual), 1)
    return expected == actual

def fingerprintChanges(expected: dict, actual: dict) -> list[dict]:
    """Each value that differs, as it is in the snapshot and as built"""
    return [{'key': key, 'expected': expected.get(key), 'actual': actual[key]} for key in actual if not isClose(expected.get(key), actual[key])]

def leftover(target: adsk.fusion.BRepBody, tool: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody | None:
    """What is left of target after cutting tool out of it, none when that's nothing"""
    tbm = adsk.fusion.TemporaryBRepManager.get()
    result = tbm.copy(target)
    tbm.booleanOperation(result, tbm.copy(tool), adsk.fusion.BooleanTypes.DifferenceBooleanType)
    if result.faces.count == 0 or result.volume * 1000 < LEFTOVER_TOLERANCE:
        return None
    return result

def leftoverData(body: adsk.fusion.BRepBody | None) -> dict | None:
    """How much is left over and where, mm³ and mm"""
    if body is None:
        return None
    box = body.boundingBox
    return {
        'volume': round(body.volume * 1000, 3),
        'pieces': body.lumps.count,
        'min': [round(v * 10, 2) for v in box.minPoint.asArray()],
        'max': [round(v * 10, 2) for v in box.maxPoint.asArray()],
    }

def compareSnapshot(folder: str, bodies: list[adsk.fusion.BRepBody]) -> list[BodyResult]:
    """
    Bodies against the snapshot, paired by name. Material left over by the subtraction either way fails, as does a body
    missing on either side. Only the fingerprint changing, the shape staying, is for review
    """
    if not hasSnapshot(folder):
        return [BodyResult('', STATUS_FAIL, ['no snapshot, run Gridfinity tests: update snapshots'])]
    with open(os.path.join(folder, FINGERPRINT_FILE), encoding='utf-8') as file:
        expectedBodies = {entry['name']: entry for entry in json.load(file)['bodies']}
    builtBodies = {body.name: body for body in bodies}

    results = []
    for name in expectedBodies:
        if name not in builtBodies:
            results.append(BodyResult(name, STATUS_FAIL, ['in the snapshot, not built']))
    tbm = adsk.fusion.TemporaryBRepManager.get()
    for (name, body) in builtBodies.items():
        expected = expectedBodies.get(name)
        if expected is None:
            results.append(BodyResult(name, STATUS_FAIL, ['built, not in the snapshot']))
            continue
        changes = fingerprintChanges(expected, fingerprint(body))
        reference = tbm.createFromFile(os.path.join(folder, expected['file'])).item(0)
        missing = leftover(reference, body)
        extra = leftover(body, reference)
        if missing is not None or extra is not None:
            status = STATUS_FAIL
        elif len(changes) > 0:
            status = STATUS_REVIEW
        else:
            status = STATUS_PASS
        results.append(BodyResult(name, status, [], changes, missing, extra, reference))
    return results
