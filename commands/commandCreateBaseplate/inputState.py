from typing import Dict
from dataclasses import dataclass

@dataclass
class InputState:
    baseWidth: float
    xyTolerance: float
    plateWidth: float
    plateLength: float

    plateType: str

    hasMagnetSockets: bool
    magnetSocketSize: float
    magnetSocketDepth: float

    hasScrewHoles: bool
    screwHoleSize: float
    screwHeadSize: float

    extraBottomThickness: float
    verticalClearance: float

    hasConnectionHoles: bool
    connectionHoleSize: float
