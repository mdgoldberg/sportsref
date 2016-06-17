BASE_URL = 'http://www.sports-reference.com/cbb/'

import boxscores
import seasons
import teams

from boxscores import BoxScore
from seasons import Season
# from teams import Team
from players import Player

__all__ = [
    'BASE_URL',
    'boxscores', 'BoxScore',
    'seasons', 'Season',
    'teams', 'Team',
    'players', 'Player',
]
