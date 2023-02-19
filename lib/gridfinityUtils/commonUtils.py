import collections.abc
import adsk.core, adsk.fusion, traceback
import os
import math

def objectCollectionFromList(items: collections.abc.Collection):
    collection = adsk.core.ObjectCollection.create();
    for item in items:
        collection.add(item)
    return collection
