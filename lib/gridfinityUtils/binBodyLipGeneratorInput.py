import adsk.core, adsk.fusion, traceback

from . import const
from .dim import Dim

class BinBodyLipGeneratorInput():
    def __init__(self):
        self.wallThickness = const.BIN_LIP_WALL_THICKNESS
        self.hasLip = False
        self.hasLipNotches = False
        self.binCornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS
        self.originZ = None

    @property
    def baseWidth(self) -> Dim:
        return self._baseWidth

    @baseWidth.setter
    def baseWidth(self, value: Dim | float):
        self._baseWidth = Dim.asLength(value)

    @property
    def baseLength(self) -> Dim:
        return self._baseLength

    @baseLength.setter
    def baseLength(self, value: Dim | float):
        self._baseLength = Dim.asLength(value)

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

    @property
    def originZ(self) -> Dim:
        """Drives the origin height for Fusion, falls back to the origin point when not set"""
        return Dim.length(self.origin.z) if self._originZ is None else self._originZ

    @originZ.setter
    def originZ(self, value: Dim):
        self._originZ = value
