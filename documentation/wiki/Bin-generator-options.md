The bin dialog, under Create > Gridfinity bin in the Solid workspace, groups its options in sections, described here in the order the dialog shows them. Defaults are the dialog's original ones, **Save as defaults** in the Changes section replaces them with your own.

<img src="../assets/ui/fusion-dialog-bin-generator.png" alt="The bin dialog with its original defaults" width="500">

# Info

A link to this page and the add-in's version.

# Basic sizes

Changing these might affect compatibility with models created by the Gridfinity community, so it isn't recommended.

## Base width unit (mm)
Default: <!-- default:base_width_unit -->

The size of a single base section along the X axis.

## Base length unit (mm)
Default: <!-- default:base_length_unit -->

The size of a single base section along the Y axis.

## Bin height unit (mm)
Default: <!-- default:height_unit -->

The size of a single vertical section.

## Bin xy clearance (mm)
Default: <!-- default:bin_xy_tolerance -->

Horizontal clearance between neighbouring bins and between the bin base and the baseplate. A smaller value gives a tighter fit, a larger value a looser one.

The baseplate sockets follow the grid exactly, the bin stands the clearance in from the grid line on every side, its feet as well as its walls. So two bins side by side have twice the clearance between them, and each foot has the clearance all around it in its socket.

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/diagrams/bin-xy-clearance-dark.svg"><img src="../assets/diagrams/bin-xy-clearance-light.svg" alt="Cross section where two bins meet over a baseplate ridge: each bin stands the clearance in from the grid line and each socket reaches the clearance past it, twice the clearance between the bins and between each foot and its socket" width="600"></picture>

# Main dimensions

The size of the bin in base units, and its actual size in mm.

## Bin width, X (u)
Default: <!-- default:bin_width -->

The bin width in whole or half base units, the number of base sections along the X axis.

```
(bin width, mm) = (base width unit, mm) * (bin width) - 2 * (bin xy clearance, mm)
```

## Bin length, Y (u)
Default: <!-- default:bin_length -->

The bin length in whole or half base units, the number of base sections along the Y axis.

```
(bin length, mm) = (base length unit, mm) * (bin length) - 2 * (bin xy clearance, mm)
```

## Half grid
Default: <!-- default:half_grid -->

Puts the bin on half size feet, for a half grid baseplate, the bin keeps its size in base units. Without it a size ending in a half gets whole feet and a row of half feet along the back or right side, halved across the row only. Half feet have no magnet or screw holes, there is no room for them.

Whole feet | Half grid | Size ending in a half
:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/models/bin-half-grid-off.png" alt="Bin on whole feet"> | <img src="../assets/models/bin-half-grid-on.png" alt="Bin on half size feet"> | <img src="../assets/models/bin-half-grid-half-row.png" alt="Bin with a row of half feet">

## Bin height, Z (u)
Default: <!-- default:bin_height -->

The bin height in height units, from the bottom of the base to the top of the bin wall, the lip comes on top.

```
(bin height, mm) = (bin height unit, mm) * (bin height) + (lip height, mm)
```

The lip adds 3.8mm with **Trim lip top**, and nothing without a lip. Untrimmed its height depends on the clearance, 4.75 - sqrt(2) / 4 ≈ 4.396mm at the default 0.25mm:

```
(lip height, mm) = 5 - (1 + sqrt(2)) * (bin xy clearance, mm)
```

The height goes into a user parameter of the design, `gfBin1_heightU`, the number being the first one available in the design, so the next bin gets `gfBin2_heightU`. Changing it in Modify > Change Parameters makes the bin taller or lower without generating it again. The parameter is made only when the bin has a body, see **Generate body**.

## Custom shape
Default: <!-- default:custom_shape -->

Shows a drawing of the bin cells, click or drag across cells to leave them out of the bin or put them back, so the bin fills an L or another tetris like spot. **Fill all** puts every cell back, unticking the option does the same.

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-custom-shape-dark.gif"><img src="../assets/gif/bin-custom-shape-light.gif" alt="Drawing a bin shape, with the bin on every cell, then cells left out"></picture>

## Actual dimensions (mm)

The width, length and height of the bin in mm, as calculated above.

