import adsk.core, adsk.fusion
import json
import os

# Tags are stored in user documents, keep these literal so they don't change with add-in config
TAG_GROUP = 'LevMishin.GridfinityGenerator'
TAG_BIN = 'bin'
TAG_BASEPLATE = 'baseplate'
TAG_HEIGHT_UNIT_PARAMETER = 'heightUnitParameter'
TAG_BASE_WIDTH_PARAMETER = 'baseWidthParameter'
TAG_BASE_LENGTH_PARAMETER = 'baseLengthParameter'

# Bump only on incompatible changes to the tag value, readers ignore fields they don't know
TAG_SCHEMA_VERSION = 1

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'GridfinityGenerator.manifest')

_generatorVersion = None

def getGeneratorVersion() -> str:
    global _generatorVersion
    if _generatorVersion is None:
        try:
            with open(MANIFEST_PATH, 'r') as manifest:
                _generatorVersion = str(json.load(manifest).get('version', ''))
        except (OSError, ValueError, AttributeError):
            _generatorVersion = ''
    return _generatorVersion

def createTagValue(generatorVersion: str, settings: list[dict] = None, parameters: list[list[str]] = None) -> str:
    """Settings are the dialog inputs the body was generated with, as sections of label and value pairs,
    parameters are label and name pairs of the user parameters driving it"""
    value = {
        'schemaVersion': TAG_SCHEMA_VERSION,
        'generatorVersion': generatorVersion,
    }
    if settings is not None:
        value['settings'] = settings
    if parameters is not None:
        value['parameters'] = parameters
    return json.dumps(value)

def parseTagValue(value: str) -> dict:
    """The tag's presence is what marks an entity, so an unreadable value still yields a dict"""
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}

def tagBody(body: adsk.fusion.BRepBody, tagName: str, settings: list[dict] = None, parameters: list[list[str]] = None):
    body.attributes.add(TAG_GROUP, tagName, createTagValue(getGeneratorVersion(), settings, parameters))

def readBodyTag(body: adsk.fusion.BRepBody) -> tuple[str, dict] | None:
    """Which generator tagged the body and the tag value, none for bodies it didn't generate"""
    for tagName in (TAG_BIN, TAG_BASEPLATE):
        attribute = body.attributes.itemByName(TAG_GROUP, tagName)
        if attribute is not None:
            return (tagName, parseTagValue(attribute.value))
    return None

def findTaggedBodies(design: adsk.fusion.Design, tagName: str) -> list[tuple[adsk.fusion.BRepBody, dict]]:
    """Returns native bodies, bodies inside components still need an occurrence for their placement"""
    taggedBodies = []
    for attribute in design.findAttributes(TAG_GROUP, tagName):
        body = adsk.fusion.BRepBody.cast(attribute.parent)
        if body is not None:
            taggedBodies.append((body, parseTagValue(attribute.value)))
    return taggedBodies

def tagParameter(parameter: adsk.fusion.UserParameter, tagName: str):
    parameter.attributes.add(TAG_GROUP, tagName, createTagValue(getGeneratorVersion()))

def findTaggedParameters(design: adsk.fusion.Design, tagName: str) -> list[tuple[adsk.fusion.UserParameter, dict]]:
    """Found by tag rather than by name, so a renamed parameter is still recognized"""
    taggedParameters = []
    for attribute in design.findAttributes(TAG_GROUP, tagName):
        parameter = adsk.fusion.UserParameter.cast(attribute.parent)
        if parameter is not None:
            taggedParameters.append((parameter, parseTagValue(attribute.value)))
    return taggedParameters
