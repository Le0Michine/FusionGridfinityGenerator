# The settings the generator dialogs start with before any saved defaults, in the config format of lib/configJson.py:
# every field of a generator's InputState by its name, lengths in mm and angles in degrees. Shape test cases only list
# the settings they change from these, so they're built the way a new bin is, see commandSnapshotTests/testCases.py.
# Kept free of Fusion imports so it can be unit tested

BIN = {
    'baseWidth': 42.0,
    'baseLength': 42.0,
    'heightUnit': 7.0,
    'xyClearance': 0.25,
    'binWidth': 2,
    'binLength': 3,
    'binHeight': 5,
    'isHalfGrid': False,
    'wallThickness': 1.2,
    'binType': 'Hollow',
    'isShellRounded': True,
    'generateBase': True,
    'generateBody': True,
    'hasJointOrigins': False,
    'hasScrewHoles': False,
    'screwHoleDiameter': 3.0,
    'hasMagnetCutouts': False,
    'hasMagnetCutoutsTabs': False,
    'magnetCutoutDiameter': 6.5,
    'magnetCutoutDepth': 2.4,
    'hasLip': True,
    'hasLipNotches': False,
    'isLipTopTrimmed': True,
    'hasScoop': False,
    'scoopMaxRadius': 25.0,
    'hasTab': False,
    'tabLength': 1,
    'tabWidth': 13.0,
    'tabPosition': 0,
    'tabOverhangAngle': 45.0,
    # follows the bin type when it changes, shelled bins get hollow tabs
    'isTabHollow': False,
    'isTabOpenThroughSides': False,
    'tabTopAngle': 0.0,
    'labelText': '',
    'labelIcon': 'None',
    'labelStyle': 'Outline',
    'isLabelBold': True,
    'compartmentsX': 1,
    'compartmentsY': 1,
    'showCompartmentsLayout': False,
    'compartmentPockets': [],
    'hasCustomShape': False,
    'shapeCells': [],
    # walls folded in for stiffness, see wallCreases
    'hasCreases': True,
    'creaseDepth': 2.0,
    # in base units, about 120 mm and 200 mm with 42 mm feet
    'creaseMinLength': 2.85,
    'creaseMaxPanelLength': 4.75,
    # in height units, 70 mm with 7 mm units
    'creaseMinHeight': 10,
}

BASEPLATE = {
    'baseWidth': 42.0,
    'baseLength': 42.0,
    'xyClearance': 0.25,
    'plateWidth': 2,
    'plateLength': 3,
    'plateType': 'Light',
    'hasMagnetSockets': True,
    'magnetSocketSize': 6.5,
    'magnetSocketDepth': 2.4,
    'hasScrewHoles': True,
    'screwHoleSize': 3.2,
    'screwHeadSize': 6.0,
    'hasPadding': False,
    'paddingLeft': 0.0,
    'paddingTop': 0.0,
    'paddingRight': 0.0,
    'paddingBottom': 0.0,
    'extraBottomThickness': 6.4,
    'verticalClearance': 0.5,
    'hasConnectionHoles': False,
    'connectionHoleSize': 3.2,
    'sizingMode': 'Fill area',
    'areaWidth': 400.0,
    'areaLength': 300.0,
    # gap between baseplates glued side by side, each takes half of it on its edge. Closer than bins are to each other
    'plateClearance': 0.1,
    # a common bed size, of the Bambu Lab A1, P1 and X1, the bed dropdown starts on custom
    'bedWidth': 256.0,
    'bedLength': 256.0,
    'bedMargin': 5.0,
    'alignmentX': 'Center',
    'alignmentY': 'Center',
    'useHalfCells': True,
    'hasJointOrigins': False,
}

# by generator, see configJson.GENERATOR_BIN
SETTINGS = {
    'bin': BIN,
    'baseplate': BASEPLATE,
}
