"""
Tests for bin and baseplate config files: writing them and reading them back into a dialog's state.
"""

import os
import json
import math
import dataclasses
import importlib.util
import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_FOLDER = os.path.join(PROJECT_ROOT, "tests", "e2e", "cases")


def _load(name, *path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, *path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


configJson = _load("configJson", "lib", "configJson.py")
binState = _load("binInputState", "commands", "commandCreateBin", "inputState.py")
baseplateState = _load("baseplateInputState", "commands", "commandCreateBaseplate", "inputState.py")
BIN = configJson.GENERATOR_BIN
BASEPLATE = configJson.GENERATOR_BASEPLATE


def case_state(name, generator, stateClass):
    with open(os.path.join(CASES_FOLDER, name)) as file:
        return configJson.stateFromJson(generator, stateClass, json.load(file)["settings"])


@pytest.fixture
def current():
    """A bin as the dialog has it"""
    return case_state("bin_2x3x5_features.json", BIN, binState.InputState)


def read(text, current, generator=BIN, stateClass=None):
    return configJson.readConfig(text, generator, stateClass or binState.InputState, current)


def test_saved_config_reads_back_to_the_same_state(current):
    text = configJson.configText(BIN, configJson.stateToJson(BIN, current), "1.7.0.0")
    (state, notes) = read(text, current)
    assert notes == []
    for field in dataclasses.fields(state):
        expected = getattr(current, field.name)
        if isinstance(expected, float):
            assert math.isclose(getattr(state, field.name), expected, abs_tol=1e-9), field.name
        else:
            assert getattr(state, field.name) == expected, field.name


def test_config_names_its_generator_and_version(current):
    data = json.loads(configJson.configText(BIN, configJson.stateToJson(BIN, current), "1.7.0.0"))
    assert data["generator"] == BIN
    assert data["generatorVersion"] == "1.7.0.0"
    assert data["settings"]["baseWidth"] == pytest.approx(current.baseWidth * 10)


def test_version_is_left_out_when_unknown(current):
    assert "generatorVersion" not in json.loads(configJson.configText(BIN, configJson.stateToJson(BIN, current)))


def test_lengths_and_angles_are_read_in_mm_and_degrees(current):
    (state, _) = read(json.dumps({"generator": BIN, "settings": {"wallThickness": 1.6, "tabOverhangAngle": 30}}), current)
    assert state.wallThickness == pytest.approx(0.16)
    assert state.tabOverhangAngle == pytest.approx(math.pi / 6)


def test_missing_settings_keep_the_current_ones(current):
    (state, notes) = read(json.dumps({"generator": BIN, "settings": {"binWidth": 4}}), current)
    assert state.binWidth == 4
    assert state.binLength == current.binLength
    assert state.wallThickness == pytest.approx(current.wallThickness)
    assert any("kept the current" in note and "binLength" in note for note in notes)


def test_unknown_settings_are_skipped(current):
    (state, notes) = read(json.dumps({"generator": BIN, "settings": {"binWidth": 4, "hasLid": True}}), current)
    assert state.binWidth == 4
    assert not hasattr(state, "hasLid")
    assert any("hasLid" in note for note in notes)


def test_shape_cells_become_tuples(current):
    (state, _) = read(json.dumps({"generator": BIN, "settings": {"shapeCells": [[0, 0], [1, 0]]}}), current)
    assert state.shapeCells == [(0, 0), (1, 0)]


def test_test_case_files_load_as_configs(current):
    with open(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json")) as file:
        (state, notes) = read(file.read(), current)
    assert notes == []
    assert state == current


@pytest.mark.parametrize("settings, name", [
    ({"hasLip": 1}, "hasLip"),
    ({"binWidth": "2"}, "binWidth"),
    ({"binWidth": True}, "binWidth"),
    ({"labelText": 5}, "labelText"),
    ({"shapeCells": "all"}, "shapeCells"),
])
def test_settings_of_the_wrong_kind_are_refused(current, settings, name):
    with pytest.raises(configJson.ConfigError, match=name):
        read(json.dumps({"generator": BIN, "settings": settings}), current)


def test_whole_numbers_count_as_lengths(current):
    (state, _) = read(json.dumps({"generator": BIN, "settings": {"baseWidth": 42}}), current)
    assert state.baseWidth == pytest.approx(4.2)


def test_baseplate_config_is_refused_by_the_bin(current):
    with pytest.raises(configJson.ConfigError, match="baseplate, not of a bin"):
        read(json.dumps({"generator": BASEPLATE, "settings": {}}), current)


@pytest.mark.parametrize("text", ["{not json", "[]", json.dumps({"generator": BIN}), json.dumps({"settings": {}})])
def test_files_that_arent_configs_are_refused(current, text):
    with pytest.raises(configJson.ConfigError):
        read(text, current)


def test_baseplate_config_reads_back():
    current = case_state("baseplate_fill_area_pieces.json", BASEPLATE, baseplateState.InputState)
    text = configJson.configText(BASEPLATE, configJson.stateToJson(BASEPLATE, current))
    (state, notes) = read(text, current, BASEPLATE, baseplateState.InputState)
    assert notes == []
    assert state.areaWidth == pytest.approx(current.areaWidth)
    assert state.sizingMode == current.sizingMode
