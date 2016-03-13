# Fill in PlayerSeasonFinder docstring
import PSF

IOD = PSF.getInputsOptionsDefaults()

paramStr = '\n'.join(
    ':param {}: default="{}"'.format(
        name,
        ','.join(dct['value'])
    )
    for name, dct in sorted(IOD.iteritems()))
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
    for name, dct in sorted(IOD.iteritems()))


PSF.PlayerSeasonFinder.__doc__ = """
Finds player-seasons that match criteria supplied by keyword arguments.

Can use tm or team for team_id.
Can use yr, year, yrs, or years for year_min, year_max.
Can use [draft_]pos, [draft_]position, [draft_]positions for a shortcut for [draft_]positions.

{}
:returns: list of matching player-season tuples
:rtype: [(player ID, season year)]

Options for inputs:
{}
""".format(paramStr, optsStr)

# clean up namespace
del IOD, paramStr, optsStr


# Fill in GamePlayFinder docstring
import GPF

IOD = GPF.getInputsOptionsDefaults()

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

GPF.GamePlayFinder.__doc__ = """
Finds plays that match criteria supplied by keyword arguments.

Can use tm or team instead of team_id.
Can use yr, year, yrs, or years instead of year_min, year_max.
For multi-valued options (like down or rush direction), separate values with commas or use a list.
For options that are yes/no/either or yes/no/any, -1 is either/any, 0 is no, 1 is yes.

{}
:returns: Pandas dataframe of plays
:rtype: pd.DataFrame

Options for the inputs:
{}
""".format(paramStr, optsStr)

# clean up namespace
del IOD, paramStr, optsStr

from PSF import PlayerSeasonFinder
from GPF import GamePlayFinder

# modules/variables to expose
__all__ = [
    'PlayerSeasonFinder',
    'GamePlayFinder',
]
