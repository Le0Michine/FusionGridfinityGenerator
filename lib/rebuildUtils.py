import adsk.core, adsk.fusion
import re
from dataclasses import dataclass, field
from typing import Callable

from . import configJson
from . import tagUtils
from .gridfinityUtils import commonUtils

# Rebuilding a generated body at its place in the timeline: the new one is built right after the old one's timeline
# group, the features after it that use the old bodies get the new ones and the old group goes. Features picking a
# face or an edge of the old bodies can't be moved over, Fusion flags them, see RebuildTarget.newlyUnhealthy

LOG_PREFIX = 'Gridfinity rebuild'

HEALTHY = adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState

@dataclass
class RebuildTarget:
    """A generated body's timeline group and what is needed to build its replacement in place"""
    group: adsk.fusion.TimelineGroup
    # native bodies the group generated with the tag, the ones features after it may use
    bodies: list[adsk.fusion.BRepBody]
    # the component the group made in a hybrid design, none in a part design where it builds into the root
    occurrence: adsk.fusion.Occurrence | None
    # the offset the group moved its bodies by, in cm
    placement: tuple[float, float]
    # timeline items after the group, in order, with their health before the rebuild
    laterItems: list[adsk.fusion.TimelineObject]
    laterHealth: list[int] = field(default_factory=list)
    # the group's items before the rebuild, the only ones it deletes, see removeOldGroup
    groupItems: list[adsk.fusion.TimelineObject] = field(default_factory=list)

