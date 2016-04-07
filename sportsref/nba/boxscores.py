import datetime
import re
import urlparse

import numpy as np
from pyquery import PyQuery as pq

import sportsref

@sportsref.decorators.memoized
class BoxScore:

    def __init__(self, bsID):
        self.bsID = bsID

    def __eq__(self, other):
        return self.bsID == other.bsID

    def __hash__(self):
        return hash(self.bsID)

    @sportsref.decorators.memoized
    def getMainDoc(self):
        url = urlparse.urljoin(
            sportsref.nba.BASE_URL, 'boxscores/{}.html'.format(self.bsID)
        )
        doc = pq(sportsref.utils.getHTML(url))
        return doc

    @sportsref.decorators.memoized
    def getPBPDoc(self):
        url = urlparse.urljoin(
            sportsref.nba.BASE_URL, 'boxscores/pbp/{}.html'.format(self.bsID)
        )
        doc = pq(sportsref.utils.getHTML(url))
        return doc
    
    @sportsref.decorators.memoized
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.bsID)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoized
    def weekday(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoized
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = self.getMainDoc()
        table = doc('div#page_content div > div > table:eq(1) table')
        hm_href = table('tr td').eq(1)('span a').eq(0).attr['href']
        return sportsref.utils.relURLToID(hm_href)

    @sportsref.decorators.memoized
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = self.getMainDoc()
        table = doc('div#page_content div > div > table:eq(1) table')
        aw_href = table('tr td').eq(0)('span a').eq(0).attr['href']
        return sportsref.utils.relURLToID(aw_href)

    @sportsref.decorators.memoized
    def homeScore(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        raise NotImplementedError("homeScore")

    @sportsref.decorators.memoized
    def awayScore(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        raise NotImplementedError("awayScore")

    @sportsref.decorators.memoized
    def winner(self):
        """Returns the team ID of the winning team. Returns NaN if a tie."""
        hmScore = self.homeScore()
        awScore = self.awayScore()
        if hmScore > awScore:
            return self.home()
        elif hmScore < awScore:
            return self.away()
        else:
            return np.nan

    @sportsref.decorators.memoized
    def season(self):
        """
        Returns the year ID of the season in which this game took place.
        Useful for week 17 January games.

        :returns: An int representing the year of the season.
        """
        raise NotImplementedError("season")
    
    @sportsref.decorators.memoized
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        raise 'not yet implemented'
