# Assuming you have not changed the general structure of the template no modification is needed in this file.
from . import commands
from . import api
from .lib import fusion360utils as futil
from .lib import scriptModule


def run(context):
    try:
        # This will run the start function in each of your commands as defined in commands/__init__.py
        commands.start()
        if not scriptModule.register(api):
            futil.log(f'Another module is named {scriptModule.MODULE_NAME}, scripts can\'t import the add-in by it')

    except:
        futil.handle_error('run')


def stop(context):
    try:
        scriptModule.unregister(api)
        # Remove all of the event handlers your app has created
        futil.clear_handlers()

        # This will run the start function in each of your commands as defined in commands/__init__.py
        commands.stop()

    except:
        futil.handle_error('stop')