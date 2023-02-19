import configparser
import os

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

