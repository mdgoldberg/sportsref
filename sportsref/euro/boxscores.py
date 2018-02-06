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
    def get_id(self, home):
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
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """

        return self.get_id(True)

    @sportsref.decorators.memoize
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        
        return self.get_id(False)

    @sportsref.decorators.memoize
    def home_score(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        linescore = self.linescore()
        return linescore.loc['home', 'T']

    @sportsref.decorators.memoize
    def away_score(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        linescore = self.linescore()
        return linescore.loc['away', 'T']

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
        d = self.date()
        if d.month >= 9:
            return d.year + 1
        else:
            return d.year

    def _get_player_stats(self, table_id_fmt):
        """Returns a DataFrame of player stats from the game (either basic or
        advanced, depending on the argument.

        :param table_id_fmt: Format string for str.format with a placeholder
            for the team ID (e.g. 'box_{}_basic')
        :returns: DataFrame of player stats
        """

        # get data
        doc = self.get_main_doc()
        tms = self.away(), self.home()
        tm_ids = [table_id_fmt.format(tm) for tm in tms]
        tables = [doc('table#{}'.format(tm_id).lower()) for tm_id in tm_ids]
        dfs = [sportsref.utils.parse_table(table) for table in tables]

        # clean data and add features
        for i, (tm, df) in enumerate(zip(tms, dfs)):
            no_time = df['mp'] == 0
            stat_cols = [col for col, dtype in df.dtypes.items()
                         if dtype != 'object']
            df.loc[no_time, stat_cols] = 0
            df['team_id'] = tm
            df['is_home'] = i == 1
            df['is_starter'] = [p < 5 for p in range(df.shape[0])]
            df.drop_duplicates(subset='player_id', keep='first', inplace=True)

        return pd.concat(dfs)

    @sportsref.decorators.memoize
    def basic_stats(self):
        """Returns a DataFrame of basic player stats from the game."""
        return self._get_player_stats('box_{}_basic')

