import datetime
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

yr = datetime.datetime.now().year

def listTeams():
    doc = pq(utils.getHTML(BASE_URL + '/teams/'))
    table = doc('table#teams_active')
    df = utils.parseTable(table)
    return df.team_name.str[:3].values

class Team:

    def __init__(self, teamID):
        self.teamID = teamID

    def roster(self, year=yr):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster.
        :returns: A DataFrame containing roster information for that year.

        """
        raise "not yet implemented"
