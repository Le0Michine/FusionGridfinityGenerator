"""
Tests for the lip height the bin dialog shows: the sharp top of an untrimmed lip follows the clearance, a trimmed one
is cut flat at 3.8mm.
"""

import math
import os
import sys
import types
import importlib.util

import pytest


def _load_lip_input():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(project_root, "lib", "gridfinityUtils")
    # a package of its own, so the relative imports of const and dim resolve without the Fusion modules
    package = types.ModuleType("lipPackage")
    package.__path__ = [folder]
    sys.modules["lipPackage"] = package
    core = sys.modules["adsk.core"]
    for name in ("ValueInput", "Base"):
        if not hasattr(core, name):
            setattr(core, name, type(name, (), {}))
    for name in ["const", "dim", "binBodyLipGeneratorInput"]:
        spec = importlib.util.spec_from_file_location(f"lipPackage.{name}", os.path.join(folder, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"lipPackage.{name}"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["lipPackage.binBodyLipGeneratorInput"]


lip = _load_lip_input()


def test_untrimmed_lip_at_the_default_clearance():
    # 5mm - (1 + sqrt(2)) * 0.25mm, in cm
    assert lip.lipHeight(False, 0.025) == pytest.approx(0.475 - math.sqrt(2) / 40)
    assert lip.lipHeight(False, 0.025) == pytest.approx(0.43964, abs=1e-5)


def test_trimmed_lip_is_flat_at_3_8mm():
    assert lip.lipHeight(True, 0.025) == pytest.approx(0.38)


def test_untrimmed_lip_is_lower_with_more_clearance():
    assert lip.lipHeight(False, 0.04) < lip.lipHeight(False, 0.025)


def test_trim_doesnt_raise_a_lip_already_below_it():
    # a clearance this wide brings the sharp top below the trim
    assert lip.lipHeight(True, 0.06) == pytest.approx(lip.lipHeight(False, 0.06))
