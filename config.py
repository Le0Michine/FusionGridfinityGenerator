# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).

import os

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window. Generally, it's useful
# to set this to True while developing an add-in and set it to False when you
# are ready to distribute it.
DEBUG = True

# Commands for developing the add-in, such as the shape snapshot tests. Only when it runs from a git checkout,
# releases ship without the .git folder, while DEBUG stays on for logging
DEV_TOOLS = os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.git'))

# Gets the name of the add-in from the name of the folder the py file is in.
# This is used when defining unique internal names for various UI elements 
# that need a unique name. It's also recommended to use a company name as 
# part of the ID to better ensure the ID is unique.
ADDIN_NAME = 'GridfinityGenerator'
COMPANY_NAME = 'LevMishin'

# Palettes
sample_palette_id = f'{COMPANY_NAME}_{ADDIN_NAME}_palette_id'