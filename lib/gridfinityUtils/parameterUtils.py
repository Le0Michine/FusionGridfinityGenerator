import adsk.core, adsk.fusion

def parameterName(prefix: str, name: str) -> str:
    return f'{prefix}_{name}'

def nextFreePrefix(design: adsk.fusion.Design, baseName: str, names: list[str]) -> str:
    """First numbered prefix for which none of the given parameter names are taken yet"""
    index = 1
    while any(design.userParameters.itemByName(parameterName(f'{baseName}{index}', name)) is not None for name in names):
        index += 1
    return f'{baseName}{index}'

def addUnitlessParameter(
    design: adsk.fusion.Design,
    name: str,
    value: float,
    comment: str,
) -> adsk.fusion.UserParameter:
    return design.userParameters.add(name, adsk.core.ValueInput.createByString(f'{value:g}'), '', comment)

def addLengthParameter(
    design: adsk.fusion.Design,
    name: str,
    value: float,
    comment: str,
) -> adsk.fusion.UserParameter:
    """Value in internal units (cm), shown in millimeters"""
    return design.userParameters.add(name, adsk.core.ValueInput.createByReal(value), 'mm', comment)
