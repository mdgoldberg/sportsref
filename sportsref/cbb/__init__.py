from . import boxscores
from . import pbp
from . import seasons
from . import teams

from .boxscores import BoxScore
from .seasons import Season
from .teams import Team
from .players import Player

BASE_URL = 'http://www.sports-reference.com/cbb'

__all__ = [
    'BASE_URL',
    'boxscores', 'BoxScore',
    'pbp',
    'seasons', 'Season',
    'teams', 'Team',
    'players', 'Player',
]
