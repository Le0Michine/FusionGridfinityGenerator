"""
Tests for the messages between a dialog and the pages shown in it.
"""

import json
import os
import sys
import importlib.util
from types import SimpleNamespace

import pytest

PACKAGE = "FusionGridfinityGenerator.lib.ui"


def _load(name: str):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", os.path.join(project_root, "lib", "ui", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = PACKAGE
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("dialogFont")
pages = _load("browserPages")
FONT = "file:///font.woff2"


@pytest.fixture(autouse=True)
def font(monkeypatch):
    monkeypatch.setattr(pages, "dialogFontUrl", lambda: FONT)


class FakeBrowser:
    def __init__(self, failing=False):
        self.id = "page"
        self.failing = failing
        self.sent = []

    def sendInfoToHTML(self, action, data):
        if self.failing:
            raise RuntimeError("not loaded")
        self.sent.append((action, data))


def message(action: str, data: str):
    return SimpleNamespace(action=action, data=data, browserCommandInput=FakeBrowser(), returnData="")


def test_answer_comes_with_the_font():
    args = message("cells", json.dumps([[0, 1]]))
    pages.handleMessage(args, {pages.READY: lambda _: {}, "cells": lambda cells: {"count": len(cells)}})
    assert json.loads(args.returnData) == {"fontUrl": FONT, "data": {"count": 1}}


def test_handler_without_answer_leaves_the_page_as_it_is():
    received = []
    args = message("pockets", json.dumps({"x": 1}))
    pages.handleMessage(args, {pages.READY: lambda _: {}, "pockets": received.append})
    assert received == [{"x": 1}]
    assert args.returnData == pages.NO_ANSWER


def test_ready_without_data():
    args = message(pages.READY, "")
    pages.handleMessage(args, {pages.READY: lambda data: {"data": data}})
    assert json.loads(args.returnData)["data"] == {"data": None}


def test_unreadable_data_gets_the_ready_answer():
    received = []
    args = message("cells", "{not json")
    pages.handleMessage(args, {pages.READY: lambda _: {"cells": []}, "cells": received.append})
    assert received == []
    assert json.loads(args.returnData)["data"] == {"cells": []}


def test_unknown_action_is_ignored():
    args = message("other", "1")
    pages.handleMessage(args, {pages.READY: lambda _: {}})
    assert args.returnData == pages.NO_ANSWER


def test_update_comes_with_the_font():
    browser = FakeBrowser()
    pages.sendUpdate(browser, {"cells": []})
    assert browser.sent == [("update", json.dumps({"fontUrl": FONT, "data": {"cells": []}}))]


def test_update_to_a_page_not_loaded_yet_is_dropped():
    pages.sendUpdate(FakeBrowser(failing=True), {})
    pages.sendUpdate(None, {})
