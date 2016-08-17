import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

from .. import decorators, utils
from . import NFL_BASE_URL

__all__ = [
    'teamNames',
    'teamIDs',
    'listTeams',
    'Team',
]

@decorators.memoized
def teamNames(year):
    """Returns a mapping from team ID to full team name for a given season.
    Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with teamID keys and full team name values.
    """
    doc = pq(utils.getHTML(NFL_BASE_URL + '/teams/'))
    active_table = doc('table#teams_active')
    active_df = utils.parseTable(active_table)
    inactive_table = doc('table#teams_inactive')
    inactive_df = utils.parseTable(inactive_table)
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

@decorators.memoized
def teamIDs(year):
    """Returns a mapping from team name to team ID for a given season. Inverse
    mapping of teamNames. Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with full team name keys and teamID values.
    """
    names = teamNames(year)
    return {v: k for k, v in names.iteritems()}

@decorators.memoized
def listTeams(year):
    """Returns a list of team IDs for a given season.

    :year: The year of the season in question (as an int).
    :returns: A list of team IDs.
    """
    return teamNames(year).keys()

@decorators.memoized
class Team:

    def __init__(self, teamID):
        self.teamID = teamID

    def __eq__(self, other):
        return (self.teamID == other.teamID)

    def __hash__(self):
        return hash(self.teamID)

    def __reduce__(self):
        return Team, (self.teamID,)

    @decorators.memoized
    def teamYearURL(self, yr_str):
        return NFL_BASE_URL + '/teams/{}/{}.htm'.format(self.teamID, yr_str)

    @decorators.memoized
    def getMainDoc(self):
        relURL = '/teams/{}'.format(self.teamID)
        teamURL = NFL_BASE_URL + relURL
        mainDoc = pq(utils.getHTML(teamURL))
        return mainDoc

    @decorators.memoized
    def getYearDoc(self, yr_str):
        return pq(utils.getHTML(self.teamYearURL(yr_str)))

    @decorators.memoized
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

    @decorators.memoized
    def roster(self, year):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        raise "not yet implemented"

    @decorators.memoized
    def boxscores(self, year):
        """Gets list of BoxScore objects corresponding to the box scores from
        that year.

        :year: The year for which we want the boxscores; defaults to current
        year.
        :returns: np.array of strings representing boxscore IDs.
        """
        doc = self.getYearDoc(year)
        table = doc('table#games')
        df = utils.parseTable(table)
        if df.empty:
            return np.array([])
        return df.boxscore_word.dropna().values

    # TODO: add functions for OC, DC, PF, PA, W-L, etc.
    # TODO: Also give a function at BoxScore.homeCoach and BoxScore.awayCoach
    # TODO: BoxScore needs a gameNum function to do this?

    @decorators.memoized
    def headCoachesByGame(self, year):
        """Returns head coach data by game.

        :year: An int representing the season in question.
        :returns: An array with an entry per game of the season that the team
        played (including playoffs). Each entry is the head coach's ID for that
        game in the season.
        """
        doc = self.getYearDoc(year)
        coaches = doc('div#meta p:contains("Coach:")')
        coachStr = utils.flattenLinks(coaches)
        regex = r'(\S+?) \((\d+)-(\d+)-(\d+)\)'
        coachAndTenure = []
        while coachStr:
            m = re.search(regex, coachStr)
            coachID, wins, losses, ties = m.groups()
            nextIndex = m.end(4) + 1
            coachStr = coachStr[nextIndex:]
            tenure = int(wins) + int(losses) + int(ties)
            coachAndTenure.append((coachID, tenure))

        coachIDs = [[cID for _ in xrange(games)]
                   for cID, games in coachAndTenure]
        coachIDs = [cID for sublist in coachIDs for cID in sublist]
        return np.array(coachIDs[::-1])

    @decorators.memoized
    def srs(self, year):
        """Returns the SRS (Simple Rating System) for a team in a year.

        :year: The year for the season in question.
        :returns: A float of SRS.
        """
        doc = self.getYearDoc(year)
        srsText = doc('div#meta p:contains("SRS")').text()
        m = re.match(r'SRS\s*?:\s*?(\S+)', srsText)
        if m:
            return float(m.group(1))
        else:
            return np.nan

    @decorators.memoized
    def sos(self, year):
        """Returns the SOS (Strength of Schedule) for a team in a year, based
        on SRS.

        :year: The year for the season in question.
        :returns: A float of SOS.
        """
        doc = self.getYearDoc(year)
        sosText = doc('div#meta p:contains("SOS")').text()
        m = re.search(r'SOS\s*?:\s*?(\S+)', sosText)
        if m:
            return float(m.group(1))
        else:
            return np.nan

    @decorators.memoized
    def stadium(self, year):
        """Returns the ID for the stadium in which the team played in a given
        year.

        :year: The year in question.
        :returns: A string representing the stadium ID.
        """
        doc = self.getYearDoc(year)
        anchor = doc('div#meta p:contains("Stadium") a')
        return utils.relURLToID(anchor.attr['href'])

    @decorators.memoized
    def passing(self, year):
        doc = self.getYearDoc(year)
        table = doc('table#passing')
        df = utils.parseTable(table)
        return df

    @decorators.memoized
    def rushingAndReceiving(self, year):
        doc = self.getYearDoc(year)
        table = doc('#rushing_and_receiving')
        df = utils.parseTable(table)
        return df
