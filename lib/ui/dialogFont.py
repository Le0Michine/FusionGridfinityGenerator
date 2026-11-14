import adsk.core
import functools
import glob
import pathlib

@functools.cache
def dialogFontUrl(weight: str = 'Medium') -> str:
    """
    The dialog's font from the Fusion install, for pages shown in dialogs, empty when it isn't found. weight: the cut
    of the font as its files name it, Medium is the dialog's text, Bold its bold text
    """
    # the api package sits in Api/Python/packages/adsk of the install, its web panels bring the font along
    install = pathlib.Path(adsk.core.__file__).resolve().parents[4]
    # mac and windows installs, a recursive search would hold up the dialog
    for pattern in [f'Resources/FusionCDEHostApps/*/ArtifaktElement{weight}.*.woff2', f'FusionCDEHostApps/*/ArtifaktElement{weight}.*.woff2']:
        matches = sorted(glob.glob(str(install / pattern)))
        if len(matches) > 0:
            return pathlib.Path(matches[0]).as_uri()
    return ''
