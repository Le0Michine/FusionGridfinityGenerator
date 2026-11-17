"""
Tests for telling the letter faces of an outline label from the tab face and the holes of letters by their nesting.
"""

import os
import sys
import importlib.util


def _load_label_faces():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "labelFaces.py")
    spec = importlib.util.spec_from_file_location("labelFaces", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


labelFaces = _load_label_faces()


def square(minX, minY, maxX, maxY):
    corners = [(minX, minY), (maxX, minY), (maxX, maxY), (minX, maxY)]
    return list(zip(corners, corners[1:] + corners[:1]))


def test_point_inside_a_square():
    outline = square(0, 0, 10, 10)
    assert labelFaces.isInside((5, 5), outline)
    assert not labelFaces.isInside((15, 5), outline)
    assert not labelFaces.isInside((5, -1), outline)


def test_segment_order_doesnt_matter():
    outline = square(0, 0, 10, 10)
    assert labelFaces.isInside((5, 5), list(reversed(outline)))


def test_letters_are_nested_once_and_their_holes_twice():
    # the tab, an l, an o and the hole of the o, then a dot inside that hole as in a ring with a dot
    outlines = [square(0, 0, 100, 20), square(10, 5, 12, 15), square(20, 5, 30, 15), square(23, 8, 27, 12), square(24, 9, 26, 11)]
    points = [(1, 1), (11, 10), (21, 6), (23.5, 8.5), (25, 10)]
    assert labelFaces.letterFlags(points, outlines) == [False, True, True, False, True]


def test_faces_side_by_side_arent_letters():
    # compartment floors in one plane
    outlines = [square(0, 0, 10, 10), square(12, 0, 22, 10)]
    assert labelFaces.letterFlags([(5, 5), (17, 5)], outlines) == [False, False]


def test_a_hole_level_with_where_two_edges_of_its_letter_meet():
    # an o as a diamond, its two right edges ending at its widest point a rounding apart, the hole's point level with it
    meet = 74.825
    letter = [((30, 70), (40, meet + 1e-12)), ((40, meet - 1e-12), (30, 80)), ((30, 80), (20, meet)), ((20, meet), (30, 70))]
    hole = square(28, 73, 32, 77)
    tab = square(0, 60, 100, 90)
    flags = labelFaces.letterFlags([(5, 65), (25, meet), (30, meet)], [tab, letter, hole])
    assert flags == [False, True, False]
