"""
Tests for the report of a failed build, the text copied from the error palette to paste into an issue.
"""

import os
import importlib.util


def _load_error_report():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "errorReport.py")
    spec = importlib.util.spec_from_file_location("errorReport", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


errorReport = _load_error_report()


def _failure():
    def build():
        raise ValueError("wall too thin")
    try:
        build()
    except ValueError as err:
        return err


def _report(config='{"generator": "bin"}\n', parameters=None):
    return errorReport.createReport(
        "Gridfinity bin failed",
        _failure(),
        [["Base width unit", "gfBaseWidth = 42 mm, 42 mm, tagged"]] if parameters is None else parameters,
        config,
        [["Add-in version", "2.2.0.0"], ["Fusion version", "2.0.1"]],
    )


def test_message_is_the_last_traceback_line():
    assert errorReport.errorMessage(_failure()) == "ValueError: wall too thin"


def test_report_has_the_error_with_where_it_failed():
    report = _report()
    assert report["message"] == "ValueError: wall too thin"
    assert report["trace"].startswith("Traceback (most recent call last):")
    assert "in build" in report["trace"]
    assert report["trace"].endswith("ValueError: wall too thin")


def test_text_has_versions_trace_parameters_and_config():
    text = _report()["text"]
    assert text.startswith("**Gridfinity bin failed**: `ValueError: wall too thin`")
    assert "- Add-in version: 2.2.0.0" in text
    assert "- Fusion version: 2.0.1" in text
    assert "in build" in text
    assert "- Base width unit: `gfBaseWidth = 42 mm, 42 mm, tagged`" in text
    assert '```json\n{"generator": "bin"}\n```' in text


def test_text_leaves_out_what_could_not_be_read():
    text = _report(config=None, parameters=[])["text"]
    assert "**Parameters**" not in text
    assert "<summary>Config</summary>" not in text
    assert "<summary>Stack trace</summary>" in text


def _body(url):
    import urllib.parse
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["body"][0]


def test_issue_link_has_the_whole_report_when_it_fits():
    report = _report()
    assert report["issueUrl"].startswith(errorReport.ISSUES_URL + "?")
    assert _body(report["issueUrl"]) == report["text"]


def test_issue_link_leaves_out_the_config_when_too_long():
    report = _report(config='{"settings": "' + "x" * 9000 + '"}')
    body = _body(report["issueUrl"])
    assert len(report["issueUrl"]) <= errorReport.MAX_ISSUE_URL_LENGTH
    assert "<summary>Config</summary>" not in body
    assert "gfBaseWidth = 42 mm" in body
    assert "ValueError: wall too thin" in body
    assert errorReport.LEFT_OUT_NOTE in body


def test_issue_link_keeps_the_end_of_a_long_trace():
    report = _report()
    report["trace"] = "Traceback (most recent call last):\n" + '  File "x.py", line 1, in f\n' * 2000 + "ValueError: wall too thin"
    url = errorReport.issueUrl(report)
    body = _body(url)
    assert len(url) <= errorReport.MAX_ISSUE_URL_LENGTH
    assert "...\n" in body
    assert body.count("ValueError: wall too thin") >= 1
    assert errorReport.LEFT_OUT_NOTE in body


def test_issue_title_is_prefixed():
    import urllib.parse
    url = _report()["issueUrl"]
    title = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["title"][0]
    assert title == "[Error report] Gridfinity bin failed: ValueError: wall too thin"


def test_issue_is_labelled():
    import urllib.parse
    url = _report()["issueUrl"]
    assert urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["labels"] == ["error report"]
