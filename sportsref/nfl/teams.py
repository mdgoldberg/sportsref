import datetime
import re
import urlparse

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

@sportsref.decorators.memoized
def teamNames(year):
    """Returns a mapping from team ID to full team name for a given season.
    Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with teamID keys and full team name values.
    """
    doc = pq(sportsref.utils.getHTML(sportsref.nfl.BASE_URL + '/teams/'))
    active_table = doc('table#teams_active')
    active_df = sportsref.utils.parseTable(active_table)
    inactive_table = doc('table#teams_inactive')
    inactive_df = sportsref.utils.parseTable(inactive_table)
    df = pd.concat((active_df, inactive_df))
    df = df.loc[~df['hasClass_partial_table']]
    ids = df.team_name.str[:3].values
    names = [tr('th a') for tr in active_table('tr').items()]
    names.extend(tr('th a') for tr in inactive_table('tr').items())
    names = filter(None, names)
    names = [lst[0].text_content() for lst in names]
    # combine IDs and team names into pandas series
    series = pd.Series(names, index=ids)
    # create a mask to filter to teams from the given year
    mask = ((df.year_min <= year) & (year <= df.year_max)).values
    # filter, convert to a dict, and return
    return series[mask].to_dict()

@sportsref.decorators.memoized
def teamIDs(year):
    """Returns a mapping from team name to team ID for a given season. Inverse
    mapping of teamNames. Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with full team name keys and teamID values.
    """
    names = teamNames(year)
    return {v: k for k, v in names.iteritems()}

@sportsref.decorators.memoized
def listTeams(year):
    """Returns a list of team IDs for a given season.

    :year: The year of the season in question (as an int).
    :returns: A list of team IDs.
    """
    return teamNames(year).keys()

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
        return (sportsref.nfl.BASE_URL +
                '/teams/{}/{}.htm'.format(self.teamID, yr_str))

    @sportsref.decorators.memoized
    def getMainDoc(self):
        relURL = '/teams/{}'.format(self.teamID)
        teamURL = sportsref.nfl.BASE_URL + relURL
        mainDoc = pq(sportsref.utils.getHTML(teamURL))
        return mainDoc

    @sportsref.decorators.memoized
    def getYearDoc(self, yr_str):
        return pq(sportsref.utils.getHTML(self.teamYearURL(yr_str)))

    @sportsref.decorators.memoized
    def name(self):
        """Returns the real name of the franchise given the team ID.

        Examples:
        'nwe' -> 'New England Patriots'
        'sea' -> 'Seattle Seahawks'

        :returns: A string corresponding to the team's full name.
        """
        doc = self.getMainDoc()
        headerwords = doc('div#meta h1')[0].text_content().split()
        lastIdx = headerwords.index('Franchise')
        teamwords = headerwords[:lastIdx]
        return ' '.join(teamwords)

    @sportsref.decorators.memoized
    def roster(self, year):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        doc = self.getYearDoc(str(year) + '_roster')
        table = doc('table#games_played_team')
        df = sportsref.utils.parseTable(table)
        df['season'] = int(year)
        df['team'] = self.teamID
        playerNames = [c.text for c in table('tbody tr td a[href]') 
                       if c.attrib['href'][1:8]=='players']
        if len(df) == len(playerNames):
            df['playerName'] = playerNames
        return df

    @sportsref.decorators.memoized
    def boxscores(self, year):
        """Gets list of BoxScore objects corresponding to the box scores from
        that year.

        :year: The year for which we want the boxscores; defaults to current
        year.
        :returns: np.array of strings representing boxscore IDs.
        """
        doc = self.getYearDoc(year)
        table = doc('table#games')
        df = sportsref.utils.parseTable(table)
        if df.empty:
            return np.array([])
        return df.boxscore_word.dropna().values

    @sportsref.decorators.memoized
    def passing(self, year):
        doc = self.getYearDoc(year)
        table = doc('table#passing')
        df = sportsref.utils.parseTable(table)
        return df

    @sportsref.decorators.memoized
    def rushingAndReceiving(self, year):
        doc = self.getYearDoc(year)
        table = doc('#rushing_and_receiving')
        df = sportsref.utils.parseTable(table)
        return df

    # TODO: add functions for HC, OC, DC, SRS, SOS, PF, PA, W-L, etc.
