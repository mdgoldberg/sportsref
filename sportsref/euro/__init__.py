from . import boxscores
from . import pbp
from . import seasons
from . import teams

from .boxscores import BoxScore
from .seasons import Season
from .teams import Team
from .players import Player

BASE_URL = 'http://www.basketball-reference.com/euro'

LEAGUE_IDS = ['greek-basket-league','eurocup','spain-liga-acb','italy-basket-serie-a','france-lnb-pro-a','euroleague']

__all__ = [
    'LEAGUE_IDS',
    'BASE_URL',
    'boxscores', 'BoxScore',
    'seasons', 'Season',
    'teams', 'Team',
    'players', 'Player',
]
