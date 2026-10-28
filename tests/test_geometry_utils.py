"""
Tests for geometry predicate utilities: isBoundingBoxFlat, isXNormal,
isYNormal, isZNormal, isHorizontal, isCollinearTo*, and getNormalFaceExtremes.
"""

import sys
import os
import math
import importlib
import types
import pytest


# ---------------------------------------------------------------------------
# Minimal stubs — no adsk dependency needed for these pure geometry functions
# ---------------------------------------------------------------------------

class Point3D:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    @classmethod
    def create(cls, x, y, z):
        return cls(x, y, z)

    def distanceTo(self, other):
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)


class BoundingBox3D:
    def __init__(self, min_pt: Point3D, max_pt: Point3D):
        self.minPoint = min_pt
        self.maxPoint = max_pt


def box(x0, y0, z0, x1, y1, z1) -> BoundingBox3D:
    """Convenience: build a BoundingBox3D from two corners."""
    return BoundingBox3D(Point3D(x0, y0, z0), Point3D(x1, y1, z1))


class FakeEdge:
    def __init__(self, bounding_box: BoundingBox3D):
        self.boundingBox = bounding_box


class FakeFace:
    def __init__(self, bounding_box: BoundingBox3D):
        self.boundingBox = bounding_box


# ---------------------------------------------------------------------------
# Module loader helpers — load geometryUtils and faceUtils without Fusion
# ---------------------------------------------------------------------------

def _load_geometry_utils():
    """Load geometryUtils with adsk stub injected."""
    # Build a minimal adsk stub just enough for the import line to succeed.
    # Use direct assignment (not setdefault) so Point3D is always present,
    # even if conftest already registered a bare adsk.core without it.
    adsk = sys.modules.get("adsk") or types.ModuleType("adsk")
    core = sys.modules.get("adsk.core") or types.ModuleType("adsk.core")
    core.Point3D = Point3D
    adsk.core = core
    adsk.fusion = sys.modules.get("adsk.fusion") or types.ModuleType("adsk.fusion")
    sys.modules["adsk"] = adsk
    sys.modules["adsk.core"] = core
    sys.modules["adsk.fusion"] = adsk.fusion

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "geometryUtils.py")

    # Stub const module
    const = types.ModuleType("lib.gridfinityUtils.const")
    const.DEFAULT_FILTER_TOLERANCE = 0.00001
    sys.modules["lib.gridfinityUtils.const"] = const

    spec = importlib.util.spec_from_file_location("geometryUtils", path)
    mod = importlib.util.module_from_spec(spec)
    # Inject const as a relative sibling
    mod.__package__ = "lib.gridfinityUtils"
    sys.modules["geometryUtils"] = mod

    # Patch the relative import by pre-populating before exec
    pkg = types.ModuleType("lib.gridfinityUtils")
    pkg.__path__ = []
    pkg.const = const
    sys.modules.setdefault("lib.gridfinityUtils", pkg)

    spec.loader.exec_module(mod)
    return mod


