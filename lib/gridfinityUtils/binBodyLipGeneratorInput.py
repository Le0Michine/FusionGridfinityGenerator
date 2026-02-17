import adsk.core, adsk.fusion, traceback

from . import const

class BinBodyLipGeneratorInput():
    def __init__(self):
        self.wallThickness = const.BIN_LIP_WALL_THICKNESS
        self.hasLip = False
        self.hasLipNotches = False
        self.binCornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS
        self.hasPadding = False
        self.paddingLeft = 0
        self.paddingTop = 0
        self.paddingRight = 0
        self.paddingBottom = 0

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

    @property
    def hasPadding(self) -> bool:
        return self._hasPadding
    
    @hasPadding.setter
    def hasPadding(self, value: bool):
        self._hasPadding = value

    @property
    def paddingLeft(self) -> float:
        return self._paddingLeft if self._hasPadding else 0
    
    @paddingLeft.setter
    def paddingLeft(self, value: float):
        self._paddingLeft = value

    @property
    def paddingTop(self) -> float:
        return self._paddingTop if self._hasPadding else 0
    
    @paddingTop.setter
    def paddingTop(self, value: float):
        self._paddingTop = value

    @property
    def paddingRight(self) -> float:
        return self._paddingRight if self._hasPadding else 0
    
    @paddingRight.setter
    def paddingRight(self, value: float):
        self._paddingRight = value

    @property
    def paddingBottom(self) -> float:
        return self._paddingBottom if self._hasPadding else 0
    
    @paddingBottom.setter
    def paddingBottom(self, value: float):
        self._paddingBottom = value
