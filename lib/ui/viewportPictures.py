"""
Pictures of models from Fusion's viewport, for the documentation and the snapshot tests' previews. The model alone,
in a color, from a view. Fusion saves the viewport larger than the picture, a palette's page cuts the render to the
model and scales it down, see pictureJobs
"""

import adsk.core, adsk.fusion
import dataclasses
import os
import re
import tempfile
from typing import Callable

# what a picture shows of a design, the bodies only
HIDDEN_FOLDERS = [
    'isOriginFolderLightBulbOn',
    'isConstructionFolderLightBulbOn',
    'isSketchFolderLightBulbOn',
    'isJointsFolderLightBulbOn',
    'isJointOriginsFolderLightBulbOn',
    'isCanvasFolderLightBulbOn',
    'isDecalFolderLightBulbOn',
]
# what a color is put on when no appearance is named, the first found
COLOR_BASE_PREFIXES = ['Plastic - Matte', 'Plastic']
# the main color of Fusion's appearance kinds: plastics, generic ones, metals
COLOR_PROPERTY_IDS = ['opaque_albedo', 'generic_diffuse', 'metal_f0']
# a render larger than this takes long to pass to the palette
MAX_RENDER_SIZE = 6000
# times the model is moved away when it touches the edge of the render, and how far each time
ZOOM_OUT_ATTEMPTS = 3
ZOOM_OUT = 1.25

app = adsk.core.Application.get()

class PictureError(Exception):
    pass

@dataclasses.dataclass
class PictureOptions:
    width: int
    height: int
    transparent: bool
    # space around the model, a share of the picture's width and height
    margin: float
    # the render is this many times the picture's size and scaled down, which smooths the edges
    supersample: int
    # stops the picture is brightened by, as a camera's exposure, and how much its colors are deepened, 1 keeps them
    exposure: float
    saturation: float

# finishes a render as the picture, see pictureJobs.finishPicture without the page to send to
Finish = Callable[..., dict]

def appearanceNamed(appearances: adsk.core.Appearances, name: str) -> adsk.core.Appearance | None:
    """By looking through them, itemByName raises an invalid name error for a name it doesn't have"""
    for index in range(appearances.count):
        if appearances.item(index).name == name:
            return appearances.item(index)
    return None

def libraryAppearance(name: str) -> adsk.core.Appearance:
    """An appearance of Fusion's libraries by name"""
    for library in app.materialLibraries:
        appearance = appearanceNamed(library.appearances, name)
        if appearance is not None:
            return appearance
    raise PictureError(f'no appearance named {name!r} in the material libraries')

def firstLibraryAppearance(prefixes: list[str]) -> adsk.core.Appearance:
    """The first appearance of Fusion's libraries starting with one of the prefixes, by their order"""
    for prefix in prefixes:
        for library in app.materialLibraries:
            appearances = library.appearances
            for index in range(appearances.count):
                if appearances.item(index).name.startswith(prefix):
                    return appearances.item(index)
    raise PictureError(f'no appearance starting with {" or ".join(prefixes)} in the material libraries')

def colorAppearance(design: adsk.fusion.Design, base: adsk.core.Appearance, color: str | None) -> adsk.core.Appearance:
    """The appearance in the color, '#rrggbb', none keeps its own, copied into the design as Fusion does when one is dragged onto a body"""
    # Fusion refuses names with some characters, # and the parentheses of library names among them
    name = re.sub(r'[^A-Za-z0-9]+', ' ', f'{base.name} {color or ""}').strip()
    appearance = appearanceNamed(design.appearances, name)
    if appearance is not None:
        return appearance
    try:
        appearance = design.appearances.addByCopy(base, name)
    except Exception as err:
        raise PictureError(f'appearance {base.name!r} not copied as {name!r}, {err}') from err
    if color is not None:
        setColor(appearance, color)
    return appearance

def setColor(appearance: adsk.core.Appearance, color: str):
    """The main color of the appearance, the one Fusion's appearance editor shows first"""
    properties = appearance.appearanceProperties
    colors = [adsk.core.ColorProperty.cast(properties.item(index)) for index in range(properties.count)]
    colors = [property for property in colors if property is not None and not property.isReadOnly]
    main = next((property for property in colors if property.id in COLOR_PROPERTY_IDS), None) or (colors[0] if colors else None)
    if main is None:
        raise PictureError(f'the appearance {appearance.name!r} has no color to change')
    if main.hasConnectedTexture:
        main.hasConnectedTexture = False
    main.value = adsk.core.Color.create(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), 255)

