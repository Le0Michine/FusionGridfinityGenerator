import adsk.core
import os
import pathlib
import webbrowser

from ...lib import fusion360utils as futil
from . import browserPages

# the info text of a dialog drawn in a page, a text box input keeps a column for its label and wraps the text early
INFO_HTML_URL = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), 'html', 'info.html').as_uri()
LINK = 'link'
HEIGHT = 'height'
# until the page tells how tall its text is, Fusion sizes a page by the dialog, not by what it shows
INITIAL_HEIGHT = 40
MAX_HEIGHT = 200
# a line marked with a yellow warning sign, see html/info.html
WARNING_CLASS = 'warning'

def addInfoPage(inputs: adsk.core.CommandInputs, browserId: str) -> adsk.core.BrowserCommandInput:
    """The text comes from infoPageHandlers once the page loads"""
    browser = inputs.addBrowserCommandInput(browserId, '', INFO_HTML_URL, INITIAL_HEIGHT, INITIAL_HEIGHT)
    browser.isFullWidth = True
    return browser

def warningLine(html: str) -> str:
    """A line of the info that needs to be seen, the html is escaped already"""
    return f'<div class="{WARNING_CLASS}">{html}</div>'

def infoPageHandlers(html: str, browser: adsk.core.BrowserCommandInput) -> dict[str, browserPages.Handler]:
    """
    Messages of the page, see browserPages.handleMessage. The html is the dialog's own, links open in the browser.
    The page tells the height of its text, more lines in a narrow dialog, and the browser input takes it
    """
    def setHeight(height):
        if not isinstance(height, (int, float)) or browser is None:
            return
        height = max(1, min(MAX_HEIGHT, int(height)))
        # a new height resizes the page, which tells it again
        if browser.minimumHeight != height or browser.maximumHeight != height:
            browser.maximumHeight = max(height, browser.maximumHeight)
            browser.minimumHeight = height
            browser.maximumHeight = height
    def openLink(url):
        if isinstance(url, str) and url.startswith('https://'):
            webbrowser.open(url)
        else:
            futil.log(f'Info page link ignored, {url}')
    return {browserPages.READY: lambda _: {'html': html}, LINK: openLink, HEIGHT: setHeight}
