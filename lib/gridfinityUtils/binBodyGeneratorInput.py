import adsk.core, adsk.fusion, traceback

from . import const

class BinBodyCompartmentDefinition():
    def __init__(self, positionX=0, positionY=0, width=1, length=1, depth=9999999999999):
        self.positionX = positionX
        self.positionY = positionY
        self.width = width
        self.length = length
        # set to something big so it would get limited by bin height
        self.depth = depth

    @property
    def positionX(self) -> float:
        return self._positionX

    @positionX.setter
    def positionX(self, value: float):
        self._positionX = value

    @property
    def positionY(self) -> float:
        return self._positionY

    @positionY.setter
    def positionY(self, value: float):
        self._positionY = value

    @property
    def width(self) -> float:
        return self._width

    @width.setter
    def width(self, value: float):
        self._width = value

    @property
    def length(self) -> float:
        return self._length

    @length.setter
    def length(self, value: float):
        self._length = value

    @property
    def depth(self) -> float:
        return self._depth

    @depth.setter
    def depth(self, value: float):
        self._depth = value

class BinBodyGeneratorInput():
    def __init__(self):
        self.wallThickness = const.BIN_WALL_THICKNESS
        self.isSolid = False
        self.hasLip = False
        self.hasLipNotches = False
        self.hasScoop = False
        self.scoopMaxRadius = const.BIN_SCOOP_MAX_RADIUS
        self.tabOverhangAngle = const.BIN_TAB_OVERHANG_ANGLE
        self.tabPosition = 0
        self.tabLength = 1
        self.tabWidth = const.BIN_TAB_WIDTH
        self.compartments = [BinBodyCompartmentDefinition()]
        self.compartmentsByX = 1
        self.compartmentsByY = 1

    @property
    def baseWidth(self) -> float:
        return self._baseWidth

    @baseWidth.setter
    def baseWidth(self, value: float):
        self._baseWidth = value

    @property
    def baseLength(self) -> float:
        return self._baseLength

    @baseLength.setter
    def baseLength(self, value: float):
        self._baseLength = value

    @property
    def heightUnit(self) -> float:
        return self._heightUnit

    @heightUnit.setter
    def heightUnit(self, value: float):
        self._heightUnit = value

    @property
    def xyTolerance(self) -> float:
        return self._xyTolerance

    @xyTolerance.setter
    def xyTolerance(self, value: float):
        self._xyTolerance = value

    @property
    def binWidth(self) -> float:
        return self._binWidth

    @binWidth.setter
    def binWidth(self, value: float):
        self._binWidth = value

    @property
    def binLength(self) -> float:
        return self._binLength

    @binLength.setter
    def binLength(self, value: float):
        self._binLength = value

    @property
    def binHeight(self) -> float:
        return self._binHeight

    @binHeight.setter
    def binHeight(self, value: float):
        self._binHeight = value

    @property
    def wallThickness(self) -> float:
        return self._wallThickness

    @wallThickness.setter
    def wallThickness(self, value: float):
        self._wallThickness = value

    @property
    def isSolid(self) -> bool:
        return self._isSolid

    @isSolid.setter
    def isSolid(self, value: bool):
        self._isSolid = value

    @property
    def hasLipNotches(self) -> bool:
        return self._hasLipNotches

    @hasLipNotches.setter
    def hasLipNotches(self, value: bool):
        self._hasLipNotches = value

    @property
    def hasLip(self) -> bool:
        return self._hasLip

    @hasLip.setter
    def hasLip(self, value: bool):
        self._hasLip = value

    @property
    def hasScoop(self) -> bool:
        return self._hasScoop

    @hasScoop.setter
    def hasScoop(self, value: bool):
        self._hasScoop = value

    @property
    def scoopMaxRadius(self) -> float:
        return self._scoopMaxRadius

    @scoopMaxRadius.setter
    def scoopMaxRadius(self, value: float):
        self._scoopMaxRadius = value

    @property
    def hasTab(self) -> bool:
        return self._hasTab

    @hasTab.setter
    def hasTab(self, value: bool):
        self._hasTab = value

    @property
    def tabWidth(self) -> float:
        return self._tabWidth

    @tabWidth.setter
    def tabWidth(self, value: float):
        self._tabWidth = value

    @property
    def tabLength(self) -> float:
        return self._tabLength

    @tabLength.setter
    def tabLength(self, value: float):
        self._tabLength = value

    @property
    def tabPosition(self) -> float:
        return self._tabPosition

    @tabPosition.setter
    def tabPosition(self, value: float):
        self._tabPosition = value

    @property
    def tabOverhangAngle(self) -> float:
        return self._tabOverhangAngle

    @tabOverhangAngle.setter
    def tabOverhangAngle(self, value: float):
        self._tabOverhangAngle = value

    @property
    def compartmentsByX(self) -> float:
        return self._compartmentsByX

    @compartmentsByX.setter
    def compartmentsByX(self, value: float):
        self._compartmentsByX = value

    @property
    def compartmentsByY(self) -> float:
        return self._compartmentsByY

    @compartmentsByY.setter
    def compartmentsByY(self, value: float):
        self._compartmentsByY = value

    @property
    def compartments(self) -> list[BinBodyCompartmentDefinition]:
        return self._compartments

    @compartments.setter
    def compartments(self, value: list[BinBodyCompartmentDefinition]):
        self._compartments = value
