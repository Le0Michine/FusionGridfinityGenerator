import adsk.core, adsk.fusion

from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

# the bodies are shown once the command that built them is over, before that the viewport drops the highlight of a
# selection made while it ends, see showBuiltBodies
SHOW_EVENT_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_showBuiltBodies'
handlers = []
pendingBodies: list[adsk.fusion.BRepBody] = []

def start():
    # left over when the add-in wasn't stopped
    app.unregisterCustomEvent(SHOW_EVENT_ID)
    futil.add_handler(app.registerCustomEvent(SHOW_EVENT_ID), show_custom_event, local_handlers=handlers)

def stop():
    global handlers
    app.unregisterCustomEvent(SHOW_EVENT_ID)
    handlers = []
    pendingBodies.clear()

def showBuiltBodies(bodies: list[adsk.fusion.BRepBody]) -> None:
    """
    Selects the bodies just built and centers the view on them, so they stand out among the others, in a part
    design they have no component of their own to tell them by. Called as their command ends, it's done after
    """
    pendingBodies[:] = bodies
    app.fireCustomEvent(SHOW_EVENT_ID)

def show_custom_event(args: adsk.core.CustomEventArgs):
    bodies = list(pendingBodies)
    pendingBodies.clear()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        return
    # bodies of a component are shown where it's placed
    placedBodies = [_inRootContext(design, body) for body in bodies if body is not None and body.isValid]
    if len(placedBodies) == 0:
        return
    selectBodies(placedBodies)
    centerView(placedBodies)

def selectBodies(bodies: list[adsk.fusion.BRepBody]) -> None:
    """Until something else is picked"""
    selections = ui.activeSelections
    selections.clear()
    for body in bodies:
        try:
            selections.add(body)
        except RuntimeError as err:
            futil.log(f'Couldn\'t select {body.name}, {err}')

def centerView(bodies: list[adsk.fusion.BRepBody]) -> None:
    """Moves the view to the middle of the bodies, looking from the same side as close as it was"""
    viewport = app.activeViewport
    if viewport is None:
        return
    box = bodies[0].boundingBox.copy()
    for body in bodies[1:]:
        box.combine(body.boundingBox)
    center = adsk.core.Point3D.create(
        (box.minPoint.x + box.maxPoint.x) / 2,
        (box.minPoint.y + box.maxPoint.y) / 2,
        (box.minPoint.z + box.maxPoint.z) / 2,
    )
    camera = viewport.camera
    shift = camera.target.vectorTo(center)
    eye = camera.eye.copy()
    eye.translateBy(shift)
    camera.eye = eye
    camera.target = center
    camera.isSmoothTransition = True
    viewport.camera = camera
    # draws the highlight of the selection too
    viewport.refresh()

def _inRootContext(design: adsk.fusion.Design, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if body.assemblyContext is not None or body.parentComponent == design.rootComponent:
        return body
    occurrences = design.rootComponent.allOccurrencesByComponent(body.parentComponent)
    return body.createForAssemblyContext(occurrences.item(0)) if occurrences.count > 0 else body
