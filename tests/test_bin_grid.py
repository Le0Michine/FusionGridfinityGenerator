"""
Tests for bin sizes in whole and half base units, and where their feet go.
"""

import os
import importlib.util


def _load_bin_grid():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "binGrid.py")
    spec = importlib.util.spec_from_file_location("binGrid", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


grid = _load_bin_grid()


def test_sizes_step_in_halves():
    assert grid.isHalfStep(2)
    assert grid.isHalfStep(2.5)
    assert not grid.isHalfStep(2.3)
    assert grid.isWhole(3.0)
    assert not grid.isWhole(0.5)


def test_split_half_leaves_the_half_over():
    assert grid.splitHalf(3) == (3, False)
    assert grid.splitHalf(2.5) == (2, True)
    assert grid.splitHalf(0.5) == (0, True)
    # sizes doubled for a half grid come in as floats
    assert grid.splitHalf(5.0) == (5, False)


def test_feet_spans_end_with_the_half_foot():
    assert grid.footSpans(2) == [(0.0, 1.0), (1.0, 1.0)]
    assert grid.footSpans(2.5) == [(0.0, 1.0), (1.0, 1.0), (2.0, 0.5)]
    assert grid.footSpans(0.5) == [(0.0, 0.5)]


def test_outline_is_in_half_cells_with_any_half():
    assert grid.outlineDivisions(2, 3, False) == 1
    assert grid.outlineDivisions(2.5, 3, False) == 2
    assert grid.outlineDivisions(2, 3.5, False) == 2
    assert grid.outlineDivisions(2, 3, True) == 2


def test_feet_per_unit():
    assert grid.feetPerUnit(False) == 1
    assert grid.feetPerUnit(True) == 2


def test_sizes_format_like_the_dialog():
    assert grid.formatSize(2.0) == "2"
    assert grid.formatSize(2.5) == "2.5"


def test_outline_cells_per_foot():
    assert grid.outlineCellsPerFoot(2, 3, False) == 1
    assert grid.outlineCellsPerFoot(2.5, 3, False) == 2
    # half grid feet are the outline cells already
    assert grid.outlineCellsPerFoot(2.5, 3, True) == 1


def test_foot_lines_skip_the_middle_of_whole_feet():
    assert grid.footLines(2.5, 2) == {0, 2, 4, 5}
    assert grid.footLines(2, 2) == {0, 2, 4}
    assert grid.footLines(3, 1) == {0, 1, 2, 3}
