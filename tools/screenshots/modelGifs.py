"""
GIFs going through saved model pictures, one after the other with a caption, cross-fading between them. The pictures
come from Fusion, see the model pictures section of README.md, so they share a view and line up.

    tools/screenshots/.venv/bin/python tools/screenshots/modelGifs.py [--only bin-bottom-options] [--dialogs]

GIFs are listed in modelGifs.json, each is written for the light and the dark theme to documentation/assets/gif.
A GIF with loopWith changes its pictures when the dialog animation it's shown beside does, by the timeline recording it
saved, see animation.py. With combine, the dialog animation is put beside the pictures in the same GIF. --dialogs first
records the dialog animations, from shots.json. Fusion's palette of model pictures runs it with --dialogs after its pictures.
"""

import argparse
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from animation import FRAME_MS, GIF_BACKGROUNDS, save, timelinePath
from screenshots import DEFAULT_SHOTS_FILE, findFonts, outputPath, takeShots

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(TOOL_DIR))
GIFS_FILE = os.path.join(TOOL_DIR, 'modelGifs.json')
PICTURES_DIR = os.path.join(ROOT_DIR, 'documentation', 'assets', 'models')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'documentation', 'assets', 'gif')
# GitHub's text colors of the themes
CAPTION_COLORS = {'light': '#1f2328', 'dark': '#e6edf3'}
DEFAULTS = {'size': 640, 'hold': 1600, 'fade': 400, 'captionSize': 30}
# space between the pictures and the dialog of a combined GIF
COMBINED_GAP = 32


class GifError(Exception):
    pass


def font(size: int, fontDir: str | None) -> ImageFont.FreeTypeFont:
    fonts = findFonts(fontDir)
    return ImageFont.truetype(fonts['Medium'], size) if 'Medium' in fonts else ImageFont.load_default(size)


def picture(path: str, gif: dict, theme: str) -> Image.Image:
    """The picture fitted in a square on the theme's page color"""
    size = gif['size']
    result = Image.new('RGBA', (size, size), GIF_BACKGROUNDS[theme])
    fitted = Image.open(path).convert('RGBA')
    fitted.thumbnail((size, size), Image.LANCZOS)
    result.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return result.convert('RGB')


def captioned(image: Image.Image, caption: str, gif: dict, theme: str, captionFont) -> Image.Image:
    """The picture with its caption under it"""
    captionHeight = round(gif['captionSize'] * 2) if any(item.get('caption') for item in gif['frames']) else 0
    result = Image.new('RGB', (image.width, image.height + captionHeight), GIF_BACKGROUNDS[theme])
    result.paste(image, (0, 0))
    if caption:
        ImageDraw.Draw(result).text((image.width / 2, image.height + captionHeight / 2), caption, font=captionFont,
                                    fill=CAPTION_COLORS[theme], anchor='mm')
    return result


def png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    return buffer.getvalue()


def gifFrames(pictures: list[Image.Image], label, gif: dict) -> list[tuple[bytes, int]]:
    """
    Each picture held, then faded into the next, the last into the first so it loops. Label captions a picture by its
    index, captions don't fade, faded text over text reads as neither, they change halfway
    """
    steps = max(1, round(gif['fade'] / FRAME_MS))
    frames = []
    for (index, current) in enumerate(pictures):
        following = (index + 1) % len(pictures)
        frames.append((png(label(current, index)), gif['hold']))
        for step in range(1, steps):
            blended = Image.blend(current, pictures[following], step / steps)
            frames.append((png(label(blended, index if step < steps / 2 else following)), FRAME_MS))
    return frames


def timeline(gif: dict, theme: str) -> dict:
    """When the dialog animation the GIF is shown beside goes to each picture, and how long it is"""
    path = timelinePath(gif['loopWith'], theme)
    if not os.path.exists(path):
        raise GifError(f'{gif["name"]}: no timeline of {gif["loopWith"]}, record it first with --dialogs')
    with open(path, encoding='utf-8') as file:
        result = json.load(file)
    wrong = [mark['picture'] for mark in result['marks'] if not 0 <= mark['picture'] < len(gif['frames'])]
    if wrong:
        raise GifError(f'{gif["name"]}: {gif["loopWith"]} goes to picture {wrong[0]}, it has {len(gif["frames"])}')
    return result


def timedFrames(pictures: list[Image.Image], label, gif: dict, times: dict) -> list[tuple[bytes, int]]:
    """
    The first picture, faded into the next one at each mark of the timeline, until its length, so the GIF changes and
    loops with the dialog animation. Captions change halfway through a fade
    """
    steps = max(1, round(gif['fade'] / FRAME_MS))
    frames = []
    (shown, at) = (0, 0)
    for mark in times['marks']:
        following = mark['picture']
        frames.append((png(label(pictures[shown], shown)), max(0, mark['at'] - at)))
        for step in range(1, steps):
            blended = Image.blend(pictures[shown], pictures[following], step / steps)
            frames.append((png(label(blended, shown if step < steps / 2 else following)), FRAME_MS))
        (shown, at) = (following, max(at, mark['at']) + (steps - 1) * FRAME_MS)
    frames.append((png(label(pictures[shown], shown)), max(FRAME_MS, times['length'] - at)))
    return [frame for frame in frames if frame[1] > 0]


