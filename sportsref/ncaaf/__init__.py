BASE_URL = 'http://www.sports-reference.com/cfb'

import boxscores
import seasons
import teams
import players

from boxscores import BoxScore
from seasons import Season
from teams import Team
from players import Player

__all__ = [
    'BASE_URL',
    'boxscores', 'BoxScore',
    'seasons', 'Season',
    'teams', 'Team',
    'players', 'Player',
]
