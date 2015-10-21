import re

import requests
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

from pfr import players, utils, BASE_URL

__all__ = [
    'listTeams',
    'Team',
]

def listTeams():
    doc = pq(utils.getHTML(BASE_URL + '/teams/'))
    table = doc('table#teams_active')
    df = utils.parseTable(table)
    return df.team_name.str[:3].values

class Team:

    def __init__(self, teamID):
        self.teamID = teamID
