"""
Tests for the 3MF writer: the slicers' paint codes, placing the objects on the plate and the file they end up in.
"""

import os
import importlib.util
import datetime
import json
import zipfile
import xml.etree.ElementTree as ElementTree
import pytest


def _load_three_mf():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "threeMf.py")
    spec = importlib.util.spec_from_file_location("threeMf", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


threeMf = _load_three_mf()
CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
SLIC3R = "{http://schemas.slic3r.org/3mf/2017/06}"


def cube(name, x=0.0, z=0.0, painted=()):
    vertices = [(x + dx, dy, z + dz) for dz in (0, 10) for dy in (0, 10) for dx in (0, 10)]
    triangles = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4), (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return threeMf.MeshObject(name, vertices, triangles, set(painted))


# ---------------------------------------------------------------------------
# paintCode
# ---------------------------------------------------------------------------

def test_paint_codes_match_what_the_slicers_saved():
    # Bambu Studio and OrcaSlicer saved filament 2 as 8, PrusaSlicer extruder 5 as 2C
    assert threeMf.paintCode(2) == "8"
    assert threeMf.paintCode(5) == "2C"


def test_paint_codes_of_the_first_filaments():
    assert [threeMf.paintCode(n) for n in range(1, 6)] == ["4", "8", "0C", "1C", "2C"]
    assert threeMf.paintCode(threeMf.MAX_FILAMENT) == "FC"


@pytest.mark.parametrize("filament", [0, threeMf.MAX_FILAMENT + 1])
def test_paint_code_refuses_filaments_it_cant_name(filament):
    with pytest.raises(ValueError):
        threeMf.paintCode(filament)


# ---------------------------------------------------------------------------
# placeOnPlate
# ---------------------------------------------------------------------------

def test_objects_keep_their_layout_around_the_plate_middle():
    placed = threeMf.placeOnPlate([cube("a", x=0), cube("b", x=20)])
    xs = [x for meshObject in placed for (x, _, _) in meshObject.vertices]
    ys = [y for meshObject in placed for (_, y, _) in meshObject.vertices]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(threeMf.DEFAULT_BED[0] / 2)
    assert (min(ys) + max(ys)) / 2 == pytest.approx(threeMf.DEFAULT_BED[1] / 2)
    assert min(x for (x, _, _) in placed[1].vertices) - min(x for (x, _, _) in placed[0].vertices) == pytest.approx(20)


def test_each_object_stands_on_the_plate():
    placed = threeMf.placeOnPlate([cube("low", z=-5), cube("high", x=20, z=30)])
    assert [min(z for (_, _, z) in meshObject.vertices) for meshObject in placed] == [0, 0]


def test_objects_go_around_the_middle_of_the_bed_given():
    placed = threeMf.placeOnPlate([cube("a")], (180, 200))
    assert threeMf.footprint(placed[0]) == (10, 10)
    assert min(x for (x, _, _) in placed[0].vertices) == pytest.approx(85)
    assert min(y for (_, y, _) in placed[0].vertices) == pytest.approx(95)


# ---------------------------------------------------------------------------
# placeOnBeds
# ---------------------------------------------------------------------------

def box(name, width, length, z=0.0):
    """A flat box with its corner at -5, -5"""
    vertices = [(-5 + dx, -5 + dy, z + dz) for dz in (0, 1) for dy in (0, length) for dx in (0, width)]
    return threeMf.MeshObject(name, vertices, [(0, 2, 1)])


def bounds(meshObject):
    xs = [x for (x, _, _) in meshObject.vertices]
    ys = [y for (_, y, _) in meshObject.vertices]
    return (min(xs), min(ys), max(xs), max(ys), min(z for (_, _, z) in meshObject.vertices))


def test_plates_fill_a_grid_of_about_as_many_columns_as_rows():
    assert [threeMf.plateColumns(count) for count in range(1, 11)] == [1, 2, 2, 2, 3, 3, 3, 3, 3, 4]


def test_plates_are_a_fifth_of_the_bed_apart_rows_going_down():
    # as Bambu Studio put the objects of three plates of a 256 mm bed
    assert threeMf.plateOrigin(0, 3, (256, 256)) == (0, 0)
    assert threeMf.plateOrigin(1, 3, (256, 256)) == pytest.approx((307.2, 0))
    assert threeMf.plateOrigin(2, 3, (256, 256)) == pytest.approx((0, -307.2))


def test_objects_go_to_their_placements_on_their_plates():
    placements = [_placement(0, 10, 20, False), _placement(1, 30, 40, False)]
    placed = threeMf.placeOnBeds([box("a", 50, 20, z=7), box("b", 50, 20)], placements, (200, 100))
    assert bounds(placed[0]) == pytest.approx((10, 20, 60, 40, 0))
    assert bounds(placed[1]) == pytest.approx((240 + 30, 40, 240 + 80, 60, 0))


def test_a_turned_object_is_a_quarter_turned_counterclockwise():
    original = box("a", 50, 20)
    corner = original.vertices[1]
    placed = threeMf.placeOnBeds([original], [_placement(0, 10, 20, True)], (200, 100))[0]
    assert bounds(placed) == pytest.approx((10, 20, 30, 70, 0))
    # the corner at +x, -y of the box ends at +x, +y
    assert placed.vertices[1][:2] == pytest.approx((30, 70))
    assert corner[:2] == (45, -5)


def _placement(bed, x, y, turned):
    import types
    return types.SimpleNamespace(bed=bed, x=x, y=y, turned=turned, fits=True)


def test_the_slicers_get_the_objects_of_each_plate(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("a"), cube('b & "c"'), cube("d")], None, plates=[0, 1, 0])
    with zipfile.ZipFile(path) as package:
        settings = ElementTree.fromstring(package.read(threeMf.MODEL_SETTINGS_PATH))
    names = {item.get("id"): item.find("metadata").get("value") for item in settings.findall("object")}
    assert names == {"1": "a", "2": 'b & "c"', "3": "d"}
    plates = [
        (plate.find("metadata[@key='plater_id']").get("value"), [instance.find("metadata[@key='object_id']").get("value") for instance in plate.findall("model_instance")])
        for plate in settings.findall("plate")
    ]
    assert plates == [("1", ["1", "3"]), ("2", ["2"])]