def nativeBody(body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    return body.nativeObject if body.assemblyContext is not None else body

def isGroupItem(group: adsk.fusion.TimelineGroup, item: adsk.fusion.TimelineObject) -> bool:
    return item == group or (item.parentGroup is not None and item.parentGroup == group)

def timelineItems(timeline: adsk.fusion.Timeline) -> list[adsk.fusion.TimelineObject]:
    """Every item in timeline order, items of groups in place of their group, groups themselves left out"""
    items = []
    def add(item: adsk.fusion.TimelineObject):
        # an item of a group may come up on its own as well, see commandSnapshotTests.unhealthyFeatures
        if not any(seen == item for seen in items):
            items.append(item)
    for index in range(timeline.count):
        item = timeline.item(index)
        if item.isGroup:
            group = adsk.fusion.TimelineGroup.cast(item)
            for childIndex in range(group.count):
                add(group.item(childIndex))
        else:
            add(item)
    return items

def generatedBy(item: adsk.fusion.TimelineObject, body: adsk.fusion.BRepBody) -> bool:
    """Whether the item made or changed the native body, or made the component it's in"""
    entity = item.entity
    occurrence = adsk.fusion.Occurrence.cast(entity)
    if occurrence is not None:
        return occurrence.component == body.parentComponent
    feature = adsk.fusion.Feature.cast(entity)
    if feature is None:
        return False
    return any(featureBody == body for featureBody in feature.bodies)

def findGroup(design: adsk.fusion.Design, body: adsk.fusion.BRepBody) -> adsk.fusion.TimelineGroup | None:
    """The timeline group the generator made the native body in, none when it was ungrouped"""
    groups = design.timeline.timelineGroups
    for groupIndex in range(groups.count):
        group = groups.item(groupIndex)
        if any(generatedBy(group.item(index), body) for index in range(group.count)):
            return group
    return None

def isPlacementName(name: str, placementName: str) -> bool:
    """Fusion numbers a name already taken in the component, like Bin placement (2) of the second bin in a part design"""
    return name == placementName or (name.startswith(f'{placementName} (') and name.endswith(')'))

def groupPlacement(group: adsk.fusion.TimelineGroup, placementName: str) -> tuple[float, float]:
    """XY offset the group's placement move of that name translates by, none moved the bodies when it isn't there"""
    moves = []
    for index in range(group.count):
        move = adsk.fusion.MoveFeature.cast(group.item(index).entity)
        if move is None:
            continue
        moves.append(move.name)
        if not isPlacementName(move.name, placementName):
            continue
        definition = adsk.fusion.MoveFeatureTranslateXYZDefinition.cast(move.definition)
        if definition is not None:
            return (definition.xDistance.value, definition.yDistance.value)
        commonUtils.fileLog(f'{LOG_PREFIX} {move.name} in {group.name} isn\'t a translation, placing at the origin')
    # a bin built at the origin has none
    commonUtils.debugLog(f'{LOG_PREFIX} no {placementName} in {group.name}, placing at the origin, its moves: {moves}')
    return (0, 0)

def findTarget(design: adsk.fusion.Design, body: adsk.fusion.BRepBody, tagName: str, placementName: str) -> RebuildTarget:
    """Placement name is of the move the generator places the bodies with. Raises ValueError when the body can't be rebuilt in place"""
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise ValueError('Rebuilding needs the design history, the timeline, turned on')
    body = nativeBody(body)
    group = findGroup(design, body)
    if group is None:
        raise ValueError(f'The timeline group {body.name} was generated in wasn\'t found, it may have been ungrouped')
    items = [group.item(index) for index in range(group.count)]
    bodies = [taggedBody for (taggedBody, _) in tagUtils.findTaggedBodies(design, tagName) if any(generatedBy(item, taggedBody) for item in items)]
    if len(bodies) == 0:
        raise ValueError(f'No generated bodies were found in the timeline group {group.name}')
    occurrence = next((adsk.fusion.Occurrence.cast(item.entity) for item in items if adsk.fusion.Occurrence.cast(item.entity) is not None), None)
    allItems = timelineItems(design.timeline)
    lastGroupIndex = max(index for (index, item) in enumerate(allItems) if isGroupItem(group, item))
    laterItems = allItems[lastGroupIndex + 1:]
    return RebuildTarget(
        group,
        bodies,
        occurrence,
        groupPlacement(group, placementName),
        laterItems,
        [item.healthState for item in laterItems],
        items,
    )

def rollAfterGroup(target: RebuildTarget):
    """Puts the marker right after the group, what is built next goes before the later features"""
    # an expanded group can't be rolled to, and with the marker after its last item what is built next joins it
    target.group.isCollapsed = True
    target.group.rollTo(False)

def hideOldBody(target: RebuildTarget):
    """
    For a preview, the old bodies stay where the new ones are shown otherwise. Turning their light bulbs off left them
    shown, the group is suppressed instead, its items one by one when Fusion won't suppress the group
    """
    try:
        target.group.isSuppressed = True
        return
    except RuntimeError as err:
        commonUtils.debugLog(f'{LOG_PREFIX} the timeline group {target.group.name} wasn\'t suppressed for the preview, {err}')
    for item in target.groupItems:
        try:
            item.isSuppressed = True
        except RuntimeError as err:
            commonUtils.debugLog(f'{LOG_PREFIX} {item.name} wasn\'t suppressed for the preview, {err}')

def bodyMap(target: RebuildTarget, newBodies: list[adsk.fusion.BRepBody]) -> list[tuple[adsk.fusion.BRepBody, adsk.fusion.BRepBody]]:
    """
    Pairs of an old native body and the new one taking its place. Bodies of the same count pair up by where they
    are, front row first, all go to a single new body, none pair up otherwise
    """
    def position(body: adsk.fusion.BRepBody):
        box = body.boundingBox
        return (round(box.minPoint.y, 3), round(box.minPoint.x, 3))
    newBodies = [nativeBody(body) for body in newBodies]
    if len(newBodies) == 1:
        return [(body, newBodies[0]) for body in target.bodies]
    if len(newBodies) == len(target.bodies):
        return list(zip(sorted(target.bodies, key=position), sorted(newBodies, key=position)))
    return []

def replaceBodies(
    target: RebuildTarget,
    newBodies: list[adsk.fusion.BRepBody],
    newOccurrence: adsk.fusion.Occurrence | None,
) -> list[str]:
    """
    Gives the later features using the old bodies the new ones instead, returns the names of those it couldn't.
    Features only take new bodies with the marker right before them, so it moves through the later items
    """
    pairs = bodyMap(target, newBodies)

    def replacement(entity):
        body = adsk.fusion.BRepBody.cast(entity)
        if body is None:
            return entity
        native = nativeBody(body)
        newBody = next((new for (old, new) in pairs if old == native), None)
        if newBody is None:
            return entity
        if body.assemblyContext is None:
            return newBody
        # a body of the old component is now one of the new component, a body of a copy of it stays in that copy
        context = newOccurrence if target.occurrence is not None and body.assemblyContext == target.occurrence else body.assemblyContext
        return newBody.createForAssemblyContext(context) if context is not None else newBody

    def replaced(entities: list) -> list | None:
        """The entities with the new bodies, none when there's nothing to replace"""
        swapped = [replacement(entity) for entity in entities]
        return swapped if any(new is not old for (new, old) in zip(swapped, entities)) else None

    def collection(entities: list) -> adsk.core.ObjectCollection:
        return commonUtils.objectCollectionFromList(entities)

    # items of a collapsed group can't be rolled to, the groups are expanded meanwhile
    collapsedGroups = []
    for item in target.laterItems:
        group = item.parentGroup
        if group is not None and group.isCollapsed and not any(seen == group for seen in collapsedGroups):
            collapsedGroups.append(group)
    for group in collapsedGroups:
        group.isCollapsed = False

    failed = []
    for item in target.laterItems:
        entity = item.entity
        feature = adsk.fusion.Feature.cast(entity)
        if feature is None:
            continue
        try:
            replaceFeatureBodies(item, feature, replaced, collection)
        except Exception as err:
            commonUtils.fileLog(f'{LOG_PREFIX} couldn\'t give {item.name} the new bodies, {err}')
            failed.append(item.name)
    # a group the marker is in can't be collapsed
    target.group.parentTimeline.moveToEnd()
    for group in collapsedGroups:
        group.isCollapsed = True
    return failed

# the inputs of a feature that may hold bodies, by the feature type, ObjectCollections and lists of entities
BODY_LIST_INPUTS = [
    (adsk.fusion.ExtrudeFeature, 'participantBodies'),
    (adsk.fusion.RevolveFeature, 'participantBodies'),
    (adsk.fusion.SweepFeature, 'participantBodies'),
    (adsk.fusion.LoftFeature, 'participantBodies'),
    (adsk.fusion.HoleFeature, 'participantBodies'),
    (adsk.fusion.PipeFeature, 'participantBodies'),
]
BODY_COLLECTION_INPUTS = [
    (adsk.fusion.CombineFeature, 'toolBodies'),
    (adsk.fusion.MoveFeature, 'inputEntities'),
    (adsk.fusion.MirrorFeature, 'inputEntities'),
    (adsk.fusion.RectangularPatternFeature, 'inputEntities'),
    (adsk.fusion.CircularPatternFeature, 'inputEntities'),
    (adsk.fusion.PathPatternFeature, 'inputEntities'),
    (adsk.fusion.ScaleFeature, 'inputEntities'),
    (adsk.fusion.SplitBodyFeature, 'splitBodies'),
]
BODY_INPUTS = [
    (adsk.fusion.CombineFeature, 'targetBody'),
    (adsk.fusion.SilhouetteSplitFeature, 'targetBody'),
]

def replaceFeatureBodies(item: adsk.fusion.TimelineObject, feature: adsk.fusion.Feature, replaced, collection):
    inputs = [(featureType.cast(feature), name, kind) for (inputs, kind) in [(BODY_LIST_INPUTS, 'list'), (BODY_COLLECTION_INPUTS, 'collection'), (BODY_INPUTS, 'body')] for (featureType, name) in inputs]
    inputs = [(typed, name, kind) for (typed, name, kind) in inputs if typed is not None]
    if len(inputs) == 0:
        return
    item.rollTo(True)
    for (typed, name, kind) in inputs:
        value = getattr(typed, name)
        if value is None:
            continue
        entities = [value] if kind == 'body' else list(value)
        swapped = replaced(entities)
        if swapped is None:
            continue
        if kind == 'body':
            setattr(typed, name, swapped[0])
        elif kind == 'collection':
            setattr(typed, name, collection(swapped))
        else:
            setattr(typed, name, swapped)
        commonUtils.debugLog(f'{LOG_PREFIX} {item.name} {name} now uses the new bodies')

def removeOldGroup(target: RebuildTarget) -> list[str]:
    """
    Once the later features have the new bodies, with the marker back at the end. Fusion may refuse to delete the
    group as a whole, without saying why, then its items go one by one, the last first so none is still used by
    what's left, and what it won't delete is suppressed. Returns the names of those
    """
    group = target.group
    groupName = group.name
    if group.count != len(target.groupItems):
        # deleting it would take whatever joined it too
        commonUtils.fileLog(f'{LOG_PREFIX} the timeline group {groupName} has {group.count} items, {len(target.groupItems)} before the rebuild')
        raise RuntimeError(f'The timeline group {groupName} of the old bin changed while rebuilding, it was left as is')
    group.isCollapsed = True
    try:
        if group.deleteMe(True):
            return []
        commonUtils.fileLog(f'{LOG_PREFIX} the timeline group {groupName} wasn\'t deleted, deleting its items one by one')
    except RuntimeError as err:
        commonUtils.fileLog(f'{LOG_PREFIX} the timeline group {groupName} wasn\'t deleted, {err}, deleting its items one by one')
    # items of a group can't be deleted on their own, the group goes and they stay in the timeline
    if group.isValid:
        group.deleteMe(False)
    kept = []
    for item in reversed(target.groupItems):
        if not item.isValid:
            continue
        name = item.name
        try:
            if item.isDeletable and item.deleteObject():
                continue
            commonUtils.fileLog(f'{LOG_PREFIX} {name} of {groupName} wasn\'t deleted, deletable: {item.isDeletable}')
        except RuntimeError as err:
            commonUtils.fileLog(f'{LOG_PREFIX} {name} of {groupName} wasn\'t deleted, {err}')
        try:
            item.isSuppressed = True
        except RuntimeError as err:
            commonUtils.fileLog(f'{LOG_PREFIX} {name} of {groupName} wasn\'t suppressed either, {err}')
        kept.append(name)
    return kept

def newlyUnhealthy(target: RebuildTarget) -> list[str]:
    """Later items that were fine before and have a warning or an error now, with Fusion's message"""
    notes = []
    for (item, health) in zip(target.laterItems, target.laterHealth):
        if not item.isValid or health != HEALTHY or item.healthState == HEALTHY:
            continue
        notes.append(f'{item.name}: {item.errorOrWarningMessage or "needs its inputs picked again"}')
    return notes

def removeUnusedParameters(design: adsk.fusion.Design, names: list[str]):
    """Parameters of the old body the new one doesn't use, kept when something else refers to them"""
    for name in names:
        parameter = design.userParameters.itemByName(name)
        if parameter is None or not parameter.isDeletable:
            continue
        # deleteMe is said to answer true for parameters still referenced, isDeletable covers that
        parameter.deleteMe()
        commonUtils.debugLog(f'{LOG_PREFIX} deleted the unused parameter {name}')

def findBodyByToken(design: adsk.fusion.Design, token: str) -> adsk.fusion.BRepBody:
    """The body a dialog rebuilds, found again after each preview is undone"""
    entities = design.findEntityByToken(token)
    body = adsk.fusion.BRepBody.cast(entities[0]) if len(entities) > 0 else None
    if body is None:
        raise ValueError('The body to rebuild is no longer in the design')
    return body

def tagParameterNames(body: adsk.fusion.BRepBody) -> list[str]:
    """Names of the user parameters in the body's tag"""
    tag = tagUtils.readBodyTag(body)
    parameters = tag[1].get('parameters') if tag is not None else None
    if not isinstance(parameters, list):
        return []
    return [str(item[1]) for item in parameters if isinstance(item, list) and len(item) == 2]

def prefixOf(names: list[str], baseName: str) -> str | None:
    """The numbered prefix of a body's own parameters, like gfBin2 of gfBin2_heightU, none when it has none"""
    pattern = re.compile(rf'^({re.escape(baseName)}\d+)_')
    for name in names:
        match = pattern.match(name)
        if match is not None:
            return match.group(1)
    return None

def bodyId(body: adsk.fusion.BRepBody, baseName: str) -> str | None:
    """The id of the body, see tagUtils.tagBody, one built before bodies had ids goes by the prefix of its parameters"""
    tag = tagUtils.readBodyTag(body)
    return (tag[1].get('id') if tag is not None else None) or prefixOf(tagParameterNames(body), baseName)

def parameterFields(parameters: list, findParameter, labelFields: dict[str, str]) -> list[tuple[str, adsk.fusion.UserParameter]]:
    """
    The parameters of a body's tag, its label and name pairs, that are still in the design, with the config field
    each holds, see tagUtils.tagParameterField. Parameters made before they were tagged go by their label in
    labelFields
    """
    fields = []
    for item in parameters if isinstance(parameters, list) else []:
        if not isinstance(item, list) or len(item) != 2:
            continue
        parameter = findParameter(str(item[1]))
        if parameter is None:
            continue
        fieldName = tagUtils.readParameterField(parameter) or labelFields.get(str(item[0]))
        if fieldName is not None:
            fields.append((fieldName, parameter))
    return fields

def configWithParameters(generator: str, config: dict, parameters: list, findParameter, labelFields: dict[str, str]) -> dict:
    """
    The config a body was built with, with the values its parameters have now, so changes made to them since aren't
    undone by building it again. findParameter looks one up by name. A field of a list item goes by its index, like
    compartmentPockets.2.label
    """
    config = dict(config)
    for (fieldName, parameter) in parameterFields(parameters, findParameter, labelFields):
        isText = parameter.valueType == adsk.fusion.ParameterValueTypes.TextParameterValueType
        if isText:
            value = parameter.textValue
        elif fieldName in configJson.MM_FIELDS[generator]:
            value = round(parameter.value * 10, 6)
        else:
            value = round(parameter.value, 6)
        path = fieldName.split('.')
        if len(path) == 3 and path[1].isdigit() and isinstance(config.get(path[0]), list):
            items = [dict(item) if isinstance(item, dict) else item for item in config[path[0]]]
            if int(path[1]) < len(items) and isinstance(items[int(path[1])], dict):
                items[int(path[1])][path[2]] = value
                config[path[0]] = items
        elif len(path) == 1 and fieldName in config:
            config[fieldName] = value
    return config

def rebuild(
    design: adsk.fusion.Design,
    target: RebuildTarget,
    prefix: str | None,
    baseName: str,
    isPreview: bool,
    build: Callable[[tuple[float, float], str | None, adsk.core.Matrix3D | None], list[adsk.fusion.BRepBody]],
    title: str,
) -> tuple[list[adsk.fusion.BRepBody], list[str]]:
    """
    Builds the replacement of the target in its place, keeping the features after it. build gets the placement, the
    prefix of the parameters to keep, none for new ones, and the transform of the component in a hybrid design, and
    returns the new bodies. Returns them with what of the later features needs a look, title names the body in it.
    A preview is undone anyway, it builds at the end of the timeline with the old body suppressed, rolling the
    timeline back and forth for each would be slow
    """
    transform = target.occurrence.transform2 if target.occurrence is not None else None
    if isPreview:
        hideOldBody(target)
        return (build(target.placement, None, transform), [])

    oldNames = tagParameterNames(target.bodies[0])
    rollAfterGroup(target)
    newBodies = build(target.placement, prefix, transform)
    newOccurrence = None
    if len(newBodies) > 0 and newBodies[0].parentComponent != design.rootComponent:
        occurrences = design.rootComponent.allOccurrencesByComponent(newBodies[0].parentComponent)
        newOccurrence = occurrences.item(0) if occurrences.count > 0 else None
    failed = replaceBodies(target, newBodies, newOccurrence)
    keptOldItems = removeOldGroup(target)
    # shared units stay, the body's own ones it no longer has go, like the label of a tab turned off
    newNames = tagParameterNames(newBodies[0]) if len(newBodies) > 0 else []
    removeUnusedParameters(design, [name for name in oldNames if prefix is not None and prefixOf([name], baseName) == prefix and name not in newNames])
    notes = [f'{name}: couldn\'t be given the new {title}' for name in failed] + newlyUnhealthy(target)
    notes += [f'{name}: of the old {title}, Fusion wouldn\'t delete it, it\'s suppressed instead' for name in keptOldItems]
    return (newBodies, notes)

def configChanges(generator: str, body: adsk.fusion.BRepBody, newConfig: dict) -> str:
    """What the rebuild changes of the config in the body's tag, a line per field as old -> new, for the log"""
    tag = tagUtils.readBodyTag(body)
    oldConfig = tag[1].get('config') if tag is not None else None
    if not isinstance(oldConfig, dict):
        return 'its old config isn\'t in its tag'
    changes = [f'  {name}: {oldConfig.get(name)!r} -> {value!r}' for (name, value) in newConfig.items() if oldConfig.get(name) != value]
    return 'changes:\n' + '\n'.join(changes) if len(changes) > 0 else 'no changes to its config'
