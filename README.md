[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

## Description
Add-In for Fusion 360 allowing quick generation of simple [gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) bins and baseplates. The created bodies are parametric and can be easily edited if needed before exporting. Bins have an option to be generated solid providing a kick start for specialized tool bins creation.

## Features

Each option is described in details on the project [wiki page](https://github.com/Le0Michine/FusionGridfinityGenerator/wiki).

Bin options | Baseplate options
:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/fusion-dialog-bin-generator.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/fusion-dialog-baseplate-generator.png)

### Baseplates
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm
- there are options to generate thick plate with magnet or/and screw holes
- thick plate can be skeletonized to reduce weight, it also allows room for connection holes which can be customized to fit certain screw size or glue in pin
- size of magnet sockets and screw holes can be adjusted

#### Baseplate types
Light | Skeleton with connection holes | Full
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-light.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-skeleton.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-full.png)

![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/baseplate-creation.gif)

### Bins
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm for base width and 7mm for the unit of height
- height is specified in base units, 1 unit will be added to the input to accomodate bin bottom
- generated bins can have a lip for better stackability or a straight wall
- lip can have notches preventing bins from sliding when stacked
- wall thickness can be adjusted
- magnet sockets can be customized to allow snug fit of the magnets, or a different size
- screw holes diameter can be adjusted
- when magnet and screw holes are enabled together, a groove will be generated to help with printability
- bin can be shelled with constant wall thickness to save printing time and filament
- label tab can be generated (length, offset and overhang angle are adjustable)
- allows generation of base or body separately, could be useful if need combine it with existing model
- compartments can be configured to use uniform scale
- custom compartmens layout is based on the uniform grid and allows merging multiple cells together, specifying custom depth and position

#### Bin bottom options
Solid bottom | With screw holes | With magnet cutouts | Combined
:-------------------------:|:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-solid-bottom.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-screw-holes.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-magnet-cutouts.png)  | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-magnet-cutouts-and-screw-holes-with-groove.png)

#### Bin half base size

Half base (21x21mm) |
:---:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-half-size-base.png)

#### Bin type options
Hollow bin | Shelled bin | Solid bin
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/hollow-bin.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/shelled-bin.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/solid-bin.png)

#### Bin compartments options

Detailed configuration options are on the [wiki](https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Bin-generator-options#grid-type)

Uniform compartments | Custom compartments A | Custom compartments B
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-uniform-compartments-options.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-custom-compartments-variant-a-options.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-custom-compartments-variant-b-options.png)
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-uniform-compartments.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-custom-compartments-variant-a.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-custom-compartments-variant-b.png)

#### Bin label tab configuration
Full length | Single slot | With offset
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-label-tab-full.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-label-tab-single-slot.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-label-tab-with-offset.png)

Note: Default label size uses 12mm continuous labels from label printers such as Brother PTP700 (higher res, PC or Mac only), PTP300BT (lower res, mobile app only), DYMO LetraTag® 200B.

#### Bin scoop feature
Scoop enabled | Scoop disabled
:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-scoop-on.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-scoop-off.png)


#### Hollow bin
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/bin-with-cutout-creation.gif)

#### Specialized Bin

Creating a 4x2 bin to hold oversized volcano nozzle
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/specialized-bin-nozzle-creation.gif)

Bin for random round things
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/specialized-bin-creation.gif)

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

The plugin is free. However, if you want to support the project you can do so by [buying me a coffe](https://www.buymeacoffee.com/levmishin) or subscribing on patreon https://www.patreon.com/levmishin.

## Credits

[Gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) by [Zack Freedman](https://www.youtube.com/c/ZackFreedman/about)

This work is licensed under the same license as Gridfinity, being a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
