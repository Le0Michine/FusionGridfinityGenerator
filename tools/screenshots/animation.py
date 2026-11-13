"""
Animations of a shot's steps: a cursor moves to what a person would click, drag or type in, the dialog reacts as it does
in Fusion, and every frame is captured into a GIF or an animated WebP. See README.md for the steps.

A shot is played twice. The first time measures how much of the dialog its inputs take over the whole animation, so
the second, captured one, keeps the same frame while inputs show and hide.

{"model": n} steps mark when a GIF of model pictures shown beside the animation goes to its picture n, at the moment
the dialog last changed. They are saved as a timeline the model GIF is made from, so the two change together, see
modelGifs.py.
"""

import io
import json
import os

from dialogPage import DialogPage

# 25 frames a second while the cursor moves
FRAME_MS = 40
# how long the first and last frames show
HOLD_START_MS = 800
HOLD_END_MS = 2000
# the cursor comes from below right of the first thing it goes to
CURSOR_START_OFFSET = (90, 60)
# GIFs have no partial transparency for the shadow, they are drawn over the page they will likely be shown on
GIF_BACKGROUNDS = {'light': '#ffffff', 'dark': '#0d1117'}
# the times model GIFs change their picture, by animation and theme
TIMELINES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timelines')


def timelinePath(name: str, theme: str) -> str:
    return os.path.join(TIMELINES_DIR, f'{name}-{theme}.json')


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def target(spec) -> dict:
    """An input id, or a part of the dialog as page/dialog.js targetPoint takes it"""
    return {'input': spec} if isinstance(spec, str) else dict(spec)


class Player:
    def __init__(self, dialog: DialogPage, capture: bool, transparent: bool):
        self.dialog = dialog
        self.capture = capture
        self.transparent = transparent
        self.frames: list[list] = []
        self.region = None
        self.cursor = None
        self.pressed = False
        # when the dialog last changed and the model pictures marked, in ms from the start
        self.changedAt = 0
        self.marks: list[dict] = []

    @property
    def elapsed(self) -> int:
        return sum(ms for (_, ms) in self.frames)

    def update(self):
        """The dialog's pages get what changed, the next frame shows it"""
        self.dialog.update()
        self.changedAt = self.elapsed

    @property
    def mouse(self):
        return self.dialog.page.mouse

    def frame(self, ms: int):
        """Shows the dialog as it is for ms, or measures it on the first play"""
        if not self.capture:
            self.measure()
            return
        png = self.dialog.screenshot(transparent=self.transparent)
        if self.frames and self.frames[-1][0] == png:
            self.frames[-1][1] += ms
        else:
            self.frames.append([png, ms])

    def measure(self):
        region = self.dialog.call('ids => measureRegion(ids)', self.dialog.shot.get('inputs') or [])
        if region is None:
            return
        if self.region is None:
            self.region = region
        else:
            self.region = {
                'top': min(self.region['top'], region['top']),
                'bottom': max(self.region['bottom'], region['bottom']),
                'dialogHeight': max(self.region['dialogHeight'], region['dialogHeight']),
            }

    def point(self, spec) -> dict:
        return self.dialog.call('target => targetPoint(target)', target(spec))

    def place(self, point: dict):
        self.dialog.call('([x, y, pressed]) => moveCursor(x, y, pressed)', [point['x'], point['y'], self.pressed])
        self.mouse.move(point['clientX'], point['clientY'])
        self.cursor = point

    def moveTo(self, spec, ms: int = 450):
        end = self.point(spec)
        start = self.cursor
        steps = max(1, round(ms / FRAME_MS)) if self.capture and start is not None else 1
        for step in range(1, steps + 1):
            t = ease(step / steps)
            self.place(end if start is None else {key: start[key] + (end[key] - start[key]) * t for key in end})
            if steps > 1 or not self.capture:
                self.frame(FRAME_MS)

    def press(self, onPage: bool):
        if onPage:
            self.mouse.down()
        self.pressed = True
        self.place(self.cursor)
        self.frame(120)

    def release(self, onPage: bool):
        if onPage:
            self.mouse.up()
        self.pressed = False
        self.place(self.cursor)

    def play(self, steps: list[dict]):
        first = next((self.firstTarget(step) for step in steps if self.firstTarget(step) is not None), None)
        if first is not None:
            point = self.point(first)
            (dx, dy) = CURSOR_START_OFFSET
            self.place({**point, 'x': point['x'] + dx, 'y': point['y'] + dy, 'clientX': point['clientX'] + dx, 'clientY': point['clientY'] + dy})
        self.frame(HOLD_START_MS)
        for step in steps:
            if len(step) != 1:
                raise ValueError(f'A step has one action, not {", ".join(step)}')
            ((action, spec),) = step.items()
            handler = getattr(self, f'step_{action}', None)
            if handler is None:
                actions = ', '.join(name[len('step_'):] for name in dir(self) if name.startswith('step_'))
                raise ValueError(f'Unknown step {action}, one of {actions}')
            handler(spec)
        self.frame(HOLD_END_MS)

    @staticmethod
    def firstTarget(step: dict):
        ((action, spec),) = step.items()
        if action in ['click', 'move']:
            return target(spec)
        if action in ['type', 'select', 'spin']:
            return {'page': spec['page'], 'selector': spec.get('selector')} if 'page' in spec else {'input': spec['input']}
        if action == 'drag':
            return {'page': spec['page'], 'selector': spec.get('selector'), 'at': spec['from']}
        return None

    # the steps a shot takes, by name

    def step_wait(self, ms: int):
        self.frame(ms)

    def step_move(self, spec):
        self.moveTo(spec)
        self.frame(200)

    def step_click(self, spec):
        """A checkbox, button or group header of the dialog, or something on a page"""
        spec = target(spec)
        onPage = 'page' in spec
        self.moveTo(spec)
        self.press(onPage)
        if not onPage:
            self.dialog.session.click(spec['input'])
        self.release(onPage)
        self.update()
        self.frame(400)

    def step_spin(self, spec):
        """Clicks on a spinner arrow, direction up or down, times over"""
        direction = spec.get('direction', 'up')
        self.moveTo({'input': spec['input'], 'part': direction})
        for _ in range(spec.get('times', 1)):
            self.press(False)
            self.dialog.session.spin(spec['input'], 1 if direction == 'up' else -1)
            self.release(False)
            self.update()
            self.frame(300)

    def step_type(self, spec):
        """Text typed in a field of the dialog, or in a field on a page"""
        text = str(spec['text'])
        if 'page' in spec:
            self.step_click({'page': spec['page'], 'selector': spec.get('selector'), 'at': spec.get('at', [0.5, 0.5])})
            self.dialog.page.keyboard.press('ControlOrMeta+A')
            for char in text:
                self.dialog.page.keyboard.type(char)
                self.frame(110)
            if spec.get('enter', True):
                self.dialog.page.keyboard.press('Enter')
            self.update()
            self.frame(400)
            return
        inputId = spec['input']
        self.moveTo({'input': inputId, 'part': 'field'})
        self.press(False)
        self.release(False)
        current = self.dialog.call('id => inputNode(id).querySelector(".field .text").textContent', inputId)
        self.dialog.call('([id, text]) => editField(id, text, true)', [inputId, current])
        self.frame(400)
        for end in range(1, len(text) + 1):
            self.dialog.call('([id, text]) => editField(id, text, false)', [inputId, text[:end]])
            self.frame(110)
        self.frame(300)
        self.dialog.session.change(inputId, text)
        self.update()
        self.frame(400)

    def step_select(self, spec):
        """An item picked from a dropdown of the dialog"""
        inputId = spec['input']
        self.moveTo({'input': inputId, 'part': 'field'})
        self.press(False)
        self.release(False)
        current = self.dialog.call('id => inputNode(id).querySelector(".field .text").textContent', inputId)
        self.dialog.call('([id, name]) => openDropdown(id, name)', [inputId, current])
        self.frame(400)
        self.moveTo({'item': spec['item']}, 350)
        self.dialog.call('name => highlightItem(name)', spec['item'])
        self.frame(250)
        self.press(False)
        self.dialog.call('() => closeDropdown()')
        self.dialog.session.change(inputId, spec['item'])
        self.release(False)
        self.update()
        self.frame(400)

    def step_drag(self, spec):
        """A drag on a page, from and to are fractions of the box of the selected element"""
        start = {'page': spec['page'], 'selector': spec.get('selector'), 'at': spec['from']}
        end = {'page': spec['page'], 'selector': spec.get('selector'), 'at': spec['to']}
        self.moveTo(start)
        self.press(True)
        self.moveTo(end, spec.get('ms', 800))
        self.release(True)
        self.update()
        self.frame(400)

    def step_key(self, key: str):
        """A key pressed on the focused page, like Enter or Escape"""
        self.dialog.page.keyboard.press(key)
        self.update()
        self.frame(300)

    def step_set(self, values: dict):
        """Inputs changed without the cursor"""
        for (inputId, value) in values.items():
            self.dialog.session.change(inputId, value)
        self.update()
        self.frame(FRAME_MS)

    def step_model(self, picture: int):
        """The model GIF beside the animation goes to this picture, by its place in the GIF, as the dialog last changed"""
        self.marks.append({'picture': picture, 'at': self.changedAt})

    def step_cursor(self, visible: bool):
        """Hides or shows the cursor again"""
        if visible:
            self.place(self.cursor)
        else:
            self.dialog.call('() => hideCursor()')
        self.frame(FRAME_MS)


