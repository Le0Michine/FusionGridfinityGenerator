PRINT_BED_CUSTOM = 'Custom'

# usable bed size X, Y in mm
PRINT_BED_SIZES: dict[str, tuple[float, float]] = {
    'Bambu Lab A1 mini': (180, 180),
    'Bambu Lab A1, P1, X1': (256, 256),
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

# labels are what the dropdown shows and saved dialog defaults store, keep them stable
PRINT_BED_PRESETS: dict[str, tuple[float, float]] = {presetLabel(name): size for (name, size) in PRINT_BED_SIZES.items()}

def presetBedSize(label: str) -> tuple[float, float] | None:
    """Bed size in Fusion internal units, cm"""
    if label not in PRINT_BED_PRESETS:
        return None
    (width, length) = PRINT_BED_PRESETS[label]
    return (width / 10, length / 10)
