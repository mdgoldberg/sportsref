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
        self._year = int(year)
        self._url = urlparse.urljoin(sportsref.nba.BASE_URL,
                                     '/leagues/NBA_{}.html'.format(year))

    def __eq__(self, other):
        return (self._year == other._year)

    def __hash__(self):
        return hash(self._year)

    @sportsref.decorators.memoized
    def getDoc(self):
        """Returns PyQuery object for the season URL.
        :returns: PyQuery object.
        """
        return pq(sportsref.utils.getHTML(self._url))

    @sportsref.decorators.memoized
    def getTeamIDs(self):
        """Returns a list of the team IDs for the given year.
        :returns: List of team IDs.
        """
        doc = self.getDoc()
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
        doc = self.getDoc()
        table = doc('table#team')
        teamNames = [tr('td').eq(1).text()
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
