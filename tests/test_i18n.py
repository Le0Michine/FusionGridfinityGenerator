"""
Tests for the translations of lib/i18n.py: a translation keeps the placeholders of its English text, English stays
as it is, and the names of sketches and planes are put together from their pieces.
"""

import os
import re
import string
import importlib.util

import pytest


def _load_i18n():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "i18n.py")
    spec = importlib.util.spec_from_file_location("i18nTest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


i18n = _load_i18n()


@pytest.fixture
def german():
    i18n._language = "de"
    yield i18n
    i18n._language = None


@pytest.fixture
def english():
    i18n._language = "en"
    yield i18n
    i18n._language = None


def _placeholders(text: str) -> set[str]:
    return {name for (_, name, _, _) in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("english_text", list(i18n.DE))
def test_translation_keeps_placeholders(english_text):
    assert _placeholders(i18n.DE[english_text]) == _placeholders(english_text)


def test_english_stays_as_it_is(english):
    assert english.t("Bin type") == "Bin type"
    assert english.t("Version {version}", version="2.6.0.0") == "Version 2.6.0.0"
    assert english.sketchName("Foot sketch") == "Foot sketch"
    assert english.pageQuery() == ""


def test_german_text_with_values(german):
    assert german.t("Version {version}", version="2.6.0.0") == "Version 2.6.0.0"
    assert german.t("Bin type") == german.DE["Bin type"]
    assert german.pageQuery() == "?lang=de"


def test_text_without_translation_stays_english(german):
    assert german.t("Not a text of the add-in") == "Not a text of the add-in"


def test_dropdown_item_reads_back_in_english(german):
    shown = german.item("Hollow")
    assert shown != "Hollow"
    assert german.key(shown) == "Hollow"
    assert german.key("Not shown") == "Not shown"


def test_sketch_and_plane_names_from_pieces(german):
    assert german.sketchName("Compartment 2 label icon sketch") == "Skizze Fach 2, Beschriftung, Symbol"
    assert german.planeName("Lip cutout plane") == "Ebene Stapelrand-Ausschnitt"


def test_pages_have_the_same_language_switch():
    """The pages read the language from their address, which pageUrl gives them"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "ui", "html", "i18n.js")
    script = open(path, encoding="utf-8").read()
    assert re.search(r"URLSearchParams\(window\.location\.search\)\.get\('lang'\)", script)
