import adsk.core, adsk.fusion, traceback

from . import const

class BinBodyTabGeneratorInput():
    def __init__(self):
        self.overhangAngle = const.BIN_TAB_OVERHANG_ANGLE
        self.position = 0

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
        return self._originUnit

    @origin.setter
    def origin(self, value: adsk.core.Point3D):
        self._originUnit = value

    @property
    def overhangAngle(self) -> float:
        return self._tabOverhangAngle

    @overhangAngle.setter
    def overhangAngle(self, value: float):
        self._tabOverhangAngle = value

    