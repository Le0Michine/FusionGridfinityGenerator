# Principles

- **Follow the Gridfinity spec** as closely as possible to avoid compatibility issues. Some things deviate slightly to simplify the code or improve printability, but bins and baseplates should stay compatible with the rest of the ecosystem.
- **General usefulness.** It's impossible to support every design variation, so the add-in focuses on the generic things and gives a kick start for further customization in Fusion.
- **Keep the UI simple.** The more parameters there are, the harder the dialogs are to use and to maintain. A feature that needs a lot of its own inputs may be better as a dedicated command.
- **CAD best practices.** Sketches are fully defined, and simple features are preferred wherever possible.
- **Show how it's built.** The timeline of a generated model should read as an example of how a CAD designer would build it, not only arrive at a working shape by the shortest route. Repeated geometry is built once and patterned rather than copied by hand, dimensions come from parameters rather than numbers worked out in code, features are named after what they make. Someone opening the timeline should be able to learn from it and change it the way they'd change their own model.
- **Code defensively against Fusion releases:**
  - Don't assume how many elements an API collection has or what order they come in, that can and does change between Fusion releases.
  - Validate and filter the contents of collections before operations such as combine.
  - Avoid complex operations such as offset or face extend. They work well for a user in the UI, but can break after a new Fusion release.

# Keeping the model parametric

A generated bin or baseplate should stay editable in Fusion like a model drawn by hand, the add-in is a kick start, not the end of the design.

- **Build in the timeline.** The generators only work in designs with history, and refuse direct modeling designs. Don't build geometry outside the timeline, temporary B-Rep bodies or base features don't follow parameters and can't be edited later.
- **Feed dimensions as expressions.** Lengths go through `Dim` (`lib/gridfinityUtils/dim.py`): `Dim.length` for a fixed value, `Dim.parameter` for a user parameter. Combining dims keeps the expression, so a feature built from `heightU * heightUnit - 5 mm` follows the parameters it was built from, and the formula stays readable in the model.
- **User parameters** are made for what users are expected to change after generating, such as `gfBin1_heightU`, `gfBin1_heightUnit`, `gfBin1_baseWidth` and the label text, named by the first free number in the design. Add a parameter when a new input is something users will want to tweak in place, and make every feature depending on it use the expression.
- **Fully defined sketches**, constrained and dimensioned rather than placed, so they move with the parameters instead of breaking.
- **Name timeline features** after what they build, Foot, Lip notch cutouts pattern and so on, the feature helpers take a required name for that. A generated model is kept in one timeline group, rebuilding from **Gridfinity settings** relies on it.
- **Test parameter changes.** A snapshot case can set user parameters once built, the run compares the recomputed model with one built with those values from the start. Add such a case for a feature that should follow a parameter.

When only parameters changed, **Gridfinity rebuild** edits them instead of rebuilding, so features a user added after the bin stay attached. The more the model follows its parameters, the more often that works.

# Performance

Every feature after a change is recomputed, in the dialog's preview and later in the user's design, so both the number of features and the expensive ones, such as shells, fillets and large combines, add to how long a change takes.

- **Build once and pattern.** Build a single foot, socket cell or hole and pattern it, instead of a feature per copy. It's how the model should be built anyway, see the principles, and it's faster: baseplates are built from one socket cell patterned across the plate, which keeps large plates fast.
- **Combine tools into one feature.** Cut or join several tool bodies with a single combine instead of one feature each.
- **Defer sketch computing** while drawing a sketch with many entities, `sketchUtils.deferSketchCompute`.
- **Keep previews light.** The dialog's preview is rebuilt on every change. Leave out of it what doesn't change the shape, as the baseplate preview leaves out joint origins.
- **Measure.** The bin dialog shows the time of the last preview, and the log has the time of each build. Compare a large bin or baseplate before and after a change, the snapshot test report also has how long the whole run took.

# Setup

1. Clone the repository:
   ```
   git clone https://github.com/Le0Michine/FusionGridfinityGenerator.git
   ```
2. In Fusion, open **Utilities > Add-Ins** (`Shift + S`), press **+** on the **Add-Ins** tab and pick the folder containing `GridfinityGenerator.py`.
3. **Run** the add-in. Restart it from the same window after changing the code, Fusion doesn't reload it on its own.

Running from a git checkout also adds the development commands to **Utilities > Add-Ins**, releases ship without them:

- **Gridfinity tests: run** and **Gridfinity tests: update snapshots**, see [Tests](#tests)
- **Gridfinity docs: render models**, see [Documentation](#documentation)

# Code layout

| Folder | |
|---|---|
| `commands/` | A folder per command. `entry.py` builds its dialog and handles its events, the bin and baseplate commands build the model in `binBuilder.py` and `baseplateBuilder.py` |
| `lib/gridfinityUtils/` | The geometry: bases, bodies, lips, labels, and the constants of the spec in `const.py` |
| `lib/ui/` | Shared dialog parts: input state, defaults, config files, the pages shown in dialogs |
| `tests/` | Unit tests and the shape snapshot cases |
| `tools/` | Dialog screenshots, model pictures, label icon previews and the wiki builder |
| `documentation/` | Pictures for the README and the wiki, and the wiki pages themselves |

# Tests

**Unit tests** run without Fusion, against a stub of its API in `tests/stubs`:

```
python3 -m pytest
```

**Shape snapshot tests** build bins and baseplates in Fusion and compare them with recorded snapshots. Each case is a JSON file in `tests/e2e/cases` with the settings that differ from the defaults. Run them with **Gridfinity tests: run**, and record new snapshots with **Gridfinity tests: update snapshots** when a change to the shapes is intended. See the [snapshot tests README](../../tests/e2e/README.md).

When fixing a bug where a bin or baseplate fails to build, add a case with the settings that failed, so it stays fixed.

# Documentation

- **The wiki** is written in `documentation/wiki` and published by a GitHub workflow on each push to master, don't edit the wiki on GitHub. `<!-- default:<input id> -->` fills in an input's default from the dialog, so the pages follow changes to the defaults. Run `python3 tools/wiki/wikiPages.py check` to list the inputs a page doesn't mention yet.
- **Dialog screenshots** are taken without Fusion by `tools/screenshots`, from the commands' own code. See the [screenshots README](../../tools/screenshots/README.md).
- **Model pictures** are rendered in Fusion from presets in `tools/screenshots/models`, with **Gridfinity docs: render models**.

When a change adds or changes a dialog input, update its section on the wiki page and the screenshots that show it.

# Pull requests

- Keep a pull request to one feature or fix.
- Run the unit tests, and the snapshot tests when the change touches how the model is built.
- Include updated snapshots, screenshots and pictures in the same pull request as the change that needs them.
- Explain in the pull request why each snapshot changed, especially one whose change has no obvious connection to the feature or fix, such as a case of an unrelated option or a default that moved.
