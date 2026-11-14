# Dialog screenshots

Screenshots of the bin and baseplate dialogs for the docs and release notes, in Fusion's dark and light themes, without
opening Fusion. Each command's own `command_created` runs against a fake of the Fusion API (`fakeAdsk`), so the inputs,
their values, what's enabled or hidden and what the drawings show all come from the add-in's code. `page/dialog.js` draws
the dialog the way Fusion does, with the add-in's own pages in it, and a headless browser captures it.

## Setup

```sh
python3 -m venv tools/screenshots/.venv
tools/screenshots/.venv/bin/pip install -r tools/screenshots/requirements.txt
```

It uses the installed Google Chrome. Without Chrome, run `tools/screenshots/.venv/bin/playwright install chromium`.
The dialog font, Artifakt Element, is taken from the Fusion install. Use `--font-dir` to point to it if it isn't found.

## Taking shots

```sh
tools/screenshots/.venv/bin/python tools/screenshots/screenshots.py                  # every shot in shots.json
tools/screenshots/.venv/bin/python tools/screenshots/screenshots.py --only bin-custom-shape-drawing --themes dark
tools/screenshots/.venv/bin/python tools/screenshots/dialogRecorder.py bin           # the inputs a shot can set
```

A shot in `shots.json`:

| Key | |
|---|---|
| `name` | File name, with `-dark` or `-light` added when it is taken in both themes |
| `command` | `bin` or `baseplate` |
| `values` | Input values by id, as the dialog saves its defaults. Lengths are in cm, or a string such as `"42 mm"`. Groups take `true` or `false` to expand or collapse them |
| `globals` | Values of the command's other state, such as `binShapeCells` or `compartmentPockets` |
| `defaults` | A saved `ui_input_defaults.json` to start from instead of the original defaults |
| `inputs` | Input ids to show. The shot takes the part of the dialog from the first to the last of them and tears the edges where it is cut. `<group id>:header` is the header of a group. Leave it out to take the whole dialog |
| `edge` | How cut edges look: `zigzag`, even teeth, the default, `wave` or `rough`, long uneven tears |
| `torn` | `false` for straight cut edges |
| `margin` | Space kept around the inputs, 10 px by default |
| `height` | Limits the dialog to this height and shows a scrollbar, like the dialog in Fusion. By default the whole dialog shows |
| `width` | Dialog width, as the command sets it by default |
| `themes` | `["dark"]`, `["light"]` or both, the default |
| `scale` | Pixels per dialog pixel, 2 by default |
| `output` | Folder for the images, from the add-in folder |
| `steps` | Makes the shot an animation, see below |
| `format` | `gif`, the default, or `webp` for an animated WebP with a transparent background |
| `background` | Color behind the dialog, GIFs default to GitHub's page color of the theme, as they can't fade a shadow into transparency |

## Animations

A shot with `steps` is a GIF of a cursor going through them. The dialog reacts through the command's own handlers and
the drawings are the add-in's pages receiving real mouse and keyboard input, so what changes, enables or shows up is
what Fusion would do. The frame stays the same size for the whole animation, large enough for the inputs at their
largest. Each step has one action:

| Step | |
|---|---|
| `{"click": "custom_shape"}` | Clicks a checkbox, a button or a group header, by input id |
| `{"click": {"page": "shape_browser", "selector": "#fill"}}` | Clicks something on a page, by CSS selector |
| `{"spin": {"input": "bin_width", "direction": "up", "times": 2}}` | Clicks a spinner arrow |
| `{"select": {"input": "bin_type", "item": "Shelled"}}` | Opens a dropdown and picks an item |
| `{"type": {"input": "bin_wall_thickness", "text": "0.8"}}` | Types in a field, in the input's units |
| `{"type": {"page": "compartments_browser", "selector": "input[type=text]", "text": "Screws"}}` | Types in a field on a page, then presses Enter unless `"enter": false` |
| `{"drag": {"page": "shape_browser", "selector": "svg", "from": [0.9, 0.1], "to": [0.9, 0.5]}}` | Drags on a page, from and to are fractions of the width and height of the selected element |
| `{"move": {"input": "bin_height", "part": "field", "at": [0.8, 0.5]}}` | Moves the cursor. A part is `field`, `checkbox`, `button`, `up` or `down` |
| `{"key": "Escape"}` | Presses a key on the focused page |
| `{"set": {"bin_height": 6}}` | Changes inputs without the cursor |
| `{"wait": 800}` | Holds the frame for some milliseconds |
| `{"cursor": false}` | Hides the cursor, `true` shows it again |
| `{"model": 2}` | Marks that a GIF of model pictures shown beside this one goes to its third picture as the dialog last changed, see below |

## Model pictures

Pictures of bins and baseplates come from Fusion itself: with the add-in running from a git checkout, Utilities >
Add-ins has a **Gridfinity docs: render models** button. It opens a palette docked on the right listing every preset
in `models/` with its saved picture, or **No picture**. **Create** or **Refresh** makes a preset's picture, **Refresh
all** makes every one and then the GIFs below, **Make GIFs** only the GIFs, **Open location** shows the folder of the
pictures in Finder or Explorer; presets are read again from their files each time, and clicks while pictures are being made
wait their turn. Click a picture to see it large, **Open file** opens it in the computer's image viewer.

A picture is made by building the preset in a new document with the add-in's own builders, hiding everything but the
bodies, setting up the view in Fusion's Photo Booth lighting and saving it, by default to
`documentation/assets/models/<preset>.png`. The document is closed without saving.

The palette also finishes the pictures, Fusion's Python has no imaging. Fusion renders the view at the viewport's
proportions and `supersample` times the picture's size, the palette's page cuts that to the model, fits it in the
picture with `margin` around it and scales it down, which smooths the edges. When the model touches an edge of the
render the camera moves back and renders again, up to 3 times; a picture still touching is saved and marked as
possibly cut off.

Each preset's result, with the full error of a failure, is written to `tools/screenshots/models-render.log`, started
anew whenever the palette is opened.

A preset has the `generator` and `settings` of a shape test case (see `tests/e2e/cases`, lengths in mm, angles in
degrees). `"extends": "_bin.json"` takes everything from another preset, so a preset only lists what differs.
`_bin.json` and `_baseplate.json` hold what the dialogs start with, files starting with `_` are only extended.

| Key | |
|---|---|
| `extends` | Another preset file to start from |
| `description` | What the picture shows, not passed on to presets extending this one |
| `generator`, `settings` | What to build, as in a test case |
| `view` | `isoTopRight`, the default, `isoTopLeft`, `isoBottomRight`, `isoBottomLeft`, `front`, `back`, `top`, `bottom`, `left` or `right`. Or `{"eye": [x, y, z], "target": [x, y, z], "up": [0, 0, 1]}` in mm. The bodies are fitted to the picture either way |
| `camera` | `perspective`, the default, or `orthographic` |
| `style` | `shadedWithEdges`, the default, `shaded`, `shadedWithHiddenEdges` or `wireframe` |
| `appearance` | An appearance from Fusion's library by name, such as `Plastic - Glossy (Black)`. A matte plastic without it |
| `color` | `#rrggbb` the appearance is turned into, `#4e79a7` by default, the blue of the dialogs' drawings. `null` keeps the appearance's own color, and Fusion's default look when there's no appearance either |
| `width`, `height` | Picture size in pixels, 2048 by default. The render behind it is `supersample` times larger, at most 6000 pixels |
| `transparent` | `false` for Fusion's background instead of a transparent one |
| `margin` | Space around the model, a share of the picture's width and height, `0.06` by default |
| `supersample` | How many times larger than the picture the render is, `3` by default |
| `exposure`, `saturation` | Stops a viewport picture is brightened by, as a camera's exposure, and how much its colors are deepened, `1` keeps them. `0.85` and `1.4` by default, which bring it close to a ray traced picture of Fusion's. Fusion's viewport has no setting for either, the palette applies them |
| `output` | Folder of the picture, from the add-in folder |

### GIFs of model pictures

`modelGifs.py` turns saved model pictures into a GIF that holds each one with a caption and cross-fades to the next,
for options shown side by side, such as the bin bottoms. The GIFs are listed in `modelGifs.json`: a `name` and the
`frames`, each a `picture`, the name of a preset, and a `caption`. `size` of the pictures in pixels, `hold` and `fade` in
milliseconds and `captionSize` are optional. `loopWith` names a dialog animation of `shots.json` going through the same
options, for the two to be shown side by side. Its `model` steps say which picture goes with what the dialog shows,
recording it saves when they happen to `timelines/<animation>-<theme>.json`, and the GIF fades to each picture at that
moment and is as long, so both change and loop together. `hold` doesn't apply to it. `"combine": true` puts the
dialog animation beside the pictures in the GIF itself, for one image instead of a pair. The dialog animations are
recorded to `tools/screenshots/dialogs`, which isn't kept in the repo, only the GIFs made from them are. Make the pictures in Fusion
first, then

    tools/screenshots/.venv/bin/python tools/screenshots/modelGifs.py [--only bin-bottom-options]

writes `documentation/assets/gif/<name>-light.gif` and `-dark.gif`, on GitHub's page colors as GIFs can't be partly
transparent. `--pictures` takes the pictures from another folder, `--dialogs` records the dialog animations of
`loopWith` first. A GIF missing a picture is reported and the others are still made.

The palette in Fusion lists the GIFs after the presets, each with its dialog animation in Fusion's theme, the pictures
it still needs, or that its pictures changed since it was made. Its **Create** or **Refresh** makes the pictures it
needs, then the GIF. The palette runs this script with `--dialogs` for it, once per GIF so its row shows the one being made, after **Refresh all** and for **Make GIFs**, with the Python of
`tools/screenshots/.venv`, so the screenshot tool has to be set up as above. Its output goes to the log of the
pictures.
