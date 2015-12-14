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
    'listTeams',
    'Team',
]

yr = datetime.datetime.now().year

def teamNames():
    doc = pq(pfr.utils.getHTML(pfr.BASE_URL + '/teams/'))
    table = doc('table#teams_active')
    df = pfr.utils.parseTable(table)
    ids = df.team_name.str[:3].values
    teamNames = [tr('td a') for tr in map(pq, table('tr'))]
    teamNames = filter(None, teamNames)
    teamNames = [lst[0].text_content() for lst in teamNames]
    d = dict(zip(ids, teamNames))
    d.update(dict(zip(teamNames, ids)))
    return d

def teamIDs():
    names = teamNames()
    ids = {v: k for k, v in names.iteritems()}
    return ids

def listTeams():
    tmNames = teamNames()
    return filter(lambda k: len(k) == 3, tmNames.keys())

class Team:

    def __init__(self, teamID):
        self.teamID = teamID
        self.relURL = '/teams/{}'.format(self.teamID)
        self.teamURL = urlparse.urljoin(pfr.BASE_URL, self.relURL)
        self.teamYearURL = lambda yr: urlparse.urljoin(
            pfr.BASE_URL, '/teams/{}/{}.htm'.format(self.teamID, yr))
        self.mainDoc = None # will be filled in when necessary
        self.yearDocs = {} # will be filled in as necessary

    def getMainDoc(self):
        if self.mainDoc:
            return self.mainDoc
        else:
            self.mainDoc = pq(self.teamURL)
            return self.mainDoc

    def getYearDoc(self, year=yr):
        try:
            return self.yearDocs[year]
        except KeyError:
            self.yearDocs[year] = pq(pfr.utils.getHTML(self.teamYearURL(year)))
        return self.yearDocs[year]

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

    def roster(self, year=yr):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        raise "not yet implemented"

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
        return df.boxscore_word.dropna().values

    def passing(self, year=yr):
        doc = self.getYearDoc(year)
        table = doc('#passing')
        df = pfr.utils.parseTable(table)
        return df

    def rushing_and_receiving(self, year=yr):
        doc = self.getYearDoc(year)
        table = doc('#rushing_and_receiving')
        df = pfr.utils.parseTable(table)
        return df
