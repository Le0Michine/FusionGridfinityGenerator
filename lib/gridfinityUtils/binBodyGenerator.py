import adsk.core, adsk.fusion, traceback
import os

from .const import BIN_BODY_BOTTOM_THICKNESS, BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CONNECTION_RECESS_DEPTH, BIN_CORNER_FILLET_RADIUS, BIN_LIP_CHAMFER, BIN_WALL_THICKNESS, DEFAULT_FILTER_TOLERANCE
from .sketchUtils import createRectangle
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface


def createBox(
    width: float,
    length: float,
    height: float,
    targetComponent: adsk.fusion.Component,
    targetPlane: adsk.core.Base,
    ):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(targetPlane)
    createRectangle(width, length, recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    return extrude

def selectEdgesByLengtth(
    faces: adsk.fusion.BRepFaces,
    filterEdgeLength: float,
    filterEdgeTolerance: float,
):
    filteredEdges = adsk.core.ObjectCollection.create()
    for face in faces:
        for edge in face.edges:
            if abs(edge.length - filterEdgeLength) < filterEdgeTolerance:
                filteredEdges.add(edge)
    return filteredEdges

def filletEdgesByLength(
    faces: adsk.fusion.BRepFaces,
    radius: float,
    filterEdgeLength: float,
    targetComponent: adsk.fusion.Component,
    ):
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    bottomFilletInput = filletFeatures.createInput()
    bottomFilletInput.isRollingBallCorner = True
    bottomFilletEdges = selectEdgesByLengtth(faces, filterEdgeLength, DEFAULT_FILTER_TOLERANCE)
    bottomFilletInput.edgeSetInputs.addConstantRadiusEdgeSet(bottomFilletEdges, adsk.core.ValueInput.createByReal(radius), True)
    filletFeatures.add(bottomFilletInput)

def chamferEdgesByLength(
    faces: adsk.fusion.BRepFaces,
    distance: float,
    filterEdgeLength: float,
    filterEdgeTolerance: float,
    targetComponent: adsk.fusion.Component,
):
    features: adsk.fusion.Features = targetComponent.features
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = selectEdgesByLengtth(faces, filterEdgeLength, filterEdgeTolerance)
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        adsk.core.ValueInput.createByReal(distance),
        True)
    chamferFeatures.add(chamferInput)

def createGridfinityBinBody(
    baseWidth: float,
    binWidth: int,
    binLength: int,
    hightUnit: float,
    binHeight: int,
    tolerance: float,
    targetComponent: adsk.fusion.Component,
    emptyBin: bool = True
    ):

    actualBodyWidth = (baseWidth * binWidth) - tolerance * 2.0
    actualBodyLength = (baseWidth * binLength) - tolerance * 2.0
    binBodyTotalHeight = binHeight * hightUnit
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    # create rectangle for the body
    binBodyExtrude = createBox(
        actualBodyWidth,
        actualBodyLength,
        binBodyTotalHeight,
        targetComponent,
        targetComponent.xYConstructionPlane
    )

    # fillet
    filletEdgesByLength(
        binBodyExtrude.faces,
        BIN_CORNER_FILLET_RADIUS,
        binBodyTotalHeight,
        targetComponent,
    )

    # sketch on top
    binBodyOpeningSketch: adsk.fusion.Sketch = sketches.add(binBodyExtrude.endFaces.item(0))
    binBodyOpeningSketchConstraints: adsk.fusion.GeometricConstraints = binBodyOpeningSketch.geometricConstraints
    curvesList: list[adsk.fusion.SketchCurve] = []
    for curve in binBodyOpeningSketch.sketchCurves:
        curvesList.append(curve)
    binBodyOpeningSketchConstraints.addOffset(curvesList,
        adsk.core.ValueInput.createByReal(-BIN_WALL_THICKNESS),
        binBodyOpeningSketch.sketchCurves.sketchLines.item(0).startSketchPoint.geometry)
    for curve in curvesList:
        curve.isConstruction = True

    # extrude inside
    cutoutDepth = (binBodyTotalHeight - BIN_BODY_BOTTOM_THICKNESS) if emptyBin else BIN_CONNECTION_RECESS_DEPTH
    extrudeCutoutInput = extrudeFeatures.createInput(binBodyOpeningSketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
    extrudeCutoutInput.participantBodies = [binBodyExtrude.bodies.item(0)]
    extrudeCutoutInputExtent = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(cutoutDepth))
    extrudeCutoutInput.setOneSideExtent(
        extrudeCutoutInputExtent,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByReal(0),
    )
    extrudeCutout = extrudeFeatures.add(extrudeCutoutInput)

    # top chamfer
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(extrudeCutout.faces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        adsk.core.ValueInput.createByReal(BIN_LIP_CHAMFER),
        True)
    chamferFeatures.add(chamferInput)

    if emptyBin:
        # fillet at the bottom
        bottomFilletInput = filletFeatures.createInput()
        bottomFilletInput.isRollingBallCorner = True
        bottomFilletEdges = adsk.core.ObjectCollection.create()
        bottomFilletEdges.add(extrudeCutout.endFaces.item(0).edges.item(0))
        bottomFilletInput.edgeSetInputs.addConstantRadiusEdgeSet(bottomFilletEdges,
            adsk.core.ValueInput.createByReal(BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS),
            True)
        filletFeatures.add(bottomFilletInput)

    return binBodyExtrude.bodies.item(0)
