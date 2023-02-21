[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

## Description
Addin for Fusion 360 allowing quick generation of simple [gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) bins and baseplates. The created bodies are parametric and can be easily edited if needed before exporting. Bins have an option to be generated solid providing a kick start for specialized tool bins creation.

## Features

Bin options | Baseplate options
:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/fusion-dialog-bin-generator.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/fusion-dialog-baseplate-generator.png)

### Baseplates
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm
- there are options to generate thick plate with magnet or/and screw cutouts
- thick plate can be skeletonized to reduce weight and allow for connection holes support
- size of magnet cutouts and screw holes can be adjusted

#### Baseplate types
Light | Skeleton with connection holes | Full
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-light.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-skeleton.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-full.png)

![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/baseplate-creation.gif)

### Bins
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm for base width and 7mm for the unit of height
- height is specified in base units and measured from the top of the base to the top of the bin body
- generated bins can have a lip for better stackability or a straight wall
- wall thickness can be adjusted
- there are options available for magnet or screw holes
- when magnet and screw holes are enabled together a groove will be generated to help with printability
- bin can be shelled with constant wall thickness to save printing time
- label tab can be generated (length, offset and overhang angle are adjustable)
- can generate only base or bin body part

Not supported at the moment
- no compartment walls configuiration available

#### Bin bottom options
Solid bottom | With screw holes | With magnet cutouts | Combined
:-------------------------:|:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-solid-bottom.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-screw-holes.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-magnet-cutouts.png)  | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-magnet-cutouts-and-screw-holes-with-groove.png)

#### Bin type options
Hollow bin | Shelled bin | Solid bin
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/hollow-bin.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/shelled-bin.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/solid-bin.png)

#### Bin label tab configuration
Full length | Single slot | With offset
:-------------------------:|:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-label-tab-full.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-label-tab-single-slot.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-label-tab-with-offset.png)

#### Bin scoop feature
Scoop enabled | Scoop disabled
:-------------------------:|:-------------------------:
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-scoop-on.png) | ![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-scoop-off.png)


#### Hollow bin
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/bin-with-cutout-creation.gif)

#### Specialized Bin
![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/gif/specialized-bin-creation.gif)

## Installation

- Download code into a location on your hard drive.

```
git clone https://github.com/Le0Michine/FusionGridfinityGenerator.git
```

- In Fusion open `Scripts and Addins` window by pressing `shift + s`. It is also can be found in the UI `Design -> Utilities -> ADD-INS`
- Select addins tab and press `+` icon to add new add in
- Select path to the repository downloaded on the first step, `GridfinityGenerator` should appear in the list of add ins
- Select `GridfinityGenerator` and click run to launch the add in
- `Gridfinity bin` and `Gridfinity baseplate` options should apperar in `Create` menu in the Solid body worspace environment

## Update

To update the script download latest sources into the same location and relaunch fusion.

## Credits

[Gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) by [Zack Freedman](https://www.youtube.com/c/ZackFreedman/about)

This work is licensed under the same license as Gridfinity, being a 
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg