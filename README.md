[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

## Description
Addin for Fusion 360 allowing quick generation of simple [gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) bins and baseplates. The created bodies are parametric and can be easily edited if needed before exporting. Bins have an option to be generated without cutout providing a kick start for specialized tool bins creation.

## Features

### Baseplates
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm

Not supported
- no weighted plates option right now

![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/baseplate-creation.gif)

### Bins
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm for base width and 7mm for the unit of height
- height is specified in base units and measured from the top of the base to the top of the bin body
- generated bins are stackable

Not supported
- no magnet/screw cutouts at the bottom right now
- no tab is automatically generated
- no scoop is automatically generated although it can be easily added in Fusion with a few clicks
- bins are generated stackable and have thicker walls `2.4mm` instead of `1.2mm` as in the original, at the moment there is no support for thinner walls

![](https://raw.githubusercontent.com/Le0Michine/FusionGridfinityGenerator/master/documentation/assets/bin-creation.gif)

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

## Credits

[Gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) by [Zack Freedman](https://www.youtube.com/c/ZackFreedman/about)

This work is licensed under the same license as Gridfinity, being a 
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg