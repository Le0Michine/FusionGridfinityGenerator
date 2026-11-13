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
tools/screenshots/.venv/bin/python tools/screenshots/screenshots.py --only bin-custom-shape --themes dark
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
