import future
import future.utils

import datetime
import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref


class BoxScore(
    future.utils.with_metaclass(sportsref.decorators.Cached, object)
):

    def __init__(self, boxscore_id):
        self.boxscore_id = boxscore_id

    def __eq__(self, other):
        return self.boxscore_id == other.boxscore_id

    def __hash__(self):
        return hash(self.boxscore_id)

    def __repr__(self):
        return 'BoxScore({})'.format(self.boxscore_id)

    @sportsref.decorators.memoize
    def get_main_doc(self):
        url = ('{}/boxscores/{}.html'
               .format(sportsref.euro.BASE_URL, self.boxscore_id))
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def get_subpage_doc(self, page):
        url = (sportsref.nba.BASE_URL +
               '/boxscores/{}/{}.html'.format(page, self.boxscore_id))
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})', self.boxscore_id)
        year, month, day = list(map(int, match.groups()))
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoize
    def weekday(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoize
    def get_raw_id(self, home):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = self.get_main_doc()
        div = doc('.scorebox')

        a_list = []
        for a in div('a').items():
            href = a.attr('href')
            if 'teams' in href:
                a_list.append(href)

        if home:
            return a_list[1]
        return a_list[0]

    @sportsref.decorators.memoize
    def get_score(self, home):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = self.get_main_doc()
        div = doc('.scorebox')

        scores = []
        for d in div('.score').items():
            scores.append(int(d.text()))
		
        if home:
            return scores[1]
        return scores[0]
    

    @sportsref.decorators.memoize
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """

        l = self.get_raw_id(home=True)
        return l.split('/')[3]

    @sportsref.decorators.memoize
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        
        l = self.get_raw_id(home=False)
        return l.split('/')[3]

    @sportsref.decorators.memoize
    def home_score(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        return self.get_score(home=True)

    @sportsref.decorators.memoize
    def away_score(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        return self.get_score(home=False)

    @sportsref.decorators.memoize
    def winner(self):
        """Returns the team ID of the winning team. Returns NaN if a tie."""
        hmScore = self.home_score()
        awScore = self.away_score()
        if hmScore > awScore:
            return self.home()
        elif hmScore < awScore:
            return self.away()
        else:
            return None

    @sportsref.decorators.memoize
    def season(self):
        """
        Returns the year ID of the season in which this game took place.

        :returns: An int representing the year of the season.
        """
        l = self.get_raw_id(home=True)
        return l.split('/')[4].replace('.html','')

    @sportsref.decorators.memoize
    def get_home_stats(self):
        doc = self.get_main_doc()
        table = doc('table#{}'.format('box-score-home'))
        df = sportsref.utils.parse_table(table)

        return df

    @sportsref.decorators.memoize
    def get_away_stats(self):
        doc = self.get_main_doc()
        table = doc('table#{}'.format('box-score-visitor'))
        df = sportsref.utils.parse_table(table)

        return df


