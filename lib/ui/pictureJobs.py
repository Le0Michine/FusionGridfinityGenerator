"""
Pictures finished by a palette's page, see html/pictureFinish.js. Fusion's Python has no imaging, the page cuts a
render to the model, fits it in the picture and scales it down in a canvas. The picture is made while Fusion waits for
the page's answer, which comes back as the PICTURE action
"""

import adsk.core
import base64
import time
from typing import Callable

PICTURE = 'picture'
TIMEOUT = 120

class PageError(Exception):
    pass

# answers of pages by job id
answers: dict[str, dict] = {}
jobCount = 0

def waitUntil(isDone, timeout: float, failure: str):
    """Lets Fusion handle events, the page's messages among them, until isDone"""
    deadline = time.monotonic() + timeout
    while not isDone():
        if time.monotonic() > deadline:
            raise PageError(failure)
        adsk.doEvents()
        time.sleep(0.02)

def dataUrl(path: str) -> str:
    with open(path, 'rb') as file:
        return 'data:image/png;base64,' + base64.b64encode(file.read()).decode('ascii')

def finishPicture(send: Callable[[dict], None], name: str, renderPath: str, width: int, height: int, margin: float,
                  transparent: bool, exposure: float = 0, saturation: float = 1) -> dict:
    """
    The picture of a render from the page send gives the job to: png, the PNG bytes, touchesEdge, if the model touched
    an edge of the render, which means it may have been cut off. Exposure brightens the render by that many stops,
    saturation deepens its colors
    """
    global jobCount
    jobCount += 1
    jobId = f'job{jobCount}'
    job = {'id': jobId, 'name': name, 'image': dataUrl(renderPath), 'width': width, 'height': height, 'margin': margin, 'transparent': transparent, 'exposure': exposure, 'saturation': saturation}
    send({'job': job})
    waitUntil(lambda: jobId in answers, TIMEOUT, 'the palette did not finish the picture')
    answer = answers.pop(jobId)
    if answer.get('error'):
        raise PageError(answer['error'])
    (_, encoded) = answer['png'].split(',', 1)
    return {**answer, 'png': base64.b64decode(encoded)}

def answer(data: dict):
    """The page's PICTURE action, a finished picture or why it couldn't be"""
    answers[data['id']] = data