# Bin features

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-features-dark.gif"><img src="../assets/gif/bin-features-light.gif" alt="Changing the size, type and wall thickness of a bin, with the bin at each change"></picture>

## Generate body
Default: <!-- default:bin_generate_body -->

When unchecked only the base is generated. Sometimes might be useful to generate base and feet separately for especially complex configurations.

## Bin type
Default: <!-- default:bin_type -->

Hollow | Shelled | Solid
:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/models/hollow-bin.png" alt="Hollow bin"> | <img src="../assets/models/shelled-bin.png" alt="Shelled bin"> | <img src="../assets/models/solid-bin.png" alt="Solid bin">

### Hollow

An empty bin with a solid bottom above the base.

### Shelled

Like hollow, but shelled to an even wall thickness on the sides and the bottom, to save printing time and filament.

### Solid

A filled bin, intended as a start for further editing, for example subtracting another body from it to make a holder for a specific item.

<img src="../assets/gif/specialized-bin-nozzle-creation.gif" alt="Creating a holder for nozzles from a solid bin">

## Bin wall thickness
Default: <!-- default:bin_wall_thickness -->

Thickness of the bin walls, and of the bottom of a shelled bin.

## Generate lip for stackability
Default: <!-- default:with_lip -->

Adds a lip to the top of the bin, so bins can be stacked on top of each other. Without it the wall remains straight and the bin is slightly shorter.

## Generate lip notches
Default: <!-- default:with_lip_notches -->

Adds little notches along the edge of the lip preventing stacked bins from sliding. Note that the notches are relatively small and are less effective on larger bins.

<img src="../assets/models/bin-lip-notches.png" alt="Bin with lip notches, highlighted, where the feet of a bin stacked on top meet" width="400">

## Lip type
Default: <!-- default:lip_type -->

**Light** keeps the same contact geometry as the original profile but reduces the lip thickness.  
**Full** follows the original Gridfinity profile, narrowing to an inner tip with a support under it, and a scoop wall as thick as the tip.

## Trim lip top
Default: <!-- default:lip_top_trimmed -->

Cuts the top of the lip flat at 3.8mm, about 0.6mm lower, instead of the sharp edge of the original profile. It doesn't change the stacking height, but helps printing consistency, as depending on slicer settings a sharp top could come out 1-2 layers different between bins.

Light | Full | Full, not trimmed
:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/models/bin-lip-light.png" alt="Light lip, cut through"> | <img src="../assets/models/bin-lip-full.png" alt="Full lip, cut through"> | <img src="../assets/models/bin-lip-full-untrimmed.png" alt="Full lip with a sharp top, cut through">

## Fold long walls for stiffness
Default: <!-- default:wall_creases -->

Folds the walls of hollow and shelled bins in along shallow creases, origami style, so tall long walls bow less. A bin gets them when it's at least **Creased bin min height** tall and its longest wall is at least **Creased wall min length** long, in base units along the whole wall, corners included, see their defaults below. Walls are split into even panels up to the max panel length, walls shorter than a panel of the longest one stay flat. The scoop wall stays flat and doesn't count towards the length, the scoop braces it. A creased bin has a single compartment and a solid label tab.

Off | On | Shorter panels
:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/models/bin-creases-off.png" alt="Bin with flat walls"> | <img src="../assets/models/bin-creases-on.png" alt="Bin with creased walls"> | <img src="../assets/models/bin-creases-panels.png" alt="Bin with walls creased in shorter panels">

### Crease depth
Default: <!-- default:wall_crease_depth -->

How far the creases fold the wall in.

### Creased wall min length (u)
Default: <!-- default:wall_crease_min_length -->

The shortest wall that gets creases, in base units.

### Crease panel max length (u)
Default: <!-- default:wall_crease_max_panel_length -->

The longest panel between creases, in base units, a wall is split into as many even panels as it takes.

### Creased bin min height (u)
Default: <!-- default:wall_crease_min_height -->

The lowest bin that gets creases, in height units.

# Bin compartments

Splits the bin into compartments, a uniform grid, or merged cells for compartments of different sizes.

## Grid width and length
Default: <!-- default:compartments_grid_w --> by <!-- default:compartments_grid_l -->

