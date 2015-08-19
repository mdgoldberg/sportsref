PFR_BASE_URL = 'http://www.pro-football-reference.com/'

# clean up namespace
__all__ = [
    # modules/variables to expose
    'PFR_BASE_URL',
    'boxscores',
    'decorators'
    'players',
]
variables = locals().keys()
for var in variables:
    # if not __var__ and not meant to be exposed...
    if not (var.startswith('__') or var in __all__):
        # delete the variable
        del locals()[var]

del var, variables
