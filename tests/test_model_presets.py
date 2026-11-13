"""
Tests for model screenshot presets: presets extending each other, their options and the presets kept in the repo.
"""

import os
import json
import importlib.util
import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS_FOLDER = os.path.join(PROJECT_ROOT, "tools", "screenshots", "models")


def _load(name, *path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, *path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


presets = _load("modelPresets", "commands", "commandModelScreenshots", "presets.py")
cases = _load("testCases", "commands", "commandSnapshotTests", "testCases.py")
binState = _load("binInputState", "commands", "commandCreateBin", "inputState.py")
baseplateState = _load("baseplateInputState", "commands", "commandCreateBaseplate", "inputState.py")

STATE_CLASSES = {cases.GENERATOR_BIN: binState.InputState, cases.GENERATOR_BASEPLATE: baseplateState.InputState}


def write(folder, name, data):
    (folder / name).write_text(json.dumps(data))


@pytest.fixture
def folder(tmp_path):
    write(tmp_path, "_base.json", {
        "description": "only to extend",
        "generator": "bin",
        "settings": {"binWidth": 2, "binLength": 3},
        "style": "shadedWithEdges",
    })
    return tmp_path


class TestExtends:
    def test_settings_merge_over_the_base(self, folder):
        write(folder, "wide.json", {"extends": "_base.json", "settings": {"binWidth": 4}})
        preset = presets.loadPreset(str(folder), "wide.json")
        assert preset.settings == {"binWidth": 4, "binLength": 3}
        assert preset.generator == "bin"

    def test_options_come_from_the_base(self, folder):
        write(folder, "wide.json", {"extends": "_base.json"})
        assert presets.loadPreset(str(folder), "wide.json").style == "shadedWithEdges"

    def test_description_is_not_inherited(self, folder):
        write(folder, "wide.json", {"extends": "_base.json"})
        assert presets.loadPreset(str(folder), "wide.json").description == ""

    def test_extends_a_chain(self, folder):
        write(folder, "wide.json", {"extends": "_base.json", "settings": {"binWidth": 4}})
        write(folder, "wide_tall.json", {"extends": "wide.json", "settings": {"binHeight": 8}})
        preset = presets.loadPreset(str(folder), "wide_tall.json")
        assert preset.settings == {"binWidth": 4, "binLength": 3, "binHeight": 8}

    def test_loop_is_an_error(self, folder):
        write(folder, "a.json", {"extends": "b.json"})
        write(folder, "b.json", {"extends": "a.json"})
        with pytest.raises(presets.PresetError, match="loop"):
            presets.loadPreset(str(folder), "a.json")

    def test_missing_base_is_an_error(self, folder):
        write(folder, "a.json", {"extends": "nope.json"})
        with pytest.raises(presets.PresetError, match="preset a"):
            presets.loadPreset(str(folder), "a.json")


class TestOptions:
    def test_defaults(self, folder):
        write(folder, "plain.json", {"extends": "_base.json"})
        preset = presets.loadPreset(str(folder), "plain.json")
        assert (preset.view, preset.camera, preset.width, preset.height, preset.transparent, preset.appearance) == \
            ("isoTopRight", "perspective", 2048, 2048, True, None)
        assert preset.output == presets.DEFAULT_OUTPUT
        assert (preset.margin, preset.supersample, preset.exposure, preset.saturation) == (0.06, 3, 0.85, 1.4)
        assert (preset.style, preset.color) == ("shadedWithEdges", "#4e79a7")

    @pytest.mark.parametrize("options, message", [
        ({"view": "sideways"}, "unknown view"),
        ({"view": {"eye": [1, 2]}}, "eye"),
        ({"view": {"eye": [1, 2, 3], "target": [0, 0, 0], "roll": 3}}, "unknown view keys"),
        ({"camera": "fisheye"}, "unknown camera"),
        ({"style": "sketchy"}, "unknown style"),
        ({"width": 0}, "width"),
        ({"margin": 0.5}, "margin"),
        ({"margin": "wide"}, "margin"),
        ({"supersample": 0}, "supersample"),
        ({"supersample": 2.5}, "supersample"),
        ({"color": "blue"}, "color"),
        ({"exposure": 4}, "exposure"),
        ({"exposure": "bright"}, "exposure"),
        ({"saturation": -1}, "saturation"),
        ({"color": "#4e79a"}, "color"),
        ({"colour": "blue"}, "unknown keys"),
    ])
    def test_bad_options(self, folder, options, message):
        write(folder, "bad.json", {"extends": "_base.json", **options})
        with pytest.raises(presets.PresetError, match=message):
            presets.loadPreset(str(folder), "bad.json")

    def test_custom_view(self, folder):
        view = {"eye": [200, -300, 250], "target": [40, 60, 20]}
        write(folder, "custom.json", {"extends": "_base.json", "view": view})
        assert presets.loadPreset(str(folder), "custom.json").view == view

    def test_color_can_be_turned_off(self, folder):
        write(folder, "own.json", {"extends": "_base.json", "color": None})
        assert presets.loadPreset(str(folder), "own.json").color is None

    def test_needs_a_generator(self, tmp_path):
        write(tmp_path, "bare.json", {"settings": {}})
        with pytest.raises(presets.PresetError, match="generator"):
            presets.loadPreset(str(tmp_path), "bare.json")


class TestLoadPresets:
    def test_skips_presets_only_to_extend(self, folder):
        write(folder, "wide.json", {"extends": "_base.json"})
        assert [preset.name for preset in presets.loadPresets(str(folder))] == ["wide"]

    def test_only(self, folder):
        write(folder, "a.json", {"extends": "_base.json"})
        write(folder, "b.json", {"extends": "_base.json"})
        assert [preset.name for preset in presets.loadPresets(str(folder), ["b"])] == ["b"]


class TestRepoPresets:
    """The presets in the repo build a state with every setting, as test cases do"""

    @pytest.mark.parametrize("preset", presets.loadPresets(PRESETS_FOLDER), ids=lambda preset: preset.name)
    def test_builds_a_state(self, preset):
        cases.stateFromJson(preset.generator, STATE_CLASSES[preset.generator], preset.settings)

    @pytest.mark.parametrize("preset", [preset for preset in presets.loadPresets(PRESETS_FOLDER) if preset.generator == cases.GENERATOR_BIN],
                             ids=lambda preset: preset.name)
    def test_custom_compartments_are_shown(self, preset):
        """The builder uses the pockets only while the compartments drawing is shown, see binBuilder"""
        merged = [pocket for pocket in preset.settings["compartmentPockets"] if pocket["width"] != 1 or pocket["length"] != 1]
        assert not merged or preset.settings["showCompartmentsLayout"]
