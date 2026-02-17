import adsk.core, adsk.fusion, traceback

from . import const

class BaseplateGeneratorInput():
    def __init__(self):
        self.hasMagnetCutouts = False
        self.hasScrewHoles = False
        self.screwHolesDiameter = const.DIMENSION_SCREW_HOLE_DIAMETER
        self.screwHeadCutoutDiameter = const.DIMENSION_SCREW_HEAD_CUTOUT_DIAMETER
        self.magnetCutoutsDiameter = const.DIMENSION_MAGNET_CUTOUT_DIAMETER
        self.magnetCutoutsDepth = const.DIMENSION_MAGNET_CUTOUT_DEPTH
        self.hasSkeletonizedBottom = True
        self.bottomExtensionHeight = const.BASEPLATE_EXTRA_HEIGHT
        self.xyClearance = const.BIN_XY_CLEARANCE
        self.binZClearance = const.BASEPLATE_BIN_Z_CLEARANCE
        self.connectionScrewHolesDiameter = const.DIMENSION_PLATE_CONNECTION_SCREW_HOLE_DIAMETER
        self.cornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS

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
    def baseplateWidth(self) -> float:
        return self._baseplateWidth

    @baseplateWidth.setter
    def baseplateWidth(self, value: float):
        self._baseplateWidth = value

    @property
    def baseplateLength(self) -> float:
        return self._baseplateLength

    @baseplateLength.setter
    def baseplateLength(self, value: float):
        self._baseplateLength = value

    @property
    def cornerFilletRadius(self) -> float:
        return self._cornerFilletRadius

    @cornerFilletRadius.setter
    def cornerFilletRadius(self, value: float):
        self._cornerFilletRadius = value

    @property
    def xyClearance(self) -> float:
        return self._xyClearance

    @xyClearance.setter
    def xyClearance(self, value: float):
        self._xyClearance = value

    @property
    def binZClearance(self) -> float:
        return self._binZClearance

    @binZClearance.setter
    def binZClearance(self, value: float):
        self._binZClearance = value

    @property
    def hasExtendedBottom(self) -> bool:
        return self._hasExtendedBottom

    @hasExtendedBottom.setter
    def hasExtendedBottom(self, value: bool):
        self._hasExtendedBottom = value

    @property
    def bottomExtensionHeight(self) -> bool:
        return self._bottomExtensionHeight

    @bottomExtensionHeight.setter
    def bottomExtensionHeight(self, value: bool):
        self._bottomExtensionHeight = value

    @property
    def hasSkeletonizedBottom(self) -> bool:
        return self._hasSkeletonizedBottom

    @hasSkeletonizedBottom.setter
    def hasSkeletonizedBottom(self, value: bool):
        self._hasSkeletonizedBottom = value

    @property
    def hasScrewHoles(self) -> bool:
        return self._hasScrewHoles

    @hasScrewHoles.setter
    def hasScrewHoles(self, value: bool):
        self._hasScrewHoles = value

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

    @property
    def hasConnectionHoles(self) -> bool:
        return self._hasConnectionHoles

    @hasConnectionHoles.setter
    def hasConnectionHoles(self, value: bool):
        self._hasConnectionHoles = value

    @property
    def connectionScrewHolesDiameter(self) -> float:
        return self._connectionScrewHolesDiameter

    @connectionScrewHolesDiameter.setter
    def connectionScrewHolesDiameter(self, value: float):
        self._connectionScrewHolesDiameter = value

    @property
    def screwHolesDiameter(self) -> float:
        return self._screwHolesDiameter

    @screwHolesDiameter.setter
    def screwHolesDiameter(self, value: float):
        self._screwHolesDiameter = value

    @property
    def screwHeadCutoutDiameter(self) -> float:
        return self._screwHeadCutoutDiameter

    @screwHeadCutoutDiameter.setter
    def screwHeadCutoutDiameter(self, value: float):
        self._screwHeadCutoutDiameter = value

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
