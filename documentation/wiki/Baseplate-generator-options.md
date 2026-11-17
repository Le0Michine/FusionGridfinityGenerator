# Basic size
Changing these parameters might affect compatibility with models created by Gridfinity community, so it ins't recommended. However it might be useful if you want to get something what meets your specific needs, for example if you want to create bins which are half standard grid wide to fill the gap in your drawer.

## Base width unit, X (mm)
Default: 42mm

This is the size of a base width unit. It defines the width and length of a single base section and measured along X axis.


## Base length unit, Y (mm)
Default: 42mm

This is the size of a base length unit. It defines the width and length of a single base section and measured along Y axis.

## Bin xy clearance (mm)
Default: 0.25mm

Horizontal clearance between bin base and baseplate surfaces. **Important:** this parameter should match xy clearance for the bins


# Main dimensions

This section allows you to specify main dimensions of baseplate.

## Plate width (u)

Total plate width specified in width units. This number would define amount of base sections along X axis.

## Plate length (u)

Total bin length specified in length units. This number would define amount of base sections along Y axis.

# Features

Configure baseplate features

## Baseplate type

### Light

Default minimalistic option. Requires less material to produce, ideal for drawers and other static applications. Doesn't support magnets or screw holes.

### Skeletonized

More rigid option which allows carrying around. Also supports magnet sockets and/or screw holes for more secure bin placement. Unlike Full variant allows connection holes on the sides which can be used to bolt multiple plates together.

### Full

The heaviest option. Takes forever to print, uses obscene amount of material.

## Magnet cutouts

Only relevant for Skeletonized and Full types.

### Add magnet cutouts

When enabled will generate sockets for magnets

### Magnet cutout diameter

Allows to customize magnet socket diameter for snug fit or to accomodate non standard magnet size.

### Magnet cutout depth

Customize magnet socket depth for non standard magnet size

## Screw holes

Only relevant for Skeletonized and Full types.

### Add screw holes

When enabled will generate screw holes which can be used to secure bins with screws from the bottom

### Screw hole diameter

Adjust hole diameter to better fit your screw size.

### Screw head cutout diameter

Adjust countersink size at the bottom for custom screws.

## Side padding
### Add side padding

When checked will generate padding bodies around baseplate sides. This allows to fill gaps between baseplate and drawer edges to prevent it from sliding around.

### Padding left

0 - disabled. When greater than 0 will generate padding on the left side of the baseplate (-X direction)

### Padding top

0 - disabled. When greater than 0 will generate padding on the top side of the baseplate (+Y direction)

### Padding right

0 - disabled. When greater than 0 will generate padding on the right side of the baseplate (+X direction)

### Padding bottom

0 - disabled. When greater than 0 will generate padding on the bottom side of the baseplate (-Y direction)

## Advanced plate size options
### Extra bottom thickness

Only relevant for Skeletonized and Full types. Make thicker plates for more rigidity and weight.

### Clearance between baseplate and bin

Vertical clearance between baseplate and bins. Could be useful to get flatter or sharper edge.

### Add connection holes

Only relevant for Skeletonized type. Adds holes on the sides of the baseplate which can be used to connect multiple plates with screws or glue them with pieces of filament.

### Connection hole diameter

Customize connection hole diameter to fit your fastener type.

# Inputs

## Save as new defaults

Saves input values as new default values which will persist even after fusion is closed. Between model creations inputs are preserved and do not reset to the default values automatically, for that to happen you need to click `Reset to defaults`

## Reset to defaults

Resets state of all inputs to the previously saved default values.

## Wipe saved settings

Deletes saved default values and resets all input values to the state of clean installation.

# Preview

## Show preview (slow)

Enables live preview of the baseplate. Might work slower for large grids as this function effectively would generate the whole model based on the provided inputs.