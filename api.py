"""
The add-in for scripts run in Fusion while it runs, such as those of an MCP server: `import gridfinity`, see
lib/scriptModule.py. The modules scripts use are here by short names, each as the add-in has it loaded, so a script
works with the same objects as the dialogs. Fusion's API runs on its main thread only, and a script blocks Fusion
while it runs, so a long build is better split into several scripts
"""

from . import config
from .lib import configJson
from .lib import defaultSettings
from .lib import tagUtils
from .lib import bedPacking
from .lib import printBeds
from .lib import threeMf
from .lib import stlFile
from .commands.commandCreateBin import binBuilder
from .commands.commandCreateBin.inputState import InputState as BinInputState
from .commands.commandCreateBaseplate import baseplateBuilder
from .commands.commandCreateBaseplate.inputState import InputState as BaseplateInputState
from .commands.commandExport import entry as export
from .commands.commandExport.entry import exportBodies, savedOptions, ExportOptions, ExportResult

# see scriptModule.MARKER
IS_GRIDFINITY_GENERATOR = True

def version() -> str:
    """The add-in's version, as its bodies are tagged with"""
    return tagUtils.getGeneratorVersion()
