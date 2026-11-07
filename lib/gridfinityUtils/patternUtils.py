from typing import Tuple
import adsk.core, adsk.fusion, traceback
import os

from .dim import Dim, valueInput, valueOf

def recPattern(
    inputEntities: adsk.core.ObjectCollection,
    directions: Tuple[adsk.core.Base, adsk.core.Base],
    distances: Tuple[Dim | float, Dim | float],
    quantities: Tuple[Dim | int, Dim | int],
    targetComponent: adsk.fusion.Component,
    computeOption=None,
    *,
    name: str,
    ):
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = targetComponent.features.rectangularPatternFeatures
    patternInput = rectangularPatternFeatures.createInput(inputEntities,
            directions[0],
            valueInput(quantities[0]),
            valueInput(distances[0]),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = directions[1]
    patternInput.quantityTwo = valueInput(quantities[1])
    patternInput.distanceTwo = valueInput(distances[1])
    if computeOption is not None:
        patternInput.patternComputeOption = computeOption
    pattern = rectangularPatternFeatures.add(patternInput)
    pattern.name = name
    return pattern

def recPatternGrid(
    inputEntities: adsk.core.ObjectCollection,
    quantities: Tuple[Dim | int, Dim | int],
    distances: Tuple[Dim | float, Dim | float],
    targetComponent: adsk.fusion.Component,
    computeOption=None,
    *,
    name: str,
    ):
    directions = (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis)
    if valueOf(quantities[0]) == 1:
        # Use the populated direction as the primary axis for a single-column grid.
        directions = directions[::-1]
        quantities = quantities[::-1]
        distances = distances[::-1]
    return recPattern(inputEntities, directions, distances, quantities, targetComponent, computeOption, name=name)

def circPattern(
    inputEntities: adsk.core.ObjectCollection,
    axis: adsk.core.Base,
    quantity: int,
    targetComponent: adsk.fusion.Component,
    *,
    name: str,
    ):
    circularPatternFeatures = targetComponent.features.circularPatternFeatures
    patternInput = circularPatternFeatures.createInput(inputEntities, axis)
    patternInput.quantity = adsk.core.ValueInput.createByReal(quantity)
    pattern = circularPatternFeatures.add(patternInput)
    pattern.name = name
    return pattern
