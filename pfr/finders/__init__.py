# Fill in PlayerSeasonFinder docstring
from pfr.finders.PlayerSeasonFinder import PlayerSeasonFinder, getConstants

constants = getConstants()
inpDefs = constants['INPUTS_DEFAULTS']
compStats = constants['COMP_STATS']
sortStats = constants['SORT_STATS']

paramDocstring = '\n'.join(':param {}: default="{}"'.format(k, v)
                           for k, v in sorted(inpDefs.iteritems()))
compStatsString = '\n'.join('* {}'.format(cs) for cs in compStats)
sortStatsString = '\n'.join('* {}'.format(ss) for ss in sortStats)


PlayerSeasonFinder.__doc__ = """
Finds player-seasons that match criteria supplied by keyword arguments.

{}
:returns: list of matching player-season tuples
:rtype: [(player relative URL, season year)]

Options for comparison stats:
{}

Options for sorting stats:
{}
""".format(paramDocstring, compStatsString, sortStatsString)


# clean up namespace
exposed_vars = [
    'PlayerSeasonFinder'
]
variables = locals().keys()
for var in variables:
    # if not __var__ and not exposed_vars and not meant to be exposed...
    if not (var.startswith('__') or var == 'exposed_vars' 
            or var in exposed_vars):
        # delete the variable
        del locals()[var]

del exposed_vars
