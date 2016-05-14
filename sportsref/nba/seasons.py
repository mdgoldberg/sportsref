import re
import urlparse

import pandas as pd
from pyquery import PyQuery as pq

import sportsref

@sportsref.decorators.memoized
class Season(object):

    """Object representing a given NBA season."""

    def __init__(self, year):
        """Initializes a Season object for an NBA season.

        :year: The year of the season we want.
        """
        self._yr = int(year)
        self._url = lambda s: urlparse.urljoin(
            sportsref.nba.BASE_URL, '/leagues/NBA_{}.html'.format(s))


    def __eq__(self, other):
        return (self._yr == other._yr)

    def __hash__(self):
        return hash(self._yr)

    @sportsref.decorators.memoized
    def getMainDoc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        return pq(sportsref.utils.getHTML(self._url(self._yr)))

    @sportsref.decorators.memoized
    def getScheduleDoc(self):
        """Returns PyQuery object for the season schedule URL.
        :returns: PyQuery object.
        """
        html = sportsref.utils.getHTML(self._url('{}_games'.format(self._yr)))
        return pq(html)

    @sportsref.decorators.memoized
    def getTeamIDs(self):
        """Returns a list of the team IDs for the given year.
        :returns: List of team IDs.
        """
        doc = self.getMainDoc()
        df = sportsref.utils.parseTable(doc('table#team'))
        if 'team_name' in df.columns:
            return df.team_name.tolist()
        else:
            print 'ERROR: no teams found'
            return []

    @sportsref.decorators.memoized
    def teamIDsToNames(self):
        """Mapping from 3-letter team IDs to full team names.
        :returns: Dictionary with team IDs as keys and full team strings as
        values.
        """
        doc = self.getMainDoc()
        table = doc('table#team')
        teamNames = [re.sub(r'\s\*', '', tr('td').eq(1).text())
                     for tr in table('tbody tr[class=""]').items()]
        teamIDs = self.getTeamIDs()
        if len(teamNames) != len(teamIDs):
            raise Exception("team names and team IDs don't align")
        return dict(zip(teamIDs, teamNames))

    @sportsref.decorators.memoized
    def teamNamesToIDs(self):
        """Mapping from full team names to 3-letter team IDs.
        :returns: Dictionary with tean names as keys and team IDs as values.
        """
        d = self.teamIDsToNames()
        return {v:k for k,v in d.items()}

    @sportsref.decorators.memoized
    @sportsref.decorators.kindRPB(include_type=False)
    def getBSIDs(self, kind='R'):
        """Returns a list of BoxScore IDs for every game in the season.
        Only needs to handle 'R' or 'P' options because decorator handles 'B'.

        :kind: 'R' for regular season, 'P' for playoffs, 'B' for both.
        :returns: List of IDs for nba.BoxScore objects.
        """
        doc = self.getScheduleDoc()
        tID = 'games' if kind == 'R' else 'games_playoffs'
        table = doc('table#{}'.format(tID))
        df = sportsref.utils.parseTable(table)
        if 'box_score_text' not in df.columns:
            print 'ERROR: no boxscores found in season'
            return []
        return df.box_score_text
