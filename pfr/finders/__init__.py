# Fill in PlayerSeasonFinder docstring
from pfr.finders import PlayerSeasonFinder

IOD = PlayerSeasonFinder.getInputsOptionsDefaults()

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


PlayerSeasonFinder.PlayerSeasonFinder.__doc__ = """
Finds player-seasons that match criteria supplied by keyword arguments.

{}
:returns: list of matching player-season tuples
:rtype: [(player ID, season year)]

Options for inputs:
{}
""".format(paramStr, optsStr)

# clean up namespace
del IOD, paramStr, optsStr


# Fill in GamePlayFinder docstring
from pfr.finders import GamePlayFinder

IOD = GamePlayFinder.getInputsOptionsDefaults()

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

GamePlayFinder.GamePlayFinder.__doc__ = """
Finds plays that match criteria supplied by keyword arguments.

Can use tm or team instead of team_id.
Can use [draft_]pos, [draft_]position, [draft_]positions for a shortcut for [draft_]positions.
For multi-valued options (like down or rush direction), separate values with commas.
For options that are yes/no/either or yes/no/any, -1 is either/any, 0 is no, 1 is yes.

{}
:returns: Pandas dataframe of plays

Options for the inputs:
{}
""".format(paramStr, optsStr)

# clean up namespace
del IOD, paramStr, optsStr

# modules/variables to expose
__all__ = [
    'PlayerSeasonFinder',
    'GamePlayFinder',
]
