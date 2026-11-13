"""
Tests for bin footprints: checking a shape can be built and tracing the outline around it.
"""

import os
import importlib.util

import pytest


def _load_bin_shape():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "binShape.py")
    spec = importlib.util.spec_from_file_location("binShape", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shape = _load_bin_shape()

# an L three cells long with its foot to the right
L_SHAPE = [(0, 0), (1, 0), (0, 1), (0, 2)]


def test_normalize_drops_bad_and_repeated_cells():
    assert shape.normalizeShape([(1, 0), [0, 0], ("1", 0), (2, 0), (0, -1), "a", None], 2, 1) == [(0, 0), (1, 0)]


def test_full_grid_is_a_rectangle():
    assert shape.isRectangle(shape.rectangle(2, 3), 2, 3)
    assert not shape.isRectangle(L_SHAPE, 2, 3)


@pytest.mark.parametrize("cells, error", [
    ([], shape.ERROR_EMPTY),
    ([(0, 0), (2, 0)], shape.ERROR_NOT_CONNECTED),
    # touching at a corner only isn't connected
    ([(0, 0), (1, 1)], shape.ERROR_NOT_CONNECTED),
    # a ring around the middle cell
    ([(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)], shape.ERROR_HOLES),
    # a C closed at a corner, its walls would touch there
    ([(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2)], shape.ERROR_HOLES),
    (L_SHAPE, None),
    (shape.rectangle(3, 2), None),
])
def test_shape_error(cells, error):
    assert shape.shapeError(cells) == error


def test_pinched_corner_counts_as_a_hole():
    # a U whose arms close in on one cell at a corner, the walls there would touch
    cells = [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (1, 2), (2, 2)]
    assert shape.isConnected(cells)
    assert shape.hasHoles(cells)


def test_rectangle_outline_is_four_convex_corners():
    assert shape.outline(shape.rectangle(2, 3)) == [(0, 0, True), (2, 0, True), (2, 3, True), (0, 3, True)]


def test_l_outline_has_one_inner_corner():
    assert shape.outline(L_SHAPE) == [
        (0, 0, True),
        (2, 0, True),
        (2, 1, True),
        (1, 1, False),
        (1, 3, True),
        (0, 3, True),
    ]


def test_outline_of_a_plus():
    plus = [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)]
    corners = shape.outline(plus)
    assert len(corners) == 12
    assert sum(1 for corner in corners if not corner[2]) == 4


def test_rectangle_wall_junctions_are_where_grid_lines_meet_the_walls():
    # as cutWallJunctionPockets places them for a plain 3 x 2 bin
    assert shape.wallJunctions(shape.rectangle(3, 2)) == [(0, 1), (1, 0), (1, 2), (2, 0), (2, 2), (3, 1)]


def test_wall_junctions_include_inner_corners():
    assert shape.wallJunctions(L_SHAPE) == [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]


def test_inner_corner_opens_towards_the_empty_cell():
    # the L's notch is right of its upright and behind its foot
    assert shape.innerCornerOpenings(L_SHAPE) == {(1, 1): (1, 1)}
    assert shape.innerCornerOpenings(shape.rectangle(2, 2)) == {}


def test_plus_inner_corners_open_diagonally_outwards():
    plus = [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)]
    assert shape.innerCornerOpenings(plus) == {(1, 1): (-1, -1), (2, 1): (1, -1), (2, 2): (1, 1), (1, 2): (-1, 1)}


def test_single_cell_has_no_wall_junctions():
    assert shape.wallJunctions([(0, 0)]) == []


def test_inset_moves_every_side_in_by_the_clearance():
    corners = shape.insetOutline(shape.outline(L_SHAPE), 4.2, 4.2, 0.025)
    expected = [
        (0.025, 0.025, True),
        (8.375, 0.025, True),
        (8.375, 4.175, True),
        # both sides meeting at the inner corner move away from the notch, so it goes further into the shape
        (4.175, 4.175, False),
        (4.175, 12.575, True),
        (0.025, 12.575, True),
    ]
    assert corners == [pytest.approx(corner) for corner in expected]


def test_corner_radii_are_centred_like_a_bin_corner():
    # the outside of the bin, 0.25 mm in from the cell lines, its outer corners are the usual 3.75 mm
    assert shape.cornerRadius(True, 0.4, 0.025) == pytest.approx(0.375)
    # an inner corner around a 3.75 mm corner of a bin in the notch, both bins' clearances apart
    assert shape.cornerRadius(False, 0.4, 0.025) == pytest.approx(0.425)
    # the pocket inside a 1.2 mm wall
    assert shape.cornerRadius(True, 0.4, 0.025 + 0.12) == pytest.approx(0.255)
    assert shape.cornerRadius(False, 0.4, 0.025 + 0.12) == pytest.approx(0.545)


def test_split_cells_makes_four_half_cells_each():
    assert shape.splitCells([(0, 0), (1, 0)]) == [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)]


def test_merge_cells_keeps_whole_cells_with_any_half():
    assert shape.mergeCells([(0, 0), (1, 1), (2, 0)]) == [(0, 0), (1, 0)]
    assert shape.mergeCells(shape.splitCells(L_SHAPE)) == sorted(L_SHAPE)


def test_foot_shape_to_outline_keeps_half_feet_a_single_cell():
    # 1.5 x 1 feet, the right column a half foot
    assert shape.footShapeToOutline([(0, 0), (1, 0)], 1.5, 1, 2) == [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]
    assert shape.footShapeToOutline(L_SHAPE, 2, 3, 1) == sorted(L_SHAPE)


def test_foot_shape_merges_back_from_the_outline():
    feet = [(0, 0), (1, 0), (2, 0), (0, 1)]
    assert shape.mergeCells(shape.footShapeToOutline(feet, 2.5, 1.5, 2)) == sorted(feet)
