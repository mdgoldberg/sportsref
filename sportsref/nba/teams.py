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

# TODO: make team functions dependent on year
# team IDs change by year, ex: NJN -> BKN

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
    def teamYearURL(self, yr_str):
        return urlparse.urljoin(
            sportsref.nba.BASE_URL,
            '/teams/{}/{}.htm'.format(self.teamID, yr_str))

    @sportsref.decorators.memoized
    def getMainDoc(self):
        relURL = '/teams/{}'.format(self.teamID)
        teamURL = urlparse.urljoin(sportsref.nba.BASE_URL, relURL)
        mainDoc = pq(sportsref.utils.getHTML(teamURL))
        return mainDoc

    @sportsref.decorators.memoized
    def getYearDoc(self, yr_str=yr):
        return pq(sportsref.utils.getHTML(self.teamYearURL(yr_str)))

    @sportsref.decorators.memoized
    def name(self):
        """Returns the real name of the franchise given the team ID.

        Examples:
        'BOS' -> 'Boston Celtics'
        'NJN' -> 'Brooklyn Nets'

        :returns: A string corresponding to the team's full name.
        """
        doc = self.getMainDoc()
        headerwords = doc('div#info_box h1')[0].text_content().split()
        lastIdx = headerwords.index('Franchise')
        teamwords = headerwords[:lastIdx]
        return ' '.join(teamwords)

    @sportsref.decorators.memoized
    def roster(self, year=yr):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        raise NotImplementedError('roster')

    @sportsref.decorators.memoized
    def boxscores(self, year=yr):
        """Gets list of BoxScore objects corresponding to the box scores from
        that year.

        :year: The year for which we want the boxscores; defaults to current
        year.
        :returns: np.array of strings representing boxscore IDs.
        """
        doc = self.getYearDoc('{}_games'.format(year))
        table = doc('table#teams_games')
        df = sportsref.utils.parseTable(table)
        if df.empty:
            return np.array([])
        return df.box_score_text.dropna().values
