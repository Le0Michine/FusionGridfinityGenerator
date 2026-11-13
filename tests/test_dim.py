"""
Tests for Dim: values and expressions combine together, the kind picks what Fusion gets.
"""

import sys
import os
import types
import importlib.util
import pytest


class _FakeValueInput:
    def __init__(self, real=None, string=None):
        self.real = real
        self.string = string

    @staticmethod
    def createByReal(value):
        return _FakeValueInput(real=value)

    @staticmethod
    def createByString(value):
        return _FakeValueInput(string=value)


def _load_dim():
    core = sys.modules["adsk.core"]
    if not hasattr(core, "ValueInput"):
        core.ValueInput = _FakeValueInput
    if not hasattr(core, "Base"):
        core.Base = type("Base", (), {})

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "dim.py")
    spec = importlib.util.spec_from_file_location("dim", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dim = _load_dim()
Dim = dim.Dim


class _FakeParameter:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.expression = None


def test_length_is_a_millimeter_literal_of_internal_units():
    length = Dim.length(0.7)
    assert length.value == 0.7
    assert length.expression == "7 mm"
    assert not length.isExpression


def test_parameter_is_fed_as_its_name():
    height = Dim.parameter(_FakeParameter("gfBin1_heightU", 5))
    assert height.value == 5
    assert height.expression == "gfBin1_heightU"
    assert height.isExpression


def test_bin_top_combines_values_and_expressions():
    height = Dim.parameter(_FakeParameter("gfBin1_heightU", 5))
    unit = Dim.parameter(_FakeParameter("gfBin1_heightUnit", 0.7))
    top = height * unit - Dim.length(0.5)
    assert top.value == pytest.approx(3.0)
    assert top.expression == "(gfBin1_heightU * gfBin1_heightUnit) - 5 mm"
    assert top.isExpression


def test_plain_values_stay_plain():
    total = Dim.length(4.2) * 2 - Dim.length(0.05)
    assert total.value == pytest.approx(8.35)
    assert total.expression == "(42 mm * 2) - 0.5 mm"
    assert not total.isExpression


def test_compound_operands_are_parenthesized():
    radius = Dim.length(0.4) - Dim.length(0.025)
    rise = Dim.length(0.4) * Dim.number(2 ** 0.5, "sqrt(2)") - radius
    assert rise.expression == "(4 mm * sqrt(2)) - (4 mm - 0.25 mm)"


def test_reverse_multiplication_by_a_number():
    doubled = 2 * Dim.length(0.4)
    assert doubled.value == pytest.approx(0.8)
    assert doubled.expression == "2 * 4 mm"


def test_bare_numbers_in_sums_are_rejected():
    with pytest.raises(TypeError):
        Dim.length(0.4) - 1
    with pytest.raises(TypeError):
        1 + Dim.number(2)


def test_as_expression_keeps_value_and_switches_kind():
    length = Dim.length(0.4).asExpression()
    assert length.isExpression
    assert (length * 2).isExpression


def test_abs_wraps_the_expression():
    offset = Dim.length(-0.4).abs()
    assert offset.value == pytest.approx(0.4)
    assert offset.expression == "abs(-4 mm)"


def test_value_input_uses_the_kind():
    assert dim.valueInput(Dim.length(0.7)).real == 0.7
    assert dim.valueInput(Dim.length(0.7).asExpression()).string == "7 mm"
    assert dim.valueInput(1.5).real == 1.5


def test_apply_to_only_drives_expressions():
    parameter = _FakeParameter("d1", 0.7)
    dim.applyTo(parameter, Dim.length(0.7))
    assert parameter.expression is None
    dim.applyTo(parameter, Dim.length(0.7).asExpression())
    assert parameter.expression == "7 mm"


def test_value_of_accepts_both():
    assert dim.valueOf(Dim.length(0.7)) == 0.7
    assert dim.valueOf(0.7) == 0.7


def test_as_length_lifts_plain_values_and_keeps_dims():
    assert Dim.asLength(4.2).expression == "42 mm"
    width = Dim.parameter(_FakeParameter("gfBaseWidth", 4.2))
    assert Dim.asLength(width) is width


def test_min_and_max_keep_the_expression():
    height = Dim(2.4, "gfHeightUnit * 4", dim.DimKind.EXPRESSION, True)
    radius = Dim.max(Dim.min(Dim.length(2.5), height), Dim.length(0.2))
    assert radius.value == pytest.approx(2.4)
    assert radius.isExpression
    assert radius.expression == "max(min(25 mm; gfHeightUnit * 4); 2 mm)"


def test_min_and_max_of_values_stay_values():
    radius = Dim.max(Dim.min(Dim.length(2.5), Dim.length(2.9)), Dim.length(0.2))
    assert radius.value == pytest.approx(2.5)
    assert not radius.isExpression
    assert dim.valueInput(radius).real == pytest.approx(2.5)
