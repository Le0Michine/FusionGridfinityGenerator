import adsk.core, adsk.fusion, traceback
import os



from .const import BIN_BODY_BOTTOM_THICKNESS, BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CONNECTION_RECESS_DEPTH, BIN_CORNER_FILLET_RADIUS, BIN_LIP_CHAMFER, BIN_LIP_WALL_THICKNESS, DEFAULT_FILTER_TOLERANCE
from .sketchUtils import createOffsetProfileSketch, createRectangle
from ...lib import fusion360utils as futil
from . import faceUtils
from ...lib.gridfinityUtils.extrudeUtils import simpleDistanceExtrude
from ...lib.gridfinityUtils.binBodyGeneratorInput import BinBodyGeneratorInput
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

def selectEdgesByLength(
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
    bottomFilletEdges = selectEdgesByLength(faces, filterEdgeLength, DEFAULT_FILTER_TOLERANCE)
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
    chamfer_edges = selectEdgesByLength(faces, filterEdgeLength, filterEdgeTolerance)
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        adsk.core.ValueInput.createByReal(distance),
        True)
    chamferFeatures.add(chamferInput)

def createGridfinityBinBody(
    input: BinBodyGeneratorInput,
    targetComponent: adsk.fusion.Component,
    ):

    actualBodyWidth = (input.baseWidth * input.binWidth) - input.xyTolerance * 2.0
    actualBodyLength = (input.baseWidth * input.binLength) - input.xyTolerance * 2.0
    binBodyTotalHeight = input.binHeight * input.heightUnit
    features: adsk.fusion.Features = targetComponent.features
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # create rectangle for the body
    binBodyExtrude = createBox(
        actualBodyWidth,
        actualBodyLength,
        binBodyTotalHeight,
        targetComponent,
        targetComponent.xYConstructionPlane
    )

    # round corners
    filletEdgesByLength(
        binBodyExtrude.faces,
        BIN_CORNER_FILLET_RADIUS,
        binBodyTotalHeight,
        targetComponent,
    )

    bottomCutoutFace: adsk.fusion.BRepFace = binBodyExtrude.endFaces.item(0);
    currentDepth = 0.0
    if input.hasLip:
        # sketch on top
        binBodyOpeningSketch = createOffsetProfileSketch(
            bottomCutoutFace,
            -BIN_LIP_WALL_THICKNESS,
            targetComponent,
        )
        # extrude inside
        lipCutout = simpleDistanceExtrude(
            binBodyOpeningSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            BIN_CONNECTION_RECESS_DEPTH,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            targetComponent,
        )
        # top chamfer
        chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
        topLipChamferInput = chamferFeatures.createInput2()
        topLipChamferEdges = adsk.core.ObjectCollection.create()
        # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
        topLipChamferEdges.add(lipCutout.faces.item(0).edges.item(0))
        topLipChamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(topLipChamferEdges,
            adsk.core.ValueInput.createByReal(BIN_LIP_CHAMFER),
            True)
        chamferFeatures.add(topLipChamferInput)

        bottomCutoutFace = lipCutout.endFaces.item(0)
        currentDepth += BIN_CONNECTION_RECESS_DEPTH

    if not input.isSolid:
        offset = (BIN_LIP_WALL_THICKNESS - input.wallThickness) if input.hasLip else -input.wallThickness
        innerCutoutSketch = createOffsetProfileSketch(
            bottomCutoutFace,
            offset,
            targetComponent,
        )

        innerCutout = simpleDistanceExtrude(
            innerCutoutSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            binBodyTotalHeight - BIN_BODY_BOTTOM_THICKNESS - currentDepth,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            targetComponent,
        )
        bottomCutoutFace = innerCutout.endFaces.item(0)

        if input.hasLip and offset > 0:
            # bottom lip chamfer, no lip if main wall thicker or same size as the lip
            chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
            bottomLipChamferInput = chamferFeatures.createInput2()
            bottomLipChamferEdges = adsk.core.ObjectCollection.create()
            # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
            bottomLipChamferEdges.add(innerCutout.startFaces.item(0).edges.item(0))
            bottomLipChamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(bottomLipChamferEdges,
                adsk.core.ValueInput.createByReal(offset),
                True)
            chamferFeatures.add(bottomLipChamferInput)
        
        # fillet at the bottom
        bottomFilletInput = filletFeatures.createInput()
        bottomFilletInput.isRollingBallCorner = True
        bottomFilletEdges = adsk.core.ObjectCollection.create()
        bottomFilletEdges.add(faceUtils.shortestEdge(bottomCutoutFace))
        bottomFilletInput.edgeSetInputs.addConstantRadiusEdgeSet(bottomFilletEdges,
            adsk.core.ValueInput.createByReal(max(BIN_BODY_CUTOUT_BOTTOM_FILLET_RADIUS, BIN_CORNER_FILLET_RADIUS - input.wallThickness)),
            True)
        filletFeatures.add(bottomFilletInput)

    return binBodyExtrude.bodies.item(0)
