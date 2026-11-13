"""
Tests for the snapshot test report: the data the report page draws and its text for the log.
"""

import os
import importlib.util


def _load_report():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "commands", "commandSnapshotTests", "report.py")
    spec = importlib.util.spec_from_file_location("snapshotReport", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load_report()

LEFTOVER = {"volume": 1.234, "pieces": 2, "min": [10.0, 20.5, 30.0], "max": [11.0, 21.5, 35.25]}


def failed_case():
    body = report.body(
        "Gridfinity bin 3x2x5",
        report.STATUS_FAIL,
        [{"key": "volume", "expected": 1000.5, "actual": 1001.0}, {"key": "faces", "expected": 120, "actual": 124}],
        missing=LEFTOVER,
    )
    return report.case("bin_a", "a bin", report.STATUS_FAIL, [body], view=report.VIEW_DIFF)


def test_counts_cases_by_status():
    cases = [failed_case(), report.case("bin_b", "", report.STATUS_PASS), report.case("bin_c", "", report.STATUS_PASS)]
    data = report.report(report.KIND_RUN, "Run", cases, 3.21)
    assert data["counts"] == {report.STATUS_FAIL: 1, report.STATUS_PASS: 2}
    assert data["seconds"] == 3.2
    assert data["pending"] is None


def test_text_lists_changes_and_leftovers():
    text = report.reportText(report.report(report.KIND_RUN, "Run", [failed_case()], 1))
    assert "FAIL       bin_a" in text
    assert "Gridfinity bin 3x2x5: volume 1000.5 -> 1001" in text
    assert "Gridfinity bin 3x2x5: faces 120 -> 124" in text
    assert "missing 1.234 mm³ in 2 piece(s), within (10, 20.5, 30) - (11, 21.5, 35.25) mm" in text


def test_text_of_a_case_note_without_a_body_name():
    item = report.case("bin_a", "", report.STATUS_FAIL, [report.body("", report.STATUS_FAIL, notes=["build failed, boom"])])
    text = report.reportText(report.report(report.KIND_RUN, "Run", [item], 1))
    assert "    build failed, boom" in text


def test_text_mentions_a_pending_update():
    pending = {"replace": 2, "remove": 1, "folder": "/snapshots"}
    data = report.report(report.KIND_UPDATE, "Update", [report.case("bin_a", "", report.STATUS_NEW)], 1, pending)
    assert "Waiting to replace 2 and remove 1 snapshot(s)" in report.reportText(data)


def test_cases_run_again_replace_their_entries_only():
    listed = [report.case(name, "", report.STATUS_UNTESTED) for name in ["bin_a", "bin_b", "bin_c"]]
    data = report.report(report.KIND_RUN, "Run", listed, 0)
    data = report.withCases(data, [failed_case()], 2.04, "done")
    assert [item["status"] for item in data["cases"]] == [report.STATUS_FAIL, report.STATUS_UNTESTED, report.STATUS_UNTESTED]
    assert data["cases"][0]["hasDocument"]
    assert data["counts"] == {report.STATUS_FAIL: 1, report.STATUS_UNTESTED: 2}
    assert data["seconds"] == 2.0
    assert data["message"] == "done"


def test_a_run_in_progress_is_cleared_when_done():
    listed = [report.case(name, "", report.STATUS_QUEUED) for name in ["bin_a", "bin_b"]]
    data = report.report(report.KIND_RUN, "Run", listed, 0)
    running = report.withCases(data, [report.case("bin_a", "", report.STATUS_RUNNING)], 0.5, "", report.progress(0, 2, "bin_a"))
    assert running["progress"] == {"done": 0, "total": 2, "current": "bin_a"}
    assert running["counts"] == {report.STATUS_RUNNING: 1, report.STATUS_QUEUED: 1}
    done = report.withCases(running, [report.case("bin_a", "", report.STATUS_PASS)], 1, "")
    assert done["progress"] is None
