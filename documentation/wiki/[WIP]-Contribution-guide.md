This page is currently work in progress.

- following the defined standards, trying to stick to the original spec as close as possible to avoid compatibility issues. There are some things which deviate slightly to simplify the code or improve printability, but the general approach is to retain compatibility.
- general usefulness. It's impossible to support every single design variation so the plugin is focused on most generic things and provides a kick start for further customization and design.
- keeping UI simple. That's related to previous one, UI should be as intuitive as possible and the more parameters are added the harder it is to maintain. For some features it might make sense to create dedicated commands with own inputs etc.
- sticking to CAD design best practices, eg sketches are fully defined, using simple features wherever possible
- some coding guidelines, based on experience, avoid assumptions about amount of elements in arrays or their order (that can and does often change between fusion releases), content of the arrays also has to be validated and filtered for operations like combine, avoid complex operations like offset, face extend etc, they work well for UI user but can also break after new fusion release.
