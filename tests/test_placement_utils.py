"""
Tests for grid placement: snapping extents to cells and greedily picking the free spot closest to the origin.
"""

import sys
import os
import types
import importlib.util
import pytest


def _load_placement_utils():
    # The modules annotate with adsk types, so they only need to exist
    fusion = sys.modules.get("adsk.fusion") or types.ModuleType("adsk.fusion")
    for name in ("BRepBody", "Design", "Component", "MoveFeature"):
        if not hasattr(fusion, name):
            setattr(fusion, name, type(name, (), {}))
    sys.modules["adsk.fusion"] = fusion
    sys.modules["adsk"].fusion = fusion

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    package = types.ModuleType("placementpkg")
    package.__path__ = []
    sys.modules["placementpkg"] = package

    def load(name):
        path = os.path.join(project_root, "lib", f"{name}.py")
        spec = importlib.util.spec_from_file_location(f"placementpkg.{name}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"placementpkg.{name}"] = mod
        setattr(package, name, mod)
        spec.loader.exec_module(mod)
        return mod

    load("tagUtils")
    return load("placementUtils")


placementUtils = _load_placement_utils()

BASE = 4.2  # cm
CLEARANCE = 0.025  # cm


def binExtent(x, y, width, length):
    """Extent of a bin placed with its grid corner at cell (x, y)"""
    return (x * BASE, y * BASE, (x + width) * BASE - CLEARANCE * 2, (y + length) * BASE - CLEARANCE * 2)


def place(footprintCells, occupied):
    return placementUtils.findFreeGridOffset(footprintCells, occupied)


# ---------------------------------------------------------------------------
# extentToCells
# ---------------------------------------------------------------------------

def test_bin_extent_covers_exactly_its_cells():
    assert placementUtils.extentToCells(binExtent(0, 0, 2, 3), BASE, BASE) == (0, 0, 2, 3)


def test_moved_bin_extent_covers_exactly_its_cells():
    assert placementUtils.extentToCells(binExtent(3, 1, 1, 1), BASE, BASE) == (3, 1, 4, 2)


def test_extent_on_cell_border_does_not_spill_into_neighbour():
    assert placementUtils.extentToCells((0, 0, BASE * 2 + 1e-7, BASE), BASE, BASE) == (0, 0, 2, 1)


def test_off_grid_extent_snaps_outward():
    assert placementUtils.extentToCells((1.0, -0.5, 5.0, 2.0), BASE, BASE) == (0, -1, 2, 1)


def test_padding_reserves_whole_cells():
    padded = (-0.5, 0, BASE * 2 - CLEARANCE * 2 + 0.5, BASE)
    assert placementUtils.extentToCells(padded, BASE, BASE) == (-1, 0, 3, 1)


# ---------------------------------------------------------------------------
# findFreeGridOffset
# ---------------------------------------------------------------------------

def test_first_item_stays_at_origin():
    assert place((0, 0, 2, 2), []) == (0, 0)


def test_second_item_goes_next_to_first_along_x():
    assert place((0, 0, 1, 1), [(0, 0, 1, 1)]) == (1, 0)


def test_equal_items_gather_into_a_square():
    occupied = []
    for _ in range(4):
        (x, y) = place((0, 0, 1, 1), occupied)
        occupied.append((x, y, x + 1, y + 1))
    assert sorted(cells[:2] for cells in occupied) == [(0, 0), (0, 1), (1, 0), (1, 1)]


def test_gap_left_by_deleted_item_is_reused():
    occupied = [(1, 0, 2, 1), (0, 1, 1, 2), (1, 1, 2, 2)]
    assert place((0, 0, 1, 1), occupied) == (0, 0)


def test_large_item_fits_in_gap_only_when_it_is_big_enough():
    # 1x1 hole at (1, 0) surrounded by items, a 2x1 item can't use it
    occupied = [(0, 0, 1, 1), (2, 0, 3, 1), (0, 1, 3, 2)]
    (x, y) = place((0, 0, 2, 1), occupied)
    shifted = (x, y, x + 2, y + 1)
    assert not any(placementUtils.cellsOverlap(shifted, cells) for cells in occupied)
    assert place((0, 0, 1, 1), occupied) == (1, 0)


def test_long_item_settles_with_its_center_closest_to_origin():
    # a 1x1 at origin; a 3x1 item fits above (center 1.5, 1.5) closer than beside it (center 2.5, 0.5)
    assert place((0, 0, 3, 1), [(0, 0, 1, 1)]) == (0, 1)


def test_negative_footprint_start_from_padding():
    # padded footprint starts one cell left of its origin, stacking above beats shifting 3 cells right
    assert place((-1, 0, 2, 1), [(-1, 0, 2, 1)]) == (0, 1)


def test_items_away_from_origin_leave_origin_free():
    assert place((0, 0, 1, 1), [(5, 5, 6, 6)]) == (0, 0)


def test_non_square_cells_scale_distance():
    # wide cells make a step along y cheaper than along x
    assert placementUtils.findFreeGridOffset((0, 0, 1, 1), [(0, 0, 1, 1)], cellWidth=10, cellLength=1) == (0, 1)


def test_result_never_overlaps():
    occupied = [(0, 0, 3, 2), (3, 0, 4, 4), (0, 2, 2, 3), (5, 1, 7, 2)]
    for footprint in [(0, 0, 1, 1), (0, 0, 2, 2), (0, 0, 4, 1), (0, 0, 1, 5)]:
        (x, y) = place(footprint, occupied)
        assert x >= 0 and y >= 0
        shifted = (footprint[0] + x, footprint[1] + y, footprint[2] + x, footprint[3] + y)
        assert not any(placementUtils.cellsOverlap(shifted, cells) for cells in occupied)
