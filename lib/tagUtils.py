import adsk.core, adsk.fusion
import json
import os

# Tags are stored in user documents, keep these literal so they don't change with add-in config
TAG_GROUP = 'LevMishin.GridfinityGenerator'
TAG_BIN = 'bin'
TAG_BASEPLATE = 'baseplate'
# on a user parameter of a bin, the config field its value is, see tagParameterField
TAG_PARAMETER_FIELD = 'parameterField'

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

def createTagValue(
    generatorVersion: str,
    settings: list[dict] = None,
    parameters: list[list[str]] = None,
    config: dict = None,
    field: str = None,
    bodyId: str = None,
    owner: str = None,
) -> str:
    """Settings are the dialog inputs the body was generated with, as sections of label and value pairs,
    parameters are label and name pairs of the user parameters driving it, config the settings to build it again
    by field name, see configJson.stateToJson. Field is the config field a user parameter holds. bodyId names the
    bin or baseplate, unique in the design, its own parameters have it as their owner and as the prefix of their names"""
    value = {
        'schemaVersion': TAG_SCHEMA_VERSION,
        'generatorVersion': generatorVersion,
    }
    if settings is not None:
        value['settings'] = settings
    if parameters is not None:
        value['parameters'] = parameters
    if config is not None:
        value['config'] = config
    if bodyId is not None:
        value['id'] = bodyId
    if field is not None:
        value['field'] = field
    if owner is not None:
        value['owner'] = owner
    return json.dumps(value)

def parseTagValue(value: str) -> dict:
    """The tag's presence is what marks an entity, so an unreadable value still yields a dict"""
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}

def tagBody(body: adsk.fusion.BRepBody, tagName: str, settings: list[dict] = None, parameters: list[list[str]] = None, config: dict = None, bodyId: str = None):
    """bodyId links the body with its parameters, see tagParameterField"""
    body.attributes.add(TAG_GROUP, tagName, createTagValue(getGeneratorVersion(), settings, parameters, config, bodyId=bodyId))

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

def tagParameterField(parameter: adsk.fusion.UserParameter, field: str, owner: str):
    """
    The config field the parameter's value is, see configJson.stateToJson, like binHeight, or an item's field by its
    index like compartmentPockets.2.label, and the id of the bin or baseplate it's of, see tagBody. Tagging again
    replaces it
    """
    parameter.attributes.add(TAG_GROUP, TAG_PARAMETER_FIELD, createTagValue(getGeneratorVersion(), field=field, owner=owner))

def readParameterTag(parameter: adsk.fusion.UserParameter) -> dict:
    """The field and owner the parameter was tagged with, empty for parameters made before they were tagged"""
    attribute = parameter.attributes.itemByName(TAG_GROUP, TAG_PARAMETER_FIELD)
    return parseTagValue(attribute.value) if attribute is not None else {}

def readParameterField(parameter: adsk.fusion.UserParameter) -> str | None:
    field = readParameterTag(parameter).get('field')
    return field if isinstance(field, str) and field else None

def findOwnedParameters(design: adsk.fusion.Design, owner: str) -> list[tuple[adsk.fusion.UserParameter, str]]:
    """The parameters of the bin or baseplate with that id, see tagBody, with the config field each holds"""
    owned = []
    for attribute in design.findAttributes(TAG_GROUP, TAG_PARAMETER_FIELD):
        parameter = adsk.fusion.UserParameter.cast(attribute.parent)
        value = parseTagValue(attribute.value)
        if parameter is not None and value.get('owner') == owner and isinstance(value.get('field'), str):
            owned.append((parameter, value['field']))
    return owned

def usedBodyIds(design: adsk.fusion.Design, tagName: str) -> set[str]:
    """The ids of the bodies with the tag, so a new one gets another, see tagBody"""
    return {str(tag['id']) for (_, tag) in findTaggedBodies(design, tagName) if tag.get('id')}

