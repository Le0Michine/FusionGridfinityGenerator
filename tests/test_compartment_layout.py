"""
Tests for compartment pockets: tiling the compartment grid, reading old saved tables and describing pockets.
"""

import os
import importlib.util


def _load_compartment_layout():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "compartmentLayout.py")
    spec = importlib.util.spec_from_file_location("compartmentLayout", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


layout = _load_compartment_layout()


def cells(pockets):
    return sorted((p["x"], p["y"], p["width"], p["length"]) for p in pockets)


def test_empty_grid_is_single_cells_in_pattern_order():
    pockets = layout.normalizePockets([], 2, 3)
    assert [(p["x"], p["y"]) for p in pockets] == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
    assert layout.isUniform(pockets)
    assert not layout.isCustomized(pockets)


def test_merged_pocket_keeps_its_cells_and_the_rest_are_filled():
    pockets = layout.normalizePockets([layout.pocket(0, 1, 2, 2, label="M3")], 2, 3)
    assert cells(pockets) == [(0, 0, 1, 1), (0, 1, 2, 2), (1, 0, 1, 1)]
    assert not layout.isUniform(pockets)
    assert layout.isCustomized(pockets)


def test_pockets_past_the_grid_or_overlapping_are_dropped():
    pockets = layout.normalizePockets([
        layout.pocket(0, 0, 2, 1),
        layout.pocket(1, 0, 1, 2),
        layout.pocket(1, 1, 2, 1),
    ], 2, 2)
    assert cells(pockets) == [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)]


def test_shrinking_the_grid_drops_pockets_that_no_longer_fit():
    pockets = layout.normalizePockets([layout.pocket(0, 0, 3, 1, depth=12)], 2, 1)
    assert cells(pockets) == [(0, 0, 1, 1), (1, 0, 1, 1)]


def test_bad_values_from_the_drawing_are_cleaned_up():
    pockets = layout.normalizePockets([
        {"x": "0", "y": 0, "width": 1, "length": 1, "depth": "", "label": None, "icon": ""},
        {"x": 1, "y": 0, "width": 1, "length": 1, "depth": -3},
        {"x": "a", "y": 0},
    ], 2, 1)
    assert [(p["depth"], p["label"], p["icon"]) for p in pockets] == [(None, "", "Default"), (None, "", "Default")]


def test_shallow_pocket_is_not_uniform():
    pockets = layout.normalizePockets([layout.pocket(0, 0, depth=10)], 2, 1)
    assert not layout.isUniform(pockets)


def test_old_table_rows_become_pockets():
    rows = [
        {
            "x_input_1": {"value": 0}, "y_input_1": {"value": 0}, "w_input_1": {"value": 2}, "l_input_1": {"value": 1},
            "d_input_1": {"value": 1.5}, "label_input_1": {"value": "M3"}, "icon_input_1": {"value": "hex-nut"},
        },
        # rows saved before labels existed, with the old full depth default
        {"x_input_2": {"value": 0}, "y_input_2": {"value": 1}, "w_input_2": {"value": 1}, "l_input_2": {"value": 1}, "d_input_2": {"value": 4.0}},
    ]
    pockets = layout.fromTableRows(rows, fullDepth=3.5)
    assert pockets == [
        layout.pocket(0, 0, 2, 1, depth=15.0, label="M3", icon="hex-nut"),
        layout.pocket(0, 1, 1, 1),
    ]


def test_describe_lists_what_is_set():
    assert layout.describe(layout.pocket(0, 1, 2, 1)) == "cell 1, 2, 2 x 1 cells, full depth"
    assert layout.describe(layout.pocket(1, 0, depth=12.5, label="M3", icon="hex-nut")) == "cell 2, 1, 1 x 1 cells, depth 12.5 mm, label M3, icon hex-nut"
