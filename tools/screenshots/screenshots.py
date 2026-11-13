"""
Screenshots of the add-in's dialogs for docs and release notes, drawn outside Fusion in its dark and light themes.

Each shot in a shots file sets the inputs of a command's dialog and takes all of it or the part with some inputs,
with torn edges where it is cut, see README.md. The dialog is built by the command's own code, see dialogRecorder.py,
and drawn by page/dialog.js in a browser, its pages are the add-in's own.

    tools/screenshots/.venv/bin/python tools/screenshots/screenshots.py [shots.json] [--only NAME ...]
"""

import argparse
import functools
import glob
import http.server
import json
import os
import pathlib
import sys
import threading

import dialogRecorder

SCREENSHOTS_DIR = dialogRecorder.SCREENSHOTS_DIR
ROOT_DIR = dialogRecorder.ROOT_DIR
DEFAULT_SHOTS_FILE = os.path.join(SCREENSHOTS_DIR, 'shots.json')
THEMES = ['dark', 'light']
# the dialog's font comes with Fusion, it isn't ours to ship
FONT_WEIGHTS = ['Regular', 'Medium', 'Bold']
FONT_PATTERNS = [
    '~/Library/Application Support/Autodesk/webdeploy/production/*/*.app/Contents/Resources/FusionCDEHostApps/*/ArtifaktElement{weight}.*.woff2',
    '~/AppData/Local/Autodesk/webdeploy/production/*/FusionCDEHostApps/*/ArtifaktElement{weight}.*.woff2',
]
FONT_URL = '/__fonts/'


def findFonts(fontDir: str | None) -> dict[str, str]:
    """The newest font file of each weight, from the Fusion install unless a folder is given"""
    fonts = {}
    for weight in FONT_WEIGHTS:
        patterns = [os.path.join(fontDir, f'ArtifaktElement{weight}*.woff2')] if fontDir else [os.path.expanduser(p.format(weight=weight)) for p in FONT_PATTERNS]
        matches = [match for pattern in patterns for match in glob.glob(pattern)]
        if matches:
            fonts[weight] = max(matches, key=os.path.getmtime)
    return fonts


class Handler(http.server.SimpleHTTPRequestHandler):
    """The add-in folder, so pages load their scripts and styles as in Fusion, and the font"""

    def __init__(self, *args, fonts: dict[str, str], **kwargs):
        self.fonts = fonts
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def translate_path(self, path: str) -> str:
        if path.startswith(FONT_URL):
            return self.fonts.get(path[len(FONT_URL):], os.path.join(ROOT_DIR, 'missing-font'))
        return super().translate_path(path)

    def end_headers(self):
        # every shot sees the files as they are now
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, format, *args):
        pass


def serve(fonts: dict[str, str]) -> str:
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, fonts=fonts))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}'


def servedModel(model: dict, origin: str) -> dict:
    """Files of the add-in from the server, pages load the dialog's font from it too"""
    rootUri = pathlib.Path(ROOT_DIR).as_uri()

    def served(value):
        if isinstance(value, str):
            return value.replace(rootUri, origin)
        if isinstance(value, list):
            return [served(item) for item in value]
        if isinstance(value, dict):
            return {key: served(item) for (key, item) in value.items()}
        return value

    def answer(text: str) -> str:
        message = json.loads(text)
        if isinstance(message, dict) and 'fontUrl' in message:
            message['fontUrl'] = f'{origin}{FONT_URL}Medium'
        return json.dumps(served(message))

    def walk(inputs: list[dict]):
        for input in inputs:
            if input['type'] == 'browser' and input['answer'].startswith('{'):
                input['answer'] = answer(input['answer'])
            walk(input.get('children', []))

    model = served(model)
    walk(model['inputs'])
    return model


def outputPath(outputDir: str, shot: dict, theme: str, themes: list[str]) -> str:
    name = shot['name'] if len(themes) == 1 else f'{shot["name"]}-{theme}'
    return os.path.join(outputDir, f'{name}.png')


def launch(playwright):
    # the installed Chrome needs no download, Playwright's own Chromium otherwise
    try:
        return playwright.chromium.launch(channel='chrome')
    except Exception:
        return playwright.chromium.launch()


def takeShots(shotsFile: str, only: list[str], outputDir: str | None, themes: list[str] | None, scale: float | None, fontDir: str | None):
    from playwright.sync_api import sync_playwright

    with open(shotsFile, 'r') as file:
        config = json.load(file)
    shots = [shot for shot in config['shots'] if not only or shot['name'] in only]
    missing = set(only or []) - {shot['name'] for shot in shots}
    if missing:
        sys.exit(f'No shots named {", ".join(sorted(missing))} in {shotsFile}')

    fonts = findFonts(fontDir)
    if len(fonts) < len(FONT_WEIGHTS):
        print(f'The Artifakt Element font of Fusion was not found, {", ".join(set(FONT_WEIGHTS) - set(fonts))} fall back to a system font. '
              'Pass --font-dir with its woff2 files to use it')
    origin = serve(fonts)

    with sync_playwright() as playwright:
        browser = launch(playwright)
        for shot in shots:
            defaults = shot.get('defaults')
            model = dialogRecorder.record(
                shot['command'],
                shot.get('values'),
                shot.get('globals'),
                os.path.join(ROOT_DIR, defaults) if defaults else None,
            )
            model = servedModel(model, origin)
            if shot.get('width'):
                model['width'] = shot['width']
            shotThemes = themes or shot.get('themes') or config.get('themes') or THEMES
            for theme in shotThemes:
                page = browser.new_page(
                    color_scheme=theme,
                    device_scale_factor=scale or shot.get('scale') or config.get('scale', 2),
                    viewport={'width': model['width'] + 200, 'height': 900},
                )
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'{origin}/tools/screenshots/page/dialog.html')
                page.evaluate('([model, shot]) => renderShot(model, shot)', [model, shot])
                if errors:
                    sys.exit(f'{shot["name"]} ({theme}): {errors[0]}')
                # paths in the shots file are from the add-in folder
                folder = os.path.join(ROOT_DIR, outputDir or shot.get('output') or config.get('output', 'documentation/assets/ui'))
                path = outputPath(folder, shot, theme, shotThemes)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                page.locator('.shot').screenshot(path=path, omit_background=True)
                page.close()
                print(os.path.relpath(path, ROOT_DIR))
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('shots', nargs='?', default=DEFAULT_SHOTS_FILE, help='the shots file, shots.json beside this script by default')
    parser.add_argument('--only', nargs='+', metavar='NAME', help='take only these shots')
    parser.add_argument('--out', help='folder for all images, from the add-in folder, instead of what the shots set')
    parser.add_argument('--themes', help='dark, light or both comma separated, instead of what the shots set')
    parser.add_argument('--scale', type=float, help='pixels per dialog pixel, 2 by default for sharp images on high density screens')
    parser.add_argument('--font-dir', help='a folder with the ArtifaktElement*.woff2 fonts, found in the Fusion install by default')
    args = parser.parse_args()
    takeShots(args.shots, args.only, args.out, args.themes.split(',') if args.themes else None, args.scale, args.font_dir)


if __name__ == '__main__':
    main()
