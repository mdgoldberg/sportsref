BASE_URL = 'http://www.sports-reference.com/cfb'

import teams
import players

from teams import Team
from players import Player

__all__ = [
    'BASE_URL',
    'teams', 'Team',
    'players', 'Player',
]
