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


def test_settings_a_case_has_not_are_the_defaults(tmp_path):
    case = cases.loadCase(write_case(tmp_path, {"binHeight": 3, "hasScoop": True}), STATE_CLASSES)
    assert case.state.binHeight == 3
    assert case.state.hasScoop is True
    defaults = cases.stateFromJson(cases.GENERATOR_BIN, binState.InputState, cases.DEFAULT_SETTINGS[cases.GENERATOR_BIN])
    assert case.state.wallThickness == pytest.approx(defaults.wallThickness)
    assert case.state.isShellRounded == defaults.isShellRounded


def test_a_case_of_no_settings_is_the_defaults(tmp_path):
    case = cases.loadCase(write_case(tmp_path, {}, generator="baseplate"), STATE_CLASSES)
    assert cases.snapshotSettings(case) == cases.DEFAULT_SETTINGS[cases.GENERATOR_BASEPLATE]


@pytest.mark.parametrize("generator", [cases.GENERATOR_BIN, cases.GENERATOR_BASEPLATE])
def test_defaults_have_every_setting_of_the_state(generator):
    state = cases.stateFromJson(generator, STATE_CLASSES[generator], cases.DEFAULT_SETTINGS[generator])
    assert cases.stateToJson(generator, state) == cases.DEFAULT_SETTINGS[generator]


def test_cases_list_only_settings_that_differ_from_the_defaults():
    for fileName in sorted(os.listdir(CASES_FOLDER)):
        with open(os.path.join(CASES_FOLDER, fileName)) as file:
            data = json.load(file)
        defaults = cases.DEFAULT_SETTINGS[data["generator"]]
        same = [name for (name, value) in data["settings"].items() if defaults.get(name) == value]
        assert same == [], f"{fileName} sets {same} to the defaults, leave them out so the case follows the defaults"


def test_settings_are_an_object(tmp_path):
    with pytest.raises(cases.TestCaseError, match="case"):
        cases.loadCase(write_case(tmp_path, [["hasLip", True]]), STATE_CLASSES)


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
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_3x2x6_tab_steep_tilted.json"), STATE_CLASSES)
    settings = json.loads(cases.caseJson(case))["settings"]
    assert settings["tabWidth"] == 20
    assert settings["tabOverhangAngle"] == 30


def test_written_case_lists_only_settings_that_differ_from_the_defaults():
    path = os.path.join(CASES_FOLDER, "bin_2x3x5_features.json")
    with open(path) as file:
        data = json.load(file)
    case = cases.loadCase(path, STATE_CLASSES)
    assert json.loads(cases.caseJson(case))["settings"] == data["settings"]


def test_snapshot_settings_have_every_setting():
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json"), STATE_CLASSES)
    settings = cases.snapshotSettings(case)
    assert list(settings) == list(binState.InputState.__dataclass_fields__)
    assert settings["labelText"] == "Test"
    assert settings["wallThickness"] == 1.2
    assert json.loads(cases.settingsText(settings)) == settings


def test_every_snapshot_has_its_settings():
    snapshots = os.path.join(PROJECT_ROOT, "tests", "e2e", "snapshots")
    for case in cases.loadCases(CASES_FOLDER, STATE_CLASSES):
        path = os.path.join(snapshots, case.name, cases.SETTINGS_FILE)
        assert os.path.isfile(path), f"{case.name} has no {cases.SETTINGS_FILE}, update its snapshot"
        with open(path) as file:
            assert set(json.load(file)) <= set(STATE_CLASSES[case.generator].__dataclass_fields__) | set(cases.snapshotSettings(case)), case.name


def test_unchanged_settings_have_no_changes():
    settings = {"wallThickness": 1.2, "hasLip": True, "shapeCells": [[0, 0]], "labelText": ""}
    assert cases.settingChanges(settings, dict(settings)) == []


