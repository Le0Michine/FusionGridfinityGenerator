import adsk.core, adsk.fusion, traceback

from .const import DIMENSION_MAGNET_CUTOUT_DEPTH, DIMENSION_MAGNET_CUTOUT_DIAMETER, DIMENSION_SCREW_HOLE_DIAMETER, BIN_CORNER_FILLET_RADIUS

class BaseGeneratorInput():
    def __init__(self):
        self.hasMagnetCutouts = False
        self.hasScrewHoles = False
        self.hasBottomChamfer = True
        self.screwHolesDiameter = DIMENSION_SCREW_HOLE_DIAMETER
        self.magnetCutoutsDiameter = DIMENSION_MAGNET_CUTOUT_DIAMETER
        self.magnetCutoutsDepth = DIMENSION_MAGNET_CUTOUT_DEPTH
        self.cornerFilletRadius = BIN_CORNER_FILLET_RADIUS
        self.hasPadding = False
        self.paddingLeft = 0
        self.paddingTop = 0
        self.paddingRight = 0
        self.paddingBottom = 0

    @property
    def originPoint(self) -> adsk.core.Point3D:
        return self._originPoint

    @originPoint.setter
    def originPoint(self, value: adsk.core.Point3D):
        self._originPoint = value

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
    def cornerFilletRadius(self) -> float:
        return self._cornerFilletRadius

    @cornerFilletRadius.setter
    def cornerFilletRadius(self, value: float):
        self._cornerFilletRadius = value

    @property
    def xyClearance(self) -> float:
        return self._xyTolerance

    @xyClearance.setter
    def xyClearance(self, value: float):
        self._xyTolerance = value

    @property
    def hasBottomChamfer(self) -> bool:
        return self._hasBottomChamfer

    @hasBottomChamfer.setter
    def hasBottomChamfer(self, value: bool):
        self._hasBottomChamfer = value

    @property
    def hasScrewHoles(self) -> bool:
        return self._hasScrewHoles

    @hasScrewHoles.setter
    def hasScrewHoles(self, value: bool):
        self._hasScrewHoles = value

    @property
    def screwHolesDiameter(self) -> float:
        return self._screwHolesDiameter

    @screwHolesDiameter.setter
    def screwHolesDiameter(self, value: float):
        self._screwHolesDiameter = value

    @property
    def hasMagnetCutouts(self) -> bool:
        return self._hasMagnetCutouts

    @hasMagnetCutouts.setter
    def hasMagnetCutouts(self, value: bool):
        self._hasMagnetCutouts = value

    @property
    def magnetCutoutsDiameter(self) -> float:
        return self._magnetCutoutsDiameter

    @magnetCutoutsDiameter.setter
    def magnetCutoutsDiameter(self, value: float):
        self._magnetCutoutsDiameter = value

    @property
    def magnetCutoutsDepth(self) -> float:
        return self._magnetCutoutsDepth

    @magnetCutoutsDepth.setter
    def magnetCutoutsDepth(self, value: float):
        self._magnetCutoutsDepth = value

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
