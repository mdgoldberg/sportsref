import datetime
import re
import urlparse

import requests
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import pfr

__all__ = [
    'teamNames',
    'teamIDs',
    'listTeams',
    'Team',
]

yr = datetime.datetime.now().year

@pfr.decorators.memoized
def teamNames():
    doc = pq(pfr.utils.getHTML(pfr.BASE_URL + '/teams/'))
    table = doc('table#teams_active')
    df = pfr.utils.parseTable(table)
    ids = df.team_name.str[:3].values
    teamNames = [tr('td a') for tr in table('tr').items()]
    teamNames = filter(None, teamNames)
    teamNames = [lst[0].text_content() for lst in teamNames]
    d = dict(zip(ids, teamNames))
    return d

@pfr.decorators.memoized
def teamIDs():
    names = teamNames()
    ids = {v: k for k, v in names.iteritems()}
    return ids

@pfr.decorators.memoized
def listTeams():
    return teamNames().keys()

@pfr.decorators.memoized
class Team:

    def __init__(self, teamID):
        self.teamID = teamID

    def __eq__(self, other):
        return (self.teamID == other.teamID)

    def __hash__(self):
        return hash(self.teamID)

    @pfr.decorators.memoized
    def teamYearURL(self, yr):
        return urlparse.urljoin(
            pfr.BASE_URL, '/teams/{}/{}.htm'.format(self.teamID, yr))

    @pfr.decorators.memoized
    def getMainDoc(self):
        relURL = '/teams/{}'.format(self.teamID)
        teamURL = urlparse.urljoin(pfr.BASE_URL, relURL)
        mainDoc = pq(pfr.utils.getHTML(teamURL))
        return mainDoc

    @pfr.decorators.memoized
    def getYearDoc(self, year=yr):
        return pq(pfr.utils.getHTML(self.teamYearURL(year)))

    @pfr.decorators.memoized
    def name(self):
        """Returns the real name of the franchise given a team ID.

        Examples:
        'nwe' -> 'New England Patriots'
        'sea' -> 'Seattle Seahawks'

        :returns: A string corresponding to the team's full name.
        """
        doc = self.getMainDoc()
        headerwords = doc('div#info_box h1')[0].text_content().split()
        lastIdx = headerwords.index('Franchise')
        teamwords = headerwords[:lastIdx]
        return ' '.join(teamwords)

    @pfr.decorators.memoized
    def roster(self, year=yr):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        raise "not yet implemented"

    @pfr.decorators.memoized
    def boxscores(self, year=yr):
        """Gets list of BoxScore objects corresponding to the box scores from
        that year.

        :year: The year for which we want the boxscores; defaults to current
        year.
        :returns: np.array of strings representing boxscore IDs.
        """
        doc = self.getYearDoc(year)
        table = doc('table#team_gamelogs')
        df = pfr.utils.parseTable(table)
        if df.empty:
            return np.array([])
        return df.boxscore_word.dropna().values

    @pfr.decorators.memoized
    def passing(self, year=yr):
        doc = self.getYearDoc(year)
        table = doc('#passing')
        df = pfr.utils.parseTable(table)
        return df

    @pfr.decorators.memoized
    def rushingAndReceiving(self, year=yr):
        doc = self.getYearDoc(year)
        table = doc('#rushing_and_receiving')
        df = pfr.utils.parseTable(table)
        return df

    @pfr.decorators.memoized
    def teamInfo(self, year=yr):
        doc = self.getYearDoc(year)
        teamDict = {}
        table = doc('#all_team_stats table.stats_table').eq(0)
        for tr in table('tbody tr').items():
            td0, td1 = tr('td')[:2]
            key = td0.text_content().lower()
            key = re.sub(r'\W', '_', key)
            val = pfr.utils.flattenLinks(td1)
            teamDict[key] = val
        return teamDict
