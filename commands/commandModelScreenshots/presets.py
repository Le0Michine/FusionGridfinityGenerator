import dataclasses
import json
import os
import re

# Model screenshot presets, one JSON file each: a bin or baseplate built from settings as in the shape test cases,
# see commandSnapshotTests/testCases.py, and how the picture of it is taken. A preset can extend another one, named
# by its file, and only list the settings and options that differ. Files starting with an underscore are only there
# to be extended, they are not rendered. Kept free of Fusion imports so it can be unit tested

# standard views of Fusion's ViewOrientations, by the start of their names
VIEWS = ['isoTopRight', 'isoTopLeft', 'isoBottomRight', 'isoBottomLeft', 'front', 'back', 'top', 'bottom', 'left', 'right']
# Fusion's VisualStyles
STYLES = {
    'shaded': 'ShadedVisualStyle',
    'shadedWithEdges': 'ShadedWithVisibleEdgesOnlyVisualStyle',
    'shadedWithHiddenEdges': 'ShadedWithHiddenEdgesVisualStyle',
    'wireframe': 'WireframeVisualStyle',
}
CAMERAS = ['perspective', 'orthographic']
DEFAULT_OUTPUT = os.path.join('documentation', 'assets', 'models')

# options of the picture, what a preset doesn't set
DEFAULT_OPTIONS = {
    'view': 'isoTopRight',
    'camera': 'perspective',
    'style': 'shadedWithEdges',
    'width': 2048,
    'height': 2048,
    'transparent': True,
    # space around the model, a share of the picture's width and height
    'margin': 0.06,
    # the render is this many times the picture's size and scaled down, which smooths the edges
    'supersample': 3,
    # stops a picture of the viewport is brightened by, as a camera's exposure, and how much its colors are deepened,
    # 1 keeps them. Fusion's viewport has no setting for either, these bring it close to a ray traced picture of Fusion's
    'exposure': 0.85,
    'saturation': 1.4,
    # a name from Fusion's appearance library, none is a matte plastic when there's a color, Fusion's default look when not
    'appearance': None,
    # the appearance in this color, '#rrggbb', the blue of the dialogs' drawings by default, none keeps its own
    'color': '#4e79a7',
    'output': DEFAULT_OUTPUT,
}
# not passed on to presets extending this one
OWN_KEYS = ['description']

class PresetError(Exception):
    pass

@dataclasses.dataclass
class Preset:
    # the file name without its extension, the picture is saved by it
    name: str
    description: str
    generator: str
    # as in a test case, lengths in mm and angles in degrees
    settings: dict
    # a name of VIEWS, or a dict with an eye and a target point and an optional up vector, in mm
    view: str | dict
    camera: str
    style: str
    width: int
    height: int
    transparent: bool
    margin: float
    supersample: int
    exposure: float
    saturation: float
    appearance: str | None
    color: str | None
    # folder of the picture, from the add-in folder
    output: str

def readPresetData(folder: str, fileName: str, extending: tuple[str, ...] = ()) -> dict:
    """The preset's data with what it extends filled in, settings merged one by one"""
    if fileName in extending:
        raise PresetError(f'presets extend each other in a loop: {" > ".join(extending + (fileName,))}')
    try:
        with open(os.path.join(folder, fileName), encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, ValueError) as err:
        raise PresetError(f'{fileName}: {err}') from err
    if not isinstance(data, dict):
        raise PresetError(f'{fileName}: a preset is a JSON object')
    baseName = data.pop('extends', None)
    if baseName is None:
        return data
    base = readPresetData(folder, baseName, extending + (fileName,))
    for key in OWN_KEYS:
        base.pop(key, None)
    return {**base, **data, 'settings': {**base.get('settings', {}), **data.get('settings', {})}}

def checkView(view) -> str | dict:
    if isinstance(view, str):
        if view not in VIEWS:
            raise PresetError(f'unknown view {view!r}, one of {", ".join(VIEWS)}')
        return view
    def point(key: str, required: bool):
        value = view.get(key)
        if value is None and not required:
            return None
        if not (isinstance(value, list) and len(value) == 3 and all(isinstance(number, (int, float)) for number in value)):
            raise PresetError(f'view {key} is a list of 3 numbers, in mm')
        return value
    if not isinstance(view, dict):
        raise PresetError('a view is a name or an object with an eye and a target')
    unknown = [key for key in view if key not in ['eye', 'target', 'up']]
    if unknown:
        raise PresetError(f'unknown view keys {unknown}')
    point('eye', True)
    point('target', True)
    point('up', False)
    return view

def loadPreset(folder: str, fileName: str) -> Preset:
    name = os.path.splitext(fileName)[0]
    try:
        data = {**DEFAULT_OPTIONS, **readPresetData(folder, fileName)}
        known = ['description', 'generator', 'settings', *DEFAULT_OPTIONS]
        unknown = [key for key in data if key not in known]
        if unknown:
            raise PresetError(f'unknown keys {unknown}')
        if 'generator' not in data or not isinstance(data.get('settings'), dict):
            raise PresetError('a preset needs a generator and settings, its own or from the one it extends')
        if data['camera'] not in CAMERAS:
            raise PresetError(f'unknown camera {data["camera"]!r}, one of {", ".join(CAMERAS)}')
        if data['style'] not in STYLES:
            raise PresetError(f'unknown style {data["style"]!r}, one of {", ".join(STYLES)}')
        for key in ['width', 'height']:
            if not isinstance(data[key], int) or data[key] <= 0:
                raise PresetError(f'{key} is a number of pixels')
        if not isinstance(data['margin'], (int, float)) or not 0 <= data['margin'] < 0.5:
            raise PresetError('margin is a share of the picture from 0 to 0.5')
        if not isinstance(data['supersample'], int) or not 1 <= data['supersample'] <= 8:
            raise PresetError('supersample is a whole number from 1 to 8')
        if not isinstance(data['exposure'], (int, float)) or isinstance(data['exposure'], bool) or not -3 <= data['exposure'] <= 3:
            raise PresetError('exposure is a number of stops from -3 to 3')
        if not isinstance(data['saturation'], (int, float)) or isinstance(data['saturation'], bool) or not 0 <= data['saturation'] <= 3:
            raise PresetError('saturation is a number from 0, grey, to 3')
        if data['color'] is not None and not (isinstance(data['color'], str) and re.fullmatch(r'#[0-9a-fA-F]{6}', data['color'])):
            raise PresetError('color is #rrggbb, or null for the appearance\'s own')
        return Preset(
            name=name,
            description=data.get('description', ''),
            generator=data['generator'],
            settings=data['settings'],
            view=checkView(data['view']),
            camera=data['camera'],
            style=data['style'],
            width=data['width'],
            height=data['height'],
            transparent=bool(data['transparent']),
            margin=float(data['margin']),
            supersample=data['supersample'],
            exposure=float(data['exposure']),
            saturation=float(data['saturation']),
            appearance=data['appearance'],
            color=data['color'],
            output=data['output'],
        )
    except PresetError as err:
        raise PresetError(f'preset {name}: {err}') from err

def loadPresets(folder: str, only: list[str] | None = None) -> list[Preset]:
    """Presets of the folder by name, but the ones only there to be extended"""
    fileNames = sorted(fileName for fileName in os.listdir(folder) if fileName.endswith('.json') and not fileName.startswith('_'))
    presets = [loadPreset(folder, fileName) for fileName in fileNames]
    return [preset for preset in presets if not only or preset.name in only]
