import adsk.core, adsk.fusion, traceback
from . import fusion360utils as futil
import configparser
import os
import json

CONFIG_FILE_NAME = 'config.ini'

def getDefaultConfig():
    config = configparser.ConfigParser()
    config['UI'] = {'IS_PROMOTED': 'yes'}
    return config

def readConfig(path: str):
    CONFIG_FILE_PATH = os.path.join(path, CONFIG_FILE_NAME)
    config = configparser.ConfigParser()
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            config.read(CONFIG_FILE_PATH)
            return config
        return getDefaultConfig()
    except:
        return getDefaultConfig()

def writeConfig(config: configparser.ConfigParser, path: str):
    try:
        CONFIG_FILE_PATH = os.path.join(path, CONFIG_FILE_NAME)
        if not os.path.exists(path):
            os.mkdir(path)
        with open(CONFIG_FILE_PATH, 'w') as configfile:
            config.write(configfile)
        return True
    except:
        return False

def deleteConfigFile(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except:
        futil.log(f'Couldn\'t delete config file from {path}')
        return None


def readJsonConfig(path: str):
    try:
        if os.path.exists(path):
            with open(path) as configFile:
                return json.load(configFile)
    except:
        futil.log(f'Couldn\'t load config file from {path}')
        return None
    
def dumpJsonConfig(path: str, config: any):
    try:
        futil.log(f'Writing config to path {os.path.dirname(path)}')
        if os.path.exists(os.path.dirname(path)):
            with open(path, 'w+') as configFile:
                json.dump(config, configFile, indent=True)
                return True
        else:
            futil.log(f'Config folder doesn\'t exist {os.path.dirname(path)}')
            return False
        
    except Exception as err:
        futil.log(f'Couldn\'t write config file to {path}, error: {err}')
        return None