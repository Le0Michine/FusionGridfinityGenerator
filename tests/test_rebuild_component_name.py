"""
Tests for the component name after a rebuild: the new component is made while the old one still has the name, so
Fusion counts it up ("Gridfinity bin 1x1x3 (1)"), once the old one is gone it gets the old name back.
"""

import sys
import os
import types
import importlib.util


def _load_rebuild_utils():
    # The module annotates with adsk types and reads one enum at import, so they only need to exist
    fusion = sys.modules["adsk.fusion"]
    for name in ("BRepBody", "Design", "Component", "Occurrence", "TimelineGroup", "TimelineObject", "Timeline",
                 "Feature", "UserParameter", "CircularPatternFeature", "CombineFeature", "ExtrudeFeature",
                 "HoleFeature", "LoftFeature", "MirrorFeature", "MoveFeature", "PathPatternFeature", "PipeFeature",
                 "RectangularPatternFeature", "RevolveFeature", "ScaleFeature", "SilhouetteSplitFeature",
                 "SplitBodyFeature", "SweepFeature"):
        if not hasattr(fusion, name):
            setattr(fusion, name, type(name, (), {}))
    core = sys.modules["adsk.core"]
    for name in ("Matrix3D", "ObjectCollection"):
        if not hasattr(core, name):
            setattr(core, name, type(name, (), {}))
    if not hasattr(fusion, "FeatureHealthStates"):
        fusion.FeatureHealthStates = types.SimpleNamespace(HealthyFeatureHealthState=0)
    # its siblings aren't used by what is tested here
    package = "rebuildUtilsTest"
    root = types.ModuleType(package)
    root.__path__ = []
    sys.modules[package] = root
    for (name, attributes) in [("configJson", {}), ("tagUtils", {}), ("gridfinityUtils", {"__path__": []})]:
        module = types.ModuleType(package + "." + name)
        module.__dict__.update(attributes)
        sys.modules[package + "." + name] = module
        setattr(root, name, module)
    logged = []
    commonUtils = types.ModuleType(package + ".gridfinityUtils.commonUtils")
    commonUtils.fileLog = logged.append
    commonUtils.debugLog = logged.append
    sys.modules[package + ".gridfinityUtils.commonUtils"] = commonUtils
    root.gridfinityUtils.commonUtils = commonUtils
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "rebuildUtils.py")
    spec = importlib.util.spec_from_file_location(package + ".rebuildUtils", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (module, logged)


(rebuildUtils, logged) = _load_rebuild_utils()


def test_counter_dropped_once_the_old_component_is_gone():
    assert rebuildUtils.oldComponentName("Gridfinity bin 1x1x3 (1)", "Gridfinity bin 1x1x3") == "Gridfinity bin 1x1x3"


def test_counted_old_name_kept():
    # the second of two bins of a size was counted already, its rebuild got the next count
    assert rebuildUtils.oldComponentName("Gridfinity bin 1x1x3 (2)", "Gridfinity bin 1x1x3 (1)") == "Gridfinity bin 1x1x3 (1)"


def test_new_size_keeps_its_name():
    assert rebuildUtils.oldComponentName("Gridfinity bin 2x1x3", "Gridfinity bin 1x1x3") is None


def test_name_not_counted_stays():
    assert rebuildUtils.oldComponentName("Gridfinity bin 1x1x3", "Gridfinity bin 1x1x3") is None


def test_renamed_old_component_not_taken_over():
    # the add-in names the new component after its settings, as before
    assert rebuildUtils.oldComponentName("Gridfinity bin 1x1x3", "Cutlery bin") is None


class FakeComponent:
    def __init__(self, name):
        self.name = name


class FakeOccurrence:
    def __init__(self, name):
        self.component = FakeComponent(name)


def test_new_component_renamed():
    occurrence = FakeOccurrence("Gridfinity baseplate 3x2 (1)")
    rebuildUtils.keepComponentName(occurrence, "Gridfinity baseplate 3x2")
    assert occurrence.component.name == "Gridfinity baseplate 3x2"


def test_part_design_has_no_component_to_rename():
    rebuildUtils.keepComponentName(None, None)


def test_refused_name_logged_and_rebuild_goes_on():
    class Refusing(FakeComponent):
        def __setattr__(self, key, value):
            if key == "name" and hasattr(self, "name"):
                raise RuntimeError("name in use")
            super().__setattr__(key, value)
    occurrence = FakeOccurrence("x")
    occurrence.component = Refusing("Gridfinity bin 1x1x3 (1)")
    logged.clear()
    rebuildUtils.keepComponentName(occurrence, "Gridfinity bin 1x1x3")
    assert occurrence.component.name == "Gridfinity bin 1x1x3 (1)"
    assert len(logged) == 1
