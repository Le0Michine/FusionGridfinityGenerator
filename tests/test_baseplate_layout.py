"""
Tests for the fill layout: fitting a centered grid into an area and splitting it into pieces fitting the print bed.
"""

import sys
import os
import importlib.util
import pytest


def _load_baseplate_layout():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "baseplateLayout.py")
    spec = importlib.util.spec_from_file_location("baseplateLayout", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["baseplateLayout"] = mod
    spec.loader.exec_module(mod)
    return mod


baseplateLayout = _load_baseplate_layout()

# Fusion internal units, cm
BASE = 4.2
CLEARANCE = 0.025


def layout(areaWidth, areaLength, bedWidth, bedLength, fitTolerance=0, bedMargin=0, **options):
    return baseplateLayout.computeFillLayout(areaWidth, areaLength, fitTolerance, bedWidth, bedLength, bedMargin, BASE, BASE, CLEARANCE, **options)


class TestFitAxis:
    def fit(self, span, alignment=None, useHalfCells=False):
        return baseplateLayout.fitAxis(span, BASE, CLEARANCE, alignment or baseplateLayout.ALIGN_CENTER, useHalfCells)

    def test_leftover_is_split_between_both_sides(self):
        (cells, paddingStart, paddingEnd, _, _) = self.fit(60)
        assert cells == 14
        # 14 cells make a 587.5mm plate without padding
        assert (paddingStart, paddingEnd) == (pytest.approx(0.625), pytest.approx(0.625))

    def test_exact_fit_needs_no_padding(self):
        assert self.fit(3 * BASE - CLEARANCE * 2)[:3] == (3, pytest.approx(0), pytest.approx(0))

    def test_area_smaller_than_a_cell_fits_none(self):
        assert self.fit(4)[0] == 0

    def test_grid_pushed_to_the_start_leaves_the_padding_at_the_end(self):
        assert self.fit(60, baseplateLayout.ALIGN_START)[1:3] == (0, pytest.approx(1.25))

    def test_grid_pushed_to_the_end_leaves_the_padding_at_the_start(self):
        assert self.fit(60, baseplateLayout.ALIGN_END)[1:3] == (pytest.approx(1.25), 0)

    def test_half_cells_take_the_leftover_when_they_fit(self):
        # 3 cells leave 3cm, enough for 2.1cm of half cells and 0.9cm of padding
        span = 3 * BASE - CLEARANCE * 2 + 3
        assert self.fit(span, useHalfCells=True) == (3, pytest.approx(0.45), pytest.approx(0.45), False, True)

    def test_half_cells_go_opposite_the_grid(self):
        span = 3 * BASE - CLEARANCE * 2 + 3
        assert self.fit(span, baseplateLayout.ALIGN_START, True) == (3, 0, pytest.approx(0.9), False, True)
        assert self.fit(span, baseplateLayout.ALIGN_END, True) == (3, pytest.approx(0.9), 0, True, False)

    def test_half_cells_are_skipped_when_they_dont_fit(self):
        span = 3 * BASE - CLEARANCE * 2 + 2
        assert self.fit(span, useHalfCells=True) == (3, pytest.approx(1), pytest.approx(1), False, False)


class TestSplitAxis:
    def test_fits_in_one_piece(self):
        assert baseplateLayout.splitAxis(5, 0, 0, BASE, CLEARANCE, 25.6) == (5,)

    def test_cells_are_spread_evenly_with_bigger_pieces_in_the_middle(self):
        assert baseplateLayout.splitAxis(13, 0, 0, BASE, CLEARANCE, 21) == (4, 5, 4)

    def test_extra_cells_go_to_the_middle_first(self):
        assert baseplateLayout.splitAxis(14, 0, 0, BASE, CLEARANCE, 21) == (5, 5, 4)

    def test_padded_edge_pieces_hold_fewer_cells(self):
        # 2cm padding leaves room for 4 cells on the edge pieces, 5 in the middle
        assert baseplateLayout.splitAxis(10, 2, 2, BASE, CLEARANCE, 21) == (3, 4, 3)

    def test_whole_cells_exactly_matching_the_bed_fit(self):
        # pieces are cut the clearance short on every side, so 5 cells fit a bed of exactly 5 units
        assert baseplateLayout.splitAxis(15, 0, 0, BASE, CLEARANCE, 5 * BASE) == (5, 5, 5)

    def test_seams_are_cut_by_the_clearance(self):
        # 5 cells less the clearance on both sides is 20.95cm, just over a 20.9cm bed
        assert baseplateLayout.splitAxis(10, 0, 0, BASE, CLEARANCE, 5 * BASE - 0.05) == (5, 5)
        assert baseplateLayout.splitAxis(10, 0, 0, BASE, CLEARANCE, 5 * BASE - 0.06) == (3, 4, 3)

    def test_bed_too_small_for_padding_and_a_cell(self):
        assert baseplateLayout.splitAxis(3, 3, 3, BASE, CLEARANCE, 6) is None


class TestComputeFillLayout:
    def test_grid_is_centered_in_the_area_less_the_tolerance(self):
        result = layout(60.1, 40.1, 25.6, 25.6, fitTolerance=0.1)
        assert (result.x.cells, result.y.cells) == (14, 9)
        assert (result.x.paddingStart, result.x.paddingEnd) == (pytest.approx(0.625), pytest.approx(0.625))
        assert result.y.paddingStart == pytest.approx((40 - (9 * BASE - CLEARANCE * 2)) / 2)

    def test_pieces_cover_the_grid_row_by_row(self):
        result = layout(60, 40, 25.6, 25.6)
        assert result.x.pieces == (5, 5, 4)
        assert result.y.pieces == (5, 4)
        assert [(piece.column, piece.row, piece.cellOffsetX, piece.cellOffsetY, piece.cellsX, piece.cellsY) for piece in result.pieces] == [
            (0, 0, 0, 0, 5, 5),
            (1, 0, 5, 0, 5, 5),
            (2, 0, 10, 0, 4, 5),
            (0, 1, 0, 5, 5, 4),
            (1, 1, 5, 5, 5, 4),
            (2, 1, 10, 5, 4, 4),
        ]

    def test_edge_flags_mark_the_outer_sides(self):
        result = layout(60, 40, 25.6, 25.6)
        middleBottom = result.pieces[1]
        assert (middleBottom.isLeftEdge, middleBottom.isRightEdge, middleBottom.isBottomEdge, middleBottom.isTopEdge) == (False, False, True, False)
        topRight = result.pieces[-1]
        assert (topRight.isLeftEdge, topRight.isRightEdge, topRight.isBottomEdge, topRight.isTopEdge) == (False, True, False, True)

    def test_single_piece_has_every_side_on_the_edge(self):
        result = layout(20, 20, 25.6, 25.6)
        assert len(result.pieces) == 1
        piece = result.pieces[0]
        assert piece.isLeftEdge and piece.isRightEdge and piece.isBottomEdge and piece.isTopEdge

    def test_bed_margin_shrinks_the_usable_bed(self):
        # 5 cells fit a 21cm bed, but not once 5mm are kept clear on every side
        assert layout(21, 4.2, 21, 21).x.pieces == (5,)
        assert layout(21, 4.2, 21, 21, bedMargin=0.5).x.pieces == (3, 2)

    def test_bed_is_turned_when_that_needs_fewer_pieces(self):
        result = layout(30, 12, 13, 31)
        assert result.isBedRotated
        assert len(result.pieces) == 1

    def test_bed_keeps_its_orientation_on_a_tie(self):
        assert not layout(60, 40, 25.6, 25.6).isBedRotated

    def test_area_too_small_for_a_cell(self):
        with pytest.raises(baseplateLayout.FillLayoutError, match='area is too small'):
            layout(4, 30, 25.6, 25.6)

    def test_bed_too_small_for_a_cell(self):
        with pytest.raises(baseplateLayout.FillLayoutError, match='print bed is too small'):
            layout(30, 30, 4, 4)


class TestPieceOutline:
    def test_pieces_span_the_area_less_the_tolerance(self):
        result = layout(60.1, 40.1, 25.6, 25.6, fitTolerance=0.1)
        outlines = [baseplateLayout.pieceOutline(result, piece, BASE, BASE, CLEARANCE) for piece in result.pieces]
        minX = min(outline[0] for outline in outlines)
        maxX = max(outline[2] for outline in outlines)
        minY = min(outline[1] for outline in outlines)
        maxY = max(outline[3] for outline in outlines)
        assert (maxX - minX, maxY - minY) == (pytest.approx(60), pytest.approx(40))
        # a plate without padding starts at the origin, so the outer padding reaches past it
        assert (minX, minY) == (pytest.approx(-result.x.paddingStart), pytest.approx(-result.y.paddingStart))

    def test_seams_leave_twice_the_clearance(self):
        result = layout(60, 40, 25.6, 25.6)
        first = baseplateLayout.pieceOutline(result, result.pieces[0], BASE, BASE, CLEARANCE)
        second = baseplateLayout.pieceOutline(result, result.pieces[1], BASE, BASE, CLEARANCE)
        assert second[0] - first[2] == pytest.approx(CLEARANCE * 2)


class TestPieceShapeKey:
    def test_only_pieces_of_the_same_size_and_edges_match(self):
        # the two middle columns are the same, the edge ones are mirrored
        result = layout(58.75, 4.2, 17.5, 17.5)
        assert result.x.pieces == (3, 4, 4, 3)
        keys = [baseplateLayout.pieceShapeKey(piece) for piece in result.pieces]
        assert keys[1] == keys[2]
        assert len(set(keys)) == 3


class TestHalfCellsInLayout:
    def test_half_cells_go_on_the_edge_pieces_and_count_against_the_bed(self):
        # 10 cells and a row of half cells on the right, the last piece has room for only 4 cells next to them
        result = layout(10 * BASE - CLEARANCE * 2 + BASE / 2, 4.2, 5 * BASE, 5 * BASE, useHalfCells=True)
        assert result.x.hasHalfCellsEnd and not result.x.hasHalfCellsStart
        assert result.x.pieces == (3, 4, 3)

    def test_outline_includes_half_cells_and_padding(self):
        area = 10 * BASE - CLEARANCE * 2 + 3
        result = layout(area, 4.2, 25.6, 25.6, useHalfCells=True, alignmentX=baseplateLayout.ALIGN_START)
        (minX, _, maxX, _) = baseplateLayout.layoutOutline(result, BASE, BASE, CLEARANCE)
        assert (minX, maxX - minX) == (pytest.approx(0), pytest.approx(area))
