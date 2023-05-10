from typing import Dict
from dataclasses import dataclass

@dataclass
class CompartmentTableRow:
    x: int
    y: int
    width: int
    length: int
    depth: float

@dataclass
class InputState:
    groups: Dict[str, bool]
    baseWidth: float
    baseLength: float
    heightUnit: float
    xyTolerance: float
    binWidth: float
    binLength: float
    binHeight: float
    hasBody: bool
    binBodyType: str
    binWallThickness: float
    hasLip: bool
    hasLipNotches: bool
    compartmentsGridWidth: int
    compartmentsGridLength: int
    compartmentsGridType: str
    hasScoop: bool
    scoopMaxRadius: float
    hasTab: bool
    tabLength: float
    tabWidth: float
    tabAngle: float
    tabOffset: float
    hasBase: bool
    hasBaseScrewHole: bool
    baseScrewHoleSize: float
    hasBaseMagnetSockets: bool
    baseMagnetSocketSize: float
    baseMagnetSocketDepth: float
    preserveChanges: bool
    customCompartments: list[CompartmentTableRow]

    def getGroupExpandedState(self, id: str):
      if id in self.groups:
        return self.groups[id]
      else:
        return True