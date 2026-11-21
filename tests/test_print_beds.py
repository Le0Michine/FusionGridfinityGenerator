"""
Tests for the print bed presets, where the purge tower goes and what each printer keeps free.
"""

import os
import importlib.util
import pytest


def _load_print_beds():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "printBeds.py")
    spec = importlib.util.spec_from_file_location("printBeds", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


printBeds = _load_print_beds()


def test_every_purge_anchor_and_excluded_area_is_of_a_listed_printer():
    assert set(printBeds.PURGE_ANCHORS) <= set(printBeds.PRINT_BED_SIZES)
    assert set(printBeds.EXCLUDED_AREAS) <= set(printBeds.PRINT_BED_SIZES)


def test_the_a1_keeps_the_purge_tower_back_left():
    label = printBeds.presetLabel('Bambu Lab A1')
    assert printBeds.purgeSquare((256.0, 256.0), 50.0, printBeds.purgeAnchor(label)) == (0.0, 206.0, 50.0, 256.0)


def test_the_x1_purge_tower_is_at_the_back_kept_on_the_bed():
    label = printBeds.presetLabel('Bambu Lab P1P, P1S, X1, X1C, X1E')
    (x0, y0, x1, y1) = printBeds.purgeSquare((256.0, 256.0), 50.0, printBeds.purgeAnchor(label))
    assert x0 == pytest.approx(0.644 * 256)
    assert (y0, x1 - x0, y1) == pytest.approx((206.0, 50.0, 256.0))


def test_the_x1_keeps_its_wiping_corner_free():
    assert printBeds.excludedAreas(printBeds.presetLabel('Bambu Lab P1P, P1S, X1, X1C, X1E')) == [(0, 0, 18, 28)]
    assert printBeds.excludedAreas(printBeds.presetLabel('Bambu Lab A1')) == []


def test_other_printers_and_custom_beds_get_it_back_right():
    for label in (printBeds.presetLabel('Prusa MK3, MK4'), printBeds.PRINT_BED_CUSTOM, 'a label gone from the list'):
        assert printBeds.purgeSquare((250.0, 210.0), 50.0, printBeds.purgeAnchor(label)) == (200.0, 160.0, 250.0, 210.0)
        assert printBeds.excludedAreas(label) == []


def test_no_purge_square_of_size_zero_and_never_bigger_than_the_bed():
    assert printBeds.purgeSquare((180.0, 180.0), 0.0, (0.0, 1.0)) is None
    assert printBeds.purgeSquare((100.0, 60.0), 80.0, (1.0, 1.0)) == (40.0, 0.0, 100.0, 60.0)


def test_a_printer_is_found_by_its_name_or_its_label():
    label = printBeds.presetLabel('Bambu Lab A1 mini')
    assert printBeds.presetLabelOf('Bambu Lab A1 mini') == label
    assert printBeds.presetLabelOf(label) == label
    assert printBeds.presetLabelOf(printBeds.PRINT_BED_CUSTOM) is None
    assert printBeds.presetLabelOf('Bambu Lab A1, P1, X1 (256 x 256 mm)') is None
