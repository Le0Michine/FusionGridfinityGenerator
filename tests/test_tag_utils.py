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
    for name in ("BRepBody", "Design"):
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
