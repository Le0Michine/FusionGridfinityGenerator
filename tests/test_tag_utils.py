"""
Tests for bin tag values: creation, tolerant parsing and the generator version lookup.
"""

import sys
import os
import json
import types
import importlib.util
import pytest


def _load_tag_utils():
    # The module annotates with adsk.fusion types, so they only need to exist
    fusion = sys.modules.get("adsk.fusion") or types.ModuleType("adsk.fusion")
    for name in ("BRepBody", "Design", "UserParameter"):
        if not hasattr(fusion, name):
            setattr(fusion, name, type(name, (), {}))
    sys.modules["adsk.fusion"] = fusion
    sys.modules["adsk"].fusion = fusion

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "tagUtils.py")
    spec = importlib.util.spec_from_file_location("tagUtils", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tagUtils = _load_tag_utils()


def test_created_value_round_trips():
    tag = tagUtils.parseTagValue(tagUtils.createTagValue("1.4.3.0"))
    assert tag == {"schemaVersion": tagUtils.TAG_SCHEMA_VERSION, "generatorVersion": "1.4.3.0"}


def test_unknown_fields_are_kept_for_newer_readers():
    tag = tagUtils.parseTagValue(json.dumps({"schemaVersion": 1, "futureField": [1, 2]}))
    assert tag["schemaVersion"] == 1
    assert tag["futureField"] == [1, 2]


@pytest.mark.parametrize("value", ["", "not json", None, "[1, 2]", "42", '"text"'])
def test_unreadable_value_still_yields_dict(value):
    assert tagUtils.parseTagValue(value) == {}


def test_generator_version_matches_manifest():
    with open(tagUtils.MANIFEST_PATH, "r") as manifest:
        expected = json.load(manifest)["version"]
    tagUtils._generatorVersion = None
    assert tagUtils.getGeneratorVersion() == expected


def test_missing_manifest_gives_empty_version(monkeypatch):
    monkeypatch.setattr(tagUtils, "MANIFEST_PATH", "/nonexistent/GridfinityGenerator.manifest")
    monkeypatch.setattr(tagUtils, "_generatorVersion", None)
    assert tagUtils.getGeneratorVersion() == ""


def test_settings_are_stored_when_given():
    settings = [{"title": "Basic sizes", "items": [["Bin width (u)", "2"]]}]
    tag = tagUtils.parseTagValue(tagUtils.createTagValue("1.6.0.0", settings))
    assert tag["settings"] == settings


def test_settings_are_left_out_when_not_given():
    assert "settings" not in tagUtils.parseTagValue(tagUtils.createTagValue("1.6.0.0"))


def test_config_is_kept_to_build_the_body_again():
    config = {"binWidth": 2, "shapeCells": [[0, 0]]}
    tag = tagUtils.parseTagValue(tagUtils.createTagValue("1.6.0.0", config=config))
    assert tag["config"] == config


def test_config_is_left_out_when_not_given():
    assert "config" not in tagUtils.parseTagValue(tagUtils.createTagValue("1.6.0.0"))


class _FakeAttribute:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value


class _FakeAttributes:
    def __init__(self):
        self.byName = {}

    def add(self, group, name, value):
        self.byName[(group, name)] = value

    def itemByName(self, group, name):
        value = self.byName.get((group, name))
        return _FakeAttribute(None, value) if value is not None else None


class _FakeParameter:
    def __init__(self, name):
        self.name = name
        self.attributes = _FakeAttributes()


def test_body_id_and_parameter_field_and_owner_are_kept():
    tag = tagUtils.parseTagValue(tagUtils.createTagValue("2.3.0.0", bodyId="gfBin3"))
    assert tag["id"] == "gfBin3"
    tag = tagUtils.parseTagValue(tagUtils.createTagValue("2.3.0.0", field="binHeight", owner="gfBin3"))
    assert (tag["field"], tag["owner"]) == ("binHeight", "gfBin3")
    assert "id" not in tag


def test_a_parameter_tagged_again_keeps_the_last_field():
    parameter = _FakeParameter("gfBin3_label")
    tagUtils.tagParameterField(parameter, "labelText", "gfBin3")
    tagUtils.tagParameterField(parameter, "compartmentPockets.0.label", "gfBin3")
    assert tagUtils.readParameterField(parameter) == "compartmentPockets.0.label"
    assert tagUtils.readParameterTag(parameter)["owner"] == "gfBin3"


def test_an_untagged_parameter_has_no_field():
    assert tagUtils.readParameterField(_FakeParameter("gfBaseWidth")) is None


def test_owned_parameters_are_found_by_their_owner(monkeypatch):
    parameters = [_FakeParameter("gfBin1_heightU"), _FakeParameter("gfBin2_heightU")]
    tagUtils.tagParameterField(parameters[0], "binHeight", "gfBin1")
    tagUtils.tagParameterField(parameters[1], "binHeight", "gfBin2")

    class _Design:
        def findAttributes(self, group, name):
            return [_FakeAttribute(parameter, parameter.attributes.byName[(group, name)]) for parameter in parameters]

    monkeypatch.setattr(tagUtils.adsk.fusion.UserParameter, "cast", staticmethod(lambda parent: parent), raising=False)
    assert tagUtils.findOwnedParameters(_Design(), "gfBin2") == [(parameters[1], "binHeight")]
