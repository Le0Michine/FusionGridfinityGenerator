"""adsk.fusion outside Fusion, there is no design open, so dialogs keep their own defaults"""

from .anything import moduleFallback

__getattr__ = moduleFallback(__name__)


class Design:
    @staticmethod
    def cast(obj):
        return None
