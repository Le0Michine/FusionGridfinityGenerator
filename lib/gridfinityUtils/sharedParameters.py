import math
import adsk.core, adsk.fusion

from .. import tagUtils
from . import const, commonUtils, parameterUtils

# User parameter names are stored in user documents, keep these literal
# shared by all bins and baseplates of the design, so changing one rescales everything built from it
HEIGHT_UNIT_PARAMETER = 'gfHeightUnit'
BASE_WIDTH_PARAMETER = 'gfBaseWidth'
BASE_LENGTH_PARAMETER = 'gfBaseLength'
# per bin or baseplate fallbacks for the shared units
BASE_WIDTH_FALLBACK_PARAMETER = 'baseWidth'
BASE_LENGTH_FALLBACK_PARAMETER = 'baseLength'
# smallest units the dialogs accept, an existing parameter has to meet them too
HEIGHT_UNIT_MIN = 0.5
BASE_UNIT_MIN = 1

def isUsableLengthParameter(design: adsk.fusion.Design, parameter: adsk.fusion.UserParameter, minimum: float) -> bool:
    """Has to be a length within the range the dialog accepts"""
    isLength = parameter.unit != '' and design.unitsManager.isValidExpression(f'1 {parameter.unit}', 'mm')
    return isLength and parameter.value >= minimum

def findSharedParameter(design: adsk.fusion.Design, tagName: str, name: str) -> tuple[adsk.fusion.UserParameter | None, str]:
    """The tagged parameter wins over an untagged one with the same name, returns it with where it was found"""
    taggedParameters = tagUtils.findTaggedParameters(design, tagName)
    if len(taggedParameters) > 0:
        return (taggedParameters[0][0], 'tagged')
    return (design.userParameters.itemByName(name), 'untagged, found by name')

def usableSharedValue(design: adsk.fusion.Design, tagName: str, name: str, minimum: float) -> float | None:
    """Value of the shared parameter when it exists and would be used as is"""
    (parameter, _) = findSharedParameter(design, tagName, name)
    if parameter is None or not isUsableLengthParameter(design, parameter, minimum):
        return None
    return parameter.value

def usableSharedHeightUnit(design: adsk.fusion.Design) -> float | None:
    return usableSharedValue(design, tagUtils.TAG_HEIGHT_UNIT_PARAMETER, HEIGHT_UNIT_PARAMETER, HEIGHT_UNIT_MIN)

def usableSharedBaseUnits(design: adsk.fusion.Design) -> tuple[float | None, float | None]:
    return (
        usableSharedValue(design, tagUtils.TAG_BASE_WIDTH_PARAMETER, BASE_WIDTH_PARAMETER, BASE_UNIT_MIN),
        usableSharedValue(design, tagUtils.TAG_BASE_LENGTH_PARAMETER, BASE_LENGTH_PARAMETER, BASE_UNIT_MIN),
    )

def findOrCreateSharedLengthParameter(
    design: adsk.fusion.Design,
    tagName: str,
    name: str,
    label: str,
    minimum: float,
    value: float,
    fallbackName: str,
    owner: str,
    logPrefix: str,
) -> adsk.fusion.UserParameter:
    """The tagged parameter wins, an untagged one with the same name is reused as is, otherwise a new one is created and tagged.
    An existing one that isn't usable or differs from the dialog value is left alone and the owner gets its own parameter instead"""
    (parameter, source) = findSharedParameter(design, tagName, name)
    if parameter is None:
        parameter = parameterUtils.addLengthParameter(design, name, value, f'Gridfinity {label}, shared by all bins and baseplates')
        tagUtils.tagParameter(parameter, tagName)
        commonUtils.debugLog(f'{logPrefix} {label}: created shared parameter {parameter.name} = {parameter.expression}')
        return parameter
    if not isUsableLengthParameter(design, parameter, minimum):
        reason = 'is not a usable length'
    elif not math.isclose(parameter.value, value, abs_tol=const.DEFAULT_FILTER_TOLERANCE):
        reason = 'differs from the dialog value'
    else:
        commonUtils.debugLog(f'{logPrefix} {label}: using existing shared parameter {parameter.name} = {parameter.expression} ({source})')
        return parameter
    ownParameter = parameterUtils.addLengthParameter(design, fallbackName, value, f'Gridfinity {owner} {label}')
    commonUtils.debugLog(f'{logPrefix} {label}: existing parameter {parameter.name} = {parameter.expression} ({source}) {reason}, created {ownParameter.name} = {ownParameter.expression} for this {owner}')
    return ownParameter

def findOrCreateBaseUnitParameters(
    design: adsk.fusion.Design,
    width: float,
    length: float,
    ownParameterPrefix: str,
    owner: str,
    logPrefix: str,
) -> tuple[adsk.fusion.UserParameter, adsk.fusion.UserParameter]:
    """Shared base width and length units, or ones of the owner's own named with the given prefix"""
    return (
        findOrCreateSharedLengthParameter(
            design,
            tagUtils.TAG_BASE_WIDTH_PARAMETER,
            BASE_WIDTH_PARAMETER,
            'base width unit',
            BASE_UNIT_MIN,
            width,
            parameterUtils.parameterName(ownParameterPrefix, BASE_WIDTH_FALLBACK_PARAMETER),
            owner,
            logPrefix,
        ),
        findOrCreateSharedLengthParameter(
            design,
            tagUtils.TAG_BASE_LENGTH_PARAMETER,
            BASE_LENGTH_PARAMETER,
            'base length unit',
            BASE_UNIT_MIN,
            length,
            parameterUtils.parameterName(ownParameterPrefix, BASE_LENGTH_FALLBACK_PARAMETER),
            owner,
            logPrefix,
        ),
    )