def record(browser, origin: str, shot: dict, theme: str, scale: float, path: str):
    webp = path.endswith('.webp')
    background = shot.get('background') or (None if webp else GIF_BACKGROUNDS[theme])

    measuring = DialogPage(browser, origin, shot, theme, scale, background)
    player = Player(measuring, capture=False, transparent=webp)
    player.play(shot['steps'])
    measuring.close()

    dialog = DialogPage(browser, origin, shot, theme, scale, background)
    dialog.call('([shot, region]) => frameShot(shot, region)', [shot, player.region])
    player = Player(dialog, capture=True, transparent=webp)
    player.play(shot['steps'])
    dialog.close()
    save(player.frames, path)
    if player.marks:
        os.makedirs(TIMELINES_DIR, exist_ok=True)
        with open(timelinePath(shot['name'], theme), 'w', encoding='utf-8') as file:
            json.dump({'length': player.elapsed, 'marks': player.marks}, file, indent=4)
            file.write('\n')


def save(frames: list[list], path: str):
    from PIL import Image
    images = [Image.open(io.BytesIO(png)) for (png, _) in frames]
    durations = [ms for (_, ms) in frames]
    if path.endswith('.webp'):
        images = [image.convert('RGBA') for image in images]
        images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0, lossless=True)
        return
    # one palette for all frames, so colors that don't change don't flicker
    images = [image.convert('RGB') for image in images]
    samples = images[::max(1, len(images) // 8)]
    sheet = Image.new('RGB', (images[0].width * len(samples), images[0].height))
    for (index, image) in enumerate(samples):
        sheet.paste(image, (index * images[0].width, 0))
    palette = sheet.quantize(colors=256, dither=Image.Dither.NONE)
    frames = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0)
