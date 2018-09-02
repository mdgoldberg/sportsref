from __future__ import division
from builtins import map, next
from past.utils import old_div
import future
import future.utils

import datetime
import re

import numpy as np
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Player',
]


class Player(future.utils.with_metaclass(sportsref.decorators.Cached, object)):

    """Each instance of this class represents an NBA player, uniquely
    identified by a player ID. The instance methods give various data available
    from the player's Basketball Reference player page."""

    def __init__(self, player_id):
        self.player_id = player_id
        self.url_base = (sportsref.nba.BASE_URL +
                         '/players/{0[0]}/{0}').format(self.player_id)
        self.main_url = self.url_base + '.htm'

    def __eq__(self, other):
        return self.player_id == other.player_id

    def __hash__(self):
        return hash(self.player_id)

    def __repr__(self):
        return 'Player({})'.format(self.player_id)

    def __str__(self):
        return self.name()

    @sportsref.decorators.memoize
    def get_main_doc(self):
        return pq(sportsref.utils.get_html(self.main_url))

    @sportsref.decorators.memoize
    def get_sub_doc(self, rel_url):
        url = '{}/{}'.format(self.url_base, rel_url)
        return pq(sportsref.utils.get_html(url))

    @sportsref.decorators.memoize
    def name(self):
        """Returns the name of the player as a string."""
        doc = self.get_main_doc()
        return doc('h1[itemprop="name"]').text()

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
        date_args = map(int, re.match(regex, date_string).groups())
        birth_date = datetime.date(*date_args)
        age_date = datetime.date(year=year, month=month, day=day)
        delta = age_date - birth_date
        age = delta.days / 365.
        return age

    @sportsref.decorators.memoize
    def position(self):
        """TODO: Docstring for position.
        :returns: TODO
        """
        raise Exception('not yet implemented - nba.Player.position')

    @sportsref.decorators.memoize
    def height(self):
        """Returns the player's height (in inches).
        :returns: An int representing a player's height in inches.
        """
        doc = self.get_main_doc()
        raw = doc('span[itemprop="height"]').text()
        try:
            feet, inches = map(int, raw.split('-'))
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

    @sportsref.decorators.memoize
    def hand(self):
        """Returns the player's handedness.
        :returns: 'L' for left-handed, 'R' for right-handed.
        """
        doc = self.get_main_doc()
        hand = re.search(r'Shoots:\s*(L|R)', doc.text()).group(1)
        return hand

    @sportsref.decorators.memoize
    def draft_pick(self):
        """Returns when in the draft the player was picked.
        :returns: TODO
        """
        doc = self.get_main_doc()
        try:
            p_tags = doc('div#meta p')
            draft_p_tag = next(p for p in p_tags.items() if p.text().lower().startswith('draft'))
            draft_pick = int(re.search(r'(\d+)\w{,3}\s+?overall', draft_p_tag.text()).group(1))
            return draft_pick
        except Exception as e:
            return None

    @sportsref.decorators.memoize
    def draft_year(self):
        """Returns the year the player was selected (or undrafted).
        :returns: TODO
        """
        raise Exception('not yet implemented - nba.Player.draft_year')

    @sportsref.decorators.kind_rpb(include_type=True)
    def _get_stats_table(self, table_id, kind='R', summary=False):
        """Gets a stats table from the player page; helper function that does
        the work for per-game, per-100-poss, etc. stats.

        :table_id: the ID of the HTML table.
        :kind: specifies regular season, playoffs, or both. One of 'R', 'P',
            'B'. Defaults to 'R'.
        :returns: A DataFrame of stats.
        """
        doc = self.get_main_doc()
        table_id = 'table#{}{}'.format(
            'playoffs_' if kind == 'P' else '', table_id)
        table = doc(table_id)
        df = sportsref.utils.parse_table(table, flatten=(not summary),
                                         footer=summary)
        return df

    @sportsref.decorators.memoize
    def stats_per_game(self, kind='R', summary=False):
        """Returns a DataFrame of per-game box score stats."""
        return self._get_stats_table('per_game', kind=kind, summary=summary)

    @sportsref.decorators.memoize
    def stats_totals(self, kind='R', summary=False):
        """Returns a DataFrame of total box score statistics by season."""
        return self._get_stats_table('totals', kind=kind, summary=summary)

    @sportsref.decorators.memoize
    def stats_per36(self, kind='R', summary=False):
        """Returns a DataFrame of per-36-minutes stats."""
        return self._get_stats_table('per_minute', kind=kind, summary=summary)

    @sportsref.decorators.memoize
    def stats_per100(self, kind='R', summary=False):
        """Returns a DataFrame of per-100-possession stats."""
        return self._get_stats_table('per_poss', kind=kind, summary=summary)

    @sportsref.decorators.memoize
    def stats_advanced(self, kind='R', summary=False):
        """Returns a DataFrame of advanced stats."""
        return self._get_stats_table('advanced', kind=kind, summary=summary)

    @sportsref.decorators.memoize
    def stats_shooting(self, kind='R', summary=False):
        """Returns a DataFrame of shooting stats."""
        return self._get_stats_table('shooting', kind=kind, summary=summary)

    @sportsref.decorators.memoize
    def stats_pbp(self, kind='R', summary=False):
        """Returns a DataFrame of play-by-play stats."""
        return self._get_stats_table('advanced_pbp', kind=kind,
                                     summary=summary)

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def gamelog_basic(self, year, kind='R'):
        """Returns a table of a player's basic game-by-game stats for a season.

        :param year: The year representing the desired season.
        :param kind: specifies regular season, playoffs, or both. One of 'R',
            'P', 'B'. Defaults to 'R'.
        :returns: A DataFrame of the player's standard boxscore stats from each
            game of the season.
        :rtype: pd.DataFrame
        """
        doc = self.get_sub_doc('gamelog/{}'.format(year))
        table = (doc('table#pgl_basic_playoffs')
                 if kind == 'P' else doc('table#pgl_basic'))
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def gamelog_advanced(self, year, kind='R'):
        """Returns a table of a player's advanced game-by-game stats for a
        season.

        :param year: The year representing the desired season.
        :param kind: specifies regular season, playoffs, or both. One of 'R',
            'P', 'B'. Defaults to 'R'.
        :returns: A DataFrame of the player's advanced stats from each game of
            the season.
        :rtype: pd.DataFrame
        """
        doc = self.get_sub_doc('gamelog-advanced/{}'.format(year))
        table = (doc('table#pgl_advanced_playoffs')
                 if kind == 'P' else doc('table#pgl_advanced'))
        df = sportsref.utils.parse_table(table)
        return df
