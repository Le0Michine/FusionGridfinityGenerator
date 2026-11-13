# What a run of the snapshot tests or an update of the snapshots found, as the data the report page draws,
# see html/report.html, and as text for the log. Kept free of Fusion imports so it can be unit tested

# a test run
STATUS_PASS = 'pass'
# the same shape built differently, see snapshots.STATUS_REVIEW
STATUS_REVIEW = 'review'
STATUS_FAIL = 'fail'
# listed in the test window, not run since it opened
STATUS_UNTESTED = 'untested'
# while a run goes, waiting for their turn and the one being built
STATUS_QUEUED = 'queued'
STATUS_RUNNING = 'running'
# an update, a review there is a change of the same shape
STATUS_NEW = 'new'
STATUS_CHANGED = 'changed'
STATUS_UNCHANGED = 'unchanged'
STATUS_REMOVED = 'removed'

KIND_RUN = 'run'
KIND_UPDATE = 'update'

def body(name: str, status: str, changes: list[dict] = None, missing: dict = None, extra: dict = None, notes: list[str] = None) -> dict:
    """
    A body of a case. changes: fingerprint values as in the snapshot and as built, see snapshots.fingerprintChanges.
    missing, extra: material left over by the subtraction, see snapshots.leftoverData
    """
    return {'name': name, 'status': status, 'changes': changes or [], 'missing': missing, 'extra': extra, 'notes': notes or []}

# how the document of a case left open shows it, the differences or the built or the snapshot shape alone
VIEW_DIFF = 'diff'
VIEW_BUILT = 'built'
VIEW_SNAPSHOT = 'snapshot'
VIEWS = [VIEW_DIFF, VIEW_BUILT, VIEW_SNAPSHOT]

def case(name: str, description: str, status: str, bodies: list[dict] = None, notes: list[str] = None, view: str = None, previews: dict = None) -> dict:
    """
    view: how its document left open shows it, none without one. previews: urls of pictures of the shape, the snapshot's
    and a new one waiting to replace it, by those names
    """
    return {
        'name': name,
        'description': description,
        'status': status,
        'bodies': bodies or [],
        'notes': notes or [],
        'hasDocument': view is not None,
        'view': view,
        'previews': previews or {},
    }

def report(kind: str, title: str, cases: list[dict], seconds: float, pending: dict = None, message: str = '') -> dict:
    """pending: an update waiting to be confirmed, the number of snapshots it replaces and removes and their folder"""
    return {
        'kind': kind,
        'title': title,
        'cases': cases,
        'counts': statusCounts(cases),
        'seconds': round(seconds, 1),
        'pending': pending,
        'message': message,
        'progress': None,
    }

def statusCounts(cases: list[dict]) -> dict:
    counts = {}
    for item in cases:
        counts[item['status']] = counts.get(item['status'], 0) + 1
    return counts

def progress(done: int, total: int, current: str) -> dict:
    """How far a run is, the cases done of those it runs and the one being built"""
    return {'done': done, 'total': total, 'current': current}

def withCases(data: dict, cases: list[dict], seconds: float, message: str, runProgress: dict = None) -> dict:
    """
    The report with the cases just run in place of those of the same name, the others as they were, new ones at the end.
    runProgress: while the run goes, see progress, none once it's done
    """
    byName = {item['name']: item for item in cases}
    known = {item['name'] for item in data['cases']}
    merged = [byName.get(item['name'], item) for item in data['cases']] + [item for item in cases if item['name'] not in known]
    return {
        **data,
        'cases': merged,
        'counts': statusCounts(merged),
        'seconds': round(seconds, 1),
        'message': message,
        'progress': runProgress,
    }

def formatValue(value) -> str:
    if isinstance(value, list):
        return '(' + ', '.join(formatValue(item) for item in value) + ')'
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)

def leftoverText(label: str, leftover: dict) -> str:
    return (f'{label} {leftover["volume"]:g} mm³ in {leftover["pieces"]} piece(s), '
        f'within {formatValue(leftover["min"])} - {formatValue(leftover["max"])} mm')

def reportText(data: dict) -> str:
    summary = ', '.join(f'{count} {status}' for (status, count) in data['counts'].items())
    lines = [data['title'], f'{len(data["cases"])} case(s): {summary}, took {data["seconds"]:g} s']
    for item in data['cases']:
        lines.append(f'{item["status"].upper():10} {item["name"]}')
        lines.extend(f'    {note}' for note in item['notes'])
        for entry in item['bodies']:
            prefix = f'    {entry["name"]}: ' if entry['name'] else '    '
            lines.extend(f'{prefix}{change["key"]} {formatValue(change["expected"])} -> {formatValue(change["actual"])}' for change in entry['changes'])
            for (label, leftover) in [('missing', entry['missing']), ('extra', entry['extra'])]:
                if leftover is not None:
                    lines.append(prefix + leftoverText(label, leftover))
            lines.extend(f'{prefix}{note}' for note in entry['notes'])
    if data['pending']:
        previews = data['pending'].get('previews', 0)
        lines.append(f'Waiting to replace {data["pending"]["replace"]} and remove {data["pending"]["remove"]} snapshot(s)'
            + (f', add {previews} preview(s)' if previews else ''))
    if data['message']:
        lines.append(data['message'])
    return '\n'.join(lines)
