## Description
Addin for Fusion 360 allowing quick generation of simple [gridfinity](https://www.youtube.com/watch?v=ra_9zU-mnl8) bins and baseplates. The created bodies are parametric and can be easily edited if needed before exporting. Bins have an option to be generated without cutout providing a kick start for specialized tool bins creation.

## Features

### Baseplates
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm

Not supported
- no weighted plates option right now

### Bins
- accepts amount of bases X and Y directions
- base measurement can be changed, default is 42mm for base width and 7mm for the unit of height
- height is specified in base units and measured from the top of the base to the top of the bin body

Not supported
- no magnet/screw cutouts at the bottom right now
- no tab is automatically generated
- no scoop is automatically generated although it can be easily added in Fusion with a few clicks

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