from dataclasses import dataclass

@dataclass
class InputState:
    """Everything a bin is built from, lengths in cm and angles in radians like Fusion's internal units"""
    baseWidth: float
    baseLength: float
    heightUnit: float
    xyClearance: float
    # in base units, may end in a half, see binGrid
    binWidth: float
    binLength: float
    # in height units
    binHeight: float
    isHalfGrid: bool
    wallThickness: float
    # see binBuilder.BIN_TYPE_HOLLOW
    binType: str
    # rounded shell type of Fusion instead of sharp, its simpler faces are easier to cut and combine with later
    isShellRounded: bool

    generateBase: bool
    generateBody: bool
    hasJointOrigins: bool

    hasScrewHoles: bool
    screwHoleDiameter: float
    hasMagnetCutouts: bool
    hasMagnetCutoutsTabs: bool
    magnetCutoutDiameter: float
    magnetCutoutDepth: float

    hasLip: bool
    hasLipNotches: bool

    hasScoop: bool
    scoopMaxRadius: float

    hasTab: bool
    # in base units
    tabLength: float
    tabWidth: float
    # in base units
    tabPosition: float
    tabOverhangAngle: float
    isTabHollow: bool
    isTabOpenThroughSides: bool
    tabTopAngle: float
    labelText: str
    labelIcon: str
    labelStyle: str
    isLabelBold: bool

    compartmentsX: int
    compartmentsY: int
    # pockets of the compartments drawing are used only while it's shown, see compartmentLayout
    showCompartmentsLayout: bool
    compartmentPockets: list[dict]

    # cells of the shape drawing, see binShape, only used with a custom shape
    hasCustomShape: bool
    shapeCells: list[tuple[int, int]]

    # see wallCreases, lengths in base units, the height in height units
    hasCreases: bool
    creaseDepth: float
    creaseMinLength: float
    creaseMaxPanelLength: float
    creaseMinHeight: float
