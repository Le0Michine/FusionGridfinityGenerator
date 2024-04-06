import adsk.core, adsk.fusion, traceback

from . import const

class BinBodyLipGeneratorInput():
    def __init__(self):
        self.wallThickness = const.BIN_LIP_WALL_THICKNESS
        self.hasLip = False
        self.hasLipNotches = False
        self.binCornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS

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
    def binCornerFilletRadius(self) -> float:
        return self._binCornerFilletRadius

    @binCornerFilletRadius.setter
    def binCornerFilletRadius(self, value: float):
        self._binCornerFilletRadius = value

    @property
    def xyClearance(self) -> float:
        return self._xyClearance

    @xyClearance.setter
    def xyClearance(self, value: float):
        self._xyClearance = value

    @property
    def wallThickness(self) -> float:
        return self._wallThickness

    @wallThickness.setter
    def wallThickness(self, value: float):
        self._wallThickness = value

    @property
    def hasLipNotches(self) -> bool:
        return self._hasLipNotches

    @hasLipNotches.setter
    def hasLipNotches(self, value: bool):
        self._hasLipNotches = value

    @property
    def origin(self) -> adsk.core.Point3D:
        return self._originUnit

    @origin.setter
    def origin(self, value: adsk.core.Point3D):
        self._originUnit = value