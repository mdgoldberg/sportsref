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
del constants, getConstants, inpDefs, compStats, sortStats
del paramDocstring, compStatsString, sortStatsString


# Fill in GamePlayFinder docstring
from pfr.finders.GamePlayFinder import GamePlayFinder, getInputsOptionsDefaults

IOD = getInputsOptionsDefaults()

paramStr = '\n'.join(
    ':param {}: default="{}"'.format(
        name,
        ','.join(dct['value'])
    )
    for name, dct in sorted(IOD.iteritems())
)

optsStr = '\n'.join(
    '{}: {}'.format(
        name,
        ','.join('"{}"'.format(opt) for opt in dct['options'])
    )
    if len(dct['options']) <= 10 else
    '{}: {}...{}'.format(
        name,
        ','.join('"{}"'.format(opt) for opt in dct['options'][:10]),
        ','.join('"{}"'.format(opt) for opt in dct['options'][-2:])
    )
    for name, dct in sorted(IOD.iteritems())
)

GamePlayFinder.__doc__ = """
Finds plays that match criteria supplied by keyword arguments.

Can use tm or team instead of team_id.
For multi-valued options (like down or rush direction), separate values with commas.
For options that are yes/no/either or yes/no/any, -1 is either/any, 0 is no, 1 is yes.

{}
:returns: Pandas dataframe of plays

Options for the inputs:
{}
""".format(paramStr, optsStr)

# clean up namespace
del getInputsOptionsDefaults, paramStr, optsStr, IOD

# modules/variables to expose
__all__ = [
    'PlayerSeasonFinder',
    'GamePlayFinder',
]
