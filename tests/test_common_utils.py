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
    # loaded into a package of its own, with stand-ins for the add-in's config and fusion360utils it imports, so no
    # other test finds them under the add-in's names
    package = "commonUtilsTest"
    for name in (package, package + ".lib", package + ".lib.gridfinityUtils"):
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    config = types.ModuleType(package + ".config")
    config.DEBUG = False
    sys.modules[package + ".config"] = config
    sys.modules[package].config = config
    futil = types.ModuleType(package + ".lib.fusion360utils")
    futil.log = lambda *a, **kw: None
    sys.modules[package + ".lib.fusion360utils"] = futil
    sys.modules[package + ".lib"].fusion360utils = futil
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "gridfinityUtils", "commonUtils.py")
    spec = importlib.util.spec_from_file_location(package + ".lib.gridfinityUtils.commonUtils", path)
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


def test_build_error_kept_when_activating_fails(monkeypatch):
    # a failed rebuild may leave the timeline rolled back, so the component active before can't be activated, the
    # error of the build is the one to report
    logged = []
    monkeypatch.setattr(commonUtils, "fileLog", logged.append)
    design = FakeDesign()
    bins = FakeOccurrence(design, "bins")
    bins.activate()
    def refuse():
        raise RuntimeError("rolled back")
    with pytest.raises(ValueError, match="Fillet failed"):
        with commonUtils.keepActiveComponent(design):
            FakeOccurrence(design, "Gridfinity bin 1x1x3").activate()
            bins.activate = refuse
            raise ValueError("Fillet failed")
    assert len(logged) == 1