def test_numbers_are_the_same_through_float_noise():
    assert cases.settingChanges({"wallThickness": 1.2, "binWidth": 2}, {"wallThickness": 1.2000000000001, "binWidth": 2.0}) == []


def test_changed_settings_are_listed_in_order():
    expected = {"binWidth": 2, "isShellRounded": False, "wallThickness": 1.2}
    actual = {"binWidth": 2, "isShellRounded": True, "wallThickness": 1.5}
    assert cases.settingChanges(expected, actual) == [
        {"key": "isShellRounded", "expected": False, "actual": True},
        {"key": "wallThickness", "expected": 1.2, "actual": 1.5},
    ]


def test_a_flag_is_not_a_number_of_the_same_value():
    assert cases.settingChanges({"binHeight": 1}, {"binHeight": True}) == [{"key": "binHeight", "expected": 1, "actual": True}]


def test_settings_on_one_side_only_are_changes():
    assert cases.settingChanges({"seamClearance": 0.5}, {"plateClearance": 0.1}) == [
        {"key": "seamClearance", "expected": 0.5, "actual": None},
        {"key": "plateClearance", "expected": None, "actual": 0.1},
    ]


def test_lists_and_objects_are_shown_as_json():
    changes = cases.settingChanges({"shapeCells": [[0, 0]]}, {"shapeCells": [[0, 0], [1, 0]]})
    assert changes == [{"key": "shapeCells", "expected": "[[0, 0]]", "actual": "[[0, 0], [1, 0]]"}]


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


def write_case_data(tmp_path, data, name="case"):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_parameters_come_in_mm_and_edit_the_state(tmp_path):
    data = {"description": "a case", "generator": "bin", "settings": sample_settings(), "parameters": {"gfBin1_baseWidth": 40, "gfBin1_heightUnit": 5}}
    case = cases.loadCase(write_case_data(tmp_path, data), STATE_CLASSES)
    assert case.parameters == {"gfBin1_baseWidth": pytest.approx(4.0), "gfBin1_heightUnit": pytest.approx(0.5)}
    edited = cases.editedState(case)
    assert edited.baseWidth == pytest.approx(4.0)
    assert edited.heightUnit == pytest.approx(0.5)
    assert edited.baseLength == case.state.baseLength
    assert case.state.baseWidth == pytest.approx(4.2)


def test_a_case_without_parameters_has_none():
    case = cases.loadCase(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json"), STATE_CLASSES)
    assert case.parameters == {}
    assert cases.editedState(case) == case.state
    assert "parameters" not in json.loads(cases.caseJson(case))


def test_a_parameter_the_generator_has_not_is_an_error(tmp_path):
    with open(os.path.join(CASES_FOLDER, "baseplate_2x2_light.json")) as file:
        data = json.load(file)
    data["parameters"] = {"gfBin1_heightUnit": 7}
    with pytest.raises(cases.TestCaseError, match="gfBin1_heightUnit"):
        cases.loadCase(write_case_data(tmp_path, data), STATE_CLASSES)


@pytest.mark.parametrize("value", [0, -1, "40", True])
def test_a_parameter_has_to_be_a_positive_length(tmp_path, value):
    data = {"description": "a case", "generator": "bin", "settings": sample_settings(), "parameters": {"gfBin1_baseWidth": value}}
    with pytest.raises(cases.TestCaseError, match="gfBin1_baseWidth"):
        cases.loadCase(write_case_data(tmp_path, data), STATE_CLASSES)


def test_written_parameters_read_back_and_are_listed_in_the_settings(tmp_path):
    data = {"description": "a case", "generator": "bin", "settings": sample_settings(), "parameters": {"gfBin1_baseLength": 50.5}}
    case = cases.loadCase(write_case_data(tmp_path, data), STATE_CLASSES)
    assert json.loads(cases.caseJson(case))["parameters"] == {"gfBin1_baseLength": 50.5}
    settings = cases.caseSettings(case)
    assert dict(settings[2]["items"]) == {"gfBin1_baseLength": "50.5"}
