import sys
import types

# The add-in as a module scripts run in Fusion can import by a short name, those of an MCP server among them. Fusion
# loads the add-in under a name made of its folder's path, so a script couldn't find it otherwise. Kept free of Fusion
# imports so it can be unit tested

MODULE_NAME = 'gridfinity'
# set on the add-in's module, a module of that name without it is left alone
MARKER = 'IS_GRIDFINITY_GENERATOR'

def register(module: types.ModuleType, modules: dict = sys.modules) -> bool:
    """Imported as MODULE_NAME from now on, unless another module has the name, replaces an earlier run's"""
    existing = modules.get(MODULE_NAME)
    if existing is not None and not getattr(existing, MARKER, False):
        return False
    modules[MODULE_NAME] = module
    return True

def unregister(module: types.ModuleType, modules: dict = sys.modules):
    """No longer imported as MODULE_NAME, when it's the one registered"""
    if modules.get(MODULE_NAME) is module:
        del modules[MODULE_NAME]
