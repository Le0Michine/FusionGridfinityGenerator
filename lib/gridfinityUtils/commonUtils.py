import collections.abc
from typing import Tuple
import adsk.core, adsk.fusion, traceback
import os
import math
import time

from ...lib import fusion360utils as futil
from ... import config

def fileLog(message: str):
    """Text command window in debug mode, and always the Fusion log file, for what a bug report needs"""
    futil.log(message)
    adsk.core.Application.get().log(message, adsk.core.LogLevels.InfoLogLevel, adsk.core.LogTypes.FileLogType)

def debugLog(message: str):
    """Text command window in debug mode, and the Fusion log file too, so it survives a restart"""
    futil.log(message)
    if config.DEBUG:
        adsk.core.Application.get().log(message, adsk.core.LogLevels.InfoLogLevel, adsk.core.LogTypes.FileLogType)

class StepTimer():
    """Logs how long each step of a generator took, in debug mode also to the Fusion log file"""
    def __init__(self, name: str):
        self.name = name
        self.startTime = time.perf_counter()
        self.lastTime = self.startTime

    def log(self, message: str):
        debugLog(message)

    def step(self, label: str):
        now = time.perf_counter()
        self.log(f'{self.name} | {label}: {now - self.lastTime:.3f}s')
        self.lastTime = now

    def total(self):
        self.log(f'{self.name} | total: {time.perf_counter() - self.startTime:.3f}s')

def objectCollectionFromList(*lists: Tuple[collections.abc.Collection, ...]):
    collection = adsk.core.ObjectCollection.create();
    for list in lists:
        for item in list:
            collection.add(item)
    return collection
