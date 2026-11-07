from typing import Tuple
import adsk.core, adsk.fusion, traceback
import os

def recPattern(
    inputEntities: adsk.core.ObjectCollection,
    directions: Tuple[adsk.core.Base, adsk.core.Base],
    distances: Tuple[float, float],
    quantities: Tuple[int, int],
    targetComponent: adsk.fusion.Component,
    computeOption=None,
    ):
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = targetComponent.features.rectangularPatternFeatures
    patternInput = rectangularPatternFeatures.createInput(inputEntities,
            directions[0],
            adsk.core.ValueInput.createByReal(quantities[0]),
            adsk.core.ValueInput.createByReal(distances[0]),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = directions[1]
    patternInput.quantityTwo = adsk.core.ValueInput.createByReal(quantities[1])
    patternInput.distanceTwo = adsk.core.ValueInput.createByReal(distances[1])
    if computeOption is not None:
        patternInput.patternComputeOption = computeOption
    return rectangularPatternFeatures.add(patternInput)

def recPatternGrid(
    inputEntities: adsk.core.ObjectCollection,
    quantities: Tuple[int, int],
    distances: Tuple[float, float],
    targetComponent: adsk.fusion.Component,
    computeOption=None,
    distanceExpressions: Tuple[str, str] = None,
    ):
    """X/Y pattern, the optional expressions drive the spacing instead of plain values"""
    directions = (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis)
    if quantities[0] == 1:
        # Use the populated direction as the primary axis for a single-column grid.
        directions = directions[::-1]
        quantities = quantities[::-1]
        distances = distances[::-1]
        if distanceExpressions is not None:
            distanceExpressions = distanceExpressions[::-1]
    pattern = recPattern(inputEntities, directions, distances, quantities, targetComponent, computeOption)
    if distanceExpressions is not None:
        pattern.distanceOne.expression = distanceExpressions[0]
        pattern.distanceTwo.expression = distanceExpressions[1]
    return pattern

def circPattern(
    inputEntities: adsk.core.ObjectCollection,
    axis: adsk.core.Base,
    quantity: int,
    targetComponent: adsk.fusion.Component,
    ):
    circularPatternFeatures = targetComponent.features.circularPatternFeatures
    patternInput = circularPatternFeatures.createInput(inputEntities, axis)
    patternInput.quantity = adsk.core.ValueInput.createByReal(quantity)
    return circularPatternFeatures.add(patternInput)
