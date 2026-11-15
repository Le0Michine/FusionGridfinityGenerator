import adsk.core, adsk.fusion
import math

def parameterName(prefix: str, name: str) -> str:
    return f'{prefix}_{name}'

def nextFreePrefix(design: adsk.fusion.Design, baseName: str, names: list[str], takenPrefixes: set[str] = frozenset()) -> str:
    """
    First numbered prefix for which none of the given parameter names are taken yet, nor the prefix itself, like the
    id of a body with no parameters of its own, see tagUtils.tagBody
    """
    index = 1
    while f'{baseName}{index}' in takenPrefixes or any(design.userParameters.itemByName(parameterName(f'{baseName}{index}', name)) is not None for name in names):
        index += 1
    return f'{baseName}{index}'

def reusedParameter(design: adsk.fusion.Design, name: str, isSame, expression: str) -> adsk.fusion.UserParameter | None:
    """
    The parameter of a body rebuilt in place, see rebuildUtils, its expression set when it's no longer the same.
    An expression the user gave it that still comes to the value stays
    """
    parameter = design.userParameters.itemByName(name)
    if parameter is not None and not isSame(parameter):
        parameter.expression = expression
    return parameter

def isSameValue(value: float):
    return lambda parameter: math.isclose(parameter.value, value, abs_tol=1e-9)

def addUnitlessParameter(
    design: adsk.fusion.Design,
    name: str,
    value: float,
    comment: str,
    reuse: bool = False,
) -> adsk.fusion.UserParameter:
    """Reuse takes the parameter of that name when there is one"""
    parameter = reusedParameter(design, name, isSameValue(value), f'{value:g}') if reuse else None
    return parameter or design.userParameters.add(name, adsk.core.ValueInput.createByString(f'{value:g}'), '', comment)

def addLengthParameter(
    design: adsk.fusion.Design,
    name: str,
    value: float,
    comment: str,
    reuse: bool = False,
) -> adsk.fusion.UserParameter:
    """Value in internal units (cm), shown in millimeters. Reuse takes the parameter of that name when there is one"""
    parameter = reusedParameter(design, name, isSameValue(value), f'{round(value * 10, 6):g} mm') if reuse else None
    return parameter or design.userParameters.add(name, adsk.core.ValueInput.createByReal(value), 'mm', comment)

def textExpression(text: str) -> str:
    """Text parameters take a single quoted literal, quotes inside are swapped for typographic ones"""
    return "'" + text.replace("'", "\u2019") + "'"

def addTextParameter(
    design: adsk.fusion.Design,
    name: str,
    text: str,
    comment: str,
    reuse: bool = False,
) -> adsk.fusion.UserParameter:
    """Reuse takes the parameter of that name when there is one"""
    parameter = reusedParameter(design, name, lambda parameter: textExpression(parameter.textValue) == textExpression(text), textExpression(text)) if reuse else None
    return parameter or design.userParameters.add(name, adsk.core.ValueInput.createByString(textExpression(text)), 'Text', comment)
