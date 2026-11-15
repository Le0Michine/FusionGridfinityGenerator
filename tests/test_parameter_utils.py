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


class _FakeParameter:
    def __init__(self, name, value, expression, textValue=''):
        self.name = name
        self.value = value
        self.expression = expression
        self.textValue = textValue


class _FakeParameters:
    def __init__(self, parameters=()):
        self.byName = {parameter.name: parameter for parameter in parameters}
        self.added = []

    def itemByName(self, name):
        return self.byName.get(name)

    def add(self, name, valueInput, unit, comment):
        self.added.append(name)
        return _FakeParameter(name, 0, '')


class _FakeParametersDesign:
    def __init__(self, parameters=()):
        self.userParameters = _FakeParameters(parameters)


def test_reuse_keeps_an_expression_that_comes_to_the_value():
    parameter = _FakeParameter("gfBin1_heightU", 6, "gfOther * 2")
    design = _FakeParametersDesign([parameter])
    assert parameterUtils.addUnitlessParameter(design, "gfBin1_heightU", 6, "", reuse=True) is parameter
    assert parameter.expression == "gfOther * 2"
    assert design.userParameters.added == []


def test_reuse_sets_a_changed_value():
    parameter = _FakeParameter("gfBin1_heightU", 6, "6")
    design = _FakeParametersDesign([parameter])
    parameterUtils.addUnitlessParameter(design, "gfBin1_heightU", 4, "", reuse=True)
    assert parameter.expression == "4"


def test_reuse_sets_a_changed_length_in_mm():
    parameter = _FakeParameter("gfBin1_baseWidth", 4.2, "42 mm")
    design = _FakeParametersDesign([parameter])
    parameterUtils.addLengthParameter(design, "gfBin1_baseWidth", 4.0, "", reuse=True)
    assert parameter.expression == "40 mm"


def test_reuse_sets_a_changed_text():
    parameter = _FakeParameter("gfBin1_label", 0, "'M3'", "M3")
    design = _FakeParametersDesign([parameter])
    parameterUtils.addTextParameter(design, "gfBin1_label", "M3", "", reuse=True)
    assert parameter.expression == "'M3'"
    parameterUtils.addTextParameter(design, "gfBin1_label", "Leo's", "", reuse=True)
    assert parameter.expression == "'Leo’s'"


def test_reuse_adds_a_missing_parameter(monkeypatch):
    valueInput = type("ValueInput", (), {"createByString": staticmethod(lambda expression: expression)})
    monkeypatch.setattr(parameterUtils.adsk.core, "ValueInput", valueInput, raising=False)
    design = _FakeParametersDesign()
    parameterUtils.addUnitlessParameter(design, "gfBin1_heightU", 6, "", reuse=True)
    assert design.userParameters.added == ["gfBin1_heightU"]


def test_a_prefix_taken_as_a_body_id_is_skipped():
    design = _FakeDesign()
    assert parameterUtils.nextFreePrefix(design, "gfPlate", ["paddingLeft"], {"gfPlate1"}) == "gfPlate2"