The number of compartment grid cells along the X and the Y axis. Each cell is as wide as the bin width divided by the number of cells, and the same for the length.

## Edit compartment layout
Default: <!-- default:compartments_show_layout -->

Shows a drawing of the compartment grid. Drag across cells to merge them into a larger compartment, compartments it cuts through fall back to single cells. Click a compartment to select it and give it its own:
- **Label**, the text of its label tab, empty takes the text from the Label tab section
- **Icon** on its label
- **Depth**, from the top of the bin in mm, empty for the full depth

**Split** turns it back into single cells. Unticking the option resets the compartments to the uniform grid.

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-compartments-dark.gif"><img src="../assets/gif/bin-compartments-light.gif" alt="Merging compartments and naming one, with the bin as compartments are merged and labeled"></picture>

Uniform compartments | Custom compartments A | Custom compartments B
:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/ui/bin-uniform-compartments-options.png" alt="Uniform compartments options"> | <img src="../assets/ui/bin-custom-compartments-variant-a-options.png" alt="Custom compartments A options"> | <img src="../assets/ui/bin-custom-compartments-variant-b-options.png" alt="Custom compartments B options">
<img src="../assets/models/bin-uniform-compartments.png" alt="Bin with uniform compartments"> | <img src="../assets/models/bin-custom-compartments-variant-a.png" alt="Bin with custom compartments A"> | <img src="../assets/models/bin-custom-compartments-variant-b.png" alt="Bin with custom compartments B">

## Scoop

### Add scoop (along bin width)
Default: <!-- default:bin_has_scoop -->

Rounds the bottom edge at the front of the bin, along the X axis, so small parts can be scooped out. Each compartment gets its own scoop.

### Scoop max radius (mm)
Default: <!-- default:bin_scoop_max_radius -->

The largest radius of the scoop, it is smaller in bins too low for it.

No scoop | Scoop
:-------------------------:|:-------------------------:
<img src="../assets/models/bin-scoop-off.png" alt="Bin without a scoop"> | <img src="../assets/models/bin-scoop-on.png" alt="Bin with a scoop">

## Label tab

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-label-tab-options-dark.gif"><img src="../assets/gif/bin-label-tab-options-light.gif" alt="Changing the label tab length and position in the dialog, with the bin for each"></picture>

### Add label tab (along bin width)
Default: <!-- default:bin_has_tab -->

Adds a label tab along the top of the back wall, along the X axis. Each compartment gets its own tab, along its back wall.

### Tab length (u)
Default: <!-- default:bin_tab_length -->

The tab length along the X axis, in base units.

### Tab width (mm)
Default: <!-- default:bin_tab_width -->

How far the tab reaches into the bin, along the Y axis.

### Tab offset (u)
Default: <!-- default:bin_tab_position -->

The tab's distance from the left side of the compartment, in base units.

### Tab overhang angle
Default: <!-- default:bin_tab_angle -->

The angle of the underside of the tab, it can be adjusted for easier printing or to save a little space under the tab.

### Tab top angle
Default: <!-- default:bin_tab_top_angle -->

Tilts the tab top down towards the front, so the label faces the front of the bin.

Full length | Single slot | With offset | Angled top
:-------------------------:|:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/models/bin-label-tab-full.png" alt="Label tab as long as the bin"> | <img src="../assets/models/bin-label-tab-single-slot.png" alt="Label tab one base long"> | <img src="../assets/models/bin-label-tab-with-offset.png" alt="Label tab moved along the wall"> | <img src="../assets/models/bin-label-tab-angled.png" alt="Label tab with its top tilted to the front">

### Hollow tab
Default: <!-- default:bin_tab_hollow -->

Shells the tab with the wall thickness. With a single compartment it is opened through the back wall of the bin, with more compartments it is left closed. On by default for shelled bins.

<img src="../assets/models/bin-label-tab-hollow.png" alt="Bin cut through its middle, its label tab hollow and open through the back wall" width="400">

### Open through side walls
Default: <!-- default:bin_tab_hollow_sides -->

Also opens a hollow tab through the side walls of the bin where it runs into them, not only through the back wall. Only for a single compartment.

### Label text
Default: empty