def _load_face_utils(geometry_utils_mod):
    """Load faceUtils with adsk stub and geometryUtils already loaded."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "lib", "gridfinityUtils", "faceUtils.py")

    # Register geometryUtils under the name faceUtils will import it as
    sys.modules["lib.gridfinityUtils.geometryUtils"] = geometry_utils_mod
    pkg = sys.modules["lib.gridfinityUtils"]
    pkg.geometryUtils = geometry_utils_mod

    const = sys.modules["lib.gridfinityUtils.const"]
    pkg.const = const

    spec = importlib.util.spec_from_file_location("faceUtils", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "lib.gridfinityUtils"
    sys.modules["faceUtils"] = mod
    sys.modules["lib.gridfinityUtils.faceUtils"] = mod
    spec.loader.exec_module(mod)
    # Patch Point3D onto the adsk.core reference faceUtils captured at load
    # time so closestToOrigin can call adsk.core.Point3D.create().
    mod.adsk.core.Point3D = Point3D
    return mod


# Load once for the whole module
_geom = _load_geometry_utils()
_face = _load_face_utils(_geom)


# ---------------------------------------------------------------------------
# isBoundingBoxFlat
# ---------------------------------------------------------------------------

class TestIsBoundingBoxFlat:
    def test_flat_on_z(self):
        assert _geom.isBoundingBoxFlat(box(0, 0, 5, 3, 4, 5), 'z') is True

    def test_not_flat_on_z(self):
        assert _geom.isBoundingBoxFlat(box(0, 0, 0, 3, 4, 5), 'z') is False

    def test_flat_on_x(self):
        assert _geom.isBoundingBoxFlat(box(2, 0, 0, 2, 4, 5), 'x') is True

    def test_flat_on_y(self):
        assert _geom.isBoundingBoxFlat(box(0, 3, 0, 4, 3, 5), 'y') is True

    def test_flat_on_two_axes(self):
        # box is flat on both x and y → collinear to Z
        assert _geom.isBoundingBoxFlat(box(1, 2, 0, 1, 2, 5), 'xy') is True

    def test_not_flat_on_two_axes_one_differs(self):
        # flat on x but not y
        assert _geom.isBoundingBoxFlat(box(1, 0, 0, 1, 2, 5), 'xy') is False

    def test_within_tolerance(self):
        epsilon = _geom.DEFAULT_FILTER_TOLERANCE / 2
        assert _geom.isBoundingBoxFlat(box(0, 0, 5, 3, 4, 5 + epsilon), 'z') is True

    def test_just_outside_tolerance(self):
        epsilon = _geom.DEFAULT_FILTER_TOLERANCE * 2
        assert _geom.isBoundingBoxFlat(box(0, 0, 5, 3, 4, 5 + epsilon), 'z') is False


# ---------------------------------------------------------------------------
# Edge predicates (isHorizontal, isCollinearTo*)
# ---------------------------------------------------------------------------

class TestEdgePredicates:
    def test_is_horizontal_flat_z(self):
        edge = FakeEdge(box(0, 0, 3, 5, 2, 3))
        assert _geom.isHorizontal(edge) is True

    def test_is_horizontal_not_flat_z(self):
        edge = FakeEdge(box(0, 0, 0, 5, 2, 3))
        assert _geom.isHorizontal(edge) is False

    def test_is_collinear_to_z(self):
        # flat on x AND y → vertical edge along Z
        edge = FakeEdge(box(1, 2, 0, 1, 2, 5))
        assert _geom.isCollinearToZ(edge) is True

    def test_is_collinear_to_z_not_flat_x(self):
        edge = FakeEdge(box(0, 2, 0, 1, 2, 5))
        assert _geom.isCollinearToZ(edge) is False

    def test_is_collinear_to_x(self):
        # flat on z AND y → edge along X
        edge = FakeEdge(box(0, 2, 3, 5, 2, 3))
        assert _geom.isCollinearToX(edge) is True

    def test_is_collinear_to_x_not_flat_y(self):
        edge = FakeEdge(box(0, 0, 3, 5, 2, 3))
        assert _geom.isCollinearToX(edge) is False

    def test_is_collinear_to_y(self):
        # flat on z AND x → edge along Y
        edge = FakeEdge(box(1, 0, 3, 1, 5, 3))
        assert _geom.isCollinearToY(edge) is True

    def test_is_collinear_to_y_not_flat_x(self):
        edge = FakeEdge(box(0, 0, 3, 1, 5, 3))
        assert _geom.isCollinearToY(edge) is False


# ---------------------------------------------------------------------------
# Face normal predicates (isXNormal, isYNormal, isZNormal)
# ---------------------------------------------------------------------------

class TestFaceNormalPredicates:
    def test_is_z_normal(self):
        face = FakeFace(box(0, 0, 5, 3, 4, 5))
        assert _face.isZNormal(face) is True

    def test_is_not_z_normal(self):
        face = FakeFace(box(0, 0, 0, 3, 4, 5))
        assert _face.isZNormal(face) is False

    def test_is_x_normal(self):
        face = FakeFace(box(2, 0, 0, 2, 4, 5))
        assert _face.isXNormal(face) is True

    def test_is_y_normal(self):
        face = FakeFace(box(0, 3, 0, 4, 3, 5))
        assert _face.isYNormal(face) is True


# ---------------------------------------------------------------------------
# getNormalFaceExtremes
# ---------------------------------------------------------------------------

class TestGetNormalFaceExtremes:
    def _z_faces(self, *z_values):
        """Create Z-normal faces at given Z positions."""
        return [FakeFace(box(0, 0, z, 5, 5, z)) for z in z_values]

    def test_returns_min_and_max_z(self):
        faces = self._z_faces(0.0, 2.0, 5.0)
        lo, hi = _face.getNormalFaceExtremes(faces, 'z')
        assert lo.boundingBox.minPoint.z == 0.0
        assert hi.boundingBox.minPoint.z == 5.0

    def test_two_faces(self):
        faces = self._z_faces(1.0, 4.0)
        lo, hi = _face.getNormalFaceExtremes(faces, 'z')
        assert lo.boundingBox.minPoint.z == 1.0
        assert hi.boundingBox.minPoint.z == 4.0

    def test_single_face_returns_same_for_both(self):
        faces = self._z_faces(3.0)
        lo, hi = _face.getNormalFaceExtremes(faces, 'z')
        assert lo is hi

    def test_skips_non_normal_faces(self):
        # Mix Z-normal and non-Z-normal faces; only Z-normal should be considered
        normal = self._z_faces(1.0, 7.0)
        non_normal = [FakeFace(box(0, 0, 0, 3, 4, 5))]  # has depth on z → not flat
        lo, hi = _face.getNormalFaceExtremes(normal + non_normal, 'z')
        assert lo.boundingBox.minPoint.z == 1.0
        assert hi.boundingBox.minPoint.z == 7.0

    def test_y_axis(self):
        faces = [FakeFace(box(0, y, 0, 5, y, 5)) for y in (0.5, 2.5, 1.0)]
        lo, hi = _face.getNormalFaceExtremes(faces, 'y')
        assert lo.boundingBox.minPoint.y == 0.5
        assert hi.boundingBox.minPoint.y == 2.5

    def test_empty_raises(self):
        with pytest.raises((ValueError, IndexError)):
            _face.getNormalFaceExtremes([], 'z')


# ---------------------------------------------------------------------------
# Bounding box access counts
#
# These verify that each function fetches .boundingBox the minimum number of
# times — once per entity — rather than the redundant multiple fetches that
# existed before the isBoundingBoxFlat / getNormalFaceExtremes refactor.
# ---------------------------------------------------------------------------

class CountingBox:
    """Wraps a BoundingBox3D and counts how many times it is accessed."""
    def __init__(self, bounding_box: BoundingBox3D):
        self._box = bounding_box
        self.access_count = 0

    @property
    def minPoint(self):
        return self._box.minPoint

    @property
    def maxPoint(self):
        return self._box.maxPoint


class CountingFaceOrEdge:
    """
    Wraps a bounding box behind a .boundingBox property and counts accesses,
    simulating the cost of a native geometry query.
    """
    def __init__(self, bounding_box: BoundingBox3D):
        self._counting_box = CountingBox(bounding_box)
        self._access_count = 0

    @property
    def boundingBox(self) -> CountingBox:
        self._access_count += 1
        return self._counting_box

    @property
    def access_count(self) -> int:
        return self._access_count


class TestBoundingBoxAccessCounts:
    """Each entity's .boundingBox should be fetched exactly once per call."""

    # --- edge predicates ---

    def test_is_horizontal_fetches_box_once(self):
        e = CountingFaceOrEdge(box(0, 0, 3, 5, 2, 3))
        _geom.isHorizontal(e)
        assert e.access_count == 1

    def test_is_collinear_to_z_fetches_box_once(self):
        e = CountingFaceOrEdge(box(1, 2, 0, 1, 2, 5))
        _geom.isCollinearToZ(e)
        assert e.access_count == 1

    def test_is_collinear_to_x_fetches_box_once(self):
        e = CountingFaceOrEdge(box(0, 2, 3, 5, 2, 3))
        _geom.isCollinearToX(e)
        assert e.access_count == 1

    def test_is_collinear_to_y_fetches_box_once(self):
        e = CountingFaceOrEdge(box(1, 0, 3, 1, 5, 3))
        _geom.isCollinearToY(e)
        assert e.access_count == 1

    # --- face normal predicates ---

    def test_is_z_normal_fetches_box_once(self):
        f = CountingFaceOrEdge(box(0, 0, 5, 3, 4, 5))
        _face.isZNormal(f)
        assert f.access_count == 1

    def test_is_x_normal_fetches_box_once(self):
        f = CountingFaceOrEdge(box(2, 0, 0, 2, 4, 5))
        _face.isXNormal(f)
        assert f.access_count == 1

    def test_is_y_normal_fetches_box_once(self):
        f = CountingFaceOrEdge(box(0, 3, 0, 4, 3, 5))
        _face.isYNormal(f)
        assert f.access_count == 1

    # --- getNormalFaceExtremes ---

    def test_get_normal_face_extremes_fetches_each_box_once(self):
        faces = [CountingFaceOrEdge(box(0, 0, z, 5, 5, z)) for z in (1.0, 3.0, 5.0)]
        _face.getNormalFaceExtremes(faces, 'z')
        for f in faces:
            assert f.access_count == 1, (
                f"Expected 1 boundingBox access per face, got {f.access_count}"
            )

    def test_get_normal_face_extremes_mixed_fetches_each_box_once(self):
        # Include a non-normal face to ensure it is still only accessed once
        normal = [CountingFaceOrEdge(box(0, 0, z, 5, 5, z)) for z in (0.0, 4.0)]
        non_normal = [CountingFaceOrEdge(box(0, 0, 0, 3, 4, 5))]
        _face.getNormalFaceExtremes(normal + non_normal, 'z')
        for f in normal + non_normal:
            assert f.access_count == 1

    # --- closestToOrigin ---

    def test_closest_to_origin_fetches_each_box_once(self):
        faces = [CountingFaceOrEdge(box(i, i, i, i+1, i+1, i+1)) for i in range(4)]
        _face.closestToOrigin(faces)
        for f in faces:
            assert f.access_count == 1, (
                f"Expected 1 boundingBox access per face, got {f.access_count}"
            )
