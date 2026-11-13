"""
A shot's dialog open in a browser page: drawn by page/dialog.js from a live DialogSession, with the add-in's pages
talking to the session as they talk to Fusion. Changes made to the session are drawn with update
"""

import json
import os
import pathlib

import dialogRecorder

ROOT_DIR = dialogRecorder.ROOT_DIR
FONT_URL = '/__fonts/'
# tall enough for the mouse to reach anything in a dialog with every group open
VIEWPORT_HEIGHT = 3000


class DialogPage:
    def __init__(self, browser, origin: str, shot: dict, theme: str, scale: float, background: str | None = None):
        self.origin = origin
        self.rootUri = pathlib.Path(ROOT_DIR).as_uri()
        self.shot = shot
        defaults = shot.get('defaults')
        self.session = dialogRecorder.DialogSession(
            shot['command'],
            shot.get('values'),
            shot.get('globals'),
            os.path.join(ROOT_DIR, defaults) if defaults else None,
        )
        model = self.model()
        self.page = browser.new_page(
            color_scheme=theme,
            device_scale_factor=scale,
            viewport={'width': model['width'] + 200, 'height': VIEWPORT_HEIGHT},
        )
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        # what pages send the dialog, see page() in dialog.js
        self.page.expose_binding('fusionSend', lambda source, inputId, action, data: self.answer(self.session.pageMessage(inputId, action, data)))
        self.page.goto(f'{origin}/tools/screenshots/page/dialog.html')
        self.call('([model, shot]) => renderDialog(model, shot)', [model, {**shot, 'background': background}])

    def served(self, value):
        """Files of the add-in from the server instead of the disk"""
        if isinstance(value, str):
            return value.replace(self.rootUri, self.origin)
        if isinstance(value, list):
            return [self.served(item) for item in value]
        if isinstance(value, dict):
            return {key: self.served(item) for (key, item) in value.items()}
        return value

    def answer(self, text: str) -> str:
        """Data for a page with the dialog's font from the server, see lib/ui/browserPages.py"""
        if not text.startswith('{'):
            return text
        message = json.loads(text)
        if 'fontUrl' in message:
            message['fontUrl'] = f'{self.origin}{FONT_URL}Medium'
        return json.dumps(self.served(message))

    def model(self) -> dict:
        model = self.served(self.session.describe())
        if self.shot.get('width'):
            model['width'] = self.shot['width']
        return model

    def call(self, script: str, arg=None):
        result = self.page.evaluate(script, arg)
        if self.errors:
            raise RuntimeError(f'{self.shot["name"]}: {self.errors[0]}')
        return result

    def update(self):
        """Draws the dialog after a change, sends pages what the dialog sent them and lets them draw it"""
        # messages pages sent last arrive meanwhile
        self.page.wait_for_timeout(30)
        self.call('model => updateDialog(model)', self.model())
        for (inputId, action, data) in self.session.takeSentInfo():
            self.call('([id, action, data]) => sendToPage(id, action, data)', [inputId, action, self.answer(data)])
        self.call('() => nextFrame()')

    def screenshot(self, path: str = None, transparent: bool = True) -> bytes:
        return self.page.locator('.shot').screenshot(path=path, omit_background=transparent, animations='disabled')

    def close(self):
        self.page.close()
