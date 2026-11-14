import subprocess
import sys

# Text to the system clipboard. Pages in dialogs can't be relied on for it, Fusion's browser may not let them

def copyText(text: str) -> None:
    """Raises OSError or subprocess.SubprocessError when the clipboard can't be set"""
    if sys.platform == 'darwin':
        # pbcopy reads the text as UTF-8 only with a UTF-8 locale
        subprocess.run(['pbcopy'], input=text.encode('utf-8'), env={'LANG': 'en_US.UTF-8'}, check=True, timeout=5)
    elif sys.platform == 'win32':
        _copyTextWindows(text)
    else:
        raise OSError(f'No clipboard on {sys.platform}')

def _copyTextWindows(text: str) -> None:
    import ctypes
    from ctypes import wintypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    # handles are pointer sized, the default int return would cut them on 64 bit
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    data = text.encode('utf-16-le') + b'\0\0'
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        user32.EmptyClipboard()
        # the clipboard owns the memory once it's set
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        user32.CloseClipboard()
