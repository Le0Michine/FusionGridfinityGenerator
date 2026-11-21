"""
Tests for packing the footprints of bodies on print beds.
"""

import os
import importlib.util
import itertools
import pytest


def _load_bed_packing():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "bedPacking.py")
    spec = importlib.util.spec_from_file_location("bedPacking", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bedPacking = _load_bed_packing()


def rectangles(sizes, placements):
    for (size, placement) in zip(sizes, placements):
        (width, length) = size[::-1] if placement.turned else size
        yield (placement.bed, placement.x, placement.y, placement.x + width, placement.y + length)


def assert_apart(sizes, placements, spacing):
    for (a, b) in itertools.combinations(list(rectangles(sizes, placements)), 2):
        if a[0] != b[0]:
            continue
        apart = a[3] + spacing <= b[1] + 1e-9 or b[3] + spacing <= a[1] + 1e-9 or a[4] + spacing <= b[2] + 1e-9 or b[4] + spacing <= a[2] + 1e-9
        assert apart, (a, b)


def assert_on_bed(sizes, placements, bed):
    for (_, minX, minY, maxX, maxY) in rectangles(sizes, placements):
        assert minX >= -1e-9 and minY >= -1e-9 and maxX <= bed[0] + 1e-9 and maxY <= bed[1] + 1e-9


def test_bins_fill_one_bed_when_they_fit():
    # nine bins of 83 mm with 3 mm between them, 255 mm a row on a 256 mm bed
    sizes = [(83, 83)] * 9
    placements = bedPacking.pack(sizes, (256, 256), 3)
    assert bedPacking.bedCount(placements) == 1
    assert_apart(sizes, placements, 3)
    assert_on_bed(sizes, placements, (256, 256))


def test_bins_go_on_to_another_bed_when_one_is_full():
    sizes = [(83, 83)] * 10
    placements = bedPacking.pack(sizes, (256, 256), 3)
    assert bedPacking.bedCount(placements) == 2
    assert sum(placement.bed == 0 for placement in placements) == 9


def test_spacing_can_take_another_bed():
    # three in a row take 252 mm without spacing, 262 mm with
    sizes = [(84, 84)] * 9
    assert bedPacking.bedCount(bedPacking.pack(sizes, (256, 256), 0)) == 1
    assert bedPacking.bedCount(bedPacking.pack(sizes, (256, 256), 5)) == 3


def test_a_long_bin_is_turned_to_fit():
    placements = bedPacking.pack([(250, 40)], (180, 256), 5)
    assert placements[0].turned
    assert placements[0].fits


def test_bins_are_turned_only_when_that_helps():
    placements = bedPacking.pack([(100, 40), (100, 40)], (256, 256), 5)
    assert not any(placement.turned for placement in placements)


def test_small_bins_fill_the_gaps_beside_big_ones():
    sizes = [(200, 200), (40, 40), (40, 40), (40, 40)]
    placements = bedPacking.pack(sizes, (256, 256), 5)
    assert bedPacking.bedCount(placements) == 1
    assert_apart(sizes, placements, 5)
    assert_on_bed(sizes, placements, (256, 256))


def test_many_mixed_bins_never_overlap():
    sizes = [(41.5 * (1 + index % 3), 41.5 * (1 + index % 4)) for index in range(40)]
    placements = bedPacking.pack(sizes, (256, 256), 4)
    assert_apart(sizes, placements, 4)
    assert_on_bed(sizes, placements, (256, 256))
    used = sum(width * length for (width, length) in sizes)
    # well packed, past the area alone at most one bed more
    assert bedPacking.bedCount(placements) <= used // (256 * 256) + 2


def test_a_bin_bigger_than_the_bed_gets_a_bed_of_its_own():
    sizes = [(40, 40), (300, 300), (40, 40)]
    placements = bedPacking.pack(sizes, (256, 256), 5)
    assert not placements[1].fits
    assert placements[0].bed == placements[2].bed != placements[1].bed
    assert bedPacking.bedCount(placements) == 2


def test_each_bed_is_centered():
    sizes = [(100, 50), (100, 50)]
    placements = bedPacking.centered(sizes, bedPacking.pack(sizes, (256, 256), 6), (256, 256))
    boxes = list(rectangles(sizes, placements))
    assert (min(box[1] for box in boxes) + max(box[3] for box in boxes)) / 2 == pytest.approx(128)
    assert (min(box[2] for box in boxes) + max(box[4] for box in boxes)) / 2 == pytest.approx(128)
    assert_apart(sizes, placements, 6)


def test_one_bigger_than_its_bed_is_centered_on_it():
    placements = bedPacking.centered([(300, 100)], bedPacking.pack([(300, 100)], (256, 256), 5), (256, 256))
    assert (placements[0].x, placements[0].y) == pytest.approx((-22, 78))


def test_nothing_to_pack():
    assert bedPacking.pack([], (256, 256), 5) == []
    assert bedPacking.bedCount([]) == 0


def test_the_margin_keeps_bins_off_the_bed_edges():
    # three 83 mm bins fill a 256 mm row, a 5 mm margin leaves room for two
    sizes = [(83, 83)] * 3
    placements = bedPacking.arrange(sizes, (256, 256), 1, 5)
    assert bedPacking.bedCount(placements) == 1
    boxes = list(rectangles(sizes, placements))
    assert min(box[1] for box in boxes) >= 5 and min(box[2] for box in boxes) >= 5
    assert max(box[3] for box in boxes) <= 251 and max(box[4] for box in boxes) <= 251
    assert_apart(sizes, placements, 1)


def test_a_bin_fitting_the_bed_but_not_its_margin_gets_a_plate_of_its_own():
    placements = bedPacking.arrange([(250, 100), (40, 40)], (256, 256), 1, 5)
    assert placements[0].turned is False and not placements[0].fits
    assert placements[1].fits and placements[1].bed != placements[0].bed


def test_without_a_margin_arranging_is_packing_centered():
    sizes = [(100, 50), (60, 70)]
    assert bedPacking.arrange(sizes, (256, 256), 2, 0) == bedPacking.centered(sizes, bedPacking.pack(sizes, (256, 256), 2), (256, 256))


def assert_clear_of(sizes, placements, area, spacing):
    for (_, minX, minY, maxX, maxY) in rectangles(sizes, placements):
        apart = maxX + spacing <= area[0] + 1e-9 or area[2] + spacing <= minX + 1e-9 \
            or maxY + spacing <= area[1] + 1e-9 or area[3] + spacing <= minY + 1e-9
        assert apart, ((minX, minY, maxX, maxY), area)


def assert_centered_per_bed(sizes, placements, bed):
    """As a slicer centers the bodies of a plate, the layout stays where it is"""
    for bedIndex in set(placement.bed for placement in placements):
        boxes = [box for box in rectangles(sizes, placements) if box[0] == bedIndex]
        assert min(box[1] for box in boxes) + max(box[3] for box in boxes) == pytest.approx(bed[0])
        assert min(box[2] for box in boxes) + max(box[4] for box in boxes) == pytest.approx(bed[1])


def test_bins_keep_the_spacing_from_an_area_kept_free():
    sizes = [(41.5, 41.5)] * 9
    area = (0.0, 120.0, 50.0, 180.0)
    placements = bedPacking.pack(sizes, (180.0, 180.0), 1.0, [area])
    assert_clear_of(sizes, placements, area, 1.0)
    assert all(placement.clear for placement in placements)


def test_a_purge_square_in_a_corner_stays_free_once_the_slicer_centers_the_plate():
    bed = (180.0, 180.0)
    square = (0.0, 130.0, 50.0, 180.0)
    sizes = [(41.5, 83.5)] * 40
    placements = bedPacking.arrange(sizes, bed, 1.0, 5.0, [square])
    assert all(placement.clear for placement in placements)
    assert_clear_of(sizes, placements, square, 1.0)
    assert_centered_per_bed(sizes, placements, bed)
    assert_apart(sizes, placements, 1.0)


def test_areas_kept_free_on_a_bigger_bed_with_the_wipe_corner_too():
    bed = (256.0, 256.0)
    square = (164.864, 206.0, 214.864, 256.0)
    wipe = (0.0, 0.0, 18.0, 28.0)
    sizes = [(41.5, 83.5)] * 13 + [(83.5, 125.5)] * 3 + [(20.5, 20.5)] * 7
    placements = bedPacking.arrange(sizes, bed, 1.0, 5.0, [square, wipe])
    assert all(placement.clear for placement in placements)
    for area in (square, wipe):
        assert_clear_of(sizes, placements, area, 1.0)
    assert_centered_per_bed(sizes, placements, bed)
    assert_apart(sizes, placements, 1.0)


def test_a_bin_that_only_fits_over_the_area_is_not_clear():
    bed = (180.0, 180.0)
    square = (0.0, 130.0, 50.0, 180.0)
    placements = bedPacking.arrange([(160.0, 160.0)], bed, 1.0, 5.0, [square])
    assert placements[0].fits
    assert not placements[0].clear


def test_without_areas_kept_free_everything_is_clear():
    placements = bedPacking.arrange([(41.5, 83.5)] * 10, (180.0, 180.0), 1.0, 5.0)
    assert all(placement.clear for placement in placements)
