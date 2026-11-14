import adsk.core
import os
import pathlib
from dataclasses import dataclass, asdict
from typing import Callable

from . import browserPages

# a row of buttons drawn in a page, native buttons in a table lose their frames, see defaultsButtons for a fixed row
BUTTON_ROW_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'buttonRow.html').as_uri()
CLICK = 'click'

@dataclass
class Button:
    action: str
    label: str
    # shown on hover
    title: str = ''

def addButtonRow(inputs: adsk.core.CommandInputs, browserId: str) -> adsk.core.BrowserCommandInput:
    """Buttons side by side, they come from buttonRowHandlers once the page loads"""
    browser = inputs.addBrowserCommandInput(browserId, '', BUTTON_ROW_HTML_URL, 30, 30)
    browser.isFullWidth = True
    return browser

def buttonRowHandlers(buttons: list[Button], onClick: Callable[[str], str | None]) -> dict[str, browserPages.Handler]:
    """
    Messages of the row, see browserPages.handleMessage. onClick gets the action of the button clicked and may
    answer a short text the button shows for a moment, like Copied
    """
    actions = [button.action for button in buttons]
    def clicked(action):
        if action in actions:
            return onClick(action)
    return {browserPages.READY: lambda _: [asdict(button) for button in buttons], CLICK: clicked}
