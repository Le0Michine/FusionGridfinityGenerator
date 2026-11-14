import traceback
import urllib.parse

# What a failed build shows in the error palette, see lib/ui/errorPalette.py, and the text copied from it to report
# the error. Kept free of Fusion imports so it can be unit tested

ISSUES_URL = 'https://github.com/Le0Michine/FusionGridfinityGenerator/issues/new'
# tells reports from the add-in apart from issues opened by hand
ISSUE_TITLE_PREFIX = '[Error report]'
# GitHub only sets them for people who can triage the repo, others get the issue without
ISSUE_LABELS = 'error report'
# GitHub turns away longer links to a new issue, what's left out of the body is on the clipboard
MAX_ISSUE_URL_LENGTH = 8000
LEFT_OUT_NOTE = '_Some of the report didn\'t fit the link, the full report is on the clipboard, paste it below._'

def errorMessage(err: BaseException) -> str:
    """The last line of a traceback, the error's type and what it says"""
    return traceback.format_exception_only(type(err), err)[-1].strip()

def createReport(title: str, err: BaseException, parameters: list[list[str]], config: str | None, environment: list[list[str]]) -> dict:
    """
    What the palette's page draws, with the report to copy. parameters are label and value pairs, the shared user
    parameters of the design, see sharedParameters.describeSharedParameters, config the inputs as a config file to build
    it again, see configJson.configText, none when they couldn't be read. environment are label and value pairs, the
    versions of the add-in and Fusion and what of the design changes how things get built
    """
    report = {
        'title': title,
        'message': errorMessage(err),
        'trace': ''.join(traceback.format_exception(type(err), err, err.__traceback__)).rstrip(),
        'environment': environment,
        'parameters': parameters,
        'config': config,
        'issuesUrl': ISSUES_URL,
    }
    report['text'] = reportText(report)
    report['issueUrl'] = issueUrl(report)
    return report

def reportText(report: dict, config: str | None = None, trace: str | None = None, note: str = '') -> str:
    """Markdown for a GitHub issue, the long parts fold so the issue reads well. config and trace are the report's
    unless given, an empty one is left out"""
    config = report['config'] if config is None else config
    trace = report['trace'] if trace is None else trace
    fence = '```'
    lines = [
        f'**{report["title"]}**: `{report["message"]}`',
        '',
        *[f'- {label}: {value}' for (label, value) in report['environment']],
        '',
        '<details><summary>Stack trace</summary>',
        '',
        fence,
        trace,
        fence,
        '</details>',
    ]
    if report['parameters']:
        lines.extend(['', '**Parameters**', '', *[f'- {label}: `{value}`' for (label, value) in report['parameters']]])
    if config:
        lines.extend(['', '<details><summary>Config</summary>', '', f'{fence}json', config.rstrip(), fence, '</details>'])
    if note:
        lines.extend(['', note])
    return '\n'.join(lines) + '\n'

def issueUrl(report: dict) -> str:
    """
    A new issue with the report filled in. When it's too long for a link the config goes first, then the trace from
    its start, its end says where it failed
    """
    title = f'{ISSUE_TITLE_PREFIX} {report["title"]}: {report["message"]}'
    def url(body: str) -> str:
        return f'{ISSUES_URL}?{urllib.parse.urlencode({"title": title, "labels": ISSUE_LABELS, "body": body})}'
    for body in [reportText(report), reportText(report, config='', note=LEFT_OUT_NOTE)]:
        if len(url(body)) <= MAX_ISSUE_URL_LENGTH:
            return url(body)
    traceLines = report['trace'].splitlines()
    for keep in range(len(traceLines) - 1, 0, -1):
        body = reportText(report, config='', trace='\n'.join(['...', *traceLines[-keep:]]), note=LEFT_OUT_NOTE)
        if len(url(body)) <= MAX_ISSUE_URL_LENGTH:
            return url(body)
    return url(LEFT_OUT_NOTE)
