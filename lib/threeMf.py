import dataclasses
import datetime
import json
import zipfile
from xml.sax.saxutils import escape, quoteattr

# 3MF files of meshes, the triangles of label letters painted with a filament the slicer picks up. Kept free of
# Fusion imports so it can be unit tested.
# The slicers keep their filament painting on the triangles, as their paint tool saves it: Bambu Studio and
# OrcaSlicer in paint_color, PrusaSlicer in slic3rpe:mmu_segmentation, both coded the same, see paintCode. They read
# it from a plain 3MF made elsewhere too. PrusaSlicer 3 still writes slic3rpe:mmu_segmentation but reads the painting
# only from a file of its own listing the painted triangles of each object, see facetsAnnotation

# where the objects are put, the middle of a 256 mm bed, the slicer arranges them on a bed of another size
PLATE_CENTER = (128.0, 128.0)
# the slicers tell their own projects by it, PrusaSlicer 3 refuses a file naming it that has no printer settings
APPLICATION = 'Fusion Gridfinity Generator'
# the most filaments a painted triangle can name, see paintCode
MAX_FILAMENT = 18

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="json" ContentType="application/json"/>
</Types>'''
# where PrusaSlicer 3 keeps the painting
FACETS_ANNOTATION_PATH = 'Metadata/Slic3r_facets_annotation.json'
RELATIONSHIPS = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>'''

@dataclasses.dataclass
class MeshObject:
    name: str
    # mm
    vertices: list[tuple[float, float, float]]
    # vertex indices, counterclockwise seen from outside
    triangles: list[tuple[int, int, int]]
    # indices of the triangles painted with the filament
    painted: set[int] = dataclasses.field(default_factory=set)

def paintCode(filament: int) -> str:
    """
    A whole triangle painted with the filament, numbered from 1, as the slicers' triangle selector writes it: hex
    digits in reverse order of the bits, two for how many sides the triangle is split on, none here, then two for
    the filament, or 3 and four more for the filament past 2
    """
    if filament < 1 or filament > MAX_FILAMENT:
        raise ValueError(f'filament {filament} is outside 1 to {MAX_FILAMENT}')
    return f'{filament << 2:X}' if filament < 3 else f'{filament - 3:X}C'

def placeOnPlate(objects: list[MeshObject]) -> list[MeshObject]:
    """Each standing on the plate, all as they were in the design side to side, around the middle of the plate"""
    vertices = [vertex for meshObject in objects for vertex in meshObject.vertices]
    if len(vertices) == 0:
        return objects
    shiftX = PLATE_CENTER[0] - (min(x for (x, _, _) in vertices) + max(x for (x, _, _) in vertices)) / 2
    shiftY = PLATE_CENTER[1] - (min(y for (_, y, _) in vertices) + max(y for (_, y, _) in vertices)) / 2
    placed = []
    for meshObject in objects:
        bottom = min((z for (_, _, z) in meshObject.vertices), default=0)
        vertices = [(x + shiftX, y + shiftY, z - bottom) for (x, y, z) in meshObject.vertices]
        placed.append(dataclasses.replace(meshObject, vertices=vertices))
    return placed

def _number(value: float) -> str:
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return '0' if text == '-0' else text

def modelXml(objects: list[MeshObject], filament: int | None, title: str = '', version: str = '', date: datetime.date | None = None) -> str:
    """
    The model part of the file, the painted triangles get the filament unless it's none. Named after the generator in
    the version, with the title and the day it was made, as the slicers show of a project
    """
    code = paintCode(filament) if filament is not None else None
    application = f'{APPLICATION} {version}' if version else APPLICATION
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">',
        f' <metadata name="Application">{escape(application)}</metadata>',
        f' <metadata name="CreationDate">{(date or datetime.date.today()).isoformat()}</metadata>',
    ]
    if title:
        lines.append(f' <metadata name="Title">{escape(title)}</metadata>')
    if code is not None:
        lines.append(' <metadata name="slic3rpe:MmPaintingVersion">1</metadata>')
    lines.append(' <resources>')
    for (index, meshObject) in enumerate(objects):
        lines += [f'  <object id="{index + 1}" type="model" name={quoteattr(meshObject.name)}>', '   <mesh>', '    <vertices>']
        lines += [f'     <vertex x="{_number(x)}" y="{_number(y)}" z="{_number(z)}"/>' for (x, y, z) in meshObject.vertices]
        lines += ['    </vertices>', '    <triangles>']
        for (triangleIndex, (a, b, c)) in enumerate(meshObject.triangles):
            paint = f' paint_color="{code}" slic3rpe:mmu_segmentation="{code}"' if code is not None and triangleIndex in meshObject.painted else ''
            lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"{paint}/>')
        lines += ['    </triangles>', '   </mesh>', '  </object>']
    lines += [' </resources>', ' <build>']
    lines += [f'  <item objectid="{index + 1}"/>' for index in range(len(objects))]
    lines += [' </build>', '</model>']
    return '\n'.join(lines)

def facetsAnnotation(objects: list[MeshObject], filament: int) -> str:
    """PrusaSlicer 3's list of the painted triangles of each object, by the object's id in the model, see modelXml"""
    code = paintCode(filament)
    return json.dumps([
        {
            'mmSegmentationFacets': [{'triangle': triangle, 'dividing': code} for triangle in sorted(meshObject.painted)],
            'mmSegmentationFacetsVersion': 1,
            'id': index + 1,
        }
        for (index, meshObject) in enumerate(objects)
    ])

def write(path: str, objects: list[MeshObject], filament: int | None, title: str = '', version: str = ''):
    """The objects in one file placed on the plate, see placeOnPlate, painted with the filament unless it's none, see modelXml"""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as package:
        package.writestr('[Content_Types].xml', CONTENT_TYPES)
        package.writestr('_rels/.rels', RELATIONSHIPS)
        package.writestr('3D/3dmodel.model', modelXml(placeOnPlate(objects), filament, title, version))
        if filament is not None:
            package.writestr(FACETS_ANNOTATION_PATH, facetsAnnotation(objects, filament))
