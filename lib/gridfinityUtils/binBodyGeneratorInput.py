import adsk.core, adsk.fusion, traceback

from .const import BIN_WALL_THICKNESS, DIMENSION_MAGNET_CUTOUT_DEPTH, DIMENSION_MAGNET_CUTOUT_DIAMETER, DIMENSION_SCREW_HOLE_DIAMETER

class BinBodyGeneratorInput():
    def __init__(self):
        self.wallThickness = BIN_WALL_THICKNESS
        self.isSolid = False
        self.hasLip = False
        self.isStackable = True
        self.hasScoop = False

    @property
    def baseWidth(self) -> float:
        return self._baseWidth

    @baseWidth.setter
    def baseWidth(self, value: float):
        self._baseWidth = value

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
    def isStackable(self) -> bool:
        return self._isStackable

    @isStackable.setter
    def isStackable(self, value: bool):
        self._isStackable = value

    @property
    def isSolid(self) -> bool:
        return self._isSolid

    @isSolid.setter
    def isSolid(self, value: bool):
        self._isSolid = value

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

    