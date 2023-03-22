import adsk.core, adsk.fusion, traceback

class StaticInputCache:
    actualBinDimensionsTable: adsk.core.TableCommandInput
    actualCompartmentDimensionUnitsTable: adsk.core.TableCommandInput