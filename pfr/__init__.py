PFR_BASE_URL = 'http://www.pro-football-reference.com/'

import boxscores
import decorators
import finders
import players

# clean up namespace
__all__ = [
    # modules/variables to expose
    'PFR_BASE_URL',
    'boxscores',
    'decorators',
    'finders',
    'players'
]
variables = locals().keys()
for var in variables:
    # if not _var and not meant to be exposed...
    if not (var.startswith('_') or var in __all__):
        # delete the variable
        del locals()[var]

del var, variables
