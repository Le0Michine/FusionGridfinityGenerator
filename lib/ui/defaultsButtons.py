import adsk.core
import json
import os
import pathlib

from .dialogFont import dialogFontUrl

# a row of buttons drawn in a page, native buttons in a table lose their frames
DEFAULTS_BUTTONS_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'defaultsButtons.html').as_uri()
DEFAULTS_SAVE = 'save'
DEFAULTS_RESET = 'reset'
DEFAULTS_FACTORY_RESET = 'factoryReset'
DEFAULTS_ACTIONS = [DEFAULTS_SAVE, DEFAULTS_RESET, DEFAULTS_FACTORY_RESET]

def addDefaultsButtonRow(inputs: adsk.core.CommandInputs, browserId: str) -> adsk.core.BrowserCommandInput:
    """Save, reset and factory reset buttons for the dialog defaults side by side, see handleDefaultsButtons"""
    browser = inputs.addBrowserCommandInput(browserId, '', DEFAULTS_BUTTONS_HTML_URL, 30, 30)
    browser.isFullWidth = True
    return browser

def handleDefaultsButtons(args: adsk.core.HTMLEventArgs) -> str | None:
    """An event from the row, the button clicked, one of DEFAULTS_ACTIONS, or none when it only asked for its font"""
    if args.action == 'ready':
        args.returnData = json.dumps({'fontUrl': dialogFontUrl()})
        return None
    args.returnData = 'OK'
    return args.data if args.action == 'defaults' and args.data in DEFAULTS_ACTIONS else None