def hideHelpers(design: adsk.fusion.Design):
    """Origins, sketches, joints and the like of every component out of the picture"""
    for component in design.allComponents:
        for folder in HIDDEN_FOLDERS:
            setattr(component, folder, False)

def frame(viewport: adsk.core.Viewport, style: str, orthographic: bool, view: str | dict):
    """
    The model fit in the viewport. style: a name of Fusion's VisualStyles. view: the start of the name of one of
    Fusion's ViewOrientations, as isoTopRight, or the eye, target and up vector of the camera, points in mm
    """
    viewport.visualStyle = getattr(adsk.core.VisualStyles, style)
    camera = viewport.camera
    camera.isSmoothTransition = False
    camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType if orthographic else adsk.core.CameraTypes.PerspectiveCameraType
    if isinstance(view, str):
        camera.viewOrientation = getattr(adsk.core.ViewOrientations, f'{view[0].upper()}{view[1:]}ViewOrientation')
    else:
        # Fusion's points are in cm
        camera.eye = adsk.core.Point3D.create(*(value / 10 for value in view['eye']))
        camera.target = adsk.core.Point3D.create(*(value / 10 for value in view['target']))
        camera.upVector = adsk.core.Vector3D.create(*view.get('up', [0, 0, 1]))
    camera.isFitView = True
    viewport.camera = camera
    viewport.refresh()
    adsk.doEvents()

def renderSize(viewport: adsk.core.Viewport, longSide: int) -> tuple[int, int]:
    """
    A render size larger than the picture so scaling it down smooths the edges. Fusion fits the view to the viewport,
    a render of other proportions would cut it off, so the render keeps the viewport's
    """
    scale = longSide / max(viewport.width, viewport.height)
    return (round(viewport.width * scale), round(viewport.height * scale))

def saveViewport(viewport: adsk.core.Viewport, renderPath: str, width: int, height: int, transparent: bool):
    options = adsk.core.SaveImageFileOptions.create(renderPath)
    options.width = width
    options.height = height
    options.isBackgroundTransparent = transparent
    options.isAntiAliased = True
    if not viewport.saveAsImageFileWithOptions(options):
        raise PictureError('Fusion did not save the viewport')

def zoomOut(viewport: adsk.core.Viewport):
    """Further away by ZOOM_OUT, the eye of a perspective camera moves back, an orthographic one sees more"""
    camera = viewport.camera
    camera.isSmoothTransition = False
    camera.isFitView = False
    if camera.cameraType == adsk.core.CameraTypes.OrthographicCameraType:
        (_, width, height) = camera.getExtents()
        camera.setExtents(width * ZOOM_OUT, height * ZOOM_OUT)
    else:
        (eye, target) = (camera.eye, camera.target)
        direction = target.vectorTo(eye)
        direction.scaleBy(ZOOM_OUT)
        moved = target.copy()
        moved.translateBy(direction)
        camera.eye = moved
    viewport.camera = camera
    viewport.refresh()
    adsk.doEvents()

def viewportPicture(viewport: adsk.core.Viewport, name: str, path: str, options: PictureOptions, finish: Finish) -> list[str]:
    """The viewport as it is saved to path, moved back while the model touches the edge, the warnings of the picture"""
    (width, height) = renderSize(viewport, min(max(options.width, options.height) * options.supersample, MAX_RENDER_SIZE))
    renderPath = os.path.join(tempfile.gettempdir(), f'gridfinity-render-{re.sub(r"[^A-Za-z0-9_.-]+", "-", name)}.png')
    try:
        for attempt in range(ZOOM_OUT_ATTEMPTS + 1):
            saveViewport(viewport, renderPath, width, height, options.transparent)
            result = finish(name, renderPath, options.width, options.height, options.margin, options.transparent,
                            exposure=options.exposure, saturation=options.saturation)
            if not result['touchesEdge'] or attempt == ZOOM_OUT_ATTEMPTS:
                break
            zoomOut(viewport)
    finally:
        if os.path.exists(renderPath):
            os.remove(renderPath)
    with open(path, 'wb') as file:
        file.write(result['png'])
    return ['the model may be cut off'] if result['touchesEdge'] else []
