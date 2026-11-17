[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

## Description
Add-In for Fusion 360 allowing quick generation of simple [gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) bins and baseplates. The created bodies are parametric and can be easily edited if needed before exporting. Bins have an option to be generated solid providing a kick start for specialized tool bins creation.

## Features

Each option is described in details on the project [wiki page](https://github.com/Le0Michine/FusionGridfinityGenerator/wiki).

Bin options | Baseplate options
:-------------------------:|:-------------------------:
<img src="documentation/assets/ui/fusion-dialog-bin-generator.png" alt="Bin dialog"> | <img src="documentation/assets/ui/fusion-dialog-baseplate-generator.png" alt="Baseplate dialog">

### Baseplates
- **Size**
  - number of bases along X and Y, or fill an area, e.g. a drawer, with the grid fitted into it
  - base measurement can be changed, default is 42mm
  - a filled area is split into pieces fitting the print bed, picked from popular printers or entered by hand, with a preview of the pieces
  - the grid can be centered or pushed to a side, space left past it takes a row of half cells or solid padding
- **Type**
  - light, a thin plate to save filament
  - full, a thick plate with room for magnets and screws
  - skeletonized, a thick plate with its bottom cut away to save weight, leaving room for connection holes between plates for a screw or a glued in pin
- **Features**
  - magnet sockets and screw holes with countersunk heads, all adjustable in size
  - padding on any side and under the sockets, and the top trimmed so bins sit on their feet
  - joint origins at the bottom of every socket, to joint bins into it
- **Settings** can be saved as the dialog defaults, saved to or loaded from a JSON file or copied to the clipboard

#### Fill an area
Enter the size of a drawer or any other area and pick your printer, the grid is fitted into the area and split into pieces fitting the print bed

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/baseplate-fill-area-dark.gif"><img src="documentation/assets/gif/baseplate-fill-area-light.gif" alt="Switching to fill area, entering the area length and switching between Prusa printers, with the baseplate pieces for each"></picture>

#### Baseplate types
<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/baseplate-types-dark.gif"><img src="documentation/assets/gif/baseplate-types-light.gif" alt="Picking each baseplate type, with light, skeletonized and full baseplates"></picture>

#### Connection holes
Skeletonized baseplates can have holes between them for a screw or a glued in pin, their size can be adjusted

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/baseplate-connection-holes-dark.gif"><img src="documentation/assets/gif/baseplate-connection-holes-light.gif" alt="Turning on connection holes and changing their diameter, with a skeletonized baseplate without, with 3.2 mm and with 5 mm connection holes"></picture>

### Bins
- **Size**
  - width and length in bases, whole or half, height in height units, 1 unit is added to the height for the bin bottom
  - base measurement can be changed, default is 42mm for base width and 7mm for the unit of height
  - half grid puts the bin on half size feet, so it can sit offset by half a base on the baseplate
  - you can play tetris with your bins defining custom shapes `▀█▀ █▄▄ ▄█▀ ██ ▀▀▀▀`
- **Body**
  - hollow, shelled with constant wall thickness to save printing time and filament, or solid as a start for specialized tool bins
  - lip for stackability, light or full as the original Gridfinity profile, its top trimmed flat or left sharp, with optional notches preventing stacked bins from sliding, or a straight wall
  - long walls of tall hollow and shelled bins can be folded in along creases, origami style, greatly increasing stiffness
  - base or body can be generated on their own, to combine them with an existing model
- **Compartments** in a uniform layout, or an easy to use configurator for more complex, irregular ones
- **Scoop** along the bin width, with an adjustable max radius
- **Label tab**
  - adjustable length, offset and overhang angle, top can be tilted to face the front
  - can be hollow, opened through the back wall of the bin and optionally its side walls
  - label with text and an icon, outlined for a slicer to color it, engraved or embossed
  - outlined label text shows in a color of its own in Fusion, and the export paints it for the slicer
  - label text can be changed later in the user parameters, without generating the bin again
- **Base**
  - magnet sockets, sized for a snug fit of the magnets, optionally with tabs holding them in
  - screw holes of adjustable diameter, with a groove for printability when combined with magnet sockets
  - joint origins at the bottom of every foot, to joint the bin into baseplate sockets
- **Settings** can be saved as the dialog defaults, saved to or loaded from a JSON file, copied to the clipboard or cloned into a new bin, also from its right-click menu
- **Rebuild** a generated bin or baseplate with changed settings, from its right-click menu or its settings window, it's built again at its place in the timeline and the features after it keep working on the new body. Features picked on a face or an edge of the old body are listed to pick again. For a bin, changing only what its parameters hold, like the height or label text, sets them instead, without building it again
- **Export** bins and baseplates from their right-click menu, all of them at once into one 3MF with the label text painted in a color of the slicer, or into an STL or STEP file each

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-features-dark.gif"><img src="documentation/assets/gif/bin-features-light.gif" alt="Changing the size, type and wall thickness of a bin, with the bin at each change"></picture>

#### Bin bottom options
<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-bottom-options-dark.gif"><img src="documentation/assets/gif/bin-bottom-options-light.gif" alt="Going through the bottom options in the dialog, with the bin for each"></picture>

#### Bin half base size

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-half-grid-dark.gif"><img src="documentation/assets/gif/bin-half-grid-light.gif" alt="Turning on half grid, then a size ending in a half, with bins on whole, half and a row of half bases"></picture>

#### Bin type options
Hollow bin | Shelled bin | Solid bin
:-------------------------:|:-------------------------:|:-------------------------:
<img src="documentation/assets/models/hollow-bin.png" alt="Hollow bin"> | <img src="documentation/assets/models/shelled-bin.png" alt="Shelled bin"> | <img src="documentation/assets/models/solid-bin.png" alt="Solid bin">

#### Stacking lip

The lip adds a stacking interface to the top of the bin. By default the **light** lip profile is used, it retains the same contact geometry but reduces lip thickness. The **full** option follows the original Gridfinity profile, which has two steps following the full base profile. **Trim lip top** cuts the top of the lip flat, it does not change stacking height but helps with printing consistency, as depending on slicer parameters the resulting bins could differ by 1-2 layers when the lip is modelled with a sharp top.

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-lip-dark.gif"><img src="documentation/assets/gif/bin-lip-light.gif" alt="Switching the lip type to full and unchecking the lip top trim, with the bin cut through its middle for each"></picture>

#### Creased walls for stiffer bins

Long walls of tall hollow and shelled bins are folded in along shallow creases, greatly increasing stiffness. Bins from the min height
with a wall from the min length get them, walls are split into even panels up to the max panel length. The scoop wall
stays flat, the scoop braces it, and a creased bin has a single compartment and a solid label tab

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-creases-dark.gif"><img src="documentation/assets/gif/bin-creases-light.gif" alt="Turning on creases and folding the walls in panels of 2 units, with the bin for each"></picture>

#### Custom bin shape

The cells of the bin can be picked on its grid, for bins such as an L or a T.

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-custom-shape-dark.gif"><img src="documentation/assets/gif/bin-custom-shape-light.gif" alt="Drawing a bin shape, with the bin on every cell, then cells left out"></picture>

#### Bin compartments options

Detailed configuration options are on the [wiki](https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Bin-generator-options#bin-compartments)

Uniform compartments | Custom compartments A | Custom compartments B
:-------------------------:|:-------------------------:|:-------------------------:
<img src="documentation/assets/ui/bin-uniform-compartments-options.png" alt="Uniform compartments options"> | <img src="documentation/assets/ui/bin-custom-compartments-variant-a-options.png" alt="Custom compartments A options"> | <img src="documentation/assets/ui/bin-custom-compartments-variant-b-options.png" alt="Custom compartments B options">
<img src="documentation/assets/models/bin-uniform-compartments.png" alt="Bin with uniform compartments"> | <img src="documentation/assets/models/bin-custom-compartments-variant-a.png" alt="Bin with custom compartments A"> | <img src="documentation/assets/models/bin-custom-compartments-variant-b.png" alt="Bin with custom compartments B">

Compartments are merged by dragging across the cells, and can be named for the label tab

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-compartments-dark.gif"><img src="documentation/assets/gif/bin-compartments-light.gif" alt="Merging compartments and naming one, with the bin as compartments are merged and labeled"></picture>

#### Bin label tab configuration
<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-label-tab-options-dark.gif"><img src="documentation/assets/gif/bin-label-tab-options-light.gif" alt="Changing the label tab length and position in the dialog, with the bin for each"></picture>

#### Bin labels
A label tab can carry text and an icon, outlined for a slicer to color it, engraved or embossed

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/gif/bin-label-options-dark.gif"><img src="documentation/assets/gif/bin-label-options-light.gif" alt="Typing label text, picking an icon and each label style, with the bin at each change"></picture>

#### Bin scoop feature
Scoop enabled | Scoop disabled
:-------------------------:|:-------------------------:
<img src="documentation/assets/models/bin-scoop-on.png" alt="Bin with a scoop"> | <img src="documentation/assets/models/bin-scoop-off.png" alt="Bin without a scoop">


#### Hollow bin
![](documentation/assets/gif/bin-with-cutout-creation.gif)

#### Specialized Bin

Creating a 4x2 bin to hold oversized volcano nozzle
![](documentation/assets/gif/specialized-bin-nozzle-creation.gif)

Bin for random round things
![](documentation/assets/gif/specialized-bin-creation.gif)

### Settings and rebuild
Right-click a generated bin or baseplate for its settings, to rebuild it in place with changed settings or to clone it into a new one. The settings window shows what it was built with, saves them to a file, copies or clones them

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/ui/context-menu-gridfinity-scene-dark.png"><img src="documentation/assets/ui/context-menu-gridfinity-scene-light.png" alt="Fusion's right-click menu opened on a bin, the pointer on Gridfinity clone below Gridfinity settings and Gridfinity rebuild" width="508"></picture>

### Export
Right-click a bin or baseplate, or a component holding them, and pick Gridfinity export. It exports the selected bodies, or every visible bin and baseplate with All Gridfinity bodies, into:
- **3MF**, one file with all of them, as they're laid out in the design. With Color label text, the text of outlined labels is painted with the label color index, so Bambu Studio, OrcaSlicer and PrusaSlicer print it in that color of their list without painting it by hand
- **STL** or **STEP**, a file of each body, named after it, at the origin with its bottom at zero whatever its place in the design

3MF and STL bodies are meshed at Fusion's very high quality

Color index metadata is stored in 3MF and is read by modern slicers to assign appropriate color/tool to the text faces.

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/ui/context-menu-export-scene-dark.png"><img src="documentation/assets/ui/context-menu-export-scene-light.png" alt="Fusion's right-click menu opened on a bin, the pointer on Gridfinity export below Properties" width="508"></picture>

<picture><source media="(prefers-color-scheme: dark)" srcset="documentation/assets/ui/fusion-dialog-export-dark.png"><img src="documentation/assets/ui/fusion-dialog-export-light.png" alt="The Gridfinity export dialog, 4 bodies selected for one 3MF in Downloads, the label text colored with color index 2" width="500"></picture>

## Installation

### Via Autodesk App Store

- Download GridfinityGenerator installer from [Autodesk App Store](https://apps.autodesk.com/FUSION/en/Detail/Index?id=7197558650811789) ([MacOS](https://apps.autodesk.com/FUSION/en/Detail/Index?id=7197558650811789&os=Mac&appLang=en) | [Windows](https://apps.autodesk.com/FUSION/en/Detail/Index?id=7197558650811789&os=Win64&appLang=en))
- Run installer and wait for installation to complete, it will automatically close
- Relaunch Fusion 360
- `Gridfinity bin` and `Gridfinity baseplate` options should appear in `Create` menu in the Solid body workspace environment


### From source code
#### Step 1: Download

Download code into a location on your hard drive.
- Option 1: Clone git repository

```
git clone https://github.com/Le0Michine/FusionGridfinityGenerator.git
```
- Option 2: Download ZIP file
  - Use [latest release page](https://github.com/Le0Michine/FusionGridfinityGenerator/releases) to download ZIP file `GridfinityGenerator-vX.X.X.X.zip`. The release page should contain latest stable version. Alternatively you can choose to use `Code / Download ZIP` option (or use this [direct link to the zip](https://github.com/Le0Michine/FusionGridfinityGenerator/archive/refs/heads/master.zip)) to download most recent changes which aren't released yet.
  - Unpack content of the ZIP file into your target location

#### Step 2: Install as Add-In to Fusion 360
- In Fusion open `Scripts and Add-Ins` window by pressing `Shift + S`.
  - It can also be found in the UI `Design -> Utilities -> ADD-INS`
- Select `Add-Ins` tab and press `+` icon to add new add in
- Select path to the repository downloaded in Step 1. Choose the folder containing `GridfinityGenerator.py`.
- `GridfinityGenerator` should appear in the list of add ins
- Select `GridfinityGenerator` and click `Run` to launch the add in
- `Gridfinity bin` and `Gridfinity baseplate` options should appear in `Create` menu in the Solid body workspace environment

## Update

To update the script download latest sources into the same location and relaunch Fusion. If you used Autodesk app store to install the addon please follow the same link then download and install the latest version from there.

## Support the project

The plugin is free. However, if you want to support the project you can do so by [buying me a coffe](https://www.buymeacoffee.com/levmishin).

## Credits

[Gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) by [Zack Freedman](https://www.youtube.com/c/ZackFreedman/about)

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
