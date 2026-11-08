"""
Tests for showing the settings stored in a body tag.
"""

import os
import importlib.util


def _load_settings_utils():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "settingsUtils.py")
    spec = importlib.util.spec_from_file_location("settingsUtils", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


settingsUtils = _load_settings_utils()


def test_sections_and_values_are_listed():
    text = settingsUtils.settingsHtml({
        "generatorVersion": "1.6.0.0",
        "settings": [{"title": "Basic sizes", "items": [["Bin width (u)", "2"], ["Bin height unit (mm)", "7 mm"]]}],
    })
    assert "Generated with version 1.6.0.0" in text
    assert "<b>Basic sizes</b>" in text
    assert "Bin width (u): 2" in text
    assert "Bin height unit (mm): 7 mm" in text


def test_values_are_escaped():
    text = settingsUtils.settingsHtml({"settings": [{"title": "Label tab", "items": [["Label text", "<b>M3 & M4</b>"]]}]})
    assert "&lt;b&gt;M3 &amp; M4&lt;/b&gt;" in text


def test_bodies_from_before_settings_say_so():
    text = settingsUtils.settingsHtml({"generatorVersion": "1.5.0.0"})
    assert "1.5.0.0" in text
    assert "weren't recorded" in text


def test_line_count_covers_titles_and_items():
    tag = {"settings": [{"title": "A", "items": [["x", "1"], ["y", "2"]]}, {"title": "B", "items": [["z", "3"]]}]}
    assert settingsUtils.settingsLineCount(tag) == 1 + (2 + 2) + (2 + 1)


def test_parameters_show_their_current_expression():
    tag = {"settings": [], "parameters": [["Bin height (u)", "gfBin1_heightU"], ["Label", "gfBin1_label"]]}
    text = settingsUtils.settingsHtml(tag, {"gfBin1_heightU": "6"}.get)
    assert "<b>Parameters</b>" in text
    assert "Bin height (u): gfBin1_heightU = 6" in text
    assert "Label: gfBin1_label = " in text and "missing" in text
