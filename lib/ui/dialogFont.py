import adsk.core
import functools
import glob
import pathlib

@functools.cache
def dialogFontUrl() -> str:
    """The dialog's font from the Fusion install, for pages shown in dialogs, empty when it isn't found"""
    # the api package sits in Api/Python/packages/adsk of the install, its web panels bring the font along
    install = pathlib.Path(adsk.core.__file__).resolve().parents[4]
    # mac and windows installs, a recursive search would hold up the dialog
    for pattern in ['Resources/FusionCDEHostApps/*/ArtifaktElementMedium.*.woff2', 'FusionCDEHostApps/*/ArtifaktElementMedium.*.woff2']:
        matches = sorted(glob.glob(str(install / pattern)))
        if len(matches) > 0:
            return pathlib.Path(matches[0]).as_uri()
    return ''
