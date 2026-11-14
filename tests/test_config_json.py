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


BIN_CHOICES = {
    "binType": configJson.Choice(["Hollow", "Shelled", "Solid"], "Hollow"),
    "labelIcon": configJson.Choice(["None", "screw"], "None"),
}


def read(text, current, generator=BIN, stateClass=None, choices=None):
    return configJson.readConfig(text, generator, stateClass or binState.InputState, current, choices)


def settings_text(**settings):
    return json.dumps({"generator": BIN, "settings": settings})


def test_saved_config_reads_back_to_the_same_state(current):
    text = configJson.configText(BIN, configJson.stateToJson(BIN, current), "1.7.0.0")
    (state, notes) = read(text, current)
    assert notes.isEmpty()
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
    assert ("binLength", current.binLength) in notes.missing
    assert "binWidth" not in [name for (name, _) in notes.missing]


def test_unknown_settings_are_skipped(current):
    (state, notes) = read(json.dumps({"generator": BIN, "settings": {"binWidth": 4, "hasLid": True}}), current)
    assert state.binWidth == 4
    assert not hasattr(state, "hasLid")
    assert notes.unknown == ["hasLid"]


def test_shape_cells_become_tuples(current):
    (state, _) = read(json.dumps({"generator": BIN, "settings": {"shapeCells": [[0, 0], [1, 0]]}}), current)
    assert state.shapeCells == [(0, 0), (1, 0)]


def test_test_case_files_load_as_configs(current):
    with open(os.path.join(CASES_FOLDER, "bin_2x3x5_features.json")) as file:
        (state, notes) = read(file.read(), current)
    assert notes.isEmpty()
    assert state == current


@pytest.mark.parametrize("settings, name", [
    ({"hasLip": 1}, "hasLip"),
    ({"binWidth": "2"}, "binWidth"),
    ({"binWidth": True}, "binWidth"),
    ({"labelText": 5}, "labelText"),
    ({"shapeCells": "all"}, "shapeCells"),
    ({"shapeCells": [[0, 0, 1]]}, "shapeCells"),
    ({"shapeCells": [[0, 0.5]]}, "shapeCells"),
    ({"compartmentPockets": [1]}, "compartmentPockets"),
    ({"compartmentsX": 2.5}, "compartmentsX"),
    ({"compartmentsX": True}, "compartmentsX"),
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
    assert notes.isEmpty()
    assert state.areaWidth == pytest.approx(current.areaWidth)
    assert state.sizingMode == current.sizingMode


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_numbers_have_to_be_finite(current, value):
    with pytest.raises(configJson.ConfigError, match="binHeight"):
        read('{"generator": "bin", "settings": {"binHeight": %s}}' % value, current)


def test_every_wrong_setting_is_named(current):
    with pytest.raises(configJson.ConfigError) as err:
        read(settings_text(hasLip=1, binWidth="2"), current)
    assert "hasLip has to be yes or no" in str(err.value)
    assert "binWidth has to be a number" in str(err.value)


def test_whole_numbers_written_with_a_fraction_are_read(current):
    (state, _) = read(settings_text(compartmentsX=3.0, shapeCells=[[1.0, 0]]), current)
    assert state.compartmentsX == 3 and isinstance(state.compartmentsX, int)
    assert state.shapeCells == [(1, 0)]


def test_values_out_of_range_are_left_to_the_dialog(current):
    (state, notes) = read(settings_text(wallThickness=-5, compartmentsX=0), current)
    assert state.wallThickness == pytest.approx(-0.5)
    assert state.compartmentsX == 0
    assert notes.replaced == []


def test_unknown_options_become_the_default(current):
    (state, notes) = read(settings_text(binType="Bucket", labelIcon="screw-m3"), current, choices=BIN_CHOICES)
    assert state.binType == "Hollow"
    assert state.labelIcon == "None"
    assert notes.replaced == [("binType", "Bucket", "Hollow"), ("labelIcon", "screw-m3", "None")]


def test_known_options_are_kept(current):
    (state, notes) = read(settings_text(binType="Solid", labelIcon="screw"), current, choices=BIN_CHOICES)
    assert (state.binType, state.labelIcon) == ("Solid", "screw")
    assert notes.replaced == []


def test_options_arent_checked_without_choices(current):
    (state, _) = read(settings_text(binType="Bucket"), current)
    assert state.binType == "Bucket"


def test_notes_list_every_change_by_kind(current):
    (_, notes) = read(settings_text(binType="Bucket", hasLid=True), current, choices=BIN_CHOICES)
    notes.missing = [("creaseDepth", 0.6), ("hasLip", True), ("shapeCells", [[0, 0]]), ("labelText", "M3"), ("binHeight", 5)]
    text = configJson.notesText(BIN, notes)
    assert text == "\n\n".join([
        "Not recognised, skipped:\n  • hasLid",
        "Not in the file, kept the current value:\n  • creaseDepth (0.6 mm)\n  • hasLip (yes)\n  • shapeCells (1 items)"
        "\n  • labelText (\"M3\")\n  • binHeight (5)",
        "Unknown option, used the default:\n  • binType \"Bucket\" → Hollow",
    ])


def test_no_notes_without_changes(current):
    assert configJson.notesText(BIN, configJson.ConfigNotes()) == ""