def test_no_plates_without_them(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("a")], None)
    with zipfile.ZipFile(path) as package:
        assert threeMf.MODEL_SETTINGS_PATH not in package.namelist()


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------

def read_model(path):
    with zipfile.ZipFile(path) as package:
        assert {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"} <= set(package.namelist())
        return ElementTree.fromstring(package.read("3D/3dmodel.model"))


def read_annotation(path):
    with zipfile.ZipFile(path) as package:
        if threeMf.FACETS_ANNOTATION_PATH not in package.namelist():
            return None
        return json.loads(package.read(threeMf.FACETS_ANNOTATION_PATH))


def test_painted_triangles_carry_both_slicers_codes(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("bin", painted={1, 4})], 2)
    triangles = read_model(path).findall(f".//{CORE}triangle")
    painted = [index for (index, triangle) in enumerate(triangles) if triangle.get("paint_color")]
    assert painted == [1, 4]
    assert all(triangles[index].get(f"{SLIC3R}mmu_segmentation") == "8" for index in painted)


def test_without_a_filament_nothing_is_painted(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("bin", painted={1})], None)
    model = read_model(path)
    assert not any(triangle.get("paint_color") for triangle in model.iter(f"{CORE}triangle"))
    assert not any(item.get("name") == "slic3rpe:MmPaintingVersion" for item in model.findall(f"{CORE}metadata"))


def test_every_object_is_built_with_its_name(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube('Bin "M3" & M4'), cube("Baseplate", x=20)], 2)
    model = read_model(path)
    assert [item.get("name") for item in model.findall(f".//{CORE}object")] == ['Bin "M3" & M4', "Baseplate"]
    assert [item.get("objectid") for item in model.findall(f".//{CORE}item")] == ["1", "2"]


def test_prusaslicer_3_gets_the_painted_triangles_of_each_object(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("a", painted={4, 1}), cube("b", x=20), cube("c", x=40, painted={0})], 5)
    assert read_annotation(path) == [
        {"mmSegmentationFacets": [{"triangle": 1, "dividing": "2C"}, {"triangle": 4, "dividing": "2C"}], "mmSegmentationFacetsVersion": 1, "id": 1},
        {"mmSegmentationFacets": [], "mmSegmentationFacetsVersion": 1, "id": 2},
        {"mmSegmentationFacets": [{"triangle": 0, "dividing": "2C"}], "mmSegmentationFacetsVersion": 1, "id": 3},
    ]


def test_no_annotation_without_painting(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("a", painted={1})], None)
    assert read_annotation(path) is None


def metadata(model):
    return {item.get("name"): item.text for item in model.findall(f"{CORE}metadata")}


def test_the_file_names_the_generator_its_version_the_title_and_day(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("bin")], 2, 'M3 & M4 "bins"', "1.4.2")
    found = metadata(read_model(path))
    assert found["Application"] == "Fusion Gridfinity Generator 1.4.2"
    assert found["Title"] == 'M3 & M4 "bins"'
    assert found["CreationDate"] == datetime.date.today().isoformat()


def test_without_a_version_or_title_the_generator_is_named_alone(tmp_path):
    path = tmp_path / "bins.3mf"
    threeMf.write(str(path), [cube("bin")], None)
    found = metadata(read_model(path))
    assert found["Application"] == "Fusion Gridfinity Generator"
    assert "Title" not in found
