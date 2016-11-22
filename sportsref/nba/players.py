import datetime
import re

import numpy as np
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Player',
]


@sportsref.decorators.memoized
class Player:

    def __init__(self, player_id):
        self.player_id = player_id
        self.main_url = (sportsref.nba.BASE_URL +
                         '/players/{0[0]}/{0}.htm').format(self.player_id)

    def __eq__(self, other):
        return self.player_id == other.player_id

    def __hash__(self):
        return hash(self.player_id)

    def __repr__(self):
        return 'Player({})'.format(self.player_id)

    def __str__(self):
        return self.name()

    def __reduce__(self):
        return Player, (self.player_id,)

    @sportsref.decorators.memoized
    def get_doc(self):
        return pq(sportsref.utils.get_html(self.main_url))

    @sportsref.decorators.memoized
    def name(self):
        """Returns the name of the player as a string."""
        doc = self.get_doc()
        return doc('h1[itemprop="name"]').text()

    @sportsref.decorators.memoized
    def age(self, year, month=10, day=1):
        """Returns the age of the player on a given date.

        :year: int representing the year.
        :month: int representing the month (1-12).
        :day: int representing the day within the month (1-31).
        :returns: Age in years as a float.
        """
        doc = self.get_doc()
        date_string = doc('span[itemprop="birthDate"]').attr('data-birth')
        regex = r'(\d{4})\-(\d{2})\-(\d{2})'
        date_args = map(int, re.match(regex, date_string).groups())
        birth_date = datetime.date(*date_args)
        age_date = datetime.date(year=year, month=month, day=day)
        delta = age_date - birth_date
        age = delta.days / 365.
        return age

    @sportsref.decorators.memoized
    def position(self):
        """TODO: Docstring for position.
        :returns: TODO
        """
        raise Exception('not yet implemented - nba.Player.position')

    @sportsref.decorators.memoized
    def height(self):
        """Returns the player's height (in inches).
        :returns: An int representing a player's height in inches.
        """
        doc = self.get_doc()
        raw = doc('span[itemprop="height"]').text()
        try:
            feet, inches = map(int, raw.split('-'))
            return feet * 12 + inches
        except ValueError:
            return np.nan

    @sportsref.decorators.memoized
    def weight(self):
        """Returns the player's weight (in pounds).
        :returns: An int representing a player's weight in pounds.
        """
        doc = self.get_doc()
        raw = doc('span[itemprop="weight"]').text()
        try:
            weight = re.match(r'(\d+)lb', raw).group(1)
            return int(weight)
        except ValueError:
            return np.nan

    @sportsref.decorators.memoized
    def hand(self):
        """Returns the player's handedness.
        :returns: 'L' for left-handed, 'R' for right-handed.
        """
        doc = self.get_doc()
        hand = re.search(r'Shoots:\s*(L|R)', doc.text()).group(1)
        return hand

    def draft_pick(self):
        """Returns when in the draft the player was picked.
        :returns: TODO
        """
        pass

    @sportsref.decorators.memoized
    def per100_stats(self):
        """Returns a DataFrame of per-100-possession stats."""
        doc = self.get_doc()
        table = doc('table#per_poss')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoized
    def shooting_stats(self):
        """Returns a DataFrame of shooting stats."""
        doc = self.get_doc()
        table = doc('table#shooting')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoized
    def pbp_stats(self):
        """Returns a DataFrame of play-by-play stats."""
        doc = self.get_doc()
        table = doc('table#advanced_pbp')
        # TODO: parse percentages as ints/floats
        df = sportsref.utils.parse_table(table)
        return df
