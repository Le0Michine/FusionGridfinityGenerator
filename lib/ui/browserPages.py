"""
Pages shown in a dialog with browser inputs and the messages between them, see html/fusionBridge.js. A page sends
an action with JSON data and gets an answer to redraw from, the dialog sends it updates. Data going to a page
comes with the dialog's font, which the bridge loads
"""

import adsk.core
import json
import os
import pathlib
from typing import Any, Callable

from ...lib import fusion360utils as futil
from .dialogFont import dialogFontUrl

# the answer when the page has nothing to redraw
NO_ANSWER = 'OK'
READY = 'ready'

Handler = Callable[[Any], Any]

def pageUrl(commandFile: str, name: str) -> str:
    """A page in the html folder beside a command's entry"""
    return pathlib.Path(os.path.dirname(os.path.abspath(commandFile)), 'html', name).as_uri()

def encode(data) -> str:
    return json.dumps({'fontUrl': dialogFontUrl(), 'data': data})

def sendUpdate(browserInput: adsk.core.BrowserCommandInput, data) -> None:
    """New data for a page to redraw from"""
    if browserInput is None:
        return
    try:
        browserInput.sendInfoToHTML('update', encode(data))
    except Exception as err:
        # the page asks for the data itself once it has loaded
        futil.log(f'Page {browserInput.id} not ready yet, {err}')

def handleMessage(args: adsk.core.HTMLEventArgs, handlers: dict[str, Handler]) -> None:
    """
    Calls the handler of the action the page sent with its data decoded and answers with what it returns, none
    when the page has nothing to redraw. Every page has a READY handler with its data, data that can't be read
    gets that answer, so the page draws what the dialog has
    """
    pageId = args.browserCommandInput.id
    handler = handlers.get(args.action)
    if handler is None:
        futil.log(f'Page {pageId} sent an unknown action {args.action}')
        args.returnData = NO_ANSWER
        return
    try:
        data = json.loads(args.data) if args.data else None
    except ValueError as err:
        futil.log(f'Ignoring {args.action} from page {pageId}, {err}')
        (handler, data) = (handlers[READY], None)
    answer = handler(data)
    args.returnData = NO_ANSWER if answer is None else encode(answer)
