import adsk.core
import os
import pathlib
from typing import Callable

from . import browserPages

# a row of buttons drawn in a page, native buttons in a table lose their frames
DEFAULTS_BUTTONS_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'defaultsButtons.html').as_uri()
DEFAULTS_SAVE = 'save'
DEFAULTS_RESET = 'reset'
DEFAULTS_FACTORY_RESET = 'factoryReset'
DEFAULTS_ACTIONS = [DEFAULTS_SAVE, DEFAULTS_RESET, DEFAULTS_FACTORY_RESET]

def addDefaultsButtonRow(inputs: adsk.core.CommandInputs, browserId: str) -> adsk.core.BrowserCommandInput:
    """Save, reset and factory reset buttons for the dialog defaults side by side, see defaultsButtonsHandlers"""
    browser = inputs.addBrowserCommandInput(browserId, '', DEFAULTS_BUTTONS_HTML_URL, 30, 30)
    browser.isFullWidth = True
    return browser

def defaultsButtonsHandlers(onClick: Callable[[str], None]) -> dict[str, browserPages.Handler]:
    """Messages of the row, see browserPages.handleMessage, onClick gets the button clicked, one of DEFAULTS_ACTIONS"""
    def clicked(action):
        if action in DEFAULTS_ACTIONS:
            onClick(action)
    # the row has no data, only the font
    return {browserPages.READY: lambda _: {}, 'defaults': clicked}
