"""
conftest.py — bootstraps the test environment so commandUiState.py
can be imported outside Fusion 360.

The challenge: commandUiState.py uses relative imports (`from ...lib import
fusion360utils`) that assume it is loaded as part of the project's package
tree.  We satisfy this by:

  1. Pointing sys.path at tests/stubs so `import adsk` resolves to our stubs.
  2. Adding the project root to sys.path.
  3. Pre-injecting stub entries into sys.modules for the relative packages
     so Python's importer finds them without needing a real package __init__.
"""
import sys
import os
import types

# ── 1. sys.path setup ───────────────────────────────────────────────────────
tests_dir    = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(tests_dir)
stubs_dir    = os.path.join(tests_dir, "stubs")

for p in (stubs_dir, project_root):
    if p not in sys.path:
        sys.path.insert(0, p)

# ── 2. Stub for fusion360utils (provides futil.log) ─────────────────────────
def _make_futil_stub():
    m = types.ModuleType("fusion360utils")
    m.log = lambda *a, **kw: None
    m.handle_error = lambda *a, **kw: None
    m.clear_handlers = lambda *a, **kw: None
    m.add_handler = lambda *a, **kw: None
    return m

futil_stub = _make_futil_stub()

# ── 3. Pre-populate sys.modules with every package node that commandUiState
#       tries to walk via relative import "...lib.fusion360utils".
#
#       commandUiState lives at:  lib/ui/commandUiState.py
#       Its relative import is:   from ...lib import fusion360utils
#       That resolves to:          <root>.lib.fusion360utils
#       where <root> is the top-level package (one level above lib/).
#
#       We create a minimal in-memory package tree so Python is happy.
# ────────────────────────────────────────────────────────────────────────────

def _pkg(name: str, parent=None):
    """Create and register a bare package module."""
    m = types.ModuleType(name)
    m.__path__ = []          # marks it as a package
    m.__package__ = name
    sys.modules[name] = m
    if parent is not None:
        setattr(parent, name.rsplit(".", 1)[-1], m)
    return m

# Root package (represents the project root as a virtual package)
root_pkg       = _pkg("FusionGridfinityGenerator")
lib_pkg        = _pkg("FusionGridfinityGenerator.lib",        root_pkg)
lib_ui_pkg     = _pkg("FusionGridfinityGenerator.lib.ui",     lib_pkg)
fu_pkg         = _pkg("FusionGridfinityGenerator.lib.fusion360utils", lib_pkg)

# Attach the futil stub so `from ...lib import fusion360utils` resolves
fu_pkg.log          = futil_stub.log
fu_pkg.handle_error = futil_stub.handle_error
lib_pkg.fusion360utils = fu_pkg
sys.modules["FusionGridfinityGenerator.lib.fusion360utils"] = fu_pkg

# ── 4. Load the real commandUiState into the virtual package ─────────────────
import importlib.util

_cu_path = os.path.join(project_root, "lib", "ui", "commandUiState.py")
_spec    = importlib.util.spec_from_file_location(
    "FusionGridfinityGenerator.lib.ui.commandUiState",
    _cu_path,
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "FusionGridfinityGenerator.lib.ui"
sys.modules["FusionGridfinityGenerator.lib.ui.commandUiState"] = _mod
_spec.loader.exec_module(_mod)

# Make CommandUiState importable as a top-level name for convenience
sys.modules["commandUiState"] = _mod

