import collections.abc
from typing import Tuple
import adsk.core, adsk.fusion, traceback
import os
import math

def objectCollectionFromList(*lists: Tuple[collections.abc.Collection, ...]):
    collection = adsk.core.ObjectCollection.create();
    for list in lists:
        for item in list:
            collection.add(item)
    return collection
