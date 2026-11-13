"""
Stand ins for the parts of the API a dialog only passes through: any attribute, call or subclass works and gives
another stand in. Modules hand them out for names they don't define, see moduleFallback
"""


class AnythingMeta(type):
    # class attributes of enums and event types, like LogLevels.InfoLogLevel
    def __getattr__(cls, name: str):
        if name.startswith('__'):
            raise AttributeError(name)
        return Anything()


class Anything(metaclass=AnythingMeta):
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name: str):
        if name.startswith('__'):
            raise AttributeError(name)
        return Anything()

    def __call__(self, *args, **kwargs):
        return Anything()

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False

    def __add__(self, other):
        return self

    __iadd__ = __add__


def moduleFallback(moduleName: str):
    """A module __getattr__ that makes a class for every name it doesn't define, so it can be used and subclassed"""
    classes = {}

    def getattr(name: str):
        if name.startswith('__'):
            raise AttributeError(name)
        if name not in classes:
            classes[name] = AnythingMeta(name, (Anything,), {'__module__': moduleName})
        return classes[name]
    return getattr
