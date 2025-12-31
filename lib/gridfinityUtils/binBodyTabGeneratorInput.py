import adsk.core, adsk.fusion, traceback

from . import const

class BinBodyTabGeneratorInput():
    def __init__(self):
        self.overhangAngle = const.BIN_TAB_OVERHANG_ANGLE
        self.labelAngle = const.BIN_TAB_LABEL_ANGLE
        self.position = 0
        self._tabMethod = const.BIN_TAB_METHOD_ANGLE
        self._rootThickness = const.BIN_TAB_DEFAULT_ROOT_THICKNESS
        self._tipThickness = const.BIN_TAB_DEFAULT_TIP_THICKNESS
        self._tabFilletTop = const.BIN_TAB_DEFAULT_TIP_THICKNESS / 2
        self._tabFilletBottom = const.BIN_TAB_DEFAULT_TIP_THICKNESS / 2
        self._tabFilletBack = const.BIN_TAB_DEFAULT_FILLET_BACK

    @property
    def topClearance(self) -> float:
        return self._topClearance

    @topClearance.setter
    def topClearance(self, value: float):
        self._topClearance = value

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
    def origin(self) -> adsk.core.Point3D:
        return self._origin

    @origin.setter
    def origin(self, value: adsk.core.Point3D):
        self._origin = value

    @property
    def overhangAngle(self) -> float:
        return self._tabOverhangAngle

    @overhangAngle.setter
    def overhangAngle(self, value: float):
        self._tabOverhangAngle = value

    @property
    def labelAngle(self) -> float:
        return self._tablabelAngle

    @labelAngle.setter
    def labelAngle(self, value: float):
        self._tablabelAngle = value

    @property
    def tabMethod(self) -> str:
        return self._tabMethod

    @tabMethod.setter
    def tabMethod(self, value: str):
        self._tabMethod = value

    @property
    def rootThickness(self) -> float:
        return self._rootThickness

    @rootThickness.setter
    def rootThickness(self, value: float):
        self._rootThickness = value

    @property
    def tipThickness(self) -> float:
        return self._tipThickness

    @tipThickness.setter
    def tipThickness(self, value: float):
        self._tipThickness = value

    @property
    def tabFilletTop(self) -> float:
        return self._tabFilletTop
    
    @tabFilletTop.setter
    def tabFilletTop(self, value: float):
        self._tabFilletTop = value

    @property
    def tabFilletBottom(self) -> float:
        return self._tabFilletBottom
    
    @tabFilletBottom.setter
    def tabFilletBottom(self, value: float):
        self._tabFilletBottom = value
    
    @property
    def tabFilletBack(self) -> float:
        return self._tabFilletBack
    
    @tabFilletBack.setter
    def tabFilletBack(self, value: float):
        self._tabFilletBack = value

    