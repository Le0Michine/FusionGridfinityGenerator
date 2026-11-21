PRINT_BED_CUSTOM = 'Custom'

# usable bed size X, Y in mm. Bambu Lab's from Bambu Studio's printer profiles, printable_area, apart by where they put
# the purge tower and what they keep free, see PURGE_ANCHORS and EXCLUDED_AREAS
PRINT_BED_SIZES: dict[str, tuple[float, float]] = {
    'Bambu Lab A1 mini': (180, 180),
    'Bambu Lab A1': (256, 256),
    'Bambu Lab A2L': (330, 320),
    'Bambu Lab P1P, P1S, X1, X1C, X1E': (256, 256),
    'Bambu Lab P2S, X2D': (256, 256),
    'Bambu Lab H2C': (330, 320),
    'Bambu Lab H2D, H2D Pro': (350, 320),
    'Bambu Lab H2S': (340, 320),
    'Bambu Lab H3C': (330, 320),
    'Prusa MINI': (180, 180),
    'Prusa MK3, MK4': (250, 210),
    'Prusa CORE One': (250, 220),
    'Prusa XL': (360, 360),
    'Creality Ender-3': (220, 220),
    'Creality K1, K1C': (220, 220),
    'Creality K1 Max': (300, 300),
    'Elegoo Neptune 4': (225, 225),
    'Voron 0': (120, 120),
    'Voron 250': (250, 250),
    'Voron 300': (300, 300),
    'Voron 350': (350, 350),
}

def presetLabel(name: str) -> str:
    (width, length) = PRINT_BED_SIZES[name]
    return f'{name} ({width:g} x {length:g} mm)'

# labels are what the dropdown shows and saved dialog defaults store, keep them stable, a label gone from the list
# opens as custom with its size
PRINT_BED_PRESETS: dict[str, tuple[float, float]] = {presetLabel(name): size for (name, size) in PRINT_BED_SIZES.items()}

def presetBedSize(label: str) -> tuple[float, float] | None:
    """Bed size in Fusion internal units, cm"""
    if label not in PRINT_BED_PRESETS:
        return None
    (width, length) = PRINT_BED_PRESETS[label]
    return (width / 10, length / 10)

# Where the slicer puts the purge tower, its corner nearest the bed's origin as a share of the bed's width and length,
# Bambu Studio's default_wipe_tower_pos of the printer profiles. Other printers and custom beds get the back right
# corner, where the tower has to be moved by hand
DEFAULT_PURGE_ANCHOR = (1.0, 1.0)
PURGE_ANCHORS: dict[str, tuple[float, float]] = {
    'Bambu Lab A1 mini': (0.0, 1.0),
    'Bambu Lab A1': (0.0, 1.0),
    'Bambu Lab A2L': (0.0, 1.0),
    'Bambu Lab P1P, P1S, X1, X1C, X1E': (0.644, 0.977),
    'Bambu Lab P2S, X2D': (0.644, 0.977),
    'Bambu Lab H2C': (0.644, 0.977),
    'Bambu Lab H2D, H2D Pro': (0.644, 0.977),
    'Bambu Lab H2S': (0.644, 0.977),
    'Bambu Lab H3C': (1.0, 0.0),
}

# Areas of the bed a printer keeps free, x0, y0, x1, y1 in mm, bed_exclude_area of Bambu Studio's printer profiles. P1
# and X1 wipe the nozzle front left, Bambu Studio warns of collisions near it
EXCLUDED_AREAS: dict[str, list[tuple[float, float, float, float]]] = {
    'Bambu Lab P1P, P1S, X1, X1C, X1E': [(0, 0, 18, 28)],
}

_NAMES = {presetLabel(name): name for name in PRINT_BED_SIZES}

def purgeAnchor(label: str) -> tuple[float, float]:
    """Where the slicer puts the purge tower on the bed of the dropdown's label, see PURGE_ANCHORS"""
    return PURGE_ANCHORS.get(_NAMES.get(label), DEFAULT_PURGE_ANCHOR)

def excludedAreas(label: str) -> list[tuple[float, float, float, float]]:
    """The areas the printer of the dropdown's label keeps free, mm, see EXCLUDED_AREAS"""
    return list(EXCLUDED_AREAS.get(_NAMES.get(label), []))

def purgeSquare(bed: tuple[float, float], size: float, anchor: tuple[float, float]) -> tuple[float, float, float, float] | None:
    """The square kept free for the purge tower, x0, y0, x1, y1 in mm, at the anchor kept on the bed, none for size 0"""
    if size <= 0:
        return None
    size = min(size, bed[0], bed[1])
    x0 = min(max(anchor[0] * bed[0], 0.0), bed[0] - size)
    y0 = min(max(anchor[1] * bed[1], 0.0), bed[1] - size)
    return (x0, y0, x0 + size, y0 + size)
