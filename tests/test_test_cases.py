"""
Tests for shape test cases: reading the JSON case files into generator states and writing them back.
"""

import os
import json
import math
import importlib.util
import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_FOLDER = os.path.join(PROJECT_ROOT, "tests", "e2e", "cases")


def _load(name, *path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, *path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cases = _load("testCases", "commands", "commandSnapshotTests", "testCases.py")
binState = _load("binInputState", "commands", "commandCreateBin", "inputState.py")
baseplateState = _load("baseplateInputState", "commands", "commandCreateBaseplate", "inputState.py")

STATE_CLASSES = {cases.GENERATOR_BIN: binState.InputState, cases.GENERATOR_BASEPLATE: baseplateState.InputState}


def write_case(tmp_path, settings, generator="bin", name="case"):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"description": "a case", "generator": generator, "settings": settings}))
    return str(path)


def sample_settings():
    with open(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json")) as file:
        return json.load(file)["settings"]


def test_every_case_in_the_repo_loads():
    loaded = cases.loadCases(CASES_FOLDER, STATE_CLASSES)
    assert len(loaded) > 0
    for case in loaded:
        assert case.generator in STATE_CLASSES


def test_lengths_come_in_mm_and_angles_in_degrees():
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json"), STATE_CLASSES)
    assert case.name == "bin_2x3x5_features"
    assert case.state.baseWidth == pytest.approx(4.2)
    assert case.state.wallThickness == pytest.approx(0.12)
    assert case.state.tabOverhangAngle == pytest.approx(math.radians(45))
    # units of the grid stay as they are
    assert case.state.binWidth == 2
    assert case.state.creaseMinHeight == 10


def test_shape_cells_become_tuples(tmp_path):
    settings = {**sample_settings(), "hasCustomShape": True, "shapeCells": [[0, 0], [1, 0]]}
    case = cases.loadCase(write_case(tmp_path, settings), STATE_CLASSES)
    assert case.state.shapeCells == [(0, 0), (1, 0)]


def test_a_missing_setting_is_an_error(tmp_path):
    settings = sample_settings()
    del settings["hasLip"]
    with pytest.raises(cases.TestCaseError, match="hasLip"):
        cases.loadCase(write_case(tmp_path, settings), STATE_CLASSES)


def test_an_unknown_setting_is_an_error(tmp_path):
    settings = {**sample_settings(), "hasLid": True}
    with pytest.raises(cases.TestCaseError, match="hasLid"):
        cases.loadCase(write_case(tmp_path, settings), STATE_CLASSES)


def test_an_unknown_generator_is_an_error(tmp_path):
    with pytest.raises(cases.TestCaseError, match="drawer"):
        cases.loadCase(write_case(tmp_path, sample_settings(), generator="drawer"), STATE_CLASSES)


def test_broken_json_names_the_case(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{")
    with pytest.raises(cases.TestCaseError, match="broken"):
        cases.loadCase(str(path), STATE_CLASSES)


def test_written_case_reads_back_the_same(tmp_path):
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json"), STATE_CLASSES)
    path = tmp_path / "copy.json"
    path.write_text(cases.caseJson(case))
    copy = cases.loadCase(str(path), STATE_CLASSES)
    assert copy.description == case.description
    for field in binState.InputState.__dataclass_fields__:
        assert getattr(copy.state, field) == pytest.approx(getattr(case.state, field)), field


def test_written_case_has_no_float_noise():
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json"), STATE_CLASSES)
    settings = json.loads(cases.caseJson(case))["settings"]
    assert settings["wallThickness"] == 1.2
    assert settings["tabOverhangAngle"] == 45


def test_case_settings_name_the_case_and_list_every_setting():
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json"), STATE_CLASSES)
    settings = cases.caseSettings(case)
    assert settings[0]["title"] == "Test case"
    assert ["Case", "bin_2x3x5_features"] in settings[0]["items"]
    items = dict(settings[1]["items"])
    assert items["wallThickness"] == "1.2"
    assert items["labelText"] == '"Test"'
    assert len(items) == len(binState.InputState.__dataclass_fields__)


def test_readme_lists_the_cases_as_they_are():
    readme = os.path.join(PROJECT_ROOT, "tests", "e2e", "README.md")
    with open(readme, encoding="utf-8") as file:
        written = file.read()
    assert written == cases.casesMarkdown(CASES_FOLDER), "tests/e2e/README.md is out of date, run python3 tests/e2e/write_readme.py"
