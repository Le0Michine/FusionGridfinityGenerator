import adsk.core, adsk.fusion
import json
import os

# Tags are stored in user documents, keep these literal so they don't change with add-in config
TAG_GROUP = 'LevMishin.GridfinityGenerator'
TAG_BIN = 'bin'
TAG_BASEPLATE = 'baseplate'

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

def createTagValue(generatorVersion: str) -> str:
    return json.dumps({
        'schemaVersion': TAG_SCHEMA_VERSION,
        'generatorVersion': generatorVersion,
    })

def parseTagValue(value: str) -> dict:
    """The tag's presence is what marks an entity, so an unreadable value still yields a dict"""
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}

def tagBody(body: adsk.fusion.BRepBody, tagName: str):
    body.attributes.add(TAG_GROUP, tagName, createTagValue(getGeneratorVersion()))

def findTaggedBodies(design: adsk.fusion.Design, tagName: str) -> list[tuple[adsk.fusion.BRepBody, dict]]:
    """Returns native bodies, bodies inside components still need an occurrence for their placement"""
    taggedBodies = []
    for attribute in design.findAttributes(TAG_GROUP, tagName):
        body = adsk.fusion.BRepBody.cast(attribute.parent)
        if body is not None:
            taggedBodies.append((body, parseTagValue(attribute.value)))
    return taggedBodies
