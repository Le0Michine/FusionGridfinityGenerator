"""
Tests for user parameter naming: numbered prefixes skip ones already taken in the design.
"""

import sys
import os
import types
import importlib.util


def _load_parameter_utils():
    # The module annotates with adsk.fusion types, so they only need to exist
    fusion = sys.modules.get("adsk.fusion") or types.ModuleType("adsk.fusion")
    for name in ("Design", "UserParameter"):
        if not hasattr(fusion, name):
            setattr(fusion, name, type(name, (), {}))
    sys.modules["adsk.fusion"] = fusion
    sys.modules["adsk"].fusion = fusion

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "parameterUtils.py")
    spec = importlib.util.spec_from_file_location("parameterUtils", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


parameterUtils = _load_parameter_utils()


class _FakeUserParameters:
    def __init__(self, names):
        self._names = set(names)

    def itemByName(self, name):
        return name if name in self._names else None


class _FakeDesign:
    def __init__(self, names=()):
        self.userParameters = _FakeUserParameters(names)


def test_first_prefix_in_empty_design():
    assert parameterUtils.nextFreePrefix(_FakeDesign(), "gfBin", ["heightU"]) == "gfBin1"


def test_skips_prefixes_already_taken():
    design = _FakeDesign(["gfBin1_heightU", "gfBin2_heightU"])
    assert parameterUtils.nextFreePrefix(design, "gfBin", ["heightU"]) == "gfBin3"


def test_any_taken_name_blocks_the_prefix():
    design = _FakeDesign(["gfBin1_widthU"])
    assert parameterUtils.nextFreePrefix(design, "gfBin", ["heightU", "widthU"]) == "gfBin2"


def test_reuses_gaps_left_by_deleted_parameters():
    design = _FakeDesign(["gfBin2_heightU"])
    assert parameterUtils.nextFreePrefix(design, "gfBin", ["heightU"]) == "gfBin1"


def test_parameter_name_joins_prefix_and_name():
    assert parameterUtils.parameterName("gfBin1", "heightU") == "gfBin1_heightU"


def test_text_expression_is_a_quoted_literal():
    assert parameterUtils.textExpression("M3 screws") == "'M3 screws'"


def test_text_expression_swaps_inner_quotes():
    assert parameterUtils.textExpression("Leo's bits") == "'Leo’s bits'"