Text on every compartment label, compartments in the layout drawing can have their own. Each label gets a text parameter, `gfBin1_label`, or `gfBin1_label1`, `gfBin1_label2` and so on with more compartments, numbered like the height parameter, so it can be changed later in Modify > Change Parameters without generating the bin again.

### Label icon
Default: <!-- default:bin_tab_label_icon -->

An icon of a screw, nut or washer before the label text.

<!-- label-icons -->

### Label style
Default: <!-- default:bin_tab_label_style -->

- **Outline** splits the tab face along the label, so a slicer can print it in a color of its own. The label shows in its own color in Fusion, and **Gridfinity export** from the right-click menu paints it for the slicer
- **Engraved** cuts the label into the tab
- **Embossed** raises the label from a lowered tab

### Bold label text
Default: <!-- default:bin_tab_label_bold -->

Sets the label text in bold.

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-label-options-dark.gif"><img src="../assets/gif/bin-label-options-light.gif" alt="Typing label text, picking an icon and each label style, with the bin at each change"></picture>

# Base interface features

The bottom of the bin, which makes it fit a Gridfinity baseplate.

<picture><source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-bottom-options-dark.gif"><img src="../assets/gif/bin-bottom-options-light.gif" alt="Going through the bottom options in the dialog, with the bin for each"></picture>

## Generate base
Default: <!-- default:bin_generate_base -->

When unchecked the bin is generated without the base, which can be useful for vase mode printing or generic boxes.

## Add joint origins
Default: <!-- default:bin_joint_origins -->

A joint origin at the bottom center of every foot, to joint the bin into baseplate sockets.

## Add screw holes
Default: <!-- default:bin_screw_holes -->

Adds a screw hole in each corner of every base section, 26mm apart, to screw the bin down.

## Screw hole diameter
Default: <!-- default:screw_diameter -->

The diameter of the screw holes, for screws of other sizes.

## Add magnet sockets
Default: <!-- default:bin_magnet_cutouts -->

Adds sockets for magnets to glue or press in after printing. Together with screw holes the sockets get grooves, so they print bridged without supports.

## Add tabs to magnet sockets
Default: <!-- default:bin_magnet_cutouts_tabs -->

Adds small cutouts around the magnet sockets, which make the magnets easier to take out. Especially useful for press fit magnets, but also for glued ones.

## Magnet cutout diameter
Default: <!-- default:magnet_diameter -->

The diameter of the magnet sockets, for magnets of other sizes or a snug fit without glue.

## Magnet cutout depth
Default: <!-- default:magnet_height -->

The depth of the magnet sockets, for magnets of other sizes.

Screw holes | Magnet sockets | Magnet sockets with tabs | Both, with grooves
:-------------------------:|:-------------------------:|:-------------------------:|:-------------------------:
<img src="../assets/models/bin-screw-holes.png" alt="Bin bottom with screw holes"> | <img src="../assets/models/bin-magnet-cutouts.png" alt="Bin bottom with magnet sockets"> | <img src="../assets/models/bin-magnet-cutouts-with-tabs.png" alt="Bin bottom with tabbed magnet sockets"> | <img src="../assets/models/bin-magnet-cutouts-and-screw-holes-with-groove.png" alt="Bin bottom with magnet sockets, screw holes and grooves">

# Changes

Keeps the dialog's inputs between bins and Fusion sessions.

- **Save as defaults** saves the current inputs as the dialog's new defaults, the dialog opens with them
- **Reset to defaults** sets the inputs back to the saved defaults
- **Clear defaults** wipes the saved defaults and sets the inputs back to the original ones
- **Save to file** saves the settings to a JSON file, **Load from file** sets the inputs from one
- **Copy** copies the settings to the clipboard as JSON

A generated bin keeps its settings, its right-click menu shows them in **Gridfinity settings**, **Gridfinity rebuild** builds it again in place with changed settings and **Gridfinity clone** opens this dialog with them.

# Preview

Shows the bin before **OK** is clicked, to make adjustments first.

## Show auto update preview (slow)
Default: <!-- default:show_preview -->

Updates the preview on every change of the inputs. It can be slow for large bins or many compartments, **Update preview once** is better for those.

## Update preview once

Shows the preview once, any change of the inputs hides it until clicked again.

## Last preview

How long the last preview took.