def dialogFrames(gif: dict, theme: str) -> list[tuple[Image.Image, int]]:
    """The frames of the dialog animation the GIF loops with, as recorded"""
    with open(DEFAULT_SHOTS_FILE, encoding='utf-8') as file:
        config = json.load(file)
    shot = next((shot for shot in config['shots'] if shot['name'] == gif['loopWith']), None)
    if shot is None:
        raise GifError(f'{gif["name"]}: no dialog animation {gif["loopWith"]} in {DEFAULT_SHOTS_FILE}')
    folder = os.path.join(ROOT_DIR, shot.get('output') or config.get('output', 'documentation/assets/ui'))
    path = outputPath(folder, shot, theme, shot.get('themes') or config.get('themes') or ['dark', 'light'])
    if not os.path.exists(path):
        raise GifError(f'{gif["name"]}: no recording of {gif["loopWith"]}, record it first with --dialogs')
    frames = []
    with Image.open(path) as recording:
        for index in range(recording.n_frames):
            recording.seek(index)
            frames.append((recording.convert('RGB'), recording.info['duration']))
    return frames


def combinedFrames(models: list[tuple[bytes, int]], dialogs: list[tuple[Image.Image, int]], theme: str) -> list[tuple[bytes, int]]:
    """
    The pictures with the dialog beside them, a frame whenever either changes. The shorter one holds its last frame
    until the other ends
    """
    pictures = [(Image.open(io.BytesIO(data)), ms) for (data, ms) in models]
    (left, right) = (pictures[0][0], dialogs[0][0])
    size = (left.width + COMBINED_GAP + right.width, max(left.height, right.height))
    ends = lambda frames: [sum(ms for (_, ms) in frames[:index + 1]) for index in range(len(frames))]
    (pictureEnds, dialogEnds) = (ends(pictures), ends(dialogs))
    frames = []
    (shownPicture, shownDialog, at) = (0, 0, 0)
    for end in sorted(set(pictureEnds) | set(dialogEnds)):
        combined = Image.new('RGB', size, GIF_BACKGROUNDS[theme])
        (picture, dialog) = (pictures[shownPicture][0], dialogs[shownDialog][0])
        combined.paste(picture, (0, (size[1] - picture.height) // 2))
        combined.paste(dialog, (picture.width + COMBINED_GAP, (size[1] - dialog.height) // 2))
        frames.append((png(combined), end - at))
        at = end
        shownPicture = min(shownPicture + (end == pictureEnds[shownPicture]), len(pictures) - 1)
        shownDialog = min(shownDialog + (end == dialogEnds[shownDialog]), len(dialogs) - 1)
    return frames


def makeGif(gif: dict, pictures: str, out: str, themes: list[str], fontDir: str | None) -> list[str]:
    gif = {**DEFAULTS, **gif}
    paths = [os.path.join(pictures, f'{item["picture"]}.png') for item in gif['frames']]
    missing = [item['picture'] for (item, path) in zip(gif['frames'], paths) if not os.path.exists(path)]
    if missing:
        raise GifError(f'{gif["name"]}: no picture of {", ".join(missing)} in {pictures}, make them in Fusion first')
    captionFont = font(gif['captionSize'], fontDir)
    captions = [item.get('caption', '') for item in gif['frames']]
    written = []
    for theme in themes:
        stills = [picture(path, gif, theme) for path in paths]
        label = lambda image, index: captioned(image, captions[index], gif, theme, captionFont)
        path = os.path.join(out, f'{gif["name"]}-{theme}.gif')
        frames = timedFrames(stills, label, gif, timeline(gif, theme)) if gif.get('loopWith') else gifFrames(stills, label, gif)
        if gif.get('combine'):
            frames = combinedFrames(frames, dialogFrames(gif, theme), theme)
        save(frames, path)
        written.append(path)
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--only', nargs='*', help='names of the GIFs to make, all by default')
    parser.add_argument('--pictures', default=PICTURES_DIR, help='folder of the model pictures')
    parser.add_argument('--out', default=OUTPUT_DIR, help='folder the GIFs are written to')
    parser.add_argument('--themes', nargs='*', default=['light', 'dark'], choices=['light', 'dark'])
    parser.add_argument('--font-dir', help='folder of the Artifakt Element fonts, the Fusion install by default')
    parser.add_argument('--dialogs', action='store_true', help='record the dialog animations the GIFs loop with first')
    args = parser.parse_args()
    with open(GIFS_FILE, encoding='utf-8') as file:
        gifs = [gif for gif in json.load(file)['gifs'] if not args.only or gif['name'] in args.only]
    os.makedirs(args.out, exist_ok=True)
    dialogs = [gif['loopWith'] for gif in gifs if gif.get('loopWith')]
    if args.dialogs and dialogs:
        takeShots(DEFAULT_SHOTS_FILE, dialogs, None, None, None, args.font_dir)
    # one GIF missing a picture doesn't keep the others from being made
    failures = []
    for gif in gifs:
        try:
            for path in makeGif(gif, os.path.abspath(args.pictures), os.path.abspath(args.out), args.themes, args.font_dir):
                print(os.path.relpath(path, ROOT_DIR), flush=True)
        except GifError as err:
            failures.append(str(err))
            print(err, file=sys.stderr, flush=True)
    if failures:
        sys.exit(1)


if __name__ == '__main__':
    main()
