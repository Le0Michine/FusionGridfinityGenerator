import adsk.core, adsk.fusion, traceback
import os

from .const import BIN_CORNER_FILLET_RADIUS
from .sketchUtils import createRectangle
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

def createGridfinityBase(base_width: float, tolerance: float, targetComponent: adsk.fusion.Component):
    actual_base_width = base_width - tolerance * 2.0
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # create rectangle for the base
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    base_plate_sketch: adsk.fusion.Sketch = sketches.add(targetComponent.xYConstructionPlane)
    createRectangle(actual_base_width, actual_base_width, base_plate_sketch)
        
    # extrude
    topExtrudeDepth = adsk.core.ValueInput.createByReal(0.23)
    topExtrudeInput = extrudeFeatures.createInput(base_plate_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    topExtrudeExtent = adsk.fusion.DistanceExtentDefinition.create(topExtrudeDepth)
    topExtrudeInput.setOneSideExtent(topExtrudeExtent,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByReal(0))
    topExtrudeFeature = extrudeFeatures.add(topExtrudeInput)

    # fillet
    filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
    filletInput = filletFeatures.createInput()
    filletInput.isRollingBallCorner = True
    fillet_edges = adsk.core.ObjectCollection.create()
    faces: adsk.fusion.BRepFaces = targetComponent.bRepBodies.item(0).faces
    for i in range(0, 4):
        fillet_edges.add(faces.item(i).edges.item(1))
    filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByReal(BIN_CORNER_FILLET_RADIUS), True)
    filletFeatures.add(filletInput)

    # chamfer
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(topExtrudeFeature.endFaces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        topExtrudeDepth,
        True)
    chamferFeatures.add(chamferInput)

    # extrude again
    topExtrudeDepth = adsk.core.ValueInput.createByReal(0.27)
    extrude = extrudeFeatures.addSimple(
        faces.item(8),
        topExtrudeDepth,
        adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # chamfer again
    chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
    chamferInput = chamferFeatures.createInput2()
    chamfer_edges = adsk.core.ObjectCollection.create()
    # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
    chamfer_edges.add(extrude.endFaces.item(0).edges.item(0))
    chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
        adsk.core.ValueInput.createByReal(0.08),
        True)
    chamferFeatures.add(chamferInput)
    return targetComponent.bRepBodies.item(0)
