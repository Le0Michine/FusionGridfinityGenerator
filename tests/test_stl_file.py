"""
Tests for the STL writer: moving a body to the origin and the binary file it ends up in.
"""

import os
import importlib.util
import struct
import pytest


def _load_stl_file():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "stlFile.py")
    spec = importlib.util.spec_from_file_location("stlFile", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stlFile = _load_stl_file()


def cube(x=0.0, y=0.0, z=0.0):
    vertices = [(x + dx, y + dy, z + dz) for dz in (0, 10) for dy in (0, 10) for dx in (0, 10)]
    triangles = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4), (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return (vertices, triangles)


def read(path):
    with open(path, "rb") as file:
        data = file.read()
    (count,) = struct.unpack_from("<I", data, 80)
    facets = [struct.unpack_from("<12fH", data, 84 + 50 * index) for index in range(count)]
    return (data[:80], count, facets, len(data))


# ---------------------------------------------------------------------------
# atOrigin
# ---------------------------------------------------------------------------

def test_a_body_away_from_the_origin_is_centered_on_it_standing_at_zero():
    (vertices, _) = cube(x=200, y=-50, z=13)
    moved = stlFile.atOrigin(vertices)
    assert min(x for (x, _, _) in moved) == pytest.approx(-5)
    assert max(x for (x, _, _) in moved) == pytest.approx(5)
    assert min(y for (_, y, _) in moved) == pytest.approx(-5)
    assert max(y for (_, y, _) in moved) == pytest.approx(5)
    assert min(z for (_, _, z) in moved) == pytest.approx(0)
    assert max(z for (_, _, z) in moved) == pytest.approx(10)


def test_no_vertices_stay_none():
    assert stlFile.atOrigin([]) == []


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------

def test_file_has_every_triangle_with_its_corners(tmp_path):
    (vertices, triangles) = cube()
    path = tmp_path / "cube.stl"
    stlFile.write(str(path), "Bin 2x1", vertices, triangles)
    (header, count, facets, size) = read(path)
    assert header.rstrip() == b"Bin 2x1"
    assert count == 12
    assert size == 84 + 50 * 12
    (a, b, c) = triangles[0]
    assert facets[0][3:12] == pytest.approx((*vertices[a], *vertices[b], *vertices[c]))


def test_normals_point_out_of_the_body(tmp_path):
    (vertices, triangles) = cube()
    path = tmp_path / "cube.stl"
    stlFile.write(str(path), "cube", vertices, triangles)
    (_, _, facets, _) = read(path)
    # the bottom faces down, the top up
    assert facets[0][0:3] == pytest.approx((0, 0, -1))
    assert facets[2][0:3] == pytest.approx((0, 0, 1))


def test_a_name_starting_with_solid_doesnt_look_like_a_text_stl(tmp_path):
    (vertices, triangles) = cube()
    path = tmp_path / "cube.stl"
    stlFile.write(str(path), "Solid bin", vertices, triangles)
    (header, _, _, _) = read(path)
    assert not header.lower().startswith(b"solid")


def test_a_long_name_is_cut_to_the_header(tmp_path):
    (vertices, triangles) = cube()
    path = tmp_path / "cube.stl"
    stlFile.write(str(path), "x" * 200, vertices, triangles)
    (_, count, _, size) = read(path)
    assert count == 12
    assert size == 84 + 50 * 12
