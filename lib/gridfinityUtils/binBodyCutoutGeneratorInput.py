import adsk.core, adsk.fusion, traceback

from . import const

class BinBodyCutoutGeneratorInput():
    def __init__(self):
        self.hasScoop = False
        self.scoopMaxRadius = const.BIN_SCOOP_MAX_RADIUS
        self.tabOverhangAngle = const.BIN_TAB_OVERHANG_ANGLE
        self.tabPosition = 0
        self.tabLength = 1
        self.tabWidth = const.BIN_TAB_WIDTH
        self.hasBottomFillet = True


    @property
    def width(self) -> float:
        return self._baseWidth

    @width.setter
    def width(self, value: float):
        self._baseWidth = value

    @property
    def length(self) -> float:
        return self._baseLength

    @length.setter
    def length(self, value: float):
        self._baseLength = value

    @property
    def height(self) -> float:
        return self._heightUnit

    @height.setter
    def height(self, value: float):
        self._heightUnit = value

    @property
    def origin(self) -> adsk.core.Point3D:
        return self._originUnit

    @origin.setter
    def origin(self, value: adsk.core.Point3D):
        self._originUnit = value

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
    def hasBottomFillet(self) -> float:
        return self._hasBottomFillet

    @hasBottomFillet.setter
    def hasBottomFillet(self, value: float):
        self._hasBottomFillet = value

    @property
    def filletRadius(self) -> float:
        return self._filletRadius

    @filletRadius.setter
    def filletRadius(self, value: float):
        self._filletRadius = value

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

    