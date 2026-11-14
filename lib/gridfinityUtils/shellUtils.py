import adsk.core, adsk.fusion, traceback
import os


def simpleShell(
    openFaces: list[adsk.fusion.BRepFace],
    thickness: float,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    isRounded: bool = False,
    ):
    shellFeatures = targetComponent.features.shellFeatures
    shellBinObjects = adsk.core.ObjectCollection.create()
    for face in openFaces:
        shellBinObjects.add(face)
    shellBinInput = shellFeatures.createInput(shellBinObjects, False)
    shellBinInput.insideThickness = adsk.core.ValueInput.createByReal(thickness)
    if isRounded:
        shellBinInput.shellType = adsk.fusion.ShellTypes.RoundedOffsetShellType
    shellFeature = shellFeatures.add(shellBinInput)
    shellFeature.name = name
    return shellFeature