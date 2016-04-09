import datetime
import re
import urlparse

import requests
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'teamNames',
    'teamIDs',
    'listTeams',
    'Team',
]

yr = datetime.datetime.now().year

@sportsref.decorators.memoized
def teamNames():
    html = sportsref.utils.getHTML(sportsref.nba.BASE_URL + '/teams/')
    doc = pq(html)
    table = doc('table#active')
    df = sportsref.utils.parseTable(table)
    ids = df.loc[df['franch_name'].str.len() == 3, 'franch_name'].values
    teamNames = [tr('td a') for tr in table('tr').items()]
    teamNames = filter(None, teamNames)
    teamNames = [lst.eq(0).text() for lst in teamNames]
    d = dict(zip(ids, teamNames))
    return d

@sportsref.decorators.memoized
def teamIDs():
    names = teamNames()
    ids = {v: k for k, v in names.iteritems()}
    return ids

@sportsref.decorators.memoized
def listTeams():
    return teamNames().keys()

@sportsref.decorators.memoized
class Team:

    def __init__(self, teamID):
        self.teamID = teamID

    def __eq__(self, other):
        return (self.teamID == other.teamID)

    def __hash__(self):
        return hash(self.teamID)

    @sportsref.decorators.memoized
    def teamYearURL(self, yr=yr):
        return urlparse.urljoin(
            sportsref.nba.BASE_URL, '/teams/{}/{}.htm'.format(self.teamID, yr))

    @sportsref.decorators.memoized
    def getMainDoc(self):
        relURL = '/teams/{}'.format(self.teamID)
        teamURL = urlparse.urljoin(sportsref.nba.BASE_URL, relURL)
        mainDoc = pq(sportsref.utils.getHTML(teamURL))
        return mainDoc

    @sportsref.decorators.memoized
    def getYearDoc(self, year=yr):
        return pq(sportsref.utils.getHTML(self.teamYearURL(year)))

    @sportsref.decorators.memoized
    def name(self):
        """Returns the real name of the franchise given a team ID.

        Examples:
        'BOS' -> 'Boston Celtics'
        'NJN' -> 'Brooklyn Nets'

        :returns: A string corresponding to the team's full name.
        """
        raise NotImplementedError('teamYearURL')

    @sportsref.decorators.memoized
    def roster(self, year=yr):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        raise NotImplementedError('teamYearURL')

    @sportsref.decorators.memoized
    def boxscores(self, year=yr):
        """Gets list of BoxScore objects corresponding to the box scores from
        that year.

        :year: The year for which we want the boxscores; defaults to current
        year.
        :returns: np.array of strings representing boxscore IDs.
        """
        raise NotImplementedError('teamYearURL')
