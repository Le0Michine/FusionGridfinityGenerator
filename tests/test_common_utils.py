"""
Tests for commonUtils.keepActiveComponent: a build activates the component it makes, afterwards the component that
was active before is active again.
"""

import sys
import os
import types
import importlib.util
import pytest


def _load_common_utils():
    # The module annotates with adsk types, so they only need to exist
    fusion = sys.modules["adsk.fusion"]
    if not hasattr(fusion, "Design"):
        fusion.Design = type("Design", (), {})
    # commonUtils imports the add-in's config, only DEBUG of it
    config = types.ModuleType("FusionGridfinityGenerator.config")
    config.DEBUG = False
    sys.modules.setdefault("FusionGridfinityGenerator.config", config)
    root = sys.modules["FusionGridfinityGenerator"]
    if not hasattr(root, "config"):
        root.config = sys.modules["FusionGridfinityGenerator.config"]
    utilsName = "FusionGridfinityGenerator.lib.gridfinityUtils"
    if utilsName not in sys.modules:
        utils = types.ModuleType(utilsName)
        utils.__path__ = []
        utils.__package__ = utilsName
        sys.modules[utilsName] = utils
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "gridfinityUtils", "commonUtils.py")
    spec = importlib.util.spec_from_file_location(utilsName + ".commonUtils", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


commonUtils = _load_common_utils()


class FakeOccurrence:
    def __init__(self, design, name):
        self.design = design
        self.name = name
        self.isValid = True

    def activate(self):
        self.design.activeOccurrence = self
        return True


class FakeDesign:
    """The active occurrence is None while the root component is active, as in Fusion"""
    def __init__(self):
        self.activeOccurrence = None

    def activateRootComponent(self):
        self.activeOccurrence = None
        return True


def test_root_active_again_after_a_build():
    design = FakeDesign()
    with commonUtils.keepActiveComponent(design):
        FakeOccurrence(design, "Gridfinity bin 1x1x3").activate()
    assert design.activeOccurrence is None


def test_previously_active_component_active_again():
    design = FakeDesign()
    bins = FakeOccurrence(design, "bins")
    bins.activate()
    with commonUtils.keepActiveComponent(design):
        FakeOccurrence(design, "Gridfinity bin 1x1x3").activate()
    assert design.activeOccurrence is bins


def test_restored_when_the_build_fails():
    design = FakeDesign()
    bins = FakeOccurrence(design, "bins")
    bins.activate()
    with pytest.raises(RuntimeError):
        with commonUtils.keepActiveComponent(design):
            FakeOccurrence(design, "Gridfinity bin 1x1x3").activate()
            raise RuntimeError("Fillet failed")
    assert design.activeOccurrence is bins


def test_root_when_the_active_component_was_removed():
    # a rebuild removes the old bin, it may have been the active one
    design = FakeDesign()
    old = FakeOccurrence(design, "Gridfinity bin 1x1x3")
    old.activate()
    with commonUtils.keepActiveComponent(design):
        FakeOccurrence(design, "Gridfinity bin 1x1x3 (1)").activate()
        old.isValid = False
    assert design.activeOccurrence is None


def test_nothing_activated_when_the_build_activated_nothing():
    # a design without components builds into the root component and activates nothing
    design = FakeDesign()
    calls = []
    design.activateRootComponent = lambda: calls.append("root")
    with commonUtils.keepActiveComponent(design):
        pass
    assert calls == []
