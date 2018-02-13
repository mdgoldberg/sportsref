import future
import future.utils

import datetime
import re
import requests

import numpy as np
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Player',
]


class Player(future.utils.with_metaclass(sportsref.decorators.Cached, object)):

    """Each instance of this class represents an Euro player, uniquely
    identified by a player ID. The instance methods give various data available
    from the player's Sports Reference player page."""

    def __init__(self, player_id):
        self.player_id = player_id
        self.main_url = self.get_main_url(player_id)

    def get_main_url(self, player_id):
        return (sportsref.euro.BASE_URL + '/players/{0}.htm').format(player_id)

    def __eq__(self, other):
        return self.player_id == other.player_id

    def __hash__(self):
        return hash(self.player_id)

    def __repr__(self):
        return 'Player({})'.format(self.player_id)

    def __str__(self):
        return self.name()

    @sportsref.decorators.memoize
    def get_main_doc(self, level='B'):
       #Need to have a level option this deep in process because all vs club vs tourney means a completely    different doc for euro, instead of nba which is just a different table and same doc

        player_id = self.player_id
        if level == 'C':
            player_id += '-club'
        if level == 'E':
            player_id += '-tournament'
        return pq(sportsref.utils.get_html(self.get_main_url(player_id))) 
    
    @sportsref.decorators.memoize
    def get_gamelog_doc(self, year, league):
        url = '{}/pgl_euro.cgi?player_id={}&year_id={}&lg_id={}'.format(sportsref.euro.BASE_URL, self.player_id, year, league)
        return pq(sportsref.utils.get_html(url))  

    @sportsref.decorators.memoize
    def available_gamelogs(self):

        tup_list = []
        doc = self.get_main_doc()
        for li in doc('#bottom_nav_container')('ul')('li').items():
            href = li('a').attr('href')
            if href and 'pgl_euro.cgi?' in href:
                tup_list.append((int(re.search(r'year_id=(.*?)&', href).group(1)), re.search(r'lg_id=(.*?)$', href).group(1)))

        return tup_list 

    @sportsref.decorators.memoize
    def name(self):
        """Returns the name of the player as a string."""
        doc = self.get_main_doc()
        return doc('h1[itemprop="name"]').text().replace(' Europe Stats', '')

    @sportsref.decorators.memoize
    def age(self, year, month=2, day=1):
        """Returns the age of the player on a given date.

        :year: int representing the year.
        :month: int representing the month (1-12).
        :day: int representing the day within the month (1-31).
        :returns: Age in years as a float.
        """
        doc = self.get_main_doc()
        date_string = doc('span[itemprop="birthDate"]').attr('data-birth')
        regex = r'(\d{4})\-(\d{2})\-(\d{2})'
        date_args = list(map(int, re.match(regex, date_string).groups()))
        birth_date = datetime.date(*date_args)
        age_date = datetime.date(year=year, month=month, day=day)
        delta = age_date - birth_date
        age = delta.days / 365.
        return age

    @sportsref.decorators.memoize
    def position(self):
        """Returns the position of a player (note: not consistently coded in bballref)
        :returns: Position
        """
        doc = self.get_main_doc()
        raw = doc('p:contains("Position:")').text()
        pos = raw.split()[1]
        return pos

    @sportsref.decorators.memoize
    def nba_id(self):
        """Returns the euro player's NBA bballref id if they played in the NBA, None if they haven't
        :returns: NBA_ID
        """
        doc = self.get_main_doc()
        p = doc('p:contains("NBA Career:")') 
        href = ''
        for a in p('a').items():
            href = a.attr('href')

        if href == '':
            return None

        nba_id = href.split('/')[3].replace('.html', '')

        return nba_id     

    @sportsref.decorators.memoize
    def height(self):
        """Returns the player's height (in inches).
        :returns: An int representing a player's height in inches.
        """
        doc = self.get_main_doc()
        raw = doc('span[itemprop="height"]').text()
        try:
            feet, inches = list(map(int, raw.split('-')))
            return feet * 12 + inches
        except ValueError:
            return None

    @sportsref.decorators.memoize
    def weight(self):
        """Returns the player's weight (in pounds).
        :returns: An int representing a player's weight in pounds.
        """
        doc = self.get_main_doc()
        raw = doc('span[itemprop="weight"]').text()
        try:
            weight = re.match(r'(\d+)lb', raw).group(1)
            return int(weight)
        except ValueError:
            return None

    @sportsref.decorators.kind_rpb(include_type=True)
    def _get_stats_table(self, table_id, kind='R', level='B', summary=False):
        """Gets a stats table from the player page; helper function that does
        the work for per-game, per-36-min, etc. stats.

        :table_id: the ID of the HTML table.
        :kind: specifies regular season, playoffs. One of 'R', 'P'.
          Defaults to 'R'.
        :level: specifies Club play (C), Eurocup/Euroleague play (E), or Both (B) - defaults to B
        :returns: A DataFrame of stats.
        """
        doc = self.get_main_doc(level=level)
        if level == 'E': 
            table_id = 'table#{}EUR0'.format(table_id)
        elif level == 'C':
            table_id = 'table#{}{}'.format(table_id, 'CLU1' if kind == 'P' else 'CLU0')
        else:
            table_id = 'table#{}{}'.format(table_id, 'ALL1' if kind == 'P' else 'ALL0')

        table = doc(table_id)
        df = sportsref.utils.parse_table(table, flatten=(not summary), footer=summary)
        return df

    @sportsref.decorators.memoize
    def stats_per_game(self, kind='R', level='B', summary=False):
        """Returns a DataFrame of per-game box score stats."""
        return self._get_stats_table('per_game', kind=kind, level=level, summary=summary)

    @sportsref.decorators.memoize
    def stats_totals(self, kind='R', level='B', summary=False):
        """Returns a DataFrame of total box score statistics by season."""
        return self._get_stats_table('totals', kind=kind, level=level, summary=summary)

    @sportsref.decorators.memoize
    def stats_per36(self, kind='R', level='B', summary=False):
        """Returns a DataFrame of per-36-minutes stats."""
        return self._get_stats_table('per_minute', kind=kind, level=level, summary=summary)

    @sportsref.decorators.memoize
    def stats_advanced(self, kind='R', summary=False):
        """Returns a dataframe of advanced stats.
        :returns: TODO (would need to pull from team page, not housed in player page)
        """
        raise Exception('not yet implemented - euro.stats_advanced')

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=False)
    def gamelog_basic(self, year, league):
        """Returns a table of a player's basic game-by-game stats for a season.

        :param year: The year representing the desired season.
        :param kind: specifies regular season, playoffs, or both. One of 'R',
            'P', 'B'. Defaults to 'R'.
        :returns: A DataFrame of the player's standard boxscore stats from each
            game of the season.
        :rtype: pd.DataFrame
        """

        doc = self.get_gamelog_doc(year, league)

        table = doc('table#pgl_basic')
        df = sportsref.utils.parse_table(table)
        return df
